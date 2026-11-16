"""LSP framing counts bytes: non-ASCII text must not move the message boundaries."""
import io
import json
import unittest

from je_web_runner.action_lsp._framing import ActionLspError, read_message, write_message
from je_web_runner.action_lsp.server import serve_stdio

_TEXT = "點擊按鈕 — clic sur le bouton"


def _frame(message) -> bytes:
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


class _Console:
    """A text stream over bytes with a locale encoding that cannot hold the test text, like a Windows console."""

    def __init__(self, data: bytes = b""):
        self.buffer = io.BytesIO(data)
        self._text = io.TextIOWrapper(self.buffer, encoding="ascii", errors="strict", newline="")

    def write(self, text):
        return self._text.write(text)

    def flush(self):
        self._text.flush()

    def readline(self):
        return self._text.readline()

    def read(self, size=-1):
        return self._text.read(size)


class TestBinaryStreams(unittest.TestCase):

    def test_two_messages_with_non_ascii_text_keep_their_boundaries(self):
        first = {"jsonrpc": "2.0", "id": 1, "method": "a", "params": {"text": _TEXT}}
        second = {"jsonrpc": "2.0", "id": 2, "method": "b", "params": {"text": "plain"}}
        stream = _Console(_frame(first) + _frame(second))
        self.assertEqual(read_message(stream), first)
        self.assertEqual(read_message(stream), second)
        self.assertIsNone(read_message(stream))

    def test_written_bytes_are_utf8_whatever_the_stream_encoding(self):
        stream = _Console()
        message = {"jsonrpc": "2.0", "id": 1, "result": {"contents": _TEXT}}
        write_message(stream, message)
        written = stream.buffer.getvalue()
        self.assertEqual(written, _frame(message))
        header, _, body = written.partition(b"\r\n\r\n")
        self.assertEqual(int(header.split(b":")[1]), len(body))

    def test_round_trip_through_the_server_loop(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "textDocument/didOpen",
             "params": {"textDocument": {"uri": "file:///x.json", "text": json.dumps([["WR_note", {"text": _TEXT}]])}}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
            {"jsonrpc": "2.0", "method": "exit"},
        ]
        stdin = _Console(b"".join(_frame(request) for request in requests))
        stdout = _Console()
        serve_stdio(stdin=stdin, stdout=stdout)
        replies = []
        output = _Console(stdout.buffer.getvalue())
        while (message := read_message(output)) is not None:
            replies.append(message)
        self.assertEqual([reply.get("id") for reply in replies if "id" in reply], [1, 2])
        self.assertTrue(any(reply.get("method") == "textDocument/publishDiagnostics" for reply in replies))


class TestTextStreams(unittest.TestCase):

    def test_in_memory_text_stream_counts_bytes_too(self):
        first = {"id": 1, "text": _TEXT}
        second = {"id": 2}
        stream = io.StringIO((_frame(first) + _frame(second)).decode("utf-8"))
        self.assertEqual(read_message(stream), first)
        self.assertEqual(read_message(stream), second)

    def test_write_to_a_text_stream(self):
        stream = io.StringIO()
        write_message(stream, {"id": 1, "text": _TEXT})
        self.assertEqual(stream.getvalue().encode("utf-8"), _frame({"id": 1, "text": _TEXT}))

    def test_end_of_stream_and_missing_length(self):
        self.assertIsNone(read_message(io.StringIO("")))
        self.assertIsNone(read_message(io.StringIO("X-Other: 1\r\n\r\n{}")))

    def test_bad_length_and_bad_body(self):
        with self.assertRaises(ActionLspError):
            read_message(io.StringIO("Content-Length: many\r\n\r\n{}"))
        with self.assertRaises(ActionLspError):
            read_message(io.StringIO("Content-Length: 5\r\n\r\n{not}"))


if __name__ == "__main__":
    unittest.main()
