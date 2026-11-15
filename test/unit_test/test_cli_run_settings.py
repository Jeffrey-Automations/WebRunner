"""CLI run settings: --var, --env, --fail-fast, the project configuration, and the tool flags."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cli import cli_main
from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.cli.run_settings import RunSettings, apply_run_settings, build_run_settings, parse_variable
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.project_config import ProjectConfig, ProjectConfigError
from je_web_runner.utils.test_record.test_record_class import test_record_instance


class _CleanExecutor(unittest.TestCase):
    """A temporary working directory, and the shared executor put back as it was."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self.addCleanup(executor.variables.clear)
        self.addCleanup(executor.set_fail_fast, executor.fail_fast.enabled)
        self.addCleanup(setattr, executor, "retry_policy", dict(executor.retry_policy))
        self.addCleanup(setattr, executor, "failure_screenshot_dir", executor.failure_screenshot_dir)
        self.addCleanup(test_record_instance.set_record_enable, test_record_instance.init_record)
        executor.variables.clear()
        self.seen = []
        executor.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value
        executor.event_dict["WR_boom"] = self._boom
        self.addCleanup(executor.event_dict.pop, "WR_probe", None)
        self.addCleanup(executor.event_dict.pop, "WR_boom", None)

    @staticmethod
    def _boom():
        raise ValueError("boom")

    def _write(self, name: str, content) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path

    def _main(self, arguments):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(arguments)
        return code, out.getvalue(), err.getvalue()


class TestParseVariable(unittest.TestCase):

    def test_json_values_keep_their_type(self):
        self.assertEqual(parse_variable("count=3"), ("count", 3))
        self.assertEqual(parse_variable("flag=true"), ("flag", True))
        self.assertEqual(parse_variable('items=[1, "a"]'), ("items", [1, "a"]))
        self.assertEqual(parse_variable('text="quoted"'), ("text", "quoted"))

    def test_other_values_are_text(self):
        self.assertEqual(parse_variable("base=https://example.test/a?b=c"), ("base", "https://example.test/a?b=c"))
        self.assertEqual(parse_variable("empty="), ("empty", ""))

    def test_missing_name_or_equals_sign(self):
        for text in ("novalue", "=3", " =x"):
            with self.subTest(text=text):
                with self.assertRaises(WebRunnerExecuteException):
                    parse_variable(text)


class TestBuildAndApply(_CleanExecutor):

    def test_flags_win_over_the_configuration(self):
        config = ProjectConfig(vars={"base": "from-file", "kept": 1}, env="staging", fail_fast=None, retries=2)
        settings = build_run_settings(config, "out", True, "prod", "envs", ["base=from-flag"])
        self.assertEqual(settings, RunSettings(
            recording=True, fail_fast=True, env="prod", env_dir="envs", retries=2, retry_backoff=0.0,
            failure_screenshot_dir=None, variables={"base": "from-flag", "kept": 1}))

    def test_configuration_fills_what_flags_leave_out(self):
        config = ProjectConfig(env="staging", env_dir="conf", fail_fast=True)
        settings = build_run_settings(config, None, False, None, None, None)
        self.assertEqual((settings.recording, settings.fail_fast, settings.env, settings.env_dir),
                         (False, True, "staging", "conf"))

    def test_apply_sets_the_executor_up(self):
        self._write("conf/.env.staging", "WR_SETTINGS_TEST_BASE=https://staging.test\n")
        self.addCleanup(os.environ.pop, "WR_SETTINGS_TEST_BASE", None)
        apply_run_settings(RunSettings(
            fail_fast=True, env="staging", env_dir="conf", retries=2, retry_backoff=0.5,
            variables={"base": "${ENV.WR_SETTINGS_TEST_BASE}/app", "count": 3}))
        self.assertTrue(executor.fail_fast.enabled)
        self.assertEqual(executor.retry_policy, {"retries": 2, "backoff": 0.5})
        self.assertEqual(executor.variables.get("base"), "https://staging.test/app")
        self.assertEqual(executor.variables.get("count"), 3)

    def test_apply_leaves_recording_and_fail_fast_alone_when_not_asked(self):
        test_record_instance.set_record_enable(True)
        executor.set_fail_fast(True)
        apply_run_settings(RunSettings())
        self.assertTrue(test_record_instance.init_record)
        self.assertTrue(executor.fail_fast.enabled)


