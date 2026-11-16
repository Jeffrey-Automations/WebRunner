"""
Action JSON Schema 匯出：給 IDE 做語法高亮 / 自動補完。
JSON Schema export for action JSON files. Pulls every registered
``WR_*`` command name from the executor and emits a Draft 2020-12 schema
that IDEs can use to validate and autocomplete.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.schema.command_arguments import (
    NUMBER_TEXT_SCHEMA,
    PLACEHOLDER_SCHEMA,
    command_argument_rules,
)


class SchemaExportError(WebRunnerException):
    """Raised when a target path cannot be written."""


def _commands() -> dict[str, Any]:
    """Every registered ``WR_*`` command of the executor singleton, by name."""
    # Imported lazily to avoid an import cycle with the executor module.
    from je_web_runner.utils.executor.action_executor import executor
    return {name: command for name, command in executor.event_dict.items()
            if isinstance(name, str) and name.startswith("WR_")}


def build_action_schema(arguments: bool = True) -> dict[str, Any]:
    """
    產生一份描述 action JSON 結構的 Draft 2020-12 Schema
    Build a Draft 2020-12 JSON Schema describing the action JSON format.

    The first slot of every action is constrained to the enum of registered
    command names. With ``arguments`` (the default), an action whose second
    slot is an object is also checked against its command's signature: the
    argument names it takes, the ones it requires, and loose types (see
    :mod:`command_arguments`). The positional form stays unchecked here; the
    linter covers it. ``arguments=False`` leaves that part out, which keeps
    the schema small enough to read.
    """
    web_runner_logger.info("build_action_schema")
    commands = _commands()
    command_enum = sorted(commands)
    argument_definitions, argument_rules, shared_values = (
        command_argument_rules(commands) if arguments else ({}, [], {}))
    action_schema: dict[str, Any] = {
        "type": "array",
        "minItems": 1,
        "maxItems": 3,
        "prefixItems": [
            {"type": "string", "enum": command_enum, "title": "WebRunner command"},
            {"oneOf": [{"type": "object"}, {"type": "array"}]},
            {"type": "object"},
        ],
        "items": False,
    }
    if argument_rules:
        action_schema["allOf"] = argument_rules
    list_form = {
        "type": "array",
        "items": {"$ref": "#/definitions/action"},
    }
    dict_form = {
        "type": "object",
        "properties": {
            "webdriver_wrapper": list_form,
            "meta": {
                "type": "object",
                "properties": {
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "skip": {"type": "string", "minLength": 1,
                             "description": "Reason the file does not run."},
                    "vars": {"type": "object",
                             "description": "Default variables, set unless already set."},
                    "setup": list_form,
                    "teardown": list_form,
                    "retries": {"type": "integer", "minimum": 0, "maximum": 100},
                    "retry_backoff": {"type": "number", "minimum": 0},
                    "fail_fast": {"type": "boolean"},
                    "dataset": {
                        "oneOf": [{"type": "string", "minLength": 1},
                                  {"type": "array", "items": {"type": "object"}}],
                        "description": "A .csv / .json file, or the rows; the actions run once per row.",
                    },
                },
                "additionalProperties": True,
            },
        },
        "required": ["webdriver_wrapper"],
        "additionalProperties": True,
    }
    definitions: dict[str, Any] = {"action": action_schema}
    if arguments:
        definitions.update(placeholder=PLACEHOLDER_SCHEMA, number_text=NUMBER_TEXT_SCHEMA,
                           values=shared_values, arguments=argument_definitions)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "WebRunner action JSON",
        "description": "Generated from the runtime executor event_dict.",
        "definitions": definitions,
        "oneOf": [list_form, dict_form],
    }


def schema_text(schema: dict[str, Any]) -> str:
    """
    ``schema`` as indented JSON, except that each command's argument rule and argument definition is on
    one line: there are over a thousand of each, and indenting them would triple the file while a
    change to one command would still touch only its own lines.
    """
    compact: dict[str, str] = {}

    def one_line(value: Any) -> str:
        marker = f"@@compact-{len(compact)}@@"
        compact[f'"{marker}"'] = json.dumps(value, ensure_ascii=False)
        return marker

    outline = json.loads(json.dumps(schema))
    definitions = outline.get("definitions", {})
    action = definitions.get("action", {})
    if "allOf" in action:
        action["allOf"] = [one_line(rule) for rule in action["allOf"]]
    if "arguments" in definitions:
        definitions["arguments"] = {name: one_line(value) for name, value in definitions["arguments"].items()}
    text = json.dumps(outline, indent=2, ensure_ascii=False)
    for marker, value in compact.items():
        text = text.replace(marker, value)
    return text


def export_schema(path: str) -> str:
    """
    將 Schema 寫到 ``path`` 並回傳寫出的路徑
    Write the schema to ``path`` and return the resolved path.
    """
    web_runner_logger.info(f"export_schema: {path}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(schema_text(build_action_schema()), encoding="utf-8")
    except OSError as error:
        raise SchemaExportError(f"failed to write schema: {error}") from error
    return str(target.resolve())
