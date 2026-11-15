"""Fail-fast: the actions after a failed one are skipped, teardown still runs."""
import threading
import unittest
from unittest.mock import patch

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.flow import FlowError
from je_web_runner.utils.flow.document import fail_fast_setting, teardown_count
from je_web_runner.utils.flow.failfast import SKIPPED_TEXT, FailFast


class TestExecutorFailFast(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()
        self.seen = []
        self.executor.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value
        self.executor.event_dict["WR_boom"] = self._boom

    @staticmethod
    def _boom():
        raise ValueError("boom")

    def _run(self, document):
        with patch("builtins.print"):
            return self.executor.collect_action_results(document)

    def test_off_by_default_every_action_runs(self):
        records, failed = self._run([["WR_boom"], ["WR_probe", [1]], ["WR_probe", [2]]])
        self.assertEqual(self.seen, [1, 2])
        self.assertEqual(len(failed), 1)
        self.assertEqual(len(records), 3)

    def test_on_skips_the_rest_and_records_them(self):
        self.executor.set_fail_fast(True)
        records, failed = self._run([["WR_probe", [1]], ["WR_boom"], ["WR_probe", [2]], ["WR_probe", [3]]])
        self.assertEqual(self.seen, [1])
        self.assertEqual(len(failed), 3)
        self.assertIn("boom", records[failed[0]])
        for key in failed[1:]:
            self.assertIn(SKIPPED_TEXT, records[key])

    def test_teardown_still_runs(self):
        self.executor.set_fail_fast(True)
        records, failed = self._run({
            "meta": {"setup": [["WR_probe", ["setup"]]],
                     "teardown": [["WR_probe", ["teardown 1"]], ["WR_probe", ["teardown 2"]]]},
            "webdriver_wrapper": [["WR_boom"], ["WR_probe", ["main"]]],
        })
        self.assertEqual(self.seen, ["setup", "teardown 1", "teardown 2"])
        self.assertEqual(len(failed), 2)
        self.assertEqual(len(records), 5)

    def test_a_failed_setup_skips_the_file_but_not_teardown(self):
        self.executor.set_fail_fast(True)
        self._run({"meta": {"setup": [["WR_boom"]], "teardown": [["WR_probe", ["teardown"]]]},
                   "webdriver_wrapper": [["WR_probe", ["main"]]]})
        self.assertEqual(self.seen, ["teardown"])

    def test_each_list_starts_fresh(self):
        self.executor.set_fail_fast(True)
        self._run([["WR_boom"], ["WR_probe", ["skipped"]]])
        self._run([["WR_probe", ["next list"]]])
        self.assertEqual(self.seen, ["next list"])

    def test_meta_fail_fast_is_for_that_file_only(self):
        self._run({"meta": {"fail_fast": True}, "webdriver_wrapper": [["WR_boom"], ["WR_probe", ["a"]]]})
        self._run([["WR_boom"], ["WR_probe", ["b"]]])
        self.assertEqual(self.seen, ["b"])
        self.assertFalse(self.executor.fail_fast.enabled)

    def test_meta_can_turn_it_off_for_a_file(self):
        self.executor.set_fail_fast(True)
        self._run({"meta": {"fail_fast": False}, "webdriver_wrapper": [["WR_boom"], ["WR_probe", ["a"]]]})
        self.assertEqual(self.seen, ["a"])

    def test_command_takes_effect_from_the_next_list(self):
        self._run([["WR_set_fail_fast", [True]], ["WR_boom"], ["WR_probe", ["same list"]]])
        self._run([["WR_boom"], ["WR_probe", ["next list"]]])
        self.assertEqual(self.seen, ["same list"])

    def test_single_actions_are_never_skipped(self):
        self.executor.set_fail_fast(True)
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_one(["WR_boom"])
        self.assertEqual(self.executor.execute_one(["WR_probe", ["still runs"]]), "still runs")

    def test_nested_lists_belong_to_their_action(self):
        self.executor.set_fail_fast(True)
        self._run([
            ["WR_execute_action", [[["WR_boom"], ["WR_probe", ["inner"]]]]],
            ["WR_probe", ["outer"]],
        ])
        # The nested list is run by one action that did not fail, so nothing is skipped.
        self.assertEqual(self.seen, ["inner", "outer"])

    def test_a_failed_block_trips_it(self):
        self.executor.set_fail_fast(True)
        self._run([["WR_repeat", {"times": 1, "do": [["WR_boom"]]}], ["WR_probe", ["after"]]])
        self.assertEqual(self.seen, [])

    def test_try_block_failure_handled_does_not_trip(self):
        self.executor.set_fail_fast(True)
        self._run([["WR_try", {"do": [["WR_boom"]], "on_error": []}], ["WR_probe", ["after"]]])
        self.assertEqual(self.seen, ["after"])


class TestFailFastState(unittest.TestCase):

    def test_meta_setting(self):
        self.assertIsNone(fail_fast_setting({}))
        self.assertTrue(fail_fast_setting({"fail_fast": True}))
        with self.assertRaises(FlowError):
            fail_fast_setting({"fail_fast": "yes"})

    def test_teardown_count(self):
        self.assertEqual(teardown_count([["WR_quit"]]), 0)
        self.assertEqual(teardown_count({"meta": {"teardown": [["a"], ["b"]]}}), 2)
        self.assertEqual(teardown_count({"meta": {"skip": "later", "teardown": [["a"]]}}), 0)

    def test_threads_do_not_share_a_run(self):
        guard = FailFast()
        guard.enabled = True
        outcome = []

        def other_thread():
            with guard.run():
                with guard.step():
                    outcome.append("ran")

        with guard.run():
            with self.assertRaises(ValueError):
                with guard.step():
                    raise ValueError("boom")
            worker = threading.Thread(target=other_thread)
            worker.start()
            worker.join()
            with self.assertRaises(WebRunnerExecuteException):
                with guard.step():
                    outcome.append("must not run")
        self.assertEqual(outcome, ["ran"])


if __name__ == "__main__":
    unittest.main()
