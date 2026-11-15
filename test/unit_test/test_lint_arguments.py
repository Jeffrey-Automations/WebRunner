"""Linter rules that compare an action's arguments with its command's signature."""
import unittest
from unittest.mock import patch

from je_web_runner.utils.action_templates.templates import available_templates, get_template
from je_web_runner.utils.linter.action_linter import lint_action
from je_web_runner.utils.linter.argument_rules import argument_findings
from je_web_runner.utils.linter.flow_rules import flow_findings
from je_web_runner.utils.md_authoring import parse_markdown

_ARGUMENT_RULES = {"unknown_argument", "missing_argument", "too_many_arguments"}
# The templates WebRunner ships, read before any test registers one of its own.
_SHIPPED_TEMPLATES = tuple(available_templates())


def _open(url: str, timeout: float = 10.0, *, retries: int = 0) -> str:
    return f"{url} {timeout} {retries}"


def _anything(*args, **kwargs):
    return args, kwargs


def _rules(findings):
    return [(finding["rule"], finding["location"]) for finding in findings if finding["rule"] in _ARGUMENT_RULES]


class TestArgumentFindings(unittest.TestCase):

    def _check(self, action, command=_open):
        return [finding["rule"] for finding in argument_findings("action[0]", action, command)]

    def test_matching_arguments(self):
        for action in (["WR_open", {"url": "x"}], ["WR_open", ["x"]], ["WR_open", ["x", 5]],
                       ["WR_open", ["x"], {"timeout": 5, "retries": 1}], ["WR_open", {"url": "x", "retries": 2}]):
            with self.subTest(action=action):
                self.assertEqual(self._check(action), [])

    def test_unknown_keyword(self):
        findings = argument_findings("action[0]", ["WR_open", {"url": "x", "timout": 5}], _open)
        self.assertEqual([finding["rule"] for finding in findings], ["unknown_argument"])
        self.assertIn("'timout'", findings[0]["message"])
        self.assertIn("retries, timeout, url", findings[0]["message"])
        self.assertEqual(findings[0]["severity"], "warning")

    def test_missing_required_argument(self):
        self.assertEqual(self._check(["WR_open"]), ["missing_argument"])
        self.assertEqual(self._check(["WR_open", {"timeout": 5}]), ["missing_argument"])
        self.assertEqual(self._check(["WR_open", []]), ["missing_argument"])

    def test_too_many_positional_values(self):
        self.assertEqual(self._check(["WR_open", ["x", 5, "extra"]]), ["too_many_arguments"])

    def test_commands_that_accept_anything(self):
        self.assertEqual(self._check(["WR_any", {"whatever": 1}], _anything), [])
        self.assertEqual(self._check(["WR_any", [1, 2, 3, 4]], _anything), [])

    def test_commands_without_a_readable_signature_are_skipped(self):
        # Some builtins have no signature Python can read; which ones differs between versions.
        with patch("je_web_runner.utils.linter.argument_rules.inspect.signature", side_effect=ValueError("none")):
            self.assertEqual(self._check(["WR_open", ["x"], {"nonsense": 1}]), [])

    def test_bound_methods_do_not_count_self(self):
        class Wrapper:
            def to_url(self, url: str) -> str:
                return url

        self.assertEqual(self._check(["WR_to_url", {"url": "x"}], Wrapper().to_url), [])
        self.assertEqual(self._check(["WR_to_url", {"self": "x"}], Wrapper().to_url),
                         ["unknown_argument", "missing_argument"])


class TestThroughTheLinter(unittest.TestCase):

    def test_typo_in_a_real_command(self):
        findings = lint_action([["WR_to_url", {"ur": "${ENV.BASE}"}]])
        self.assertEqual(_rules(findings), [("unknown_argument", "action[0]"), ("missing_argument", "action[0]")])

    def test_nested_actions_and_hooks_are_checked(self):
        findings = lint_action({
            "meta": {"tags": ["x"], "setup": [["WR_set_var", {"nam": "a", "value": 1}]]},
            "webdriver_wrapper": [["WR_repeat", {"times": 1, "do": [["WR_sleep", {"second": 1}]]}]],
        })
        self.assertEqual(sorted(set(_rules(findings))), [
            ("missing_argument", "meta.setup[0]"),
            ("unknown_argument", "action[0].do[0]"),
            ("unknown_argument", "meta.setup[0]"),
        ])

    def test_block_commands_match_their_own_signatures(self):
        actions = [
            ["WR_if", {"condition": True, "then": [], "otherwise": []}],
            ["WR_for_each", {"items": [], "do": [], "var": "x", "index_var": "i"}],
            ["WR_repeat", {"times": 1, "do": [], "index_var": "i"}],
            ["WR_while", {"condition": False, "do": [], "max_iterations": 1}],
            ["WR_try", {"do": [], "on_error": [], "always": []}],
            ["WR_retry_block", {"do": [], "retries": 1, "backoff": 0}],
            ["WR_capture", {"name": "x", "action": ["WR_note"]}],
            ["WR_call_file", {"path": "x.json", "params": {}}],
            ["WR_assert_var", {"var": "x", "op": "eq", "value": 1}],
            ["WR_use_row", {"row": {}, "index": 0, "local": False}],
            ["WR_set_fail_fast", [True]],
        ]
        self.assertEqual(_rules(lint_action(actions)), [])

    def test_names_only_leave_the_argument_rules_out(self):
        findings = flow_findings([["WR_to_url", {"ur": "x"}]], known_commands=["WR_to_url"])
        self.assertEqual(_rules(findings), [])


class TestWhatWebRunnerEmits(unittest.TestCase):
    """The actions the authoring helpers produce must fit the commands they name."""

    def test_markdown_bullets(self):
        actions = parse_markdown("\n".join([
            "- open https://example.com", '- type "alice" into #user', "- click #submit", "- wait 2s",
            '- assert title "Welcome"', "- press Enter", "- screenshot", "- a bullet nothing matches", "- quit",
        ]))
        self.assertEqual(_rules(lint_action(actions)), [])

    def test_shipped_templates(self):
        for name in _SHIPPED_TEMPLATES:
            with self.subTest(template=name):
                self.assertEqual(_rules(lint_action(get_template(name).actions)), [])


if __name__ == "__main__":
    unittest.main()
