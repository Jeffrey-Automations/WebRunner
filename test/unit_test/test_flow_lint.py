"""The linter and the validator read the actions inside blocks and know the language rules."""
import unittest

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.flow.structure import defined_variables, misshapen_blocks, nested_actions
from je_web_runner.utils.json.json_validator import validate_action_json
from je_web_runner.utils.linter.action_linter import lint_action
from je_web_runner.utils.linter.flow_rules import every_action, flow_findings


def _rules(findings, rule):
    return [finding for finding in findings if finding["rule"] == rule]


class TestStructure(unittest.TestCase):

    def test_nested_actions_of_each_block(self):
        action = ["WR_try", {"do": [["a"], ["b"]], "on_error": [["c"]], "always": [["d"]]}]
        self.assertEqual(list(nested_actions(action, "action[0]")), [
            ("action[0].do[0]", ["a"]), ("action[0].do[1]", ["b"]),
            ("action[0].on_error[0]", ["c"]), ("action[0].always[0]", ["d"]),
        ])

    def test_capture_and_conditions(self):
        self.assertEqual(list(nested_actions(["WR_capture", {"name": "x", "action": ["a"]}], "p")),
                         [("p.action", ["a"])])
        condition = {"all": [{"succeeds": ["a"]}, {"not": {"any": [{"succeeds": ["b"]}]}}]}
        found = list(nested_actions(["WR_if", {"condition": condition, "then": [["c"]]}], "p"))
        self.assertEqual(found, [
            ("p.then[0]", ["c"]),
            ("p.condition.all[0].succeeds", ["a"]),
            ("p.condition.all[1].not.any[0].succeeds", ["b"]),
        ])

    def test_three_element_actions_and_plain_commands(self):
        self.assertEqual(list(nested_actions(["WR_repeat", [], {"times": 1, "do": [["a"]]}], "p")),
                         [("p.do[0]", ["a"])])
        self.assertEqual(list(nested_actions(["WR_to_url", {"url": "x"}], "p")), [])
        self.assertEqual(list(nested_actions("not an action", "p")), [])

    def test_misshapen_blocks(self):
        self.assertEqual(misshapen_blocks(["WR_if", {"condition": True, "then": "WR_quit", "otherwise": [["a"]]}]),
                         ["then"])
        self.assertEqual(misshapen_blocks(["WR_if", {"condition": True}]), [])

    def test_defined_variables(self):
        cases = [
            (["WR_set_var", {"name": "a", "value": 1}], ["a"]),
            (["WR_set_var", ["b", 1]], ["b"]),
            (["WR_capture", {"name": "c", "action": ["x"]}], ["c"]),
            (["WR_for_each", {"items": [], "do": []}], ["item"]),
            (["WR_for_each", {"items": [], "var": "row", "index_var": "i", "do": []}], ["row", "i"]),
            (["WR_repeat", {"times": 1, "index_var": "n", "do": []}], ["n"]),
            (["WR_try", {"do": [], "on_error": []}], ["error"]),
            (["WR_call_file", {"path": "x.json", "params": {"user": 1}}], ["user"]),
            (["WR_to_url", {"url": "x"}], []),
        ]
        for action, expected in cases:
            with self.subTest(action=action):
                self.assertEqual(defined_variables(action), expected)

    def test_every_action_walks_all_levels(self):
        actions = [["WR_for_each", {"items": [], "do": [["WR_if", {"condition": True, "then": [["WR_quit"]]}]]}]]
        self.assertEqual([location for location, _action in every_action(actions)],
                         ["action[0]", "action[0].do[0]", "action[0].do[0].then[0]"])


