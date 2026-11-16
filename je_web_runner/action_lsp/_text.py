"""
LSP 位置與文字偏移量的換算
LSP positions and text offsets. A position is a zero-based line and a character counted in UTF-16 code
units, which is what a client sends unless another encoding was negotiated; an offset is an index into the
Python string.
"""
from __future__ import annotations

from typing import Any

_ASTRAL = 0x10000


def _units(char: str) -> int:
    """How many UTF-16 code units ``char`` takes."""
    return 2 if ord(char) >= _ASTRAL else 1


def offset_at(text: str, line: int, character: int) -> int:
    """The offset of a position; a position past the end of its line or of the text is clamped."""
    start = 0
    for _ in range(max(0, line)):
        newline = text.find("\n", start)
        if newline == -1:
            return len(text)
        start = newline + 1
    offset = start
    units = 0
    while offset < len(text) and text[offset] not in "\r\n" and units < character:
        units += _units(text[offset])
        offset += 1
    return offset


def position_at(text: str, offset: int) -> dict[str, int]:
    """The position of an offset."""
    offset = max(0, min(offset, len(text)))
    line_start = text.rfind("\n", 0, offset) + 1
    return {
        "line": text.count("\n", 0, offset),
        "character": sum(_units(char) for char in text[line_start:offset]),
    }


def range_between(text: str, start: int, end: int) -> dict[str, dict[str, int]]:
    """The range from one offset to another."""
    return {"start": position_at(text, start), "end": position_at(text, end)}


def request_offset(text: str, params: dict[str, Any]) -> int | None:
    """The offset of the ``position`` of a request, or None when it has none."""
    position = params.get("position")
    if not isinstance(position, dict):
        return None
    line = position.get("line")
    character = position.get("character")
    if not isinstance(line, int) or not isinstance(character, int):
        return None
    return offset_at(text, line, character)
