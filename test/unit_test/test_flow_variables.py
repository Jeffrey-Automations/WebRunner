import os
import unittest
from unittest.mock import patch

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor._flow_commands import DEFERRED_EXPANSION
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.flow import FlowError, VariableStore, is_missing


class TestVariableStore(unittest.TestCase):

    def setUp(self):
        self.store = VariableStore()

    def test_set_get_unset(self):
        self.assertEqual(self.store.set("user", "alice"), "alice")
        self.assertTrue(self.store.has("user"))
        self.assertEqual(self.store.get("user"), "alice")
        self.assertTrue(self.store.unset("user"))
        self.assertFalse(self.store.unset("user"))
        self.assertEqual(self.store.get("user", "nobody"), "nobody")

    def test_names_are_sorted_and_clear_removes_them(self):
        self.store.set("b", 1)
        self.store.set("a", 2)
        self.assertEqual(self.store.names(), ["a", "b"])
        self.store.clear()
        self.assertEqual(self.store.names(), [])

    def test_bad_names_are_refused(self):
        for name in ("", "1st", "a-b", "a.b", None, 3):
            with self.subTest(name=name):
                with self.assertRaises(FlowError):
                    self.store.set(name, 1)

    def test_reserved_namespaces_are_refused(self):
        for name in ("ENV", "ROW"):
            with self.subTest(name=name):
                with self.assertRaises(FlowError):
                    self.store.set(name, 1)

    def test_scope_names_end_with_the_block(self):
        self.store.set("outer", 1)
        with self.store.scope({"item": "x"}):
            self.assertEqual(self.store.get("item"), "x")
            self.store.set("item", "y")
            self.store.set("outer", 2)
            self.store.set("made_inside", 3)
            self.assertEqual(self.store.get("item"), "y")
        self.assertFalse(self.store.has("item"))
        self.assertEqual(self.store.get("outer"), 2)
        self.assertEqual(self.store.get("made_inside"), 3)

    def test_scope_ends_when_the_block_raises(self):
        with self.assertRaises(ValueError):
            with self.store.scope({"item": 1}):
                raise ValueError("boom")
        self.assertFalse(self.store.has("item"))


class TestExpand(unittest.TestCase):

    def setUp(self):
        self.store = VariableStore()
        self.store.set("count", 3)
        self.store.set("user", {"name": "alice", "emails": ["a@example.test", "b@example.test"]})

    def test_whole_placeholder_keeps_the_type(self):
        self.assertEqual(self.store.expand("${count}"), 3)
        self.assertEqual(self.store.expand("${user.emails}"), ["a@example.test", "b@example.test"])

    def test_placeholder_inside_text_is_inserted_as_text(self):
        self.assertEqual(self.store.expand("n=${count}, ${user.name}"), "n=3, alice")

    def test_paths_into_dicts_and_lists(self):
        self.assertEqual(self.store.expand("${user.emails.1}"), "b@example.test")

    def test_containers_are_walked(self):
        data = {"a": ["${count}", ("${user.name}", 1)], "b": {"c": "${count}"}, "d": 7}
        self.assertEqual(self.store.expand(data), {"a": [3, ("alice", 1)], "b": {"c": 3}, "d": 7})

    def test_expand_does_not_change_its_input(self):
        data = {"a": ["${count}"]}
        self.store.expand(data)
        self.assertEqual(data, {"a": ["${count}"]})

    def test_unknown_placeholders_stay(self):
        text = "`hello ${name}` and ${ROW.col} and ${ROW}"
        self.assertEqual(self.store.expand(text), text)
        self.assertEqual(self.store.expand("${nothing}"), "${nothing}")

    def test_known_variable_with_a_missing_path_is_an_error(self):
        for placeholder in ("${user.age}", "${user.emails.5}", "${user.emails.first}", "${count.x}"):
            with self.subTest(placeholder=placeholder):
                with self.assertRaises(FlowError):
                    self.store.expand(placeholder)

    def test_environment_variables(self):
        with patch.dict(os.environ, {"WR_FLOW_TEST": "from-env"}):
            self.assertEqual(self.store.expand("${ENV.WR_FLOW_TEST}/x"), "from-env/x")
        self.assertEqual(self.store.expand("${ENV.WR_FLOW_TEST_UNSET}"), "${ENV.WR_FLOW_TEST_UNSET}")
        self.assertEqual(self.store.expand("${ENV.A.B}"), "${ENV.A.B}")

    def test_resolve_reports_unknown_names(self):
        self.assertTrue(is_missing(self.store.resolve("nothing")))
        self.assertFalse(is_missing(self.store.resolve("count")))

    def test_none_is_a_value(self):
        self.store.set("empty", None)
        self.assertIsNone(self.store.expand("${empty}"))
        self.assertEqual(self.store.expand("[${empty}]"), "[None]")


