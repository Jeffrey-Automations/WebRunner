"""
檢查動作檔的 MCP 工具 / The offline MCP tools that check an action file before it runs.

They are part of :func:`je_web_runner.mcp_server.offline_tools.build_default_tools`; each
handler imports its WebRunner module lazily, like the tools there.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.mcp_server._policy import checked_path
from je_web_runner.mcp_server._schema import arg as _arg
from je_web_runner.mcp_server._schema import args_schema as _args
from je_web_runner.mcp_server._types import READ_ONLY, McpServerError, Tool

_FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "rule": {"type": "string"},
        "severity": {"type": "string"},
        "message": {"type": "string"},
        "location": {"type": "string"},
    },
}


def _tool_validate_action(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
    from je_web_runner.utils.json.json_validator import validate_action_json
    document = arguments.get("actions")
    if not isinstance(document, (list, dict)):
        raise McpServerError("'actions' must be an action list or an object with 'webdriver_wrapper'")
    try:
        validate_action_json(document)
    except WebRunnerExecuteException as error:
        # The validator stops at the first problem, so there is one message at most.
        return {"valid": False, "errors": [str(error)]}
    return {"valid": True, "errors": []}


def _tool_lint_action_file(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.linter.action_linter import lint_action_file, severity_counts
    path = checked_path(str(arguments.get("path", "")))
    findings = lint_action_file(path)
    return {"path": path, "findings": findings, "counts": severity_counts(findings)}


def _tool_translate_backend(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sel_to_pw.backend_translate import BackendTranslationError, translate_for_backend
    from je_web_runner.utils.sel_to_pw.translator import SelToPwError
    document = arguments.get("actions")
    backend = arguments.get("backend", "playwright")
    if not isinstance(document, (list, dict)):
        raise McpServerError("'actions' must be an action list or an object with 'webdriver_wrapper'")
    try:
        return {"translated": True, "actions": translate_for_backend(document, backend), "problems": []}
    except BackendTranslationError as error:
        problems = [{"location": problem.location, "command": problem.command, "reason": problem.reason}
                    for problem in error.problems]
        return {"translated": False, "actions": None, "problems": problems}
    except SelToPwError as error:
        raise McpServerError(str(error)) from error


def _translate_backend_tool() -> Tool:
    return Tool(
        name="webrunner_translate_backend",
        title="Translate an action file to the other backend",
        description=(
            "Translate an action list or document to the commands of one backend: 'playwright' (from"
            " WR_* Selenium commands) or 'selenium' (from WR_pw_*). Arguments are converted (seconds to"
            " milliseconds, locators to selectors) and nested blocks, meta.setup and meta.teardown are"
            " included. Nothing is dropped silently: when a command has no faithful equivalent the"
            " result is {'translated': false, 'problems': [{location, command, reason}]} naming every"
            " one; otherwise {'translated': true, 'actions': <same shape as the input>}. Nothing runs."
        ),
        input_schema=_args(
            ("actions",),
            actions=_arg(None, "The action list, or the whole document object ({meta, webdriver_wrapper})."),
            backend=_arg("string", "'playwright' (default) or 'selenium'."),
        ),
        handler=_tool_translate_backend,
        annotations=READ_ONLY,
        output_schema={
            "type": "object",
            "properties": {
                "translated": {"type": "boolean"},
                "actions": {},
                "problems": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["translated", "problems"],
        },
    )


def build_authoring_tools() -> list[Tool]:
    """The tools that validate, lint and translate action files."""
    return [
        _translate_backend_tool(),
        Tool(
            name="webrunner_validate_action",
            title="Validate an action file's structure",
            description=(
                "Check that an action list, or an object document with meta and webdriver_wrapper, has the"
                " structure the executor accepts: the shape of every action, of the actions inside blocks"
                " and of meta.setup / meta.teardown. Returns {'valid': bool, 'errors': [message]}; the"
                " check stops at the first problem. It does not check command names or arguments:"
                " webrunner_lint_action does."
            ),
            input_schema=_args(
                ("actions",),
                actions=_arg(None, "The action list, or the whole document object ({meta, webdriver_wrapper})."),
            ),
            handler=_tool_validate_action,
            annotations=READ_ONLY,
            output_schema={
                "type": "object",
                "properties": {
                    "valid": {"type": "boolean"},
                    "errors": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["valid", "errors"],
            },
        ),
        Tool(
            name="webrunner_lint_action_file",
            title="Lint an action file on disk",
            description=(
                "Read one action JSON file from disk and lint it, meta included: unknown commands, legacy"
                " names, hard-coded URLs, wrong arguments, mistakes in blocks and variables. Returns"
                " {'path': str, 'findings': [{rule, severity, message, location}], 'counts': {severity:"
                " number}}. With WEBRUNNER_MCP_ROOT set, the file must be inside that directory."
            ),
            input_schema=_args(("path",), path=_arg("string", "Path of the action JSON file.")),
            handler=_tool_lint_action_file,
            annotations=READ_ONLY,
            output_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "findings": {"type": "array", "items": _FINDING_SCHEMA},
                    "counts": {"type": "object"},
                },
                "required": ["path", "findings", "counts"],
            },
        ),
    ]
