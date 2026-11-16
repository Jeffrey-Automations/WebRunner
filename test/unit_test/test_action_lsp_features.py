"""Hover, position-aware completion, formatting, quick fixes and nested diagnostic lines of the action LSP.

``|`` marks the cursor in the test texts.
"""
import json
import unittest

from je_web_runner.action_lsp._commands import hover_markdown, parameters, single_replacement
from je_web_runner.action_lsp._completion import document_variables
from je_web_runner.action_lsp._text import offset_at
from je_web_runner.action_lsp.server import ActionLspServer
from je_web_runner.utils.action_formatter.formatter import format_text

_URI = "file:///actions.json"


# pylint: disable-next=keyword-arg-before-vararg,unused-argument  # only its signature and docstring are read
def _sample_command(url: str, timeout: int = 5, *extra: str, flag: bool = False, **more: str) -> None:
    """Go somewhere.

    Second paragraph.
    """


def _opened(text):
    server = ActionLspServer()
    notification = server.handle({
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": _URI, "text": text}},
    })
    return server, notification["params"]["diagnostics"]


def _at_cursor(marked, method, server=None):
    """The result of ``method`` with the cursor where ``|`` is in ``marked``."""
    offset = marked.index("|")
    text = marked.replace("|", "", 1)
    if server is None:
        server, _diagnostics = _opened(text)
    else:
        server.handle({"method": "textDocument/didChange", "params": {
            "textDocument": {"uri": _URI, "version": 2}, "contentChanges": [{"text": text}]}})
    position = {"line": text.count("\n", 0, offset), "character": offset - (text.rfind("\n", 0, offset) + 1)}
    response = server.handle({"id": 7, "method": method,
                              "params": {"textDocument": {"uri": _URI}, "position": position}})
    return response["result"]


def _labels(marked, server=None):
    return [item["label"] for item in _at_cursor(marked, "textDocument/completion", server)["items"]]


def _apply(text, edits):
    """``text`` after the LSP text edits, applied from the last one to the first."""
    ordered = sorted(edits, key=lambda edit: (edit["range"]["start"]["line"], edit["range"]["start"]["character"]),
                     reverse=True)
    for edit in ordered:
        start = offset_at(text, edit["range"]["start"]["line"], edit["range"]["start"]["character"])
        end = offset_at(text, edit["range"]["end"]["line"], edit["range"]["end"]["character"])
        text = text[:start] + edit["newText"] + text[end:]
    return text


class TestCapabilities(unittest.TestCase):

    def test_initialize_advertises_every_feature(self):
        capabilities = ActionLspServer().handle({"id": 1, "method": "initialize"})["result"]["capabilities"]
        self.assertIs(capabilities["hoverProvider"], True)
        self.assertIs(capabilities["documentFormattingProvider"], True)
        self.assertEqual(capabilities["codeActionProvider"], {"codeActionKinds": ["quickfix"]})
        self.assertIn("{", capabilities["completionProvider"]["triggerCharacters"])
        self.assertEqual(capabilities["textDocumentSync"], 1)


class TestCommandDescriptions(unittest.TestCase):

    def test_parameters_an_action_can_name(self):
        self.assertEqual(parameters(_sample_command),
                         {"url": "url: str", "timeout": "timeout: int = 5", "flag": "flag: bool = False"})

    def test_parameters_of_something_without_a_signature(self):
        self.assertEqual(parameters(12), {})

    def test_hover_markdown(self):
        markdown = hover_markdown("WR_sample", _sample_command)
        self.assertTrue(markdown.startswith(
            "```python\nWR_sample(url: str, timeout: int = 5, *extra: str, flag: bool = False, **more: str)"
            " -> None\n```\n\nGo somewhere."))
        self.assertIn("Second paragraph.", markdown)

    def test_hover_markdown_names_the_modern_command(self):
        self.assertIn("prefer `WR_quit_all`", hover_markdown("WR_quit", _sample_command))

    def test_hover_markdown_without_signature_or_docstring(self):
        self.assertEqual(hover_markdown("WR_odd", object.__new__(type("Bare", (), {}))),
                         "```python\nWR_odd(...)\n```")

    def test_single_replacement(self):
        self.assertEqual(single_replacement("WR_quit"), "WR_quit_all")
        self.assertIsNone(single_replacement("WR_element_get_select"))
        self.assertIsNone(single_replacement("WR_to_url"))


