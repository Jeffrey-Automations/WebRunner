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
from je_web_runner.utils.cli.failure_count import FailureCount
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
        pool = pool_class.return_value.__enter__.return_value
        pool.submit.return_value.result.return_value = ("a.json", True, [])
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


class _Future:
    """A finished or still-pending pool future, as far as the fail-fast loop looks at one."""

    def __init__(self, result, pending=False):
        self._result = result
        self.pending = pending
        self.cancelled = False

    def cancel(self):
        self.cancelled = self.pending
        return self.pending

    def result(self):
        return self._result


class TestPoolFailFast(_CleanExecutor):

    def test_process_pool_cancels_what_has_not_started(self):
        for name in ("a", "b", "c", "d"):
            self._write(f"suite/{name}.json", [["WR_probe"]])
        futures = [_Future(("a.json", True, [])), _Future(("b.json", False, [])),
                   _Future(("c.json", True, [])), _Future(("d.json", True, []), pending=True)]
        pool_class = MagicMock()
        pool_class.return_value.__enter__.return_value.submit.side_effect = futures
        with patch.object(cli_main, "ProcessPoolExecutor", pool_class):
            code, _out, err = self._main(["-d", str(self.root / "suite"), "--parallel", "2",
                                          "--parallel-mode", "process", "--fail-fast"])
        self.assertEqual(code, 1)
        self.assertEqual([future.cancelled for future in futures], [False, False, False, True])
        self.assertIn("1 file(s) not run", err)

    def test_process_pool_without_fail_fast_uses_map(self):
        self._write("suite/a.json", [["WR_probe"]])
        pool_class = MagicMock()
        pool = pool_class.return_value.__enter__.return_value
        pool.map.return_value = [("a.json", True, [])]
        with patch.object(cli_main, "ProcessPoolExecutor", pool_class):
            self._main(["-d", str(self.root / "suite"), "--parallel", "2", "--parallel-mode", "process"])
        pool.map.assert_called_once()
        pool.submit.assert_not_called()

    def test_thread_pool_stops_starting_files(self):
        self._write("suite/a.json", [["WR_boom"]])
        for name in ("b", "c", "d"):
            self._write(f"suite/{name}.json", [["WR_probe", [name]]])
        files = [str(self.root / "suite" / f"{name}.json") for name in ("a", "b", "c", "d")]
        err = io.StringIO()
        # One worker, so the files start in the list's order; the count is what main() keeps open.
        with FailureCount(), redirect_stdout(io.StringIO()), redirect_stderr(err):
            outcome = cli_main._run_with_thread_pool(files, 1, None, fail_fast=True)
        self.assertEqual(outcome, {files[0]: False})
        self.assertEqual(self.seen, [])
        self.assertIn("3 file(s) not run", err.getvalue())

    def test_thread_pool_without_fail_fast_runs_every_file(self):
        self._write("suite/a.json", [["WR_boom"]])
        self._write("suite/b.json", [["WR_probe", ["b"]]])
        files = [str(self.root / "suite" / f"{name}.json") for name in ("a", "b")]
        with FailureCount(), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            outcome = cli_main._run_with_thread_pool(files, 1, None)
        self.assertEqual(outcome, {files[0]: False, files[1]: True})
        self.assertEqual(self.seen, ["b"])