class TestCliFlags(_CleanExecutor):

    def test_var_reaches_the_action_file(self):
        action_file = self._write("a.json", [["WR_probe", ["${greeting} ${count}"]]])
        code, _out, _err = self._main(["-e", str(action_file), "--var", "greeting=hello", "--var", "count=2"])
        self.assertEqual((code, self.seen), (0, ["hello 2"]))

    def test_configuration_file_is_discovered(self):
        self._write("webrunner.toml", '[vars]\nwho = "config"\n')
        action_file = self._write("a.json", [["WR_probe", ["${who}"]]])
        self._main(["-e", str(action_file)])
        self._main(["-e", str(action_file), "--var", "who=flag"])
        executor.variables.clear()  # a new process would start without the variables of the last run
        self._main(["-e", str(action_file), "--no-config"])
        self.assertEqual(self.seen, ["config", "flag", "${who}"])

    def test_explicit_config_and_its_cli_defaults(self):
        config = self._write("conf/ci.toml", 'exclude_tag = ["skip-me"]\n')
        self._write("suite/run.json", {"meta": {"tags": ["x"]}, "webdriver_wrapper": [["WR_probe", ["run"]]]})
        self._write("suite/skip.json", {"meta": {"tags": ["skip-me"]}, "webdriver_wrapper": [["WR_probe", ["no"]]]})
        self._main(["-d", str(self.root / "suite"), "--config", str(config)])
        self.assertEqual(self.seen, ["run"])
        self.seen.clear()
        self._main(["-d", str(self.root / "suite"), "--config", str(config), "--exclude-tag", "x"])
        self.assertEqual(self.seen, ["no"])

    def test_bad_configuration_fails_before_anything_runs(self):
        self._write("webrunner.toml", "no_such_setting = 1\n")
        action_file = self._write("a.json", [["WR_probe", ["x"]]])
        with self.assertRaises(ProjectConfigError):
            self._main(["-e", str(action_file)])
        self.assertEqual(self.seen, [])

    def test_fail_fast_skips_the_rest_of_the_file(self):
        action_file = self._write("a.json", [["WR_boom"], ["WR_probe", ["after"]]])
        code, _out, _err = self._main(["-e", str(action_file), "--fail-fast"])
        self.assertEqual((code, self.seen), (1, []))

    def test_fail_fast_stops_a_directory_run(self):
        self._write("suite/a.json", [["WR_boom"]])
        self._write("suite/b.json", [["WR_probe", ["b"]]])
        code, _out, err = self._main(["-d", str(self.root / "suite"), "--fail-fast"])
        self.assertEqual((code, self.seen), (1, []))
        self.assertIn("1 file(s) not run", err)

    def test_without_fail_fast_every_file_runs(self):
        self._write("suite/a.json", [["WR_boom"]])
        self._write("suite/b.json", [["WR_probe", ["b"]]])
        code, _out, _err = self._main(["-d", str(self.root / "suite")])
        self.assertEqual((code, self.seen), (1, ["b"]))

    def test_process_workers_get_the_run_settings(self):
        self._write("suite/a.json", [["WR_probe"]])
        test_record_instance.set_record_enable(False)
        pool_class = MagicMock()
        pool_class.return_value.__enter__.return_value.map.return_value = [("a.json", True, [])]
        with patch.object(cli_main, "ProcessPoolExecutor", pool_class):
            self._main(["-d", str(self.root / "suite"), "--parallel", "2", "--parallel-mode", "process",
                        "--var", "who=worker", "--fail-fast"])
        (settings,) = pool_class.call_args.kwargs["initargs"]
        self.assertEqual((settings.variables, settings.fail_fast, settings.recording),
                         ({"who": "worker"}, True, False))


class TestToolFlags(_CleanExecutor):

    def test_list_commands(self):
        code, out, _err = self._main(["--list-commands"])
        names = out.split()
        self.assertEqual(code, 0)
        self.assertIn("WR_to_url", names)
        self.assertEqual(names, sorted(names))
        self.assertEqual([name for name in names if not name.startswith("WR_")], [])

    def test_lint_warning_exits_1(self):
        action_file = self._write("a.json", [["WR_quit"]])
        code, out, _err = self._main(["--lint", str(action_file)])
        self.assertEqual(code, 1)
        self.assertIn("warning [legacy_name] action[0]", out)
        self.assertIn("1 warning(s)", out)

    def test_lint_information_only_exits_0(self):
        action_file = self._write("a.json", [["WR_quit_all", {}]])
        code, out, _err = self._main(["--lint", str(action_file)])
        self.assertEqual(code, 0)
        self.assertIn("info [empty_kwargs]", out)

    def test_lint_directory_includes_subdirectories(self):
        self._write("suite/ok.json", {"meta": {"tags": ["x"]}, "webdriver_wrapper": [["WR_quit_all"]]})
        self._write("suite/nested/bad.json", [["WR_no_such_command"]])
        code, out, _err = self._main(["--lint", str(self.root / "suite")])
        self.assertEqual(code, 1)
        self.assertIn("unknown_command", out)
        self.assertIn("2 file(s), 1 warning(s)", out)

    def test_lint_missing_target(self):
        with self.assertRaises(FileNotFoundError):
            self._main(["--lint", str(self.root / "nowhere")])

    def test_init_writes_a_starter_workspace(self):
        target = self.root / "new_project"
        code, out, _err = self._main(["--init", str(target)])
        self.assertEqual(code, 0)
        self.assertTrue(any(target.rglob("*.json")))
        self.assertIn("created:", out)
        _code, out, _err = self._main(["--init", str(target)])
        self.assertIn("skipped:", out)
        self.assertNotIn("created:", out)


if __name__ == "__main__":
    unittest.main()