class TestHover(unittest.TestCase):

    def test_on_a_command_name(self):
        result = _at_cursor('[\n  ["WR_to|_url", {"url": "x"}]\n]', "textDocument/hover")
        self.assertEqual(result["contents"]["kind"], "markdown")
        self.assertIn("```python\nWR_to_url(url: str)", result["contents"]["value"])
        self.assertIn("Navigate to a given URL", result["contents"]["value"])
        self.assertEqual(result["range"], {"start": {"line": 1, "character": 3},
                                           "end": {"line": 1, "character": 14}})

    def test_on_the_quotes_of_a_command_name(self):
        self.assertIsNotNone(_at_cursor('[[|"WR_to_url"]]', "textDocument/hover"))
        self.assertIsNotNone(_at_cursor('[["WR_to_url|"]]', "textDocument/hover"))
        self.assertIsNone(_at_cursor('[["WR_to_url"|]]', "textDocument/hover"))

    def test_on_a_nested_command_name(self):
        result = _at_cursor('[["WR_repeat", {"times": 2, "do": [["WR_set|_var", {"name": "x"}]]}]]',
                            "textDocument/hover")
        self.assertIn("WR_set_var(name: str", result["contents"]["value"])

    def test_nothing_elsewhere(self):
        for marked in ('[["WR_to_url", {"u|rl": "x"}]]',
                       '[["WR_to_url", {"url": "WR_to|_url"}]]',
                       '[["WR_to_url", ["WR_to|_url"]]]',
                       '[["WR_to_url", |{"url": "x"}]]',
                       '[["WR_no_such|_command"]]',
                       '["WR_to|_url"]',
                       '|[["WR_to_url"]]',
                       '[["WR_to|'):
            with self.subTest(marked=marked):
                self.assertIsNone(_at_cursor(marked, "textDocument/hover"))

    def test_without_a_position_or_an_open_document(self):
        server = ActionLspServer()
        for params in ({}, {"textDocument": {"uri": "file:///closed.json"},
                            "position": {"line": 0, "character": 3}}):
            response = server.handle({"id": 3, "method": "textDocument/hover", "params": params})
            self.assertEqual(response, {"jsonrpc": "2.0", "id": 3, "result": None})