class TestDependencyLevels(_CleanExecutor):

    def test_levels(self):
        from je_web_runner.utils.cli.dependency_levels import dependency_levels
        graph = {"login": [], "cart": ["login"], "search": [], "checkout": ["cart", "search"]}
        self.assertEqual(dependency_levels(graph), [["login", "search"], ["cart"], ["checkout"]])

    def test_cycle_is_an_error(self):
        from je_web_runner.utils.cli.dependency_levels import dependency_levels
        from je_web_runner.utils.test_filter.dependency import DependencyError
        with self.assertRaises(DependencyError):
            dependency_levels({"a": ["b"], "b": ["a"]})

    def test_failed_dependency_skips_what_depends_on_it(self):
        from je_web_runner.utils.cli.dependency_levels import run_in_levels
        graph = {"login": [], "cart": ["login"], "search": [], "checkout": ["cart"], "about": ["search"]}
        batches, skipped = [], []

        def run_batch(paths):
            batches.append(list(paths))
            return {path: path != "login" for path in paths}

        outcome = run_in_levels(graph, run_batch, skipped.append)
        self.assertEqual(batches, [["login", "search"], ["about"]])
        self.assertEqual(skipped, ["cart", "checkout"])
        self.assertEqual(outcome, {"login": False, "search": True, "cart": False, "about": True, "checkout": False})

    def test_fail_fast_stops_after_the_failing_level(self):
        from je_web_runner.utils.cli.dependency_levels import run_in_levels
        batches = []

        def run_batch(paths):
            batches.append(list(paths))
            return {path: False for path in paths}

        run_in_levels({"a": [], "b": ["a"], "c": []}, run_batch, lambda _path: None, fail_fast=True)
        self.assertEqual(batches, [["a", "c"]])

    def test_directory_with_dependencies_runs_in_the_pool_by_level(self):
        self._write("suite/login.json", {"meta": {"tags": ["x"]}, "webdriver_wrapper": [["WR_probe", ["login"]]]})
        self._write("suite/cart.json", {"meta": {"depends_on": ["login"]},
                                        "webdriver_wrapper": [["WR_probe", ["cart"]]]})
        self._write("suite/pay.json", {"meta": {"depends_on": ["cart"]},
                                       "webdriver_wrapper": [["WR_probe", ["pay"]]]})
        code, _out, _err = self._main(["-d", str(self.root / "suite"), "--parallel", "2"])
        self.assertEqual((code, self.seen), (0, ["login", "cart", "pay"]))

    def test_failed_upstream_skips_downstream_in_the_pool(self):
        self._write("suite/login.json", [["WR_boom"]])
        self._write("suite/cart.json", {"meta": {"depends_on": ["login"]},
                                        "webdriver_wrapper": [["WR_probe", ["cart"]]]})
        self._write("suite/other.json", [["WR_probe", ["other"]]])
        code, _out, _err = self._main(["-d", str(self.root / "suite"), "--parallel", "2"])
        self.assertEqual(code, 1)
        self.assertEqual(self.seen, ["other"])


class TestFormatAndExportFlags(_CleanExecutor):

    def test_format_rewrites_only_what_changes(self):
        messy = self._write("suite/messy.json", '[["WR_quit_all"],["WR_note",{"text":"x"}]]')
        code, out, _err = self._main(["--format", str(self.root / "suite")])
        self.assertEqual(code, 0)
        self.assertIn("reformatted:", out)
        formatted = messy.read_text(encoding="utf-8")
        self.assertNotEqual(formatted, '[["WR_quit_all"],["WR_note",{"text":"x"}]]')
        self.assertEqual(json.loads(formatted), [["WR_quit_all"], ["WR_note", {"text": "x"}]])
        _code, out, _err = self._main(["--format", str(self.root / "suite")])
        self.assertNotIn("reformatted:", out)

    def test_format_check_changes_nothing_and_exits_1(self):
        original = '[["WR_quit_all"],["WR_note",{"text":"x"}]]'
        messy = self._write("messy.json", original)
        code, out, _err = self._main(["--format", str(messy), "--format-check"])
        self.assertEqual(code, 1)
        self.assertIn("would reformat:", out)
        self.assertEqual(messy.read_text(encoding="utf-8"), original)

    def test_export_schema_and_command_reference(self):
        schema = self.root / "out" / "schema.json"
        reference = self.root / "out" / "commands.md"
        code, _out, _err = self._main(["--export-schema", str(schema), "--export-command-reference", str(reference)])
        self.assertEqual(code, 0)
        self.assertIn("oneOf", json.loads(schema.read_text(encoding="utf-8")))
        self.assertIn("`WR_to_url`", reference.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
