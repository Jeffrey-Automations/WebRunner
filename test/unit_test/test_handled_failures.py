"""A failure the action list handled on purpose is not a failure in the records."""
import threading
import unittest
from unittest.mock import patch

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.test_record.test_record_class import (
    mark_handled,
    record_action_to_list,
    test_record_instance,
    track_records,
)


class _Recording(unittest.TestCase):
    """Recording on, an empty record list, both restored afterwards."""

    def setUp(self):
        self.addCleanup(test_record_instance.set_record_enable, test_record_instance.init_record)
        previous = test_record_instance.test_record_list
        self.addCleanup(setattr, test_record_instance, "test_record_list", previous)
        test_record_instance.test_record_list = []
        test_record_instance.set_record_enable(True)

    @staticmethod
    def _failures():
        return [record for record in test_record_instance.test_record_list
                if record["program_exception"] != "None"]


class TestTracking(_Recording):

    def test_tracks_what_the_block_records(self):
        record_action_to_list("before", None)
        with track_records() as outer:
            record_action_to_list("first", None)
            with track_records() as inner:
                record_action_to_list("second", None, ValueError("boom"))
            record_action_to_list("third", None)
        record_action_to_list("after", None)
        self.assertEqual([record["function_name"] for record in outer], ["first", "second", "third"])
        self.assertEqual([record["function_name"] for record in inner], ["second"])
        self.assertEqual(len(test_record_instance.test_record_list), 5)

    def test_mark_handled_moves_the_error_text(self):
        with track_records() as records:
            record_action_to_list("ok", None)
            record_action_to_list("failed", {"a": 1}, ValueError("boom"))
        self.assertEqual(mark_handled(records), 1)
        self.assertEqual(self._failures(), [])
        failed = test_record_instance.test_record_list[1]
        self.assertIn("boom", failed["handled_exception"])
        self.assertNotIn("handled_exception", test_record_instance.test_record_list[0])

    def test_nothing_is_tracked_while_recording_is_off(self):
        test_record_instance.set_record_enable(False)
        with track_records() as records:
            record_action_to_list("unrecorded", None, ValueError("boom"))
        self.assertEqual(records, [])

    def test_other_threads_are_not_tracked(self):
        with track_records() as records:
            worker = threading.Thread(target=record_action_to_list, args=("elsewhere", None, ValueError("x")))
            worker.start()
            worker.join()
        self.assertEqual(records, [])
        self.assertEqual(len(self._failures()), 1)


class TestHandledByTheActionList(_Recording):

    def setUp(self):
        super().setUp()
        self.executor = Executor()
        self.executor.event_dict["WR_wrapper_fails"] = self._wrapper_fails
        self.executor.event_dict["WR_flaky_wrapper"] = self._flaky_wrapper
        self.failures_left = 0

    @staticmethod
    def _wrapper_fails():
        """What a Selenium wrapper call does: record its error, then raise it."""
        error = ValueError("no such element")
        record_action_to_list("webdriver wrapper find", {"selector": "#x"}, error)
        raise error

    def _flaky_wrapper(self):
        if self.failures_left:
            self.failures_left -= 1
            self._wrapper_fails()
        record_action_to_list("webdriver wrapper find", {"selector": "#x"}, None)
        return "found"

    def test_succeeds_condition(self):
        self.executor.execute_one(["WR_if", {"condition": {"succeeds": ["WR_wrapper_fails"]}, "then": []}])
        self.assertEqual(self._failures(), [])
        self.assertEqual(len(test_record_instance.test_record_list), 1)

    def test_try_with_on_error(self):
        self.executor.execute_one(["WR_try", {"do": [["WR_wrapper_fails"]], "on_error": []}])
        self.assertEqual(self._failures(), [])

    def test_try_without_on_error_stays_a_failure(self):
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_one(["WR_try", {"do": [["WR_wrapper_fails"]], "always": []}])
        self.assertEqual(len(self._failures()), 1)

    def test_retry_block_that_recovers(self):
        self.failures_left = 2
        with patch("je_web_runner.utils.flow.blocks.time.sleep"):
            self.executor.execute_one(["WR_retry_block", {"retries": 2, "do": [["WR_flaky_wrapper"]]}])
        self.assertEqual(self._failures(), [])
        self.assertEqual(len(test_record_instance.test_record_list), 3)

    def test_retry_block_that_gives_up_keeps_its_last_failure(self):
        with patch("je_web_runner.utils.flow.blocks.time.sleep"):
            with self.assertRaises(WebRunnerExecuteException):
                self.executor.execute_one(["WR_retry_block", {"retries": 1, "do": [["WR_wrapper_fails"]]}])
        self.assertEqual(len(self._failures()), 1)
        self.assertEqual(len(test_record_instance.test_record_list), 2)

    def test_retry_policy_that_recovers(self):
        self.failures_left = 1
        self.executor.set_retry_policy(retries=2)
        self.assertEqual(self.executor.execute_one(["WR_flaky_wrapper"]), "found")
        self.assertEqual(self._failures(), [])

    def test_retry_policy_that_gives_up_keeps_its_last_failure(self):
        self.executor.set_retry_policy(retries=1)
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_one(["WR_wrapper_fails"])
        self.assertEqual(len(self._failures()), 1)

    def test_an_unhandled_failure_is_still_a_failure(self):
        with patch("builtins.print"):
            _records, failed = self.executor.collect_action_results([["WR_wrapper_fails"]])
        self.assertEqual(len(failed), 1)
        self.assertEqual(len(self._failures()), 1)


if __name__ == "__main__":
    unittest.main()