class TestCompletion(unittest.TestCase):

    def test_command_names_by_prefix(self):
        labels = _labels('[\n  ["WR_to_u|"]\n]')
        self.assertIn("WR_to_url", labels)
        self.assertEqual([label for label in labels if not label.startswith("WR_to_u")], [])

    def test_command_item_replaces_the_whole_name(self):
        marked = '[["WR_to_u|xyz", {"url": "x"}]]'
        items = _at_cursor(marked, "textDocument/completion")["items"]
        item = next(entry for entry in items if entry["label"] == "WR_to_url")
        self.assertEqual(item["kind"], 14)
        self.assertEqual(_apply(marked.replace("|", ""), [item["textEdit"]]), '[["WR_to_url", {"url": "x"}]]')

    def test_command_names_in_a_half_typed_document(self):
        self.assertIn("WR_quit_all", _labels('[\n  ["WR_to_url", {"url": "x"}],\n  ["WR_quit|'))

    def test_command_name_before_the_quote_is_typed(self):
        marked = '[["WR_quit_all"], [|'
        item = next(entry for entry in _at_cursor(marked, "textDocument/completion")["items"]
                    if entry["label"] == "WR_to_url")
        self.assertEqual(_apply(marked.replace("|", ""), [item["textEdit"]]), '[["WR_quit_all"], ["WR_to_url"')

    def test_command_names_inside_blocks(self):
        self.assertIn("WR_to_url", _labels('[["WR_if", {"condition": true, "then": [["WR_to_|"]]}]]'))
        self.assertIn("WR_to_url", _labels('{"webdriver_wrapper": [["WR_try", {"do": [["WR_quit_all"], ["WR_to_|'))
        self.assertIn("WR_to_url", _labels('[["WR_capture", {"name": "n", "action": ["WR_to_|"]}]]'))
        self.assertIn("WR_to_url", _labels('{"meta": {"setup": [["WR_to_|"]]}, "webdriver_wrapper": []}'))

    def test_parameter_names(self):
        self.assertEqual(_labels('[["WR_set_var", {"|"}]]'), ["name", "value", "local"])

    def test_parameter_names_leave_out_the_ones_present(self):
        self.assertEqual(_labels('[["WR_set_var", {"value": 1, "|": 2, "local": false}]]'), ["name"])
        self.assertEqual(_labels('[["WR_set_var", {"name": "n", |'), ["value", "local"])

    def test_parameter_names_by_prefix(self):
        self.assertEqual(_labels('[["WR_set_var", {"va|'), ["value"])

    def test_parameter_item_edits(self):
        quoted = '[["WR_set_var", {"na|": "x"}]]'
        item = _at_cursor(quoted, "textDocument/completion")["items"][0]
        self.assertEqual((item["label"], item["kind"], item["detail"]), ("name", 10, "name: str"))
        self.assertEqual(_apply(quoted.replace("|", ""), [item["textEdit"]]), '[["WR_set_var", {"name": "x"}]]')
        bare = '[["WR_set_var", {|'
        item = _at_cursor(bare, "textDocument/completion")["items"][0]
        self.assertEqual(_apply(bare.replace("|", ""), [item["textEdit"]]), '[["WR_set_var", {"name"')

    def test_parameter_names_of_a_nested_action_with_positional_arguments(self):
        marked = '[["WR_for_each", {"items": [1], "do": [["WR_set_var", ["n"], {"|"}]]}]]'
        self.assertEqual(_labels(marked), ["name", "value", "local"])

    def test_no_parameter_names_for_an_unknown_command_or_another_object(self):
        self.assertEqual(_labels('[["WR_no_such_command", {"|"}]]'), [])
        self.assertEqual(_labels('[["WR_set_var", {"value": {"|"}}]]'), [])
        self.assertEqual(_labels('{"|"}'), [])

    def test_variable_names(self):
        text = ('{"meta": {"vars": {"base": "x"}, "setup": [["WR_set_var", {"name": "from_setup"}]]},'
                ' "webdriver_wrapper": [\n'
                '["WR_set_var", {"name": "token", "value": 1}],\n'
                '["WR_for_each", {"items": [1], "var": "row", "index_var": "position", "do": [\n'
                '  ["WR_capture", {"name": "title", "action": ["WR_get_title"]}],\n'
                '  ["WR_to_url", {"url": "http://x.test/${|"}]]}]]}')
        self.assertEqual(_labels(text), ["base", "from_setup", "position", "row", "title", "token"])

    def test_variable_names_by_prefix_and_edit(self):
        marked = '[["WR_set_var", {"name": "token"}], ["WR_set_var", {"name": "total"}],' \
                 ' ["WR_to_url", {"url": "a/${x}/${to|}"}]]'
        items = _at_cursor(marked, "textDocument/completion")["items"]
        self.assertEqual([item["label"] for item in items], ["token", "total"])
        self.assertEqual(items[0]["kind"], 6)
        self.assertIn('"a/${x}/${token}"', _apply(marked.replace("|", ""), [items[0]["textEdit"]]))

    def test_variable_names_in_positional_arguments(self):
        self.assertEqual(_labels('[["WR_set_var", ["token", 1]], ["WR_to_url", ["${|"]]]'), ["token"])

    def test_variable_names_survive_a_half_typed_document(self):
        server, _diagnostics = _opened('[["WR_set_var", {"name": "token"}]]')
        self.assertEqual(_labels('[["WR_set_var", {"name": "token"}], ["WR_to_url", {"url": "${|', server),
                         ["token"])

    def test_no_variable_names_outside_an_open_placeholder(self):
        prefix = '[["WR_set_var", {"name": "token"}], '
        for marked in (prefix + '["WR_to_url", {"url": "plain |"}]]',
                       prefix + '["WR_to_url", {"url": "${token} |"}]]',
                       prefix + '["WR_to_url", {"url": |"${"}]]'):
            with self.subTest(marked=marked):
                self.assertEqual(_labels(marked), [])

    def test_nothing_elsewhere(self):
        for marked in ('|[["WR_quit_all"]]',
                       '[|["WR_quit_all"]]',
                       '["WR_|"]',
                       '[["WR_quit_all", |]]',
                       '[["WR_quit_all", ["WR_|"]]]',
                       '[["WR_to_url", {"url": |}]]',
                       '[["WR_to_url", {"url": "WR_|"}]]',
                       '[["WR_to_url"|]]',
                       '{"meta": {"tags": ["WR_|"]}, "webdriver_wrapper": []}',
                       '|'):
            with self.subTest(marked=marked):
                self.assertEqual(_labels(marked), [])

    def test_request_without_a_position_lists_every_command(self):
        server, _diagnostics = _opened('[["WR_quit_all"]]')
        result = server.handle({"id": 5, "method": "textDocument/completion",
                                "params": {"textDocument": {"uri": _URI}}})["result"]
        self.assertEqual([item["label"] for item in result["items"]], server.command_names())
        self.assertIs(result["isIncomplete"], False)

    def test_document_variables_of_odd_documents(self):
        self.assertEqual(document_variables(None), [])
        self.assertEqual(document_variables({"meta": [], "webdriver_wrapper": "x"}), [])
        self.assertEqual(document_variables([["WR_try", {"do": [], "on_error": []}], 3]), ["error"])


