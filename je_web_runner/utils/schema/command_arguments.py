"""
由命令簽章產生引數的 JSON Schema
The JSON Schema of each command's keyword arguments, read from the command's signature: the names it
takes, the ones it requires, and a type where the annotation names one JSON can express.

It is advisory, for editors. The types are loose on purpose, so that a file that runs is not flagged:
``int`` and ``float`` are both ``number``, an annotation the mapping does not know puts no constraint on
the value, and any argument may be a ``${placeholder}`` string, whose value is only known at run time.
"""
from __future__ import annotations

import inspect
import re
from typing import Any, Callable, Iterable, Mapping

PLACEHOLDER_REF = {"$ref": "#/definitions/placeholder"}
# A string holding ``${name}``: the executor replaces it before the command sees the value.
PLACEHOLDER_SCHEMA = {"type": "string", "pattern": "\\$\\{[^}]+\\}"}
NUMBER_TEXT_REF = {"$ref": "#/definitions/number_text"}
# A number written as text (``"3"``): existing files do that and the browser drivers accept it.
NUMBER_TEXT_SCHEMA = {"type": "string", "pattern": "^-?[0-9]+(\\.[0-9]+)?$"}

_NAMED = (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
# The head of an annotation (``list[str]`` -> ``list``) -> the JSON type.
_JSON_TYPES = {
    "str": "string",
    "int": "number", "float": "number",
    "bool": "boolean",
    "list": "array", "List": "array", "tuple": "array", "Tuple": "array",
    "Sequence": "array", "Iterable": "array",
    "dict": "object", "Dict": "object", "Mapping": "object",
    "None": "null", "NoneType": "null",
}


def _annotation_text(annotation: Any) -> str | None:
    """``annotation`` as source text, or None when the parameter has none."""
    if annotation is inspect.Parameter.empty:
        return None
    if isinstance(annotation, str):
        return annotation
    return getattr(annotation, "__name__", None) or str(annotation)


def _union_members(text: str) -> list[str]:
    """The members of ``A | B[C | D] | None``, split at the top level only."""
    members, depth, current = [], 0, ""
    for character in text:
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
        if character == "|" and depth == 0:
            members.append(current.strip())
            current = ""
        else:
            current += character
    return [*members, current.strip()]


def _json_types(text: str) -> list[str] | None:
    """The JSON types of an annotation, or None when a member of it is not one of the known ones."""
    types: list[str] = []
    for member in _union_members(text):
        head = member.split("[", 1)[0].strip().rsplit(".", 1)[-1]
        json_type = _JSON_TYPES.get(head)
        if json_type is None:
            return None
        if json_type not in types:
            types.append(json_type)
    return types


def value_schema(parameter: inspect.Parameter) -> dict[str, Any]:
    """The schema of one argument: its JSON types or a placeholder; ``{}`` when the type is not known."""
    text = _annotation_text(parameter.annotation)
    types = _json_types(text) if text else None
    if not types:
        return {}
    if parameter.default is None and "null" not in types:
        types = [*types, "null"]
    typed: dict[str, Any] = {"type": types[0] if len(types) == 1 else types}
    if "string" in types:
        return typed
    alternatives = [typed, PLACEHOLDER_REF]
    if "number" in types:
        alternatives.append(NUMBER_TEXT_REF)
    return {"anyOf": alternatives}


def arguments_schema(command: Callable[..., Any]) -> dict[str, Any] | None:
    """
    The schema of the arguments object of ``command`` (the ``{...}`` of ``["WR_x", {...}]``), or None
    when Python cannot read its signature. A command taking ``**kwargs`` accepts other names too.
    """
    try:
        parameters = list(inspect.signature(command).parameters.values())
    except (TypeError, ValueError):
        return None
    named = [parameter for parameter in parameters if parameter.kind in _NAMED]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {parameter.name: value_schema(parameter) for parameter in named},
        "additionalProperties": any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters),
    }
    required = [parameter.name for parameter in named if parameter.default is inspect.Parameter.empty]
    if required:
        schema["required"] = required
    return schema


def name_pattern(names: Iterable[str]) -> str:
    """A pattern matching exactly one of ``names`` (a command and its aliases)."""
    return "^(" + "|".join(re.escape(name) for name in names) + ")$"


def _shared_values(schemas: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """
    Move the value schemas that many arguments repeat (``number`` or a placeholder ...) into one
    definition each and leave a reference in their place; returns those definitions by name. It keeps
    the exported file a fraction of the size it would have with every argument spelled out.
    """
    shared: dict[str, Any] = {}
    for schema in schemas:
        for name, value in schema["properties"].items():
            if "anyOf" not in value:
                continue
            types = value["anyOf"][0]["type"]
            key = types if isinstance(types, str) else "_or_".join(types)
            shared[key] = value
            schema["properties"][name] = {"$ref": f"#/definitions/values/{key}"}
    return shared


def command_argument_rules(
        commands: Mapping[str, Callable[..., Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """
    ``(definitions, rules, values)`` for ``commands``. ``definitions`` holds one arguments schema per
    distinct command, under the first of its names; each rule is an ``if`` / ``then`` pair applying that
    schema to an action whose name is the command or one of its aliases and whose second item is an
    object; ``values`` holds the value schemas the arguments share (``#/definitions/values/<name>``).
    The positional form (``["WR_x", [values]]``) is left to the linter.
    """
    names_of: dict[int, list[str]] = {}
    schema_of: dict[int, dict[str, Any]] = {}
    for name in sorted(commands):
        command = commands[name]
        key = id(getattr(command, "__func__", command))
        if key not in schema_of:
            schema = arguments_schema(command)
            if schema is None:
                continue
            schema_of[key] = schema
        names_of.setdefault(key, []).append(name)
    definitions = {names[0]: schema_of[key] for key, names in names_of.items()}
    rules = [
        {
            "if": {"prefixItems": [{"pattern": name_pattern(names)}, {"type": "object"}], "minItems": 2},
            "then": {"prefixItems": [{}, {"$ref": f"#/definitions/arguments/{names[0]}"}]},
        }
        for names in names_of.values()
    ]
    return definitions, rules, _shared_values(definitions.values())
