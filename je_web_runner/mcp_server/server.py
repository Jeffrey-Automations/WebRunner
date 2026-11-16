"""
WebRunner MCP server：用 Model Context Protocol (JSON-RPC 2.0) 把 WR_* 動作對外開放。
WebRunner MCP server. Exposes a curated subset of WebRunner actions and
helper utilities as MCP tools so any MCP-compatible client (Claude, IDE
plugins, etc.) can drive WebRunner.

Transport: ndjson over stdio (one JSON object per line). Run via::

    python -m je_web_runner.mcp_server

Both protocol eras are served, decided per request:

* handshake era (2024-11-05 to 2025-11-25): ``initialize``,
  ``notifications/initialized``, ``ping`` and the feature methods below.
  ``initialize`` answers with the client's protocol version when it is one of
  :data:`SUPPORTED_PROTOCOL_VERSIONS`, otherwise with the newest.
* 2026-07-28 (stateless): a request whose ``params._meta`` names a protocol
  version is served on its own, without ``initialize``: ``server/discover``
  and the feature methods (see :mod:`._stateless`).

Feature methods, the same in every revision: ``tools/list``, ``tools/call``;
``resources/list``, ``resources/templates/list``, ``resources/read`` when the server
has resources; ``prompts/list``, ``prompts/get`` when it has prompts. A feature the
server does not have is neither advertised as a capability nor answered.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, TextIO

from je_web_runner.mcp_server._protocol import (
    INSTRUCTIONS,
    SUPPORTED_PROTOCOL_VERSIONS,
    negotiate_protocol_version,
    server_info,
    server_version,
)
from je_web_runner.mcp_server._stateless import DISCOVER_METHOD, discover_result, shape_result, stateless_version
from je_web_runner.mcp_server._types import (
    McpInvalidParams,
    McpProtocolError,
    McpServerError,
    Tool,
    ToolResult,
)
from je_web_runner.mcp_server._validation import validate_arguments
from je_web_runner.mcp_server.offline_tools import build_default_tools
from je_web_runner.mcp_server.prompts import Prompt, build_default_prompts, get_prompt
from je_web_runner.mcp_server.resources import (
    RESOURCE_NOT_FOUND,
    Resource,
    ResourceTemplate,
    build_default_resource_templates,
    build_default_resources,
    read_resource,
)
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

__all__ = [
    "SUPPORTED_PROTOCOL_VERSIONS", "McpInvalidParams", "McpProtocolError", "McpServer", "McpServerError",
    "Prompt", "Resource", "ResourceTemplate", "Tool", "ToolResult", "build_default_tools",
    "make_default_server", "negotiate_protocol_version", "serve_stdio", "server_version",
]

_Handler = Callable[[dict[str, Any]], Any]
#: Answers a read of an unknown URI in 2026-07-28, where the older revisions say "resource not found".
_INVALID_PARAMS = -32602


@dataclass
class McpServer:
    """JSON-RPC 2.0 server that speaks the MCP wire protocol over stdio."""

    tools: dict[str, Tool] = field(default_factory=dict)
    initialized: bool = False
    resources: dict[str, Resource] = field(default_factory=dict)
    resource_templates: list[ResourceTemplate] = field(default_factory=list)
    prompts: dict[str, Prompt] = field(default_factory=dict)
    #: The revision the handshake agreed on; the newest until a client sends ``initialize``.
    protocol_version: str = SUPPORTED_PROTOCOL_VERSIONS[0]

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise McpServerError(f"tool {tool.name!r} already registered")
        self.tools[tool.name] = tool

    def register_resource(self, resource: Resource) -> None:
        """Offer ``resource`` under its URI."""
        if resource.uri in self.resources:
            raise McpServerError(f"resource {resource.uri!r} already registered")
        self.resources[resource.uri] = resource

    def register_resource_template(self, template: ResourceTemplate) -> None:
        """Offer the resources of ``template``."""
        if any(known.uri_template == template.uri_template for known in self.resource_templates):
            raise McpServerError(f"resource template {template.uri_template!r} already registered")
        self.resource_templates.append(template)

    def register_prompt(self, prompt: Prompt) -> None:
        """Offer ``prompt`` under its name."""
        if prompt.name in self.prompts:
            raise McpServerError(f"prompt {prompt.name!r} already registered")
        self.prompts[prompt.name] = prompt

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """
        處理一則訊息；notification（沒有 ``id``）一律不回應
        Answer one JSON-RPC message. A notification (no ``id`` member) never gets a response,
        not even an error.
        """
        response = self._respond(message)
        if "id" not in message:
            return None
        return response

    def _respond(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        if not isinstance(method, str):
            return self._error(request_id, -32600, "method must be a string")
        if not isinstance(params, dict):
            return self._error(request_id, -32602, "params must be an object")
        try:
            result = self._run(method, params)
        except McpProtocolError as error:
            return self._error(request_id, error.code, str(error), error.data)
        except Exception as error:  # pylint: disable=broad-except — answered as -32603 and logged
            web_runner_logger.error(
                f"mcp handler crashed in {method!r}: {error!r}\n{traceback.format_exc()}"
            )
            return self._error(request_id, -32603, f"internal error: {error!r}")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _run(self, method: str, params: dict[str, Any]) -> Any:
        """Serve ``method`` in the era the request declares (``initialize`` is always the handshake)."""
        version = None if method == "initialize" else stateless_version(params)
        if version is None:
            if method == DISCOVER_METHOD:
                raise McpInvalidParams(f"{DISCOVER_METHOD} needs the 2026-07-28 _meta fields")
            return self._run_handshake_era(method, params)
        if method == DISCOVER_METHOD:
            return shape_result(
                method, discover_result(INSTRUCTIONS, self._capabilities(stateless=True)), server_info(version))
        handler = self._feature_handlers(version, _INVALID_PARAMS).get(method)
        if handler is None:
            raise McpProtocolError(-32601, f"unknown method {method!r} in {version}")
        return shape_result(method, handler(params), server_info(version))

    def _run_handshake_era(self, method: str, params: dict[str, Any]) -> Any:
        handlers: dict[str, _Handler] = {
            "initialize": self._initialize,
            "ping": lambda _params: {},
            "notifications/initialized": self._on_initialized,
            **self._feature_handlers(self.protocol_version, RESOURCE_NOT_FOUND),
        }
        handler = handlers.get(method)
        if handler is None:
            raise McpProtocolError(-32601, f"unknown method {method!r}")
        return handler(params)

    def _feature_handlers(self, version: str, not_found_code: int) -> dict[str, _Handler]:
        """
        The methods of what this server offers, as the revision ``version`` shapes them.
        ``not_found_code`` answers a read of a URI nothing has.
        """
        handlers: dict[str, _Handler] = {
            "tools/list": lambda _params: self._tools_list(),
            "tools/call": self._tools_call,
        }
        if self._has_resources():
            handlers["resources/list"] = lambda _params: {
                "resources": [resource.describe(version) for resource in self.resources.values()]}
            handlers["resources/templates/list"] = lambda _params: {
                "resourceTemplates": [template.describe(version) for template in self.resource_templates]}
            handlers["resources/read"] = lambda params: read_resource(
                params.get("uri"), self.resources, self.resource_templates, not_found_code)
        if self.prompts:
            handlers["prompts/list"] = lambda _params: {
                "prompts": [prompt.describe(version) for prompt in self.prompts.values()]}
            handlers["prompts/get"] = lambda params: get_prompt(self.prompts, params)
        return handlers

    def _has_resources(self) -> bool:
        return bool(self.resources or self.resource_templates)

    def _capabilities(self, stateless: bool) -> dict[str, Any]:
        """
        What the server offers. The handshake revisions say that no list changes and nothing
        can be subscribed to; 2026-07-28 moved both to ``subscriptions/listen``, which this
        server does not serve, so its capability objects are empty.
        """
        static: dict[str, Any] = {} if stateless else {"listChanged": False}
        capabilities: dict[str, Any] = {"tools": dict(static)}
        if self._has_resources():
            capabilities["resources"] = dict(static) if stateless else {"subscribe": False, **static}
        if self.prompts:
            capabilities["prompts"] = dict(static)
        return capabilities

    def _on_initialized(self, _params: dict[str, Any]) -> None:
        self.initialized = True

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        client_version = params.get("protocolVersion")
        version = negotiate_protocol_version(client_version)
        web_runner_logger.info(f"mcp initialize: client {client_version!r}, answered {version!r}")
        self.protocol_version = version
        return {
            "protocolVersion": version,
            "capabilities": self._capabilities(stateless=False),
            "serverInfo": server_info(version),
            "instructions": INSTRUCTIONS,
        }

    def _tools_list(self) -> dict[str, Any]:
        return {"tools": [tool.schema() for tool in self.tools.values()]}

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str):
            raise McpInvalidParams("tool 'name' is required")
        if name not in self.tools:
            raise McpInvalidParams(f"unknown tool {name!r}")
        if not isinstance(arguments, dict):
            raise McpInvalidParams("'arguments' must be an object")
        problems = validate_arguments(self.tools[name].input_schema, arguments)
        if problems:
            return _text_result("invalid arguments: " + "; ".join(problems), is_error=True)
        try:
            result = self.tools[name].handler(arguments)
        except Exception as error:  # pylint: disable=broad-except — a tool failure is a result, not a crash
            web_runner_logger.warning(
                f"mcp tool {name!r} failed: {error!r}\n{traceback.format_exc()}"
            )
            return _text_result(f"{type(error).__name__}: {error}", is_error=True)
        if isinstance(result, ToolResult):
            return _value_result(result.value, is_error=result.is_error)
        return _value_result(result, is_error=False)

    @staticmethod
    def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _render(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)


def _text_result(text: str, *, is_error: bool) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _value_result(value: Any, *, is_error: bool) -> dict[str, Any]:
    """A handler's value as text, plus ``structuredContent`` when it is a JSON object."""
    text = _render(value)
    result = _text_result(text, is_error=is_error)
    if isinstance(value, dict):
        # Re-parse the rendered text so the structured copy is plain JSON too.
        result["structuredContent"] = json.loads(text)
    return result


