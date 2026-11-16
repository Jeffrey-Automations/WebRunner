"""Stepping through an action list: --step and WR_breakpoint."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor import action_executor
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.flow.debugger import ABORTED_TEXT, Stepper


class _Console:
    """Scripted answers for the stepper, and what it printed."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.lines = []
        self.prompts = 0

    def read(self, _prompt):
        self.prompts += 1
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)

    def write(self, line):
        self.lines.append(line)


class TestStepper(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()
        self.seen = []
        self.executor.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value

    def _run(self, answers, actions):
        console = _Console(answers)
        self.executor.debugger = Stepper(console.read, console.write)
        with patch("builtins.print"):
            records, failed = self.executor.collect_action_results(actions)
        return console, records, failed

    def test_next_pauses_before_every_top_level_action(self):
        console, _records, failed = self._run(["n", "", "next"], [["WR_probe", [1]], ["WR_probe", [2]],
                                                                  ["WR_probe", [3]]])
        self.assertEqual((self.seen, failed, console.prompts), ([1, 2, 3], [], 3))
        self.assertEqual([line for line in console.lines if line.startswith("next:")],
                         ["next: ['WR_probe', [1]]", "next: ['WR_probe', [2]]", "next: ['WR_probe', [3]]"])

    def test_continue_runs_to_the_end(self):
        console, _records, _failed = self._run(["c"], [["WR_probe", [1]], ["WR_probe", [2]]])
        self.assertEqual((self.seen, console.prompts), ([1, 2], 1))

    def test_continue_stops_at_a_breakpoint(self):
        console, _records, _failed = self._run(["c", "n", "c"], [
            ["WR_probe", [1]], ["WR_breakpoint", {"message": "before two"}], ["WR_probe", [2]], ["WR_probe", [3]]])
        self.assertEqual(self.seen, [1, 2, 3])
        self.assertIn("breakpoint: before two", console.lines)
        self.assertEqual(console.prompts, 3)

    def test_nested_actions_run_with_their_block(self):
        console, _records, _failed = self._run(["n"], [["WR_repeat", {"times": 2, "do": [["WR_probe", ["x"]]]}]])
        self.assertEqual((self.seen, console.prompts), (["x", "x"], 1))

    def test_variables_are_shown(self):
        self.executor.variables.set("user", "alice")
        self.executor.variables.set("long", "x" * 500)
        console, _records, _failed = self._run(["v", "n"], [["WR_probe"]])
        self.assertIn("  user = 'alice'", console.lines)
        long_line = next(line for line in console.lines if line.startswith("  long = "))
        self.assertLess(len(long_line), 130)

    def test_no_variables_and_unknown_answers(self):
        console, _records, _failed = self._run(["v", "what", "n"], [["WR_probe"]])
        self.assertIn("(no variables)", console.lines)
        self.assertTrue(any("variables" in line and "stop" in line for line in console.lines))

    def test_quit_leaves_the_rest_not_run(self):
        console, records, failed = self._run(["n", "q"], [["WR_probe", [1]], ["WR_probe", [2]], ["WR_probe", [3]]])
        self.assertEqual(self.seen, [1])
        self.assertEqual(len(failed), 2)
        self.assertTrue(all(ABORTED_TEXT in records[key] for key in failed))
        self.assertEqual(console.prompts, 2)

    def test_closed_console_continues(self):
        console, _records, failed = self._run([], [["WR_probe", [1]], ["WR_probe", [2]]])
        self.assertEqual((self.seen, failed, console.prompts), ([1, 2], [], 1))
        self.assertIn("input ended; continuing without pausing", console.lines)

    def test_breakpoint_without_a_stepper_does_nothing(self):
        self.assertIs(self.executor.execute_one(["WR_breakpoint", {"message": "ignored"}]), False)

    def test_single_actions_are_not_stepped(self):
        console = _Console([])
        self.executor.debugger = Stepper(console.read, console.write)
        self.assertEqual(self.executor.execute_one(["WR_probe", [2]]), 2)
        self.assertEqual(console.prompts, 0)


class TestStepFlag(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self.shared = action_executor.executor
        self.addCleanup(setattr, self.shared, "debugger", None)
        self.seen = []
        self.shared.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value
        self.addCleanup(self.shared.event_dict.pop, "WR_probe", None)
        self.action_file = self.root / "a.json"
        self.action_file.write_text(json.dumps([["WR_probe", [1]], ["WR_probe", [2]]]), encoding="utf-8")

    def test_step_flag_pauses_on_the_console(self):
        out = io.StringIO()
        with patch("builtins.input", side_effect=["n", "c"]) as asked, redirect_stdout(out), \
                redirect_stderr(io.StringIO()):
            code = main(["-e", str(self.action_file), "--step", "--no-config"])
        self.assertEqual((code, self.seen, asked.call_count), (0, [1, 2], 2))
        self.assertIn("next: ['WR_probe', [1]]", out.getvalue())

    def test_step_is_refused_with_a_pool(self):
        for extra in (["--parallel", "2"], ["--parallel-mode", "async"]):
            with self.subTest(extra=extra):
                with self.assertRaises(WebRunnerExecuteException):
                    main(["-d", str(self.root), "--step", "--no-config", *extra])
        self.assertIsNone(self.shared.debugger)
        self.assertEqual(self.seen, [])


if __name__ == "__main__":
    unittest.main()