class TestExecutorVariables(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()
        self.seen = []
        self.executor.event_dict["WR_probe"] = lambda *args, **kwargs: self.seen.append((args, kwargs)) or "probed"

    def test_kwargs_are_expanded_before_the_command(self):
        self.executor.execute_one(["WR_set_var", {"name": "url", "value": "https://example.test"}])
        self.executor.execute_one(["WR_probe", {"url": "${url}/login"}])
        self.assertEqual(self.seen, [((), {"url": "https://example.test/login"})])

    def test_positional_and_keyword_arguments_are_expanded(self):
        self.executor.variables.set("n", 2)
        self.executor.execute_one(["WR_probe", ["${n}", "x${n}"], {"k": "${n}"}])
        self.assertEqual(self.seen, [((2, "x2"), {"k": 2})])

    def test_record_keys_keep_the_action_as_written(self):
        self.executor.variables.set("secret", "hunter2")
        with patch("builtins.print"):
            records = self.executor.execute_action([["WR_probe", {"password": "${secret}"}]])
        self.assertEqual(list(records), ["execute: ['WR_probe', {'password': '${secret}'}]"])
        self.assertEqual(self.seen, [((), {"password": "hunter2"})])

    def test_command_name_is_not_expanded(self):
        self.executor.variables.set("command", "WR_probe")
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_one(["${command}", {"a": 1}])
        self.assertEqual(self.seen, [])

    def test_capture_stores_the_result(self):
        result = self.executor.execute_one(["WR_capture", {"name": "largest", "action": ["max", [[1, 5, 2]]]}])
        self.assertEqual(result, 5)
        self.assertEqual(self.executor.execute_one(["WR_get_var", ["largest"]]), 5)

    def test_capture_expands_its_action_when_it_runs(self):
        self.executor.variables.set("values", [4, 9])
        self.executor.execute_one(["WR_capture", {"name": "largest", "action": ["max", ["${values}"]]}])
        self.assertEqual(self.executor.variables.get("largest"), 9)

    def test_failed_capture_leaves_the_variable(self):
        self.executor.variables.set("kept", "before")
        with self.assertRaises(WebRunnerExecuteException):
            self.executor.execute_one(["WR_capture", {"name": "kept", "action": ["WR_no_such_command"]}])
        self.assertEqual(self.executor.variables.get("kept"), "before")

    def test_nested_action_lists_are_expanded_when_they_run(self):
        self.assertIn("WR_execute_action", DEFERRED_EXPANSION)
        with patch("builtins.print"):
            self.executor.execute_action([["WR_execute_action", [[
                ["WR_set_var", {"name": "step", "value": "late"}],
                ["WR_probe", {"value": "${step}"}],
            ]]]])
        self.assertEqual(self.seen, [((), {"value": "late"})])

    def test_unset_clear_and_list(self):
        self.executor.execute_one(["WR_set_var", ["a", 1]])
        self.executor.execute_one(["WR_set_var", ["b", 2]])
        self.assertEqual(self.executor.execute_one(["WR_list_vars"]), ["a", "b"])
        self.assertTrue(self.executor.execute_one(["WR_unset_var", ["a"]]))
        self.executor.execute_one(["WR_clear_vars"])
        self.assertEqual(self.executor.execute_one(["WR_list_vars"]), [])

    def test_restricted_commands_stay_refused_inside_capture(self):
        with self.executor.restricted({"WR_probe"}):
            with self.assertRaises(WebRunnerExecuteException):
                self.executor.execute_one(["WR_capture", {"name": "x", "action": ["WR_probe"]}])
        self.assertEqual(self.seen, [])

    def test_each_executor_has_its_own_variables(self):
        other = Executor()
        self.executor.variables.set("mine", 1)
        self.assertFalse(other.variables.has("mine"))


if __name__ == "__main__":
    unittest.main()
