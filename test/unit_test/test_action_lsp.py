import io
import json
import unittest

from je_web_runner.action_lsp._positions import action_lines
from je_web_runner.action_lsp.server import (
    ActionLspServer,
    serve_stdio,
)


def _open(server, text, uri="file:///x.json"):
    return server.handle({
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": uri, "text": text}},
    })


def _frame(message):
    body = json.dumps(message)
    return f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}"


class TestActionLspServer(unittest.TestCase):

    def test_initialize_returns_capabilities(self):
        server = ActionLspServer()
        result = server.handle({"id": 1, "method": "initialize", "params": {}})
        capabilities = result["result"]["capabilities"]
        self.assertEqual(capabilities["textDocumentSync"], 1)
        self.assertIn("triggerCharacters", capabilities["completionProvider"])

    def test_did_open_publishes_diagnostics(self):
        server = ActionLspServer()
        result = server.handle({
            "method": "textDocument/didOpen",
            "params": {"textDocument": {
                "uri": "file:///x.json",
                "text": "not json",
            }},
        })
        self.assertEqual(result["method"], "textDocument/publishDiagnostics")
        diags = result["params"]["diagnostics"]
        self.assertTrue(any("JSON parse error" in d["message"] for d in diags))

    def test_did_open_clean_array_no_diagnostics(self):
        server = ActionLspServer()
        result = server.handle({
            "method": "textDocument/didOpen",
            "params": {"textDocument": {
                "uri": "file:///x.json",
                "text": "[]",
            }},
        })
        self.assertEqual(result["params"]["diagnostics"], [])

    def test_object_without_action_list_is_an_error(self):
        diags = _open(ActionLspServer(), "{}")["params"]["diagnostics"]
        self.assertEqual([d["severity"] for d in diags], [1])
        self.assertIn("webdriver_wrapper", diags[0]["message"])

    def test_string_root_is_an_error(self):
        diags = _open(ActionLspServer(), '"WR_quit"')["params"]["diagnostics"]
        self.assertEqual([d["severity"] for d in diags], [1])

    def test_lint_finding_becomes_a_warning_on_its_action_line(self):
        text = '[\n  ["WR_to_url", {"url": "${ENV.BASE}"}],\n  ["WR_quit"]\n]'
        diags = _open(ActionLspServer(), text)["params"]["diagnostics"]
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0]["severity"], 2)
        self.assertEqual(diags[0]["range"]["start"]["line"], 2)
        self.assertIn("[legacy_name]", diags[0]["message"])

    def test_info_finding_is_information(self):
        diags = _open(ActionLspServer(), '[["WR_quit_all", {}]]')["params"]["diagnostics"]
        self.assertEqual([(d["severity"], d["range"]["start"]["line"]) for d in diags], [(3, 0)])
        self.assertIn("[empty_kwargs]", diags[0]["message"])

    def test_object_document_is_linted(self):
        text = ('{\n "meta": {"tags": ["smoke"]},\n "webdriver_wrapper": [\n'
                '  ["WR_quit_all"],\n  ["WR_quit"]\n ]\n}')
        diags = _open(ActionLspServer(), text)["params"]["diagnostics"]
        self.assertEqual([d["range"]["start"]["line"] for d in diags], [4])
        self.assertIn("[legacy_name]", diags[0]["message"])

    def test_document_level_finding_is_on_the_first_line(self):
        diags = _open(ActionLspServer(), '{"webdriver_wrapper": []}')["params"]["diagnostics"]
        self.assertEqual([d["range"]["start"]["line"] for d in diags], [0])
        self.assertIn("[missing_tags]", diags[0]["message"])

    def test_did_close_clears_diagnostics(self):
        server = ActionLspServer()
        _open(server, '[["WR_quit"]]')
        result = server.handle({
            "method": "textDocument/didClose",
            "params": {"textDocument": {"uri": "file:///x.json"}},
        })
        self.assertEqual(result["params"], {"uri": "file:///x.json", "diagnostics": []})
        self.assertNotIn("file:///x.json", server.documents)

    def test_did_change_updates_text(self):
        server = ActionLspServer()
        server.handle({
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": "file:///x.json", "text": "[]"}},
        })
        server.handle({
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": "file:///x.json", "version": 2},
                "contentChanges": [{"text": "not json"}],
            },
        })
        self.assertEqual(server.documents["file:///x.json"].text, "not json")

    def test_completion_returns_command_names(self):
        server = ActionLspServer()
        # Stub command list so the test doesn't depend on full executor state
        server._command_names = ["WR_quit_all", "WR_to_url"]
        result = server.handle({"id": 5, "method": "textDocument/completion",
                                "params": {}})
        labels = [item["label"] for item in result["result"]["items"]]
        self.assertEqual(set(labels), {"WR_quit_all", "WR_to_url"})

    def test_completion_offers_only_action_commands(self):
        names = ActionLspServer().command_names()
        self.assertIn("WR_to_url", names)
        self.assertEqual([name for name in names if not name.startswith("WR_")], [])

    def test_unknown_notification_is_ignored(self):
        self.assertIsNone(ActionLspServer().handle({"method": "textDocument/didSave", "params": {}}))

    def test_unknown_method_returns_error(self):
        server = ActionLspServer()
        result = server.handle({"id": 9, "method": "noSuch"})
        self.assertEqual(result["error"]["code"], -32601)


class TestActionLines(unittest.TestCase):

    def test_list_document(self):
        self.assertEqual(action_lines('[\n["a"],\n\n["b", {"k": [1, 2]}], ["c"]\n]', False), [1, 3, 3])

    def test_brackets_and_quotes_inside_strings_are_skipped(self):
        text = '[["a", {"k": "x], [\\" y"}],\n["b"]]'
        self.assertEqual(action_lines(text, False), [0, 1])

    def test_object_document_uses_the_wrapper_list(self):
        text = '{"meta": {"webdriver_wrapper": [1]},\n"webdriver_wrapper": [\n["a"]]}'
        self.assertEqual(action_lines(text, True), [2])

    def test_missing_list_gives_no_lines(self):
        self.assertEqual(action_lines('{"meta": {}}', True), [])
        self.assertEqual(action_lines('', False), [])


class TestServeStdio(unittest.TestCase):

    def test_round_trip(self):
        message_a = _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                            "params": {}})
        message_b = _frame({"jsonrpc": "2.0", "method": "exit"})
        stdin = io.StringIO(message_a + message_b)
        stdout = io.StringIO()
        serve_stdio(stdin=stdin, stdout=stdout)
        output = stdout.getvalue()
        self.assertIn("Content-Length:", output)
        self.assertIn('"jsonrpc": "2.0"', output)


if __name__ == "__main__":
    unittest.main()
