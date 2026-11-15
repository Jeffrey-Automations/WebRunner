"""
找出每個動作在文件中的行號
Where each action of an action document starts, so a lint finding lands on the action it is about.

The linter reports ``action[<index>]``; an editor needs a line. The document is scanned as JSON text (strings,
brackets, commas) without building values, so it works on the exact text the editor holds.
"""
from __future__ import annotations

from typing import Iterator

_WRAPPER_KEY = '"webdriver_wrapper"'
_OPENERS = "[{"
_CLOSERS = "]}"
_SEPARATORS = ",:"


def _string_end(text: str, index: int) -> int:
    """The offset after the string that opens at ``index`` (the end of the text if it never closes)."""
    index += 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return index + 1
        index += 1
    return len(text)


def _tokens(text: str) -> Iterator[tuple[int, str, int]]:
    """``(offset, token, depth)``: whole strings, brackets, separators and each character of a scalar."""
    index = 0
    depth = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            end = _string_end(text, index)
            yield index, text[index:end], depth
            index = end
            continue
        if char in _OPENERS:
            yield index, char, depth
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
            yield index, char, depth
        elif not char.isspace():
            yield index, char, depth
        index += 1


def _array_start(text: str, dict_root: bool) -> int | None:
    """The offset of the ``[`` that opens the action list, or None when the text has none."""
    tokens = list(_tokens(text))
    if not dict_root:
        return tokens[0][0] if tokens and tokens[0][1] == "[" else None
    for position in range(len(tokens) - 2):
        _offset, token, depth = tokens[position]
        if depth == 1 and token == _WRAPPER_KEY and tokens[position + 1][1] == ":" \
                and tokens[position + 2][1] == "[":
            return tokens[position + 2][0]
    return None


def _element_offsets(text: str, array_start: int) -> list[int]:
    """The offset of every element of the array that opens at ``array_start``."""
    offsets: list[int] = []
    array_depth: int | None = None
    expecting = True
    for offset, token, depth in _tokens(text):
        if offset == array_start:
            array_depth = depth
            continue
        if array_depth is None:
            continue
        if token == "]" and depth == array_depth:
            break
        if depth != array_depth + 1:
            continue
        if token == ",":
            expecting = True
        elif expecting:
            offsets.append(offset)
            expecting = False
    return offsets


def action_lines(text: str, dict_root: bool) -> list[int]:
    """
    每個動作起始的行號（從 0 起算）
    The zero-based line each action starts on; ``dict_root`` picks the ``webdriver_wrapper`` list of an object
    document instead of the top-level list. Empty when the list cannot be found.
    """
    start = _array_start(text, dict_root)
    if start is None:
        return []
    return [text.count("\n", 0, offset) for offset in _element_offsets(text, start)]
