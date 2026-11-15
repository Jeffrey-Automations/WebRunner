"""Control-flow blocks of the action-file language, run through a real Executor."""
import unittest
from unittest.mock import patch

from je_web_runner.utils.exception.exceptions import WebRunnerAssertException, WebRunnerExecuteException
from je_web_runner.utils.executor._flow_commands import DEFERRED_EXPANSION, FLOW_COMMANDS
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.flow import FlowError, VariableStore
from je_web_runner.utils.flow.conditions import OPERATORS, compare, evaluate


def _never(_action):
    raise AssertionError("no action should run")


class TestConditions(unittest.TestCase):

    def setUp(self):
        self.store = VariableStore()
        self.store.set("count", 3)
        self.store.set("name", "alice")
        self.store.set("tags", ["smoke", "fast"])
        self.store.set("limit", 5)

    def _holds(self, condition, run_action=_never):
        return evaluate(condition, self.store, run_action)

    def test_comparisons(self):
        cases = [
            ({"var": "count", "op": "eq", "value": 3}, True),
            ({"var": "count", "op": "ne", "value": 3}, False),
            ({"var": "count", "op": "gt", "value": 2}, True),
            ({"var": "count", "op": "ge", "value": 3}, True),
            ({"var": "count", "op": "lt", "value": 3}, False),
            ({"var": "count", "op": "le", "value": 3}, True),
            ({"var": "tags", "op": "contains", "value": "smoke"}, True),
            ({"var": "name", "op": "contains", "value": "lic"}, True),
            ({"var": "name", "op": "in", "value": ["bob", "alice"]}, True),
            ({"var": "name", "op": "startswith", "value": "al"}, True),
            ({"var": "name", "op": "endswith", "value": "x"}, False),
            ({"var": "tags.0", "op": "eq", "value": "smoke"}, True),
        ]
        for condition, expected in cases:
            with self.subTest(condition=condition):
                self.assertIs(self._holds(condition), expected)

    def test_value_placeholders_are_expanded(self):
        self.assertTrue(self._holds({"var": "count", "op": "lt", "value": "${limit}"}))

    def test_presence_operators(self):
        self.store.set("empty", "")
        self.assertTrue(self._holds({"var": "count"}))
        self.assertTrue(self._holds({"var": "empty", "op": "exists"}))
        self.assertFalse(self._holds({"var": "empty"}))
        self.assertFalse(self._holds({"var": "missing", "op": "exists"}))
        self.assertFalse(self._holds({"var": "missing", "op": "truthy"}))
        self.assertTrue(self._holds({"var": "missing", "op": "falsy"}))

    def test_comparing_an_unset_variable_is_an_error(self):
        with self.assertRaises(FlowError):
            self._holds({"var": "missing", "op": "eq", "value": 1})

    def test_unknown_operator_and_uncomparable_values(self):
        with self.assertRaises(FlowError):
            self._holds({"var": "count", "op": "matches", "value": ".*"})
        with self.assertRaises(FlowError):
            self._holds({"var": "name", "op": "gt", "value": 1})

    def test_all_any_not(self):
        yes = {"var": "count", "op": "eq", "value": 3}
        no = {"var": "count", "op": "eq", "value": 4}
        self.assertTrue(self._holds({"all": [yes, yes]}))
        self.assertFalse(self._holds({"all": [yes, no]}))
        self.assertTrue(self._holds({"any": [no, yes]}))
        self.assertFalse(self._holds({"any": []}))
        self.assertTrue(self._holds({"not": no}))

    def test_all_and_any_stop_early(self):
        ran = []
        probe = {"succeeds": ["probe"]}
        no = {"var": "count", "op": "eq", "value": 4}
        yes = {"var": "count", "op": "eq", "value": 3}
        self.assertFalse(self._holds({"all": [no, probe]}, ran.append))
        self.assertTrue(self._holds({"any": [yes, probe]}, ran.append))
        self.assertEqual(ran, [])

    def test_succeeds(self):
        def run(action):
            if action == ["bad"]:
                raise ValueError("no")

        self.assertTrue(self._holds({"succeeds": ["good"]}, run))
        self.assertFalse(self._holds({"succeeds": ["bad"]}, run))

    def test_plain_values(self):
        self.store.set("flag", False)
        self.assertTrue(self._holds(True))
        self.assertFalse(self._holds(False))
        self.assertFalse(self._holds("${flag}"))
        self.assertTrue(self._holds("${count}"))

    def test_bad_shapes(self):
        for condition in ({}, {"var": "count", "not": True}, {"all": "x"}, {"var": 3}, {"equals": 1}):
            with self.subTest(condition=condition):
                with self.assertRaises(FlowError):
                    self._holds(condition)

    def test_operators_are_listed(self):
        self.assertIn("startswith", OPERATORS)
        self.assertTrue(compare(self.store, "count"))


