"""
工具 input schema 的小工具 / Helpers that build a tool's input schema, shared by the tool modules.
"""
from __future__ import annotations

from typing import Any


def args_schema(required: tuple[str, ...], **properties: dict[str, Any]) -> dict[str, Any]:
    """A closed ``object`` input schema: unknown arguments are rejected."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def arg(json_type: str | None, description: str, **extra: Any) -> dict[str, Any]:
    """One described property; ``json_type=None`` accepts any JSON value."""
    spec: dict[str, Any] = {"description": description, **extra}
    if json_type:
        spec["type"] = json_type
    return spec