class TestFormatting(unittest.TestCase):

    def _format(self, text):
        server, _diagnostics = _opened(text)
        return server.handle({"id": 4, "method": "textDocument/formatting", "params": {
            "textDocument": {"uri": _URI}, "options": {"tabSize": 4, "insertSpaces": True}}})["result"]

    def test_one_edit_replaces_the_whole_document(self):
        text = '[["WR_to_url",\n   {"zeta": 1, "url": "x"}],\n\n ["WR_quit_all"]]\n'
        edits = self._format(text)
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0]["range"], {"start": {"line": 0, "character": 0},
                                             "end": {"line": 4, "character": 0}})
        self.assertEqual(edits[0]["newText"], format_text(text))
        self.assertEqual(_apply(text, edits), '[\n  ["WR_to_url", {"url": "x", "zeta": 1}],\n  ["WR_quit_all"]\n]\n')

    def test_document_without_a_final_newline(self):
        text = '[["WR_quit_all"]]'
        edits = self._format(text)
        self.assertEqual(edits[0]["range"]["end"], {"line": 0, "character": len(text)})
        self.assertEqual(_apply(text, edits), format_text(text))

    def test_no_edits_when_already_formatted(self):
        self.assertEqual(self._format(format_text('[["WR_to_url", {"url": "x"}], ["WR_quit_all"]]')), [])

    def test_no_edits_when_not_valid_json(self):
        self.assertEqual(self._format('[["WR_quit_all"'), [])
        self.assertEqual(self._format(""), [])

    def test_no_edits_for_a_document_the_formatter_does_not_take(self):
        self.assertEqual(self._format('{"webdriver_wrapper": [["WR_quit_all"]]}'), [])

    def test_no_edits_for_a_document_that_is_not_open(self):
        response = ActionLspServer().handle({"id": 4, "method": "textDocument/formatting",
                                             "params": {"textDocument": {"uri": _URI}}})
        self.assertEqual(response["result"], [])


