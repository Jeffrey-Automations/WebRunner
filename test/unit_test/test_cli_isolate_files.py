"""``--isolate-files``: a file's variables and saved locators end with the file."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.cli.arguments import _build_parser
from je_web_runner.utils.cli.cli_main import _run_settings, main
from je_web_runner.utils.cli.run_settings import RunSettings, apply_run_settings
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor._isolation import file_isolation, isolated_file
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.project_config.config import ProjectConfig, load_config
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record

SETS = [["WR_set_var", {"name": "leak_probe", "value": "from the first file"}],
        ["WR_save_test_object", {"test_object_name": "leak_locator", "object_type": "id"}]]
# Passes only when the variable the other file set is still there.
NEEDS = [["WR_assert_var", {"var": "leak_probe", "value": "from the first file"}]]


class _IsolationCase(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.addCleanup(setattr, executor, "isolate_files", False)
        self.addCleanup(executor.variables.unset, "leak_probe")
        self.addCleanup(executor.variables.unset, "from_setup")
        saved = dict(test_object_record.test_object_record_dict)
        self.addCleanup(setattr, test_object_record, "test_object_record_dict", saved)

    def write(self, name: str, content) -> str:
        path = self.folder / name
        path.write_text(json.dumps(content), encoding="utf-8")
        return str(path)


class TestIsolatedFile(_IsolationCase):

    def test_what_a_file_sets_ends_with_it(self):
        with isolated_file(executor):
            executor.execute_action(SETS)
            self.assertTrue(executor.variables.has("leak_probe"))
            self.assertIn("leak_locator", test_object_record.test_object_record_dict)
        self.assertFalse(executor.variables.has("leak_probe"))
        self.assertNotIn("leak_locator", test_object_record.test_object_record_dict)

    def test_a_file_starts_with_what_the_run_set_up(self):
        executor.variables.set("from_setup", 7)
        test_object_record.save_test_object("setup_locator", "id")
        with isolated_file(executor):
            self.assertEqual(executor.variables.resolve("from_setup"), 7)
            self.assertIn("setup_locator", test_object_record.test_object_record_dict)
            test_object_record.remove_test_object("setup_locator")
        self.assertIn("setup_locator", test_object_record.test_object_record_dict)

    def test_the_table_is_restored_when_the_file_raises(self):
        with self.assertRaises(RuntimeError):
            with isolated_file(executor):
                test_object_record.save_test_object("leak_locator", "id")
                raise RuntimeError("boom")
        self.assertNotIn("leak_locator", test_object_record.test_object_record_dict)

    def test_off_changes_nothing(self):
        with file_isolation(executor):
            executor.execute_action(SETS)
        self.assertTrue(executor.variables.has("leak_probe"))
        self.assertIn("leak_locator", test_object_record.test_object_record_dict)


class TestIsolateFilesCli(_IsolationCase):

    def test_without_the_flag_a_later_file_sees_the_earlier_one(self):
        self.write("a_sets.json", SETS)
        self.write("b_needs.json", NEEDS)
        self.assertEqual(main(["-d", str(self.folder), "--no-config"]), 0)

    def test_with_the_flag_the_dependency_shows(self):
        self.write("a_sets.json", SETS)
        self.write("b_needs.json", NEEDS)
        self.assertEqual(main(["-d", str(self.folder), "--isolate-files", "--no-config"]), 1)
        self.assertFalse(executor.variables.has("leak_probe"))

    def test_run_variables_reach_every_isolated_file(self):
        needs_var = [["WR_assert_var", {"var": "leak_probe", "value": "given"}]]
        self.write("a.json", needs_var)
        self.write("b.json", needs_var)
        code = main(["-d", str(self.folder), "--isolate-files", "--var", "leak_probe=given", "--no-config"])
        self.assertEqual(code, 0)

    def test_refused_where_files_share_a_process_at_one_time(self):
        for extra in (["--parallel", "2"], ["--parallel-mode", "async"]):
            args = _build_parser().parse_args(["--isolate-files", *extra])
            args.project_config = ProjectConfig()
            with self.subTest(extra=extra), self.assertRaises(WebRunnerException):
                _run_settings(args)
        args = _build_parser().parse_args(["--isolate-files", "--parallel", "2", "--parallel-mode", "process"])
        args.project_config = ProjectConfig()
        self.assertTrue(_run_settings(args).isolate_files)

    def test_configuration_key_and_apply(self):
        path = self.folder / "webrunner.toml"
        path.write_text("isolate_files = true\n", encoding="utf-8")
        self.assertTrue(load_config(str(path)).isolate_files)
        apply_run_settings(RunSettings(isolate_files=True))
        self.assertTrue(executor.isolate_files)


if __name__ == "__main__":
    unittest.main()