def make_default_server() -> McpServer:
    # Imported lazily so ``server`` can be imported without dragging the
    # full executor (and therefore Selenium / Playwright) into modules that
    # only need the protocol skeleton.
    from je_web_runner.mcp_server.browser_tools import build_browser_tools
    server = McpServer()
    for tool in build_default_tools():
        server.register(tool)
    for tool in build_browser_tools():
        server.register(tool)
    for resource in build_default_resources():
        server.register_resource(resource)
    for template in build_default_resource_templates():
        server.register_resource_template(template)
    for prompt in build_default_prompts():
        server.register_prompt(prompt)
    return server


def serve_stdio(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    server: McpServer | None = None,
) -> None:
    """
    主迴圈：每行一個 JSON-RPC 2.0 訊息，直到 stdin EOF
    Read newline-delimited JSON-RPC messages from ``stdin`` until EOF and
    write responses to ``stdout``.

    With the default streams both directions are UTF-8 with ``\\n`` line ends whatever the
    console code page. Side effect of the default ``stdout``: for the rest of the process
    anything else written to stdout (``print``, C extensions, child processes) goes to
    stderr, so only protocol messages reach the client.
    """
    in_stream = stdin or open(  # noqa: SIM115 — wraps the process stdin; the OS closes it
        sys.stdin.fileno(), encoding="utf-8", closefd=False,
    )
    out_stream = stdout or _claim_stdout()
    used_server = server or make_default_server()
    for line in in_stream:
        stripped = line.strip()
        if not stripped:
            continue
        message = _parse_message(stripped, used_server, out_stream)
        if message is None:
            continue
        _dispatch(message, used_server, out_stream)


def _claim_stdout() -> TextIO:
    """Keep fd 1 for the protocol (UTF-8, LF) and point the process's stdout at stderr."""
    sys.stdout.flush()
    protocol_out = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", newline="\n")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr
    return protocol_out


def _parse_message(line: str, server: McpServer, out_stream: TextIO) -> Any:
    try:
        return json.loads(line)
    except ValueError:
        response = server._error(  # pylint: disable=protected-access
            None, -32700, "parse error"
        )
        _write_message(out_stream, response)
        return None


def _dispatch(message: Any, server: McpServer, out_stream: TextIO) -> None:
    if isinstance(message, list):
        # JSON-RPC batching was removed from MCP in revision 2025-06-18.
        _write_message(out_stream, server._error(  # pylint: disable=protected-access
            None, -32600, "batch requests are not supported"))
        return
    if not isinstance(message, dict):
        _write_message(out_stream, server._error(  # pylint: disable=protected-access
            None, -32600, "a message must be a JSON object"))
        return
    response = server.handle(message)
    if response is not None:
        _write_message(out_stream, response)


def _write_message(out_stream: TextIO, message: dict[str, Any]) -> None:
    out_stream.write(json.dumps(message, ensure_ascii=False) + "\n")
    out_stream.flush()
