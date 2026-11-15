"""WR_call_file: one action file running another, with parameters."""
import contextlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor import action_executor
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.flow import FlowError
from je_web_runner.utils.flow.subflow import MAX_CALL_DEPTH, FileStack


def _write(path: Path, actions) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(actions), encoding="utf-8")
    return path


class _Workspace(unittest.TestCase):
    """A temporary directory that is the working directory for the test."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.root)
        self.executor = Executor()
        self.seen = []
        self.executor.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value
        self.executor.event_dict["WR_boom"] = self._boom

    @staticmethod
    def _boom():
        raise ValueError("boom")


class TestCallFile(_Workspace):

    def test_runs_the_called_file_with_parameters(self):
        _write(self.root / "login.json", [["WR_probe", ["${user}@${host}"]], ["WR_probe", ["done"]]])
        self.executor.variables.set("host", "example.test")
        result = self.executor.execute_one(["WR_call_file", {"path": "login.json", "params": {"user": "alice"}}])
        self.assertEqual(result, ["alice@example.test", "done"])
        self.assertFalse(self.executor.variables.has("user"))

    def test_parameters_are_expanded_at_the_call(self):
        _write(self.root / "echo.json", [["WR_probe", ["${value}"]]])
        self.executor.variables.set("n", 7)
        self.executor.execute_one(["WR_call_file", {"path": "echo.json", "params": {"value": "${n}"}}])
        self.assertEqual(self.seen, [7])

    def test_object_documents_are_accepted(self):
        _write(self.root / "doc.json", {"meta": {"tags": ["x"]}, "webdriver_wrapper": [["WR_probe", [1]]]})
        self.assertEqual(self.executor.execute_one(["WR_call_file", {"path": "doc.json"}]), [1])

    def test_relative_paths_start_at_the_calling_file(self):
        _write(self.root / "flows" / "main.json", [["WR_call_file", {"path": "parts/step.json"}]])
        _write(self.root / "flows" / "parts" / "step.json", [["WR_call_file", {"path": "../shared.json"}]])
        _write(self.root / "flows" / "shared.json", [["WR_probe", ["shared"]]])
        with patch("builtins.print"):
            self.executor.execute_files([str(self.root / "flows" / "main.json")])
        self.assertEqual(self.seen, ["shared"])
        self.assertIsNone(self.executor.files.current)

    def test_a_failure_in_the_called_file_fails_the_call(self):
        _write(self.root / "bad.json", [["WR_probe", [1]], ["WR_boom"], ["WR_probe", [2]]])
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_one(["WR_call_file", {"path": "bad.json"}])
        self.assertEqual(self.seen, [1])
        self.assertIsNone(self.executor.files.current)

    def test_a_file_cannot_call_itself(self):
        _write(self.root / "a.json", [["WR_call_file", {"path": "b.json"}]])
        _write(self.root / "b.json", [["WR_call_file", {"path": "a.json"}]])
        with self.assertRaises(WebRunnerExecuteException) as raised:
            self.executor.execute_one(["WR_call_file", {"path": "a.json"}])
        self.assertIn("already running", str(raised.exception))

    def test_paths_outside_the_allowed_directories_are_refused(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        secret = _write(Path(outside.name).resolve() / "secret.json", [["WR_probe", ["leak"]]])
        for path in (str(secret), os.path.relpath(secret, self.root)):
            with self.subTest(path=path):
                with self.assertRaises(WebRunnerExecuteException) as raised:
                    self.executor.execute_one(["WR_call_file", {"path": path}])
                self.assertIn("outside", str(raised.exception))
        self.assertEqual(self.seen, [])

    def test_the_directory_of_the_started_file_is_allowed(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        base = Path(elsewhere.name).resolve()
        main_file = _write(base / "main.json", [["WR_call_file", {"path": "sub/part.json"}]])
        _write(base / "sub" / "part.json", [["WR_probe", ["part"]]])
        with patch("builtins.print"):
            self.executor.execute_file(str(main_file))
        self.assertEqual(self.seen, ["part"])

    def test_bad_arguments(self):
        _write(self.root / "ok.json", [])
        for arguments in ({"path": "missing.json"}, {"path": ""}, {"path": 3},
                          {"path": "ok.json", "params": ["x"]}):
            with self.subTest(arguments=arguments):
                with self.assertRaises(WebRunnerExecuteException):
                    self.executor.execute_one(["WR_call_file", arguments])

    def test_gates_apply_in_the_called_file(self):
        _write(self.root / "probe.json", [["WR_probe", ["x"]]])
        with self.executor.restricted({"WR_probe"}):
            with self.assertRaises(WebRunnerExecuteException):
                self.executor.execute_one(["WR_call_file", {"path": "probe.json"}])
        self.assertEqual(self.seen, [])


class TestFileStack(_Workspace):

    def test_depth_limit(self):
        stack = FileStack()
        target = _write(self.root / "leaf.json", [])
        with contextlib.ExitStack() as running:
            for index in range(MAX_CALL_DEPTH):
                running.enter_context(stack.scope(self.root / f"f{index}.json"))
            with self.assertRaises(FlowError) as raised:
                stack.resolve_call(str(target))
        self.assertIn("deep", str(raised.exception))

    def test_each_thread_has_its_own_stack(self):
        stack = FileStack()
        seen = []
        with stack.scope(self.root / "main.json"):
            worker = threading.Thread(target=lambda: seen.append(stack.current))
            worker.start()
            worker.join()
            self.assertEqual(stack.current, self.root / "main.json")
        self.assertEqual(seen, [None])


class TestCliGivesTheFileContext(_Workspace):

    def setUp(self):
        super().setUp()
        self.shared = action_executor.executor
        self.shared.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value
        self.addCleanup(self.shared.event_dict.pop, "WR_probe", None)
        _write(self.root / "suite" / "main.json", [["WR_call_file", {"path": "helper.json"}]])
        _write(self.root / "suite" / "helper.json", [["WR_probe", ["helper"]]])

    def test_execute_file(self):
        with patch("builtins.print"):
            self.assertEqual(main(["-e", str(self.root / "suite" / "main.json")]), 0)
        self.assertEqual(self.seen, ["helper"])

    def test_execute_dir(self):
        with patch("builtins.print"):
            main(["-d", str(self.root / "suite")])
        self.assertEqual(sorted(self.seen), ["helper", "helper"])


if __name__ == "__main__":
    unittest.main()