class TestCodeAction(unittest.TestCase):

    @staticmethod
    def _actions(server, diagnostics):
        return server.handle({"id": 6, "method": "textDocument/codeAction", "params": {
            "textDocument": {"uri": _URI},
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
            "context": {"diagnostics": diagnostics}}})["result"]

    def test_diagnostics_carry_the_rule_as_code(self):
        _server, diagnostics = _opened('[["WR_quit", {}]]')
        self.assertEqual(sorted(entry["code"] for entry in diagnostics), ["empty_kwargs", "legacy_name"])
        self.assertEqual({entry["data"]["location"] for entry in diagnostics}, {"action[0]"})

    def test_parse_error_has_no_code(self):
        _server, diagnostics = _opened("not json")
        self.assertNotIn("code", diagnostics[0])

    def test_quick_fix_replaces_the_legacy_name(self):
        text = '[\n  ["WR_to_url", {"url": "${ENV.BASE}"}],\n  ["WR_quit"]\n]'
        server, diagnostics = _opened(text)
        actions = self._actions(server, diagnostics)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["title"], "Replace 'WR_quit' with 'WR_quit_all'")
        self.assertEqual(actions[0]["kind"], "quickfix")
        self.assertEqual(actions[0]["diagnostics"], diagnostics)
        self.assertEqual(list(actions[0]["edit"]["changes"]), [_URI])
        self.assertEqual(_apply(text, actions[0]["edit"]["changes"][_URI]),
                         '[\n  ["WR_to_url", {"url": "${ENV.BASE}"}],\n  ["WR_quit_all"]\n]')

    def test_quick_fix_for_a_nested_action_and_a_hook(self):
        text = ('{"meta": {"tags": ["t"], "teardown": [["WR_single_quit"]]}, "webdriver_wrapper": [\n'
                '  ["WR_repeat", {"times": 2, "do": [\n    ["WR_explict_wait", {"wait_time": 1}]]}]]}')
        server, diagnostics = _opened(text)
        legacy = [entry for entry in diagnostics if entry["code"] == "legacy_name"]
        self.assertEqual(sorted(entry["range"]["start"]["line"] for entry in legacy), [0, 2])
        actions = self._actions(server, diagnostics)
        self.assertEqual([len(action["edit"]["changes"][_URI]) for action in actions], [1, 1])
        fixed = _apply(text, [edit for action in actions for edit in action["edit"]["changes"][_URI]])
        self.assertIn('["WR_quit_current"]', fixed)
        self.assertIn('["WR_explicit_wait", {"wait_time": 1}]', fixed)
        self.assertEqual(json.loads(fixed)["meta"]["tags"], ["t"])

    def test_two_identical_names_on_one_line_are_told_apart_by_data(self):
        text = '[["WR_quit"], ["WR_quit"]]'
        server, diagnostics = _opened(text)
        legacy = [entry for entry in diagnostics if entry["code"] == "legacy_name"]
        self.assertEqual(len(legacy), 2)
        actions = self._actions(server, legacy[1:])
        self.assertEqual(len(actions), 1)
        self.assertEqual(_apply(text, actions[0]["edit"]["changes"][_URI]), '[["WR_quit"], ["WR_quit_all"]]')

    def test_client_that_drops_data_gets_every_match_on_the_line(self):
        text = '[["WR_quit"], ["WR_quit"]]'
        server, diagnostics = _opened(text)
        sent = {key: value for key, value in diagnostics[0].items() if key != "data"}
        actions = self._actions(server, [sent])
        self.assertEqual(_apply(text, actions[0]["edit"]["changes"][_URI]), '[["WR_quit_all"], ["WR_quit_all"]]')

    def test_no_quick_fix_when_the_table_lists_several_names(self):
        server, diagnostics = _opened('[["WR_element_get_select"]]')
        self.assertEqual([entry["code"] for entry in diagnostics], ["legacy_name"])
        self.assertEqual(self._actions(server, diagnostics), [])

    def test_no_quick_fix_for_other_diagnostics(self):
        server, diagnostics = _opened('[["WR_quit_all", {}]]')
        self.assertEqual([entry["code"] for entry in diagnostics], ["empty_kwargs"])
        self.assertEqual(self._actions(server, diagnostics), [])

    def test_stale_or_malformed_diagnostics_give_nothing(self):
        server, diagnostics = _opened('[["WR_quit"]]')
        moved = dict(diagnostics[0], range={"start": {"line": 5, "character": 0},
                                            "end": {"line": 5, "character": 200}})
        self.assertEqual(self._actions(server, [moved, "junk", {"code": "legacy_name"}]), [])
        self.assertEqual(self._actions(server, None), [])
        server.handle({"method": "textDocument/didChange", "params": {
            "textDocument": {"uri": _URI, "version": 2}, "contentChanges": [{"text": '[["WR_quit"'}]}})
        self.assertEqual(self._actions(server, diagnostics), [])


class TestNestedDiagnosticLines(unittest.TestCase):

    def test_finding_lands_on_its_nested_action(self):
        text = ('[\n  ["WR_quit_all"],\n  ["WR_repeat", {"times": 2, "do": [\n'
                '    ["WR_quit_all"],\n    ["WR_quit"]\n  ]}]\n]')
        _server, diagnostics = _opened(text)
        self.assertEqual([(entry["code"], entry["range"]["start"]["line"]) for entry in diagnostics],
                         [("legacy_name", 4)])
        self.assertEqual(diagnostics[0]["data"], {"location": "action[1].do[1]"})

    def test_finding_in_a_condition_and_a_deeper_block(self):
        text = ('[["WR_if", {\n "condition": {"not": {"succeeds":\n  ["WR_quit"]}},\n "then": [\n'
                '  ["WR_try", {"do": [["WR_quit_all"]], "always": [\n   ["WR_single_quit"]]}]]}]]')
        _server, diagnostics = _opened(text)
        lines = {entry["data"]["location"]: entry["range"]["start"]["line"]
                 for entry in diagnostics if entry["code"] == "legacy_name"}
        self.assertEqual(lines, {"action[0].condition.not.succeeds": 2, "action[0].then[0].always[0]": 5})

    def test_argument_finding_lands_on_its_value(self):
        text = '[\n  ["WR_to_url", {\n    "url": "http://hard.test/"}]\n]'
        _server, diagnostics = _opened(text)
        self.assertEqual([(entry["code"], entry["range"]["start"]["line"]) for entry in diagnostics],
                         [("hardcoded_url", 2)])

    def test_hook_finding_lands_in_the_hook(self):
        text = '{"meta": {"tags": ["t"],\n "setup": [\n  ["WR_quit"]]},\n "webdriver_wrapper": []}'
        _server, diagnostics = _opened(text)
        self.assertEqual([(entry["code"], entry["range"]["start"]["line"]) for entry in diagnostics],
                         [("legacy_name", 2)])


if __name__ == "__main__":
    unittest.main()
