"""
LLM tool / function-call assertions.

Tools (a.k.a. function calls) are the seam where an LLM crosses from
"text generation" into "side effects". Tests that exercise this seam
need to check:

* The right tool name was called (no off-by-one swap).
* Arguments match the tool's JSON Schema (no missing required key,
  no extra unknown key, types align).
* No forbidden tool was invoked (caller can list a denylist).
* Tool was called at least N times / at most N times.
* In multi-tool chains, the call order matches an expected sequence.

The module is schema-light: it implements just enough of JSON Schema
(``type``, ``required``, ``properties``, ``enum``) to catch the common
contract bugs without dragging ``jsonschema`` in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ToolCallAssertError(WebRunnerException):
    """Raised on tool-call protocol violation."""


@dataclass
class ToolCall:
    """One tool call made by the model; an empty name or non-dict arguments raise ``ToolCallAssertError``."""
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ToolCallAssertError("tool name required")
        if not isinstance(self.arguments, dict):
            raise ToolCallAssertError("arguments must be a dict")


JSON_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str, "integer": int, "number": (int, float),
    "boolean": bool, "object": dict, "array": list,
}


def parse_calls(payload: Any) -> list[ToolCall]:
    """Turn a list of tool-call dicts into ``ToolCall`` records, skipping entries that
    are not dicts. Raises ``ToolCallAssertError`` when the payload is not a list.
    """
    if not isinstance(payload, list):
        raise ToolCallAssertError("payload must be a list of tool-call dicts")
    out: list[ToolCall] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(ToolCall(
            name=str(raw.get("name") or ""),
            arguments=dict(raw.get("arguments") or {}),
            call_id=str(raw.get("call_id") or ""),
        ))
    return out


def assert_called(
    calls: Iterable[ToolCall], *, name: str, times: int | None = None,
    min_times: int | None = None, max_times: int | None = None,
) -> list[ToolCall]:
    """Return the calls to tool ``name``, after checking their number against ``times``
    (exact), ``min_times`` and ``max_times`` when given. Raises ``ToolCallAssertError``
    when a bound is not met.
    """
    if not name:
        raise ToolCallAssertError("name must be non-empty")
    matches = [c for c in calls if c.name == name]
    if times is not None:
        if times < 0:
            raise ToolCallAssertError("times must be >= 0")
        if len(matches) != times:
            raise ToolCallAssertError(
                f"tool {name!r} called {len(matches)} times, expected {times}"
            )
    if min_times is not None and len(matches) < min_times:
        raise ToolCallAssertError(
            f"tool {name!r} called {len(matches)} times, expected >= {min_times}"
        )
    if max_times is not None and len(matches) > max_times:
        raise ToolCallAssertError(
            f"tool {name!r} called {len(matches)} times, expected <= {max_times}"
        )
    return matches


def assert_not_called(
    calls: Iterable[ToolCall], *, denylist: Sequence[str],
) -> None:
    """Raise ``ToolCallAssertError`` when a tool named in ``denylist`` was called."""
    if not denylist:
        raise ToolCallAssertError("denylist must be non-empty")
    bad = [c for c in calls if c.name in denylist]
    if bad:
        raise ToolCallAssertError(
            f"forbidden tool(s) called: {[c.name for c in bad]}"
        )


def _validate_object(args: Any, schema: Mapping[str, Any], path: str) -> None:
    if not isinstance(args, dict):
        raise ToolCallAssertError(
            f"{path or 'arguments'}: expected object, got {type(args).__name__}"
        )
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    for key in required:
        if key not in args:
            raise ToolCallAssertError(
                f"{path or 'arguments'}: missing required key {key!r}"
            )
    for key, value in args.items():
        if key in properties:
            _validate_against_schema(value, properties[key], f"{path}.{key}")
        elif schema.get("additionalProperties") is False:
            raise ToolCallAssertError(
                f"{path or 'arguments'}: unknown key {key!r}"
            )


def _validate_against_schema(args: Mapping[str, Any],
                             schema: Mapping[str, Any], path: str = "") -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        _validate_object(args, schema, path)
        return
    if schema_type and schema_type in JSON_TYPE_MAP:
        expected = JSON_TYPE_MAP[schema_type]
        # bool is an int subclass in Python; in JSON Schema a boolean is not an integer or a number.
        is_number_type = schema_type in ("integer", "number")
        if not isinstance(args, expected) or (is_number_type and isinstance(args, bool)):
            raise ToolCallAssertError(
                f"{path or 'value'}: expected {schema_type}, "
                f"got {type(args).__name__}"
            )
    if "enum" in schema and args not in schema["enum"]:
        raise ToolCallAssertError(
            f"{path or 'value'}: {args!r} not in enum {schema['enum']}"
        )


def assert_args_match_schema(
    call: ToolCall, schema: Mapping[str, Any],
) -> None:
    """Raise ``ToolCallAssertError`` when the call's arguments do not satisfy ``schema``."""
    if not isinstance(schema, Mapping):
        raise ToolCallAssertError("schema must be a mapping")
    _validate_against_schema(call.arguments, schema)


def assert_call_order(
    calls: Iterable[ToolCall], *, expected: Sequence[str],
) -> None:
    """Raise ``ToolCallAssertError`` unless the tool names, in call order, equal ``expected``."""
    actual = [c.name for c in calls]
    if actual != list(expected):
        raise ToolCallAssertError(
            f"tool call order mismatch: expected {list(expected)}, got {actual}"
        )