class TestLanguageRules(unittest.TestCase):

    def test_unknown_command_at_any_depth(self):
        findings = lint_action([
            ["WR_no_such", {}],
            ["WR_repeat", {"times": 1, "do": [["WR_also_missing"]]}],
        ])
        unknown = _rules(findings, "unknown_command")
        self.assertEqual([finding["location"] for finding in unknown], ["action[0]", "action[1].do[0]"])
        self.assertTrue(all(finding["severity"] == "warning" for finding in unknown))

    def test_registered_commands_and_builtins_are_known(self):
        findings = lint_action([["WR_to_url", {"url": "${ENV.BASE}"}], ["print", ["x"]], ["WR_set_var", ["a", 1]]])
        self.assertEqual(_rules(findings, "unknown_command"), [])

    def test_unknown_command_rule_needs_the_command_list(self):
        self.assertEqual(flow_findings([["WR_no_such"]]), [])
        self.assertEqual(len(flow_findings([["WR_no_such"]], known_commands=["WR_other"])), 1)

    def test_while_without_limit(self):
        findings = lint_action([["WR_while", {"condition": True, "do": []}]])
        self.assertEqual(len(_rules(findings, "while_without_limit")), 1)
        findings = lint_action([["WR_while", {"condition": True, "do": [], "max_iterations": 3}]])
        self.assertEqual(_rules(findings, "while_without_limit"), [])

    def test_block_shape(self):
        findings = lint_action([["WR_if", {"condition": True, "then": "WR_quit_all"}]])
        self.assertEqual([finding["location"] for finding in _rules(findings, "block_shape")], ["action[0]"])

    def test_undefined_variable_is_information(self):
        findings = lint_action([
            ["WR_set_var", {"name": "base", "value": "https://example.test"}],
            ["WR_to_url", {"url": "${base}/${page}"}],
        ])
        undefined = _rules(findings, "undefined_variable")
        self.assertEqual([(finding["severity"], finding["location"]) for finding in undefined],
                         [("info", "action[1]")])
        self.assertIn("${page}", undefined[0]["message"])

    def test_variables_defined_anywhere_in_the_file_count(self):
        findings = lint_action({
            "meta": {"tags": ["x"], "vars": {"base": "b"}, "setup": [["WR_set_var", ["token", "t"]]]},
            "webdriver_wrapper": [
                ["WR_for_each", {"items": [1], "var": "row", "do": [
                    ["WR_capture", {"name": "seen", "action": ["len", ["${row}"]]}],
                ]}],
                ["WR_try", {"do": [], "on_error": [["WR_note", {"text": "${error} ${seen} ${base} ${token}"}]]}],
                ["WR_note", {"text": "${ENV.HOME} ${ROW.col}"}],
            ],
        })
        self.assertEqual(_rules(findings, "undefined_variable"), [])

    def test_script_arguments_are_not_read_for_placeholders(self):
        findings = lint_action([["WR_execute_script", {"script": "return `hello ${name}`"}]])
        self.assertEqual(_rules(findings, "undefined_variable"), [])

    def test_name_rules_reach_nested_actions_and_hooks(self):
        findings = lint_action({
            "meta": {"tags": ["x"], "teardown": [["WR_quit"]]},
            "webdriver_wrapper": [["WR_repeat", {"times": 1, "do": [["WR_execute_script", {"script": "1"}]]}]],
        })
        self.assertEqual([finding["location"] for finding in _rules(findings, "arbitrary_script")],
                         ["action[0].do[0]"])
        self.assertEqual([finding["location"] for finding in _rules(findings, "legacy_name")],
                         ["meta.teardown[0]"])

    def test_top_level_actions_are_not_reported_twice(self):
        findings = lint_action([["WR_quit"]])
        self.assertEqual(len(_rules(findings, "legacy_name")), 1)

    def test_nested_urls_are_reported_once(self):
        findings = lint_action([["WR_repeat", {"times": 1, "do": [["WR_to_url", {"url": "https://x.test/a"}]]}]])
        self.assertEqual(len(_rules(findings, "hardcoded_url")), 1)


class TestValidator(unittest.TestCase):

    def test_valid_nested_document(self):
        self.assertTrue(validate_action_json({
            "meta": {"setup": [["WR_note"]], "teardown": [["WR_quit_all"]]},
            "webdriver_wrapper": [
                ["WR_if", {"condition": {"succeeds": ["WR_note"]}, "then": [["WR_repeat", {"times": 1, "do": []}]]}],
            ],
        }))

    def test_bad_nested_actions_are_refused(self):
        documents = [
            [["WR_repeat", {"times": 1, "do": ["WR_quit"]}]],
            [["WR_repeat", {"times": 1, "do": "WR_quit"}]],
            [["WR_if", {"condition": True, "then": [["WR_try", {"do": [[]]}]]}]],
            [["WR_capture", {"name": "x", "action": "WR_quit"}]],
            [["WR_if", {"condition": {"succeeds": ["a", "b", "c", "d"]}}]],
            {"meta": {"setup": "WR_note"}, "webdriver_wrapper": [["WR_note"]]},
            {"meta": {"teardown": [["WR_note", 3]]}, "webdriver_wrapper": [["WR_note"]]},
        ]
        for document in documents:
            with self.subTest(document=document):
                with self.assertRaises(WebRunnerExecuteException):
                    validate_action_json(document)

    def test_error_names_the_nested_action(self):
        with self.assertRaises(WebRunnerExecuteException) as raised:
            validate_action_json([["WR_note"], ["WR_repeat", {"times": 1, "do": [["WR_note"], "oops"]}]])
        self.assertIn("1.do[1]", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
