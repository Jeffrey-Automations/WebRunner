"""``--backend``: every list is translated before it runs, and an untranslatable command is refused."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.cli.arguments import _build_parser
from je_web_runner.utils.cli.cli_main import _run_settings, main
from je_web_runner.utils.cli.run_settings import RunSettings, apply_run_settings
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.project_config.config import ProjectConfig, load_config
from je_web_runner.utils.sel_to_pw import BackendTranslationError, SelToPwError

NEUTRAL = [["WR_set_var", {"name": "backend_probe", "value": 1}],
           ["WR_assert_var", {"var": "backend_probe", "value": 1}]]
NO_EQUIVALENT = ["WR_maximize_window"]


class _BackendCase(unittest.TestCase):

    def setUp(self):
        self.addCleanup(executor.set_backend, None)
        self.addCleanup(executor.variables.unset, "backend_probe")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def write(self, name: str, content) -> str:
        path = self.folder / name
        path.write_text(json.dumps(content), encoding="utf-8")
        return str(path)


class TestExecutorBackend(_BackendCase):

    def test_default_runs_lists_as_written(self):
        self.assertIsNone(executor.backend)
        self.assertEqual(executor.document_actions([["WR_to_url", {"url": "https://example.test"}]]),
                         [["WR_to_url", {"url": "https://example.test"}]])

    def test_actions_are_translated_before_they_run(self):
        executor.set_backend("playwright")
        self.assertEqual(executor.document_actions([["WR_to_url", {"url": "https://example.test"}]]),
                         [["WR_pw_to_url", {"url": "https://example.test"}]])

    def test_setup_and_teardown_are_translated(self):
        executor.set_backend("playwright")
        document = {"meta": {"setup": [["WR_to_url", {"url": "https://a.test"}]],
                             "teardown": [["WR_to_url", {"url": "https://z.test"}]]},
                    "webdriver_wrapper": NEUTRAL}
        names = [action[0] for action in executor.document_actions(document)]
        self.assertEqual(names, ["WR_pw_to_url", "WR_set_var", "WR_assert_var", "WR_pw_to_url"])
        self.assertEqual(document["meta"]["setup"][0][0], "WR_to_url")

    def test_a_command_without_an_equivalent_is_refused_by_name(self):
        executor.set_backend("playwright")
        with self.assertRaises(BackendTranslationError) as caught:
            executor.execute_action([*NEUTRAL, NO_EQUIVALENT])
        self.assertIn("WR_maximize_window", str(caught.exception))
        self.assertIn("action[2]", str(caught.exception))

    def test_a_called_file_is_translated_too(self):
        executor.set_backend("playwright")
        self.write("called.json", [NO_EQUIVALENT])
        caller = self.write("caller.json", [["WR_call_file", {"path": "called.json"}]])
        with executor.files.scope(caller):
            with self.assertRaises(WebRunnerException) as caught:
                executor.execute_one(["WR_call_file", {"path": "called.json"}])
        self.assertIn("WR_maximize_window", str(caught.exception))

    def test_unknown_backend_is_refused_and_changes_nothing(self):
        with self.assertRaises(SelToPwError):
            executor.set_backend("webkitgtk")
        self.assertIsNone(executor.backend)

    def test_not_a_list_is_still_the_executor_error(self):
        executor.set_backend("playwright")
        with self.assertRaises(WebRunnerException) as caught:
            executor.document_actions("WR_quit")
        self.assertNotIsInstance(caught.exception, SelToPwError)


class TestBackendSettings(_BackendCase):

    def test_flag_wins_over_the_configuration(self):
        args = _build_parser().parse_args(["--backend", "selenium"])
        args.project_config = ProjectConfig(backend="playwright")
        self.assertEqual(_run_settings(args).backend, "selenium")
        args = _build_parser().parse_args([])
        args.project_config = ProjectConfig(backend="playwright")
        self.assertEqual(_run_settings(args).backend, "playwright")

    def test_configuration_key(self):
        path = self.folder / "webrunner.toml"
        path.write_text('backend = "playwright"\n', encoding="utf-8")
        self.assertEqual(load_config(str(path)).backend, "playwright")
        path.write_text('backend = "puppeteer"\n', encoding="utf-8")
        with self.assertRaises(WebRunnerException):
            load_config(str(path))

    def test_apply_sets_the_executor(self):
        apply_run_settings(RunSettings(backend="playwright"))
        self.assertEqual(executor.backend, "playwright")

    def test_flag_rejects_another_name(self):
        with self.assertRaises(SystemExit):
            _build_parser().parse_args(["--backend", "puppeteer"])


class TestBackendCli(_BackendCase):

    def test_translatable_file_runs(self):
        path = self.write("good.json", NEUTRAL)
        self.assertEqual(main(["-e", path, "--backend", "playwright", "--no-config"]), 0)

    def test_untranslatable_file_fails_the_run(self):
        path = self.write("bad.json", [*NEUTRAL, NO_EQUIVALENT])
        # ``main`` lets it out; the entry point prints it on one line and exits 1.
        with self.assertRaises(BackendTranslationError):
            main(["-e", path, "--backend", "playwright", "--no-config"])
        # Nothing of the file ran: it is refused as a whole, not at the action that cannot be translated.
        self.assertFalse(executor.variables.has("backend_probe"))

    def test_directory_reports_the_file_that_cannot_run(self):
        self.write("a_good.json", NEUTRAL)
        self.write("b_bad.json", [NO_EQUIVALENT])
        self.assertEqual(main(["-d", str(self.folder), "--backend", "playwright", "--no-config"]), 1)


if __name__ == "__main__":
    unittest.main()