class TestBlocks(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()
        self.seen = []
        self.executor.event_dict["WR_probe"] = self._probe
        self.executor.event_dict["WR_boom"] = self._boom
        self.failures_left = 0

    def _probe(self, value=None):
        self.seen.append(value)
        return value

    def _boom(self, message="boom"):
        raise ValueError(message)

    def _flaky(self):
        if self.failures_left:
            self.failures_left -= 1
            raise ValueError("not yet")
        return "ready"

    def _run(self, action):
        return self.executor.execute_one(action)

    def test_every_block_defers_expansion(self):
        blocks_with_actions = {"WR_if", "WR_for_each", "WR_repeat", "WR_while", "WR_try", "WR_retry_block"}
        self.assertLessEqual(blocks_with_actions, DEFERRED_EXPANSION)
        self.assertLessEqual(blocks_with_actions, set(FLOW_COMMANDS))

    def test_if_then_and_otherwise(self):
        self.executor.variables.set("n", 2)
        action = ["WR_if", {
            "condition": {"var": "n", "op": "gt", "value": 1},
            "then": [["WR_probe", ["then"]]],
            "otherwise": [["WR_probe", ["otherwise"]]],
        }]
        self.assertEqual(self._run(action), ["then"])
        self.executor.variables.set("n", 0)
        self.assertEqual(self._run(action), ["otherwise"])
        self.assertEqual(self.seen, ["then", "otherwise"])

    def test_if_without_a_branch_runs_nothing(self):
        self.assertEqual(self._run(["WR_if", {"condition": False, "then": [["WR_probe"]]}]), [])
        self.assertEqual(self.seen, [])

    def test_if_condition_can_be_an_action(self):
        self._run(["WR_if", {"condition": {"succeeds": ["WR_boom"]},
                             "then": [["WR_probe", ["ok"]]], "otherwise": [["WR_probe", ["failed"]]]}])
        self.assertEqual(self.seen, ["failed"])

    def test_for_each_sets_the_item_and_index(self):
        self.executor.variables.set("users", ["alice", "bob"])
        rounds = self._run(["WR_for_each", {
            "items": "${users}", "var": "user", "index_var": "i",
            "do": [["WR_probe", ["${i}:${user}"]]],
        }])
        self.assertEqual(rounds, 2)
        self.assertEqual(self.seen, ["0:alice", "1:bob"])
        self.assertFalse(self.executor.variables.has("user"))
        self.assertFalse(self.executor.variables.has("i"))

    def test_for_each_default_variable_and_literal_items(self):
        self._run(["WR_for_each", {"items": [1, 2, 3], "do": [["WR_probe", ["${item}"]]]}])
        self.assertEqual(self.seen, [1, 2, 3])

    def test_for_each_needs_a_list(self):
        with self.assertRaises(WebRunnerExecuteException):
            self._run(["WR_for_each", {"items": "abc", "do": []}])

    def test_nested_loops(self):
        self._run(["WR_for_each", {"items": ["a", "b"], "var": "outer", "do": [
            ["WR_repeat", {"times": 2, "index_var": "n", "do": [["WR_probe", ["${outer}${n}"]]]}],
        ]}])
        self.assertEqual(self.seen, ["a0", "a1", "b0", "b1"])

    def test_values_set_inside_a_loop_are_read_at_run_time(self):
        self._run(["WR_set_var", ["total", 0]])
        self._run(["WR_for_each", {"items": [1, 2, 3], "do": [
            ["WR_capture", {"name": "total", "action": ["sum", [["${total}", "${item}"]]]}],
        ]}])
        self.assertEqual(self.executor.variables.get("total"), 6)

    def test_repeat_counts_and_limits(self):
        self.assertEqual(self._run(["WR_repeat", {"times": 3, "do": [["WR_probe"]]}]), 3)
        self.assertEqual(len(self.seen), 3)
        for times in (-1, 1.5, "x", True, 10 ** 9):
            with self.subTest(times=times):
                with self.assertRaises(WebRunnerExecuteException):
                    self._run(["WR_repeat", {"times": times, "do": []}])

    def test_while_runs_until_the_condition_fails(self):
        self._run(["WR_set_var", ["n", 0]])
        rounds = self._run(["WR_while", {
            "condition": {"var": "n", "op": "lt", "value": 3},
            "max_iterations": 10,
            "do": [["WR_capture", {"name": "n", "action": ["sum", [["${n}", 1]]]}]],
        }])
        self.assertEqual(rounds, 3)

    def test_while_fails_at_its_limit(self):
        with self.assertRaises(WebRunnerExecuteException) as raised:
            self._run(["WR_while", {"condition": True, "max_iterations": 4, "do": [["WR_probe"]]}])
        self.assertIn("4 rounds", str(raised.exception))
        self.assertEqual(len(self.seen), 4)

    def test_while_requires_a_limit(self):
        with self.assertRaises(WebRunnerExecuteException):
            self._run(["WR_while", {"condition": True, "do": []}])

    def test_a_failing_action_fails_its_block_and_stops_it(self):
        with self.assertRaises(WebRunnerExecuteException):
            self._run(["WR_repeat", {"times": 2, "do": [["WR_probe", [1]], ["WR_boom"], ["WR_probe", [2]]]}])
        self.assertEqual(self.seen, [1])

    def test_try_on_error_swallows_the_failure(self):
        outcome = self._run(["WR_try", {
            "do": [["WR_boom", ["broken"]], ["WR_probe", ["skipped"]]],
            "on_error": [["WR_probe", ["${error}"]]],
            "always": [["WR_probe", ["always"]]],
        }])
        self.assertTrue(outcome["failed"])
        self.assertIn("broken", outcome["error"])
        self.assertIn("broken", self.seen[0])
        self.assertEqual(self.seen[1], "always")
        self.assertFalse(self.executor.variables.has("error"))

    def test_try_without_on_error_still_fails_after_always(self):
        with self.assertRaises(WebRunnerExecuteException):
            self._run(["WR_try", {"do": [["WR_boom"]], "always": [["WR_probe", ["always"]]]}])
        self.assertEqual(self.seen, ["always"])

    def test_try_success(self):
        outcome = self._run(["WR_try", {"do": [["WR_probe", [1]]], "on_error": [["WR_probe", ["no"]]]}])
        self.assertEqual(outcome, {"failed": False, "error": None})
        self.assertEqual(self.seen, [1])

    def test_retry_block_reruns_from_the_start(self):
        self.executor.event_dict["WR_flaky"] = self._flaky
        self.failures_left = 2
        with patch("je_web_runner.utils.flow.blocks.time.sleep") as sleep:
            attempts = self._run(["WR_retry_block", {
                "retries": 3, "backoff": 0.5, "do": [["WR_probe", ["start"]], ["WR_flaky"]],
            }])
        self.assertEqual(attempts, 3)
        self.assertEqual(self.seen, ["start", "start", "start"])
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])

    def test_retry_block_gives_up(self):
        with patch("je_web_runner.utils.flow.blocks.time.sleep"):
            with self.assertRaises(WebRunnerExecuteException):
                self._run(["WR_retry_block", {"retries": 1, "do": [["WR_boom"]]}])

    def test_fail_and_assert_var(self):
        with self.assertRaises(WebRunnerExecuteException) as raised:
            self._run(["WR_fail", {"message": "stop here"}])
        self.assertIn("stop here", str(raised.exception))
        self.executor.variables.set("status", 200)
        self.assertTrue(self._run(["WR_assert_var", {"var": "status", "op": "eq", "value": 200}]))
        with self.assertRaises(WebRunnerExecuteException) as raised:
            self._run(["WR_assert_var", {"var": "status", "op": "eq", "value": 404}])
        self.assertIsInstance(raised.exception.__cause__, WebRunnerAssertException)
        self.assertIn("variable status is 200; expected eq 404", str(raised.exception))

    def test_assert_var_message_shows_the_expanded_value_and_unset_variables(self):
        self.executor.variables.set("name", "Grace")
        self.executor.variables.set("greeting", "Hello Ada")
        with self.assertRaises(WebRunnerExecuteException) as raised:
            self._run(["WR_assert_var", {"var": "greeting", "op": "eq", "value": "Hello ${name}"}])
        self.assertIn("variable greeting is 'Hello Ada'; expected eq 'Hello Grace'", str(raised.exception))
        with self.assertRaises(WebRunnerExecuteException) as raised:
            self._run(["WR_assert_var", {"var": "missing"}])
        self.assertIn("variable missing is not set; expected truthy", str(raised.exception))

    def test_gates_apply_inside_blocks(self):
        with self.executor.restricted({"WR_probe"}):
            with self.assertRaises(WebRunnerExecuteException):
                self._run(["WR_if", {"condition": True, "then": [["WR_probe"]]}])
            self.assertEqual(self.seen, [])
        self.executor.set_allow_arbitrary_script(False)
        with self.assertRaises(WebRunnerExecuteException):
            self._run(["WR_repeat", {"times": 1, "do": [["WR_execute_script", {"script": "1"}]]}])

    def test_a_block_must_be_a_list_of_actions(self):
        for block in ("WR_probe", [["WR_probe"], "WR_probe"], [[]]):
            with self.subTest(block=block):
                with self.assertRaises(WebRunnerExecuteException):
                    self._run(["WR_repeat", {"times": 1, "do": block}])

    def test_a_failed_block_is_one_failed_record(self):
        with patch("builtins.print"):
            records, failed = self.executor.collect_action_results([
                ["WR_repeat", {"times": 1, "do": [["WR_boom"]]}],
                ["WR_probe", ["after"]],
            ])
        self.assertEqual(len(failed), 1)
        self.assertEqual(len(records), 2)
        self.assertEqual(self.seen, ["after"])


if __name__ == "__main__":
    unittest.main()
