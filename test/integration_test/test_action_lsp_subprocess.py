"""
Integration: drive the Action JSON LSP as a real subprocess.

Frames messages with the LSP-required ``Content-Length`` headers and
walks initialize → didOpen (with a JSON parse error) →
publishDiagnostics → exit.

Note: the subprocess pipes use binary mode. ``text=True`` would convert
``\\n`` to ``\\r\\n`` on Windows, corrupting the framing.
"""
import json
import os
import subprocess  # nosec B404 — argv-only invocation, controlled args
import sys
import unittest


def _frame(message) -> bytes:
    body = json.dumps(message).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _read_messages(stream_bytes: bytes):
    """Parse a stream of LSP-framed messages from raw bytes."""
    messages = []
    cursor = 0
    while cursor < len(stream_bytes):
        header_end = stream_bytes.find(b"\r\n\r\n", cursor)
        if header_end == -1:
            break
        headers = stream_bytes[cursor:header_end].decode("ascii", errors="replace")
        body_start = header_end + 4
        length = 0
        for header_line in headers.split("\r\n"):
            if ":" in header_line:
                name, _, value = header_line.partition(":")
                if name.strip().lower() == "content-length":
                    length = int(value.strip())
        body = stream_bytes[body_start:body_start + length]
        if body:
            messages.append(json.loads(body.decode("utf-8")))
        cursor = body_start + length
    return messages


def _spawn(env=None):
    return subprocess.Popen(  # nosec B603 — argv list, no shell
        [sys.executable, "-m", "je_web_runner.action_lsp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        env=env,
    )


def _drive(proc, frames):
    """Pipe ``frames`` through the proc's input via communicate()."""
    payload = b"".join(frames)
    try:
        stdout_data, stderr_data = proc.communicate(input=payload, timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout_data, stderr_data = proc.communicate(timeout=5)
        except Exception:  # pylint: disable=broad-except  # nosec B110 — best-effort drain
            stdout_data, stderr_data = b"", b""
    return stdout_data, stderr_data


class TestActionLspSubprocess(unittest.TestCase):

    def test_initialize_didopen_publishes_diagnostics(self):
        proc = _spawn()
        stdout_data, stderr_data = _drive(proc, [
            _frame({"jsonrpc": "2.0", "id": 1,
                    "method": "initialize", "params": {}}),
            _frame({"jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {"textDocument": {
                        "uri": "file:///x.json",
                        "text": "this is not json",
                    }}}),
            _frame({"jsonrpc": "2.0", "method": "exit"}),
        ])
        self.assertEqual(proc.returncode, 0,
                         msg=f"stderr={stderr_data!r}")
        messages = _read_messages(stdout_data)
        self.assertGreaterEqual(len(messages), 2,
                                msg=f"raw stdout: {stdout_data!r}")
        init_response = next(m for m in messages if m.get("id") == 1)
        self.assertIn("capabilities", init_response["result"])
        diagnostics_msg = next(
            m for m in messages
            if m.get("method") == "textDocument/publishDiagnostics"
        )
        diags = diagnostics_msg["params"]["diagnostics"]
        self.assertTrue(diags)
        self.assertIn("JSON parse error", diags[0]["message"])

    def test_completion_returns_command_names(self):
        proc = _spawn()
        stdout_data, _stderr = _drive(proc, [
            _frame({"jsonrpc": "2.0", "id": 1,
                    "method": "initialize", "params": {}}),
            _frame({"jsonrpc": "2.0", "id": 2,
                    "method": "textDocument/completion",
                    "params": {}}),
            _frame({"jsonrpc": "2.0", "method": "exit"}),
        ])
        messages = _read_messages(stdout_data)
        completion = next(m for m in messages if m.get("id") == 2)
        labels = [item["label"] for item in completion["result"]["items"]]
        self.assertTrue(any(name.startswith("WR_") for name in labels))

    def test_hover_completion_formatting_and_quick_fix(self):
        uri = "file:///x.json"
        text = '[["WR_quit"],\n ["WR_set_var", {"name": "token", "": 1}]]'
        document = {"textDocument": {"uri": uri}}
        # The hover text holds the bilingual docstring, so this also checks that the server writes UTF-8
        # whatever the locale's encoding is. A non-UTF-8 locale is forced to make that a real check.
        proc = _spawn(env={**os.environ, "PYTHONIOENCODING": "ascii"})
        stdout_data, stderr_data = _drive(proc, [
            _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            _frame({"jsonrpc": "2.0", "method": "textDocument/didOpen",
                    "params": {"textDocument": {"uri": uri, "text": text}}}),
            _frame({"jsonrpc": "2.0", "id": 2, "method": "textDocument/hover",
                    "params": {**document, "position": {"line": 0, "character": 5}}}),
            _frame({"jsonrpc": "2.0", "id": 3, "method": "textDocument/completion",
                    "params": {**document, "position": {"line": 1, "character": 35}}}),
            _frame({"jsonrpc": "2.0", "id": 4, "method": "textDocument/formatting",
                    "params": {**document, "options": {"tabSize": 2, "insertSpaces": True}}}),
            _frame({"jsonrpc": "2.0", "id": 5, "method": "textDocument/codeAction",
                    "params": {**document, "context": {"diagnostics": [{
                        "code": "legacy_name",
                        "message": "[legacy_name] 'WR_quit' is a legacy alias; prefer 'WR_quit_all'",
                        "range": {"start": {"line": 0, "character": 0},
                                  "end": {"line": 0, "character": 200}},
                    }]}}}),
            _frame({"jsonrpc": "2.0", "method": "exit"}),
        ])
        self.assertEqual(proc.returncode, 0, msg=f"stderr={stderr_data!r}")
        results = {message["id"]: message["result"]
                   for message in _read_messages(stdout_data) if "id" in message}
        capabilities = results[1]["capabilities"]
        self.assertTrue(capabilities["hoverProvider"])
        self.assertTrue(capabilities["documentFormattingProvider"])
        self.assertIn("WR_quit()", results[2]["contents"]["value"])
        self.assertEqual([item["label"] for item in results[3]["items"]], ["value", "local"])
        self.assertEqual(results[4][0]["newText"],
                         '[\n  ["WR_quit"],\n  ["WR_set_var", {"": 1, "name": "token"}]\n]\n')
        self.assertEqual(results[5][0]["edit"]["changes"][uri][0]["newText"], '"WR_quit_all"')


if __name__ == "__main__":
    unittest.main()
