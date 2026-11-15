"""A dataset bound to an action file: its actions run once per row, reading ``${ROW.col}``."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.executor import action_executor
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.flow import FlowError, VariableStore
from je_web_runner.utils.flow.dataset import load_rows, per_row_actions, use_row
from je_web_runner.utils.flow.subflow import FileStack
from je_web_runner.utils.schema.action_schema import build_action_schema


class _Workspace(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self.executor = Executor()
        self.seen = []
        self.executor.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value
        self.executor.event_dict["WR_boom"] = self._boom

    @staticmethod
    def _boom():
        raise ValueError("boom")

    def _write(self, name: str, content) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path

    def _run(self, document):
        with patch("builtins.print"):
            return self.executor.collect_action_results(document)


class TestLoadRows(_Workspace):

    def test_inline_rows(self):
        rows = [{"user": "a"}, {"user": "b"}]
        self.assertIs(load_rows(rows, FileStack()), rows)

    def test_csv_and_json_files(self):
        self._write("users.csv", "user,age\nalice,30\nbob,41\n")
        self._write("users.json", [{"user": "carol", "age": 25}])
        self.assertEqual(load_rows("users.csv", FileStack()),
                         [{"user": "alice", "age": "30"}, {"user": "bob", "age": "41"}])
        self.assertEqual(load_rows("users.json", FileStack()), [{"user": "carol", "age": 25}])

    def test_relative_to_the_running_file(self):
        self._write("suite/data/users.json", [{"user": "dave"}])
        stack = FileStack()
        with stack.scope(self.root / "suite" / "login.json"):
            self.assertEqual(load_rows("data/users.json", stack), [{"user": "dave"}])

    def test_bad_sources(self):
        self._write("rows.txt", "user\nalice\n")
        self._write("not_rows.json", {"user": "x"})
        self._write("mixed.json", [{"user": "x"}, "y"])
        for source in (3, "", "missing.csv", "rows.txt", "mixed.json", [1, 2], {"user": "x"}):
            with self.subTest(source=source):
                with self.assertRaises(FlowError):
                    load_rows(source, FileStack())
        with self.assertRaises(Exception):
            load_rows("not_rows.json", FileStack())

    def test_files_outside_the_allowed_directories_are_refused(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        secret = Path(outside.name).resolve() / "secret.csv"
        secret.write_text("a\n1\n", encoding="utf-8")
        with self.assertRaises(FlowError):
            load_rows(str(secret), FileStack())


class TestRows(unittest.TestCase):

    def test_per_row_actions(self):
        planned = per_row_actions([["a"], ["b"]], [{"x": 1}, {"x": 2}])
        self.assertEqual(planned, [
            ["WR_use_row", {"index": 0, "row": {"x": 1}, "local": False}], ["a"], ["b"],
            ["WR_use_row", {"index": 1, "row": {"x": 2}, "local": False}], ["a"], ["b"],
        ])
        self.assertEqual(per_row_actions([["a"]], []), [])

    def test_use_row_binds_row_and_index(self):
        store = VariableStore()
        row = {"user": "alice", "tags": ["x", "y"]}
        self.assertIs(use_row(store, row, 4), row)
        self.assertEqual(store.expand("${ROW.user} #${ROW_INDEX} ${ROW.tags.1}"), "alice #4 y")
        self.assertEqual(store.expand("${ROW.tags}"), ["x", "y"])

    def test_unknown_column_is_an_error_inside_a_dataset(self):
        store = VariableStore()
        use_row(store, {"user": "alice"})
        with self.assertRaises(FlowError):
            store.expand("${ROW.email}")

    def test_row_placeholders_stay_outside_a_dataset(self):
        self.assertEqual(VariableStore().expand("${ROW.user}"), "${ROW.user}")

    def test_use_row_needs_an_object(self):
        with self.assertRaises(FlowError):
            use_row(VariableStore(), ["alice"])


class TestDocumentDataset(_Workspace):

    def test_actions_run_once_per_row(self):
        records, failed = self._run({
            "meta": {"dataset": [{"user": "alice"}, {"user": "bob"}]},
            "webdriver_wrapper": [["WR_probe", ["${ROW_INDEX}:${ROW.user}"]]],
        })
        self.assertEqual(self.seen, ["0:alice", "1:bob"])
        self.assertEqual(failed, [])
        self.assertEqual(len(records), 4)

    def test_setup_and_teardown_run_once_around_all_rows(self):
        self._run({
            "meta": {"dataset": [{"n": 1}, {"n": 2}], "setup": [["WR_probe", ["setup"]]],
                     "teardown": [["WR_probe", ["teardown"]]]},
            "webdriver_wrapper": [["WR_probe", ["${ROW.n}"]]],
        })
        self.assertEqual(self.seen, ["setup", 1, 2, "teardown"])

    def test_a_failing_row_does_not_stop_the_others(self):
        _records, failed = self._run({
            "meta": {"dataset": [{"n": 1}, {"n": 2}]},
            "webdriver_wrapper": [["WR_boom"], ["WR_probe", ["${ROW.n}"]]],
        })
        self.assertEqual(self.seen, [1, 2])
        self.assertEqual(len(failed), 2)

    def test_fail_fast_stops_at_the_first_failing_row_but_runs_teardown(self):
        self._run({
            "meta": {"dataset": [{"n": 1}, {"n": 2}], "fail_fast": True, "teardown": [["WR_probe", ["teardown"]]]},
            "webdriver_wrapper": [["WR_boom"], ["WR_probe", ["${ROW.n}"]]],
        })
        self.assertEqual(self.seen, ["teardown"])

    def test_dataset_file_next_to_the_action_file(self):
        self._write("suite/users.csv", "user\nalice\nbob\n")
        action_file = self._write("suite/login.json", {
            "meta": {"dataset": "users.csv"}, "webdriver_wrapper": [["WR_probe", ["${ROW.user}"]]]})
        with patch("builtins.print"):
            self.executor.execute_file(str(action_file))
        self.assertEqual(self.seen, ["alice", "bob"])

    def test_empty_dataset_runs_only_the_hooks(self):
        self._run({"meta": {"dataset": [], "setup": [["WR_probe", ["setup"]]]},
                   "webdriver_wrapper": [["WR_probe", ["never"]]]})
        self.assertEqual(self.seen, ["setup"])

    def test_skipped_file_does_not_load_its_dataset(self):
        records, _failed = self._run({"meta": {"skip": "later", "dataset": "missing.csv"},
                                      "webdriver_wrapper": [["WR_probe"]]})
        self.assertEqual(list(records.values()), ["skipped: later"])

    def test_bad_dataset_fails_the_document(self):
        with self.assertRaises(FlowError):
            self._run({"meta": {"dataset": "missing.csv"}, "webdriver_wrapper": [["WR_probe"]]})
        self.assertEqual(self.seen, [])

    def test_default_dataset_applies_to_files_without_their_own(self):
        self.executor.default_dataset = [{"who": "default"}]
        self._run([["WR_probe", ["${ROW.who}"]]])
        self._run({"meta": {"dataset": [{"who": "own"}]}, "webdriver_wrapper": [["WR_probe", ["${ROW.who}"]]]})
        self.assertEqual(self.seen, ["default", "own"])

    def test_a_called_file_keeps_its_rows_to_the_call(self):
        self._write("part.json", {"meta": {"dataset": [{"n": "inner"}]},
                                  "webdriver_wrapper": [["WR_probe", ["${ROW.n}"]]]})
        self.executor.default_dataset = [{"n": "unused by the called file"}]
        self._run({
            "meta": {"dataset": [{"n": "outer"}]},
            "webdriver_wrapper": [["WR_call_file", {"path": "part.json"}], ["WR_probe", ["${ROW.n}"]]],
        })
        self.assertEqual(self.seen, ["inner", "outer"])

    def test_schema_declares_the_key(self):
        document = next(form for form in build_action_schema()["oneOf"] if form.get("type") == "object")
        self.assertIn("dataset", document["properties"]["meta"]["properties"])


class TestCliDataset(_Workspace):

    def setUp(self):
        super().setUp()
        shared = action_executor.executor
        shared.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value
        self.addCleanup(shared.event_dict.pop, "WR_probe", None)
        self.addCleanup(setattr, shared, "default_dataset", shared.default_dataset)
        self.addCleanup(shared.variables.clear)

    def _main(self, arguments):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main(arguments)

    def test_dataset_flag_runs_each_file_per_row(self):
        self._write("data/users.csv", "user\nalice\nbob\n")
        self._write("suite/a.json", [["WR_probe", ["a:${ROW.user}"]]])
        self._write("suite/nested/b.json", [["WR_probe", ["b:${ROW.user}"]]])
        code = self._main(["-d", str(self.root / "suite"), "--dataset", "data/users.csv", "--no-config"])
        self.assertEqual(code, 0)
        self.assertEqual(self.seen, ["a:alice", "a:bob", "b:alice", "b:bob"])

    def test_dataset_flag_may_name_a_file_outside_the_working_directory(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        data = Path(elsewhere.name).resolve() / "users.csv"
        data.write_text("user\nerin\n", encoding="utf-8")
        action_file = self._write("one.json", [["WR_probe", ["${ROW.user}"]]])
        self._main(["-e", str(action_file), "--dataset", str(data), "--no-config"])
        self.assertEqual(self.seen, ["erin"])

    def test_dataset_flag_must_be_csv_or_json(self):
        self._write("users.txt", "user\nalice\n")
        action_file = self._write("one.json", [["WR_probe", ["${ROW.user}"]]])
        with self.assertRaises(FlowError):
            self._main(["-e", str(action_file), "--dataset", "users.txt", "--no-config"])
        self.assertEqual(self.seen, [])

    def test_dataset_flag_with_a_single_file(self):
        self._write("users.json", [{"user": "carol"}])
        action_file = self._write("one.json", [["WR_probe", ["${ROW.user}"]]])
        self._main(["-e", str(action_file), "--dataset", "users.json", "--no-config"])
        self.assertEqual(self.seen, ["carol"])


if __name__ == "__main__":
    unittest.main()
