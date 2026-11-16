"""
MCP 資源 / The MCP resources: what a model reads before it writes an action file.

=====================================  ========================================================
``webrunner://commands``               the Markdown reference of every ``WR_*`` command
``webrunner://commands/{name}``        one command's signature and documentation (a template)
``webrunner://schema/action``          the JSON Schema of an action file
``webrunner://guide/action-language``  how to write an action file
=====================================  ========================================================

Content is built when a resource is read, never when the server starts or lists them, so
it always shows the commands registered at that moment.
"""
from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from je_web_runner.mcp_server._action_guide import ACTION_LANGUAGE_GUIDE, GUIDE_URI
from je_web_runner.mcp_server._policy import denied_commands
from je_web_runner.mcp_server._protocol import TITLE_SINCE
from je_web_runner.mcp_server._types import McpInvalidParams, McpProtocolError

COMMANDS_URI = "webrunner://commands"
COMMAND_URI_TEMPLATE = "webrunner://commands/{name}"
SCHEMA_URI = "webrunner://schema/action"
#: "Resource not found" of the handshake-era revisions. 2026-07-28 retired the code: there
#: an unknown URI is invalid params (-32602).
RESOURCE_NOT_FOUND = -32002
_MARKDOWN = "text/markdown"
_JSON = "application/json"
_COMMAND_NAME = re.compile(r"WR_\w+")
_VARIABLE = re.compile(r"\{\w+\}")


def _described(entry: dict[str, Any], title: str, version: str) -> dict[str, Any]:
    """``entry`` with ``title`` when the revision ``version`` defines it for resources."""
    if version >= TITLE_SINCE:
        entry["title"] = title
    return entry


@dataclass(frozen=True)
class Resource:
    """
    一個固定 URI 的資源
    One resource with a fixed URI. ``read`` builds its text and is called for every read.
    """
    uri: str
    name: str
    title: str
    description: str
    mime_type: str
    read: Callable[[], str]

    def describe(self, version: str) -> dict[str, Any]:
        """The resource as ``resources/list`` sends it in the revision ``version``."""
        return _described(
            {"uri": self.uri, "name": self.name, "description": self.description, "mimeType": self.mime_type},
            self.title, version)


@dataclass(frozen=True)
class ResourceTemplate:
    """
    一個 URI 樣板的資源
    A family of resources under a URI template whose last part is its one variable
    (``webrunner://commands/{name}``). ``read`` takes the variable's value and returns the
    text, or None when there is no such resource.
    """
    uri_template: str
    name: str
    title: str
    description: str
    mime_type: str
    read: Callable[[str], str | None]

    def describe(self, version: str) -> dict[str, Any]:
        """The template as ``resources/templates/list`` sends it in the revision ``version``."""
        return _described(
            {"uriTemplate": self.uri_template, "name": self.name, "description": self.description,
             "mimeType": self.mime_type},
            self.title, version)

    def variable_of(self, uri: str) -> str | None:
        """The value ``uri`` gives the template's variable, or None when ``uri`` is not of this template."""
        prefix = _VARIABLE.split(self.uri_template)[0]
        if not uri.startswith(prefix) or len(uri) == len(prefix):
            return None
        return uri[len(prefix):]


def read_resource(uri: Any, resources: dict[str, Resource], templates: list[ResourceTemplate],
                  not_found_code: int = RESOURCE_NOT_FOUND) -> dict[str, Any]:
    """
    讀取一個資源
    The ``resources/read`` result for ``uri``: a fixed resource first, then the templates.

    :raises McpInvalidParams: when ``uri`` is not a string.
    :raises McpProtocolError: with ``not_found_code`` when nothing has that URI.
    """
    if not isinstance(uri, str) or not uri:
        raise McpInvalidParams("resources/read needs 'uri' as a string")
    resource = resources.get(uri)
    if resource is not None:
        return _contents(uri, resource.mime_type, resource.read())
    for template in templates:
        value = template.variable_of(uri)
        text = None if value is None else template.read(value)
        if text is not None:
            return _contents(uri, template.mime_type, text)
    raise McpProtocolError(not_found_code, f"resource not found: {uri}", data={"uri": uri})


def _contents(uri: str, mime_type: str, text: str) -> dict[str, Any]:
    return {"contents": [{"uri": uri, "mimeType": mime_type, "text": text}]}


def _read_command_reference() -> str:
    from je_web_runner.utils.docs.command_reference import build_command_reference
    return build_command_reference()


def _read_action_schema() -> str:
    from je_web_runner.utils.schema.action_schema import build_action_schema
    # Without the per-command argument rules: they make the schema about twenty times longer, and a
    # model reads one command's arguments from webrunner://commands/{name}.
    return json.dumps(build_action_schema(arguments=False), indent=2, ensure_ascii=False)


def _signature_of(command: Any) -> str:
    try:
        return str(inspect.signature(command))
    except (TypeError, ValueError):
        return "(...)"


def _read_command(name: str) -> str | None:
    """One command's signature and documentation as Markdown; None when no such command is registered."""
    if not _COMMAND_NAME.fullmatch(name):
        return None
    from je_web_runner.utils.executor.action_executor import executor
    command = executor.event_dict.get(name)
    if command is None:
        return None
    lines = [f"# {name}", "", "```", f"{name}{_signature_of(command)}", "```", ""]
    lines.append(inspect.getdoc(command) or "This command has no documentation.")
    if name in denied_commands():
        lines.extend(["", "This server refuses to run this command (see the MCP caller policy)."])
    return "\n".join(lines) + "\n"


def build_default_resources() -> list[Resource]:
    """The fixed-URI resources shipped with the server."""
    return [
        Resource(
            uri=COMMANDS_URI,
            name="commands",
            title="WR_* command reference",
            description="Every WR_* command with its signature and a one-line summary, as a Markdown table.",
            mime_type=_MARKDOWN,
            read=_read_command_reference,
        ),
        Resource(
            uri=SCHEMA_URI,
            name="action-schema",
            title="Action file JSON Schema",
            description="The JSON Schema (draft 2020-12) of an action file: a list of actions, or an object "
                        "with meta and webdriver_wrapper.",
            mime_type=_JSON,
            read=_read_action_schema,
        ),
        Resource(
            uri=GUIDE_URI,
            name="action-language-guide",
            title="How to write an action file",
            description="A short guide to action files: action shapes, variables and ${name}, control-flow "
                        "blocks and conditions, WR_call_file, meta keys, datasets and locator files.",
            mime_type=_MARKDOWN,
            read=lambda: ACTION_LANGUAGE_GUIDE,
        ),
    ]


def build_default_resource_templates() -> list[ResourceTemplate]:
    """The resource templates shipped with the server."""
    return [
        ResourceTemplate(
            uri_template=COMMAND_URI_TEMPLATE,
            name="command",
            title="One WR_* command",
            description="One command's signature and full documentation; {name} is a name from "
                        "webrunner://commands or webrunner_list_commands, e.g. WR_to_url.",
            mime_type=_MARKDOWN,
            read=_read_command,
        ),
    ]
