"""
Action JSON LSP server：基於 LSP 3.17 protocol，提供 ``WR_*`` 補全、hover、格式化、快速修正與 lint 診斷。
Minimal LSP server speaking JSON-RPC 2.0 over stdio with the standard
``Content-Length`` headers. Supports:

- ``initialize`` / ``initialized`` / ``shutdown`` / ``exit``
- ``textDocument/didOpen`` / ``didChange`` / ``didClose``
- ``textDocument/completion`` — by cursor position: command names in the first element of an action,
  parameter names on a key of its keyword arguments, variable names after ``${`` in a string value; a
  request without a position gets every registered ``WR_*`` command
- ``textDocument/hover`` — the signature and docstring of the command under the cursor
- ``textDocument/formatting`` — the document in the action formatter's canonical form
- ``textDocument/codeAction`` — a quick fix that replaces a legacy command name
- ``textDocument/publishDiagnostics`` — pushes lint findings on document
  open / change, each on the line of what it is about, and clears them on close

A document is a list of actions or an object whose ``webdriver_wrapper`` holds one, as the executor accepts.
Notifications the server does not know are ignored; unknown requests get ``-32601``.

The action linter, the formatter and the command list are pulled from existing modules so
the LSP stays a thin presentation layer; each feature lives in its own module of this package.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Callable, TextIO

from je_web_runner.action_lsp._completion import (
    COMMAND_DETAIL,
    CompletionSource,
    completion_items,
    document_variables,
)
from je_web_runner.action_lsp._diagnostics import lint_text, result_diagnostics
from je_web_runner.action_lsp._edits import QUICK_FIX, formatting_edits, legacy_name_fixes
from je_web_runner.action_lsp._framing import ActionLspError
from je_web_runner.action_lsp._framing import read_message as _read_message
from je_web_runner.action_lsp._framing import write_message as _write_message
from je_web_runner.action_lsp._hover import hover
from je_web_runner.action_lsp._text import request_offset
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


_COMMAND_PREFIX = "WR_"


@dataclass
class _Document:
    uri: str
    text: str
    version: int = 0
    # The last text of the document that was valid JSON, parsed: a half-typed document still has variables.
    data: Any = None


@dataclass
class ActionLspServer:
    """The state of one language-server session: the open documents and the command list."""
    documents: dict[str, _Document] = field(default_factory=dict)
    initialized: bool = False
    _command_names: list[str] | None = field(default=None, init=False, repr=False)
    _commands: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def commands(self) -> dict[str, Any]:
        """The registered ``WR_*`` commands by name."""
        if self._commands is None:
            try:
                from je_web_runner.utils.executor.action_executor import executor
                registered = dict(executor.event_dict)
            except Exception as error:  # pylint: disable=broad-except
                web_runner_logger.warning(f"action_lsp executor unavailable: {error!r}")
                registered = {}
            # The executor also holds the allowlisted builtins (``print`` …); an action file is about WR_*.
            self._commands = {name: command for name, command in registered.items()
                              if isinstance(name, str) and name.startswith(_COMMAND_PREFIX)}
        return self._commands

    def command_names(self) -> list[str]:
        """The names of the registered ``WR_*`` commands, sorted."""
        if self._command_names is None:
            self._command_names = sorted(self.commands())
        return self._command_names

    # --- Top-level dispatch ----------------------------------------------

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Answer one JSON-RPC message: a response, a notification to send, or None."""
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params") or {}
        notification = self._notifications().get(method)
        if notification is not None:
            return notification(params)
        request = self._requests().get(method)
        if request is not None:
            return self._respond(request_id, request(params))
        if request_id is None:
            # A notification (``didSave``, ``$/cancelRequest`` …) must not be answered.
            return None
        return self._error(request_id, -32601, f"unknown method {method!r}")

    def _notifications(self) -> dict[Any, Callable[[dict[str, Any]], dict[str, Any] | None]]:
        return {
            "initialized": self._on_initialized,
            "exit": self._on_exit,
            "textDocument/didOpen": self._on_did_open,
            "textDocument/didChange": self._on_did_change,
            "textDocument/didClose": self._on_did_close,
        }

    def _requests(self) -> dict[Any, Callable[[dict[str, Any]], Any]]:
        return {
            "initialize": self._initialize,
            "shutdown": self._shutdown,
            "textDocument/completion": self._completion,
            "textDocument/hover": self._hover,
            "textDocument/formatting": self._formatting,
            "textDocument/codeAction": self._code_action,
        }

    # --- Handlers --------------------------------------------------------

    @staticmethod
    def _initialize(_params: dict[str, Any]) -> dict[str, Any]:
        return {
            "capabilities": {
                "textDocumentSync": 1,  # full sync
                "completionProvider": {"triggerCharacters": ['"', "_", "{"]},
                "hoverProvider": True,
                "documentFormattingProvider": True,
                "codeActionProvider": {"codeActionKinds": [QUICK_FIX]},
            },
            "serverInfo": {"name": "webrunner-action-lsp", "version": "0.2.0"},
        }

    def _on_initialized(self, _params: dict[str, Any]) -> None:
        self.initialized = True

    @staticmethod
    def _on_exit(_params: dict[str, Any]) -> None:
        return None

    @staticmethod
    def _shutdown(_params: dict[str, Any]) -> None:
        return None

    def _on_did_open(self, params: dict[str, Any]) -> dict[str, Any]:
        document = params.get("textDocument") or {}
        uri = str(document.get("uri", ""))
        text = str(document.get("text", ""))
        self.documents[uri] = _Document(uri=uri, text=text, version=int(document.get("version", 0)))
        return self._diagnostics_notification(uri, text)

    def _on_did_change(self, params: dict[str, Any]) -> dict[str, Any]:
        document = params.get("textDocument") or {}
        uri = str(document.get("uri", ""))
        changes = params.get("contentChanges") or []
        if uri not in self.documents:
            return self._diagnostics_notification(uri, "")
        full_text = self.documents[uri].text
        for change in changes:
            if isinstance(change, dict) and "text" in change:
                full_text = str(change["text"])
        self.documents[uri].text = full_text
        self.documents[uri].version = int(document.get("version", 0))
        return self._diagnostics_notification(uri, full_text)

    def _on_did_close(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = str((params.get("textDocument") or {}).get("uri", ""))
        self.documents.pop(uri, None)
        return self._diagnostics_notification(uri, "")

    def _document(self, params: dict[str, Any]) -> _Document:
        """The open document a request is about; an empty one when it is not open."""
        uri = str((params.get("textDocument") or {}).get("uri", ""))
        return self.documents.get(uri) or _Document(uri=uri, text="")

    def _completion(self, params: dict[str, Any]) -> dict[str, Any]:
        document = self._document(params)
        offset = request_offset(document.text, params)
        if offset is None:
            # No cursor to go by: every command, as before completion looked at the position.
            items = [
                {
                    "label": name,
                    "kind": 14,  # CompletionItemKind.Keyword
                    "detail": COMMAND_DETAIL,
                    "insertText": name,
                }
                for name in self.command_names()
            ]
        else:
            source = CompletionSource(names=self.command_names(), commands=self.commands(),
                                      variables=document_variables(document.data))
            items = completion_items(document.text, offset, source)
        return {"isIncomplete": False, "items": items}

    def _hover(self, params: dict[str, Any]) -> dict[str, Any] | None:
        document = self._document(params)
        offset = request_offset(document.text, params)
        return None if offset is None else hover(document.text, offset, self.commands())

    def _formatting(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return formatting_edits(self._document(params).text)

    def _code_action(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        document = self._document(params)
        diagnostics = (params.get("context") or {}).get("diagnostics")
        if not isinstance(diagnostics, list):
            return []
        return legacy_name_fixes(document.text, document.uri, diagnostics)

    # --- Diagnostics -----------------------------------------------------

    def _diagnostics_notification(self, uri: str, text: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": self._lint_diagnostics(text, uri),
            },
        }

    def _lint_diagnostics(self, text: str, uri: str | None = None) -> list[dict[str, Any]]:
        result = lint_text(text)
        if result.data is not None and uri in self.documents:
            self.documents[uri].data = result.data
        return result_diagnostics(result)

    # --- Helpers ---------------------------------------------------------

    @staticmethod
    def _respond(request_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message},
        }


def serve_stdio(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    server: ActionLspServer | None = None,
) -> None:
    """Run the LSP loop until stdin EOF or an ``exit`` notification."""
    in_stream = stdin or sys.stdin
    out_stream = stdout or sys.stdout
    used_server = server or ActionLspServer()
    while True:
        try:
            message = _read_message(in_stream)
        except ActionLspError as error:
            web_runner_logger.warning(f"action_lsp parse error: {error}")
            continue
        if message is None:
            return
        response = used_server.handle(message)
        if message.get("method") == "exit":
            return
        if response is not None:
            _write_message(out_stream, response)
