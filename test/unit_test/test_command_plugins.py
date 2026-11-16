"""Command plugins through entry points, and the console scripts."""
import io
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib import import_module
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cli import entry_points
from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.cli.run_settings import RunSettings, apply_run_settings, build_run_settings
from je_web_runner.utils.executor.action_executor import Executor, executor
from je_web_runner.utils.package_manager import entry_point_commands as plugins
from je_web_runner.utils.package_manager.entry_point_commands import (
    CommandPluginError,
    available_plugins,
    load_command_plugins,
)
from je_web_runner.utils.project_config import ProjectConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


def _greet(name: str = "world") -> str:
    """Say hello."""
    return f"hello {name}"


def _entry_point(name, loaded):
    point = MagicMock()
    point.name = name
    point.load.return_value = loaded
    return point


class _Installed(unittest.TestCase):
    """Pretend some command plugins are installed."""

    def install(self, **tables):
        points = [_entry_point(name, loaded) for name, loaded in tables.items()]
        patcher = patch.object(plugins.metadata, "entry_points", return_value=points)
        self.entry_points = patcher.start()
        self.addCleanup(patcher.stop)
        return points


class TestLoadCommandPlugins(_Installed):

    def setUp(self):
        self.executor = Executor()

    def test_listing_loads_nothing(self):
        points = self.install(zeta={"WR_zeta": _greet}, alpha={"WR_alpha": _greet})
        self.assertEqual(available_plugins(), ["alpha", "zeta"])
        self.entry_points.assert_called_with(group="je_web_runner.commands")
        for point in points:
            point.load.assert_not_called()

    def test_named_plugin_registers_its_commands(self):
        points = self.install(mine={"WR_mine_greet": _greet}, other={"WR_other": _greet})
        self.assertEqual(load_command_plugins(["mine"], self.executor), ["WR_mine_greet"])
        self.assertEqual(self.executor.execute_one(["WR_mine_greet", {"name": "you"}]), "hello you")
        self.assertNotIn("WR_other", self.executor.event_dict)
        points[1].load.assert_not_called()

    def test_a_function_returning_the_table(self):
        self.install(mine=lambda: {"WR_mine_greet": _greet})
        self.assertEqual(load_command_plugins(["mine"], self.executor), ["WR_mine_greet"])

    def test_unknown_plugin_names_the_installed_ones(self):
        self.install(mine={"WR_mine_greet": _greet})
        with self.assertRaises(CommandPluginError) as raised:
            load_command_plugins(["missing"], self.executor)
        self.assertIn("mine", str(raised.exception))

    def test_bad_tables_register_nothing(self):
        cases = {
            "empty": {},
            "not_a_table": ["WR_x"],
            "bad_name": {"greet": _greet},
            "not_callable": {"WR_value": 3},
            "taken": {"WR_to_url": _greet},
        }
        for name, table in cases.items():
            with self.subTest(plugin=name):
                self.install(good={"WR_good": _greet}, **{name: table})
                before = set(self.executor.event_dict)
                with self.assertRaises(CommandPluginError):
                    load_command_plugins(["good", name], self.executor)
                self.assertEqual(set(self.executor.event_dict), before)

    def test_two_plugins_cannot_bring_the_same_command(self):
        self.install(one={"WR_same": _greet}, two={"WR_same": _greet})
        with self.assertRaises(CommandPluginError):
            load_command_plugins(["one", "two"], self.executor)

    def test_no_action_command_loads_a_plugin(self):
        names = [name for name in executor.event_dict if "plugin" in str(name).lower()]
        self.assertEqual(names, [])


class TestRunSettingsAndFlags(_Installed):

    def tearDown(self):
        executor.event_dict.pop("WR_mine_greet", None)
        executor.variables.clear()

    def test_configuration_and_flag_are_merged_without_repeats(self):
        settings = build_run_settings(ProjectConfig(plugins=["from_config"]), None, False, None, None, None)
        self.assertEqual(settings.plugins, ("from_config",))

    def test_apply_loads_the_named_plugins(self):
        self.install(mine={"WR_mine_greet": _greet})
        apply_run_settings(RunSettings(plugins=("mine",)))
        self.assertIn("WR_mine_greet", executor.event_dict)

    def test_plugin_flag_makes_the_command_usable(self):
        self.install(mine={"WR_mine_greet": _greet})
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--execute_str", '[["WR_mine_greet", {"name": "cli"}]]', "--plugin", "mine", "--no-config"])
        self.assertEqual(code, 0)
        self.assertIn("hello cli", out.getvalue())

    def test_list_plugins_flag(self):
        self.install(beta={"WR_b": _greet}, alpha={"WR_a": _greet})
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--list-plugins", "--no-config"])
        self.assertEqual((code, out.getvalue().split()), (0, ["alpha", "beta"]))


class TestConsoleScripts(unittest.TestCase):

    def test_scripts_point_at_importable_functions_in_both_metadata_files(self):
        for name in ("pyproject.toml", "dev.toml"):
            with open(REPO_ROOT / name, "rb") as metadata_file:
                scripts = tomllib.load(metadata_file)["project"]["scripts"]
            self.assertEqual(sorted(scripts), ["web_runner", "webrunner", "webrunner-issue-worker",
                                               "webrunner-lsp", "webrunner-mcp"])
            for script, target in scripts.items():
                with self.subTest(file=name, script=script):
                    module_name, _, function_name = target.partition(":")
                    self.assertTrue(callable(getattr(import_module(module_name), function_name)))

    def test_mcp_script_starts_the_server(self):
        with patch("je_web_runner.mcp_server.server.serve_stdio") as serve:
            entry_points.mcp_main()
        serve.assert_called_once_with()

    def test_lsp_script_turns_newline_translation_off(self):
        stdin, stdout = MagicMock(), MagicMock()
        with patch("je_web_runner.action_lsp.server.serve_stdio") as serve, \
                patch.object(entry_points.sys, "stdin", stdin), patch.object(entry_points.sys, "stdout", stdout):
            entry_points.lsp_main()
        stdin.reconfigure.assert_called_once_with(newline="")
        stdout.reconfigure.assert_called_once_with(newline="")
        serve.assert_called_once_with()

    def test_issue_worker_script_returns_the_exit_status(self):
        with patch("je_web_runner.issue_worker.__main__.run", return_value=3) as run:
            self.assertEqual(entry_points.issue_worker_main(), 3)
        run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
