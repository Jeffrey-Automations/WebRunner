"""
找出每個動作在文件中的行號
Where each action of an action document starts, so a lint finding lands on the action it is about.

The linter reports ``action[<index>]`` for a top-level action and a longer path for what is inside it
(``action[1].do[0]``, ``action[2].condition.succeeds``, ``meta.setup[0]``, ``action[0].args[0].url``); an
editor needs a line. The document is scanned as JSON text (strings, brackets, commas) without building
values, so it works on the exact text the editor holds.
"""
from __future__ import annotations

import json
import re
from typing import Iterator

_WRAPPER_KEY = '"webdriver_wrapper"'
_OPENERS = "[{"
_CLOSERS = "]}"
_SEPARATORS = ",:"
# One step of a linter location: ``.name`` or ``[index]`` (the first name has no dot).
_STEP = re.compile(r"\.?([^.\[\]]+)|\[(\d+)]")
_ACTION_ROOT = "action"
_META_ROOT = "meta"
# ``action[1].args[0]`` is the first slot after the command name.
_ARGUMENT_SLOTS = "args"


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


def _tokens(text: str, start: int = 0) -> Iterator[tuple[int, str, int]]:
    """
    ``(offset, token, depth)`` from ``start`` on: whole strings, brackets, separators and each character of
    a scalar. The depth counts from ``start``.
    """
    index = start
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


def _direct_tokens(text: str, container_start: int) -> Iterator[tuple[int, str]]:
    """``(offset, token)`` for the tokens directly inside the container that opens at ``container_start``."""
    tokens = _tokens(text, container_start)
    next(tokens, None)
    for offset, token, depth in tokens:
        if depth == 0:
            return
        if depth == 1:
            yield offset, token


def _element_offsets(text: str, array_start: int) -> list[int]:
    """The offset of every element of the array that opens at ``array_start``."""
    offsets: list[int] = []
    expecting = True
    for offset, token in _direct_tokens(text, array_start):
        if token == ",":
            expecting = True
        elif expecting:
            offsets.append(offset)
            expecting = False
    return offsets


def _member_offsets(text: str, object_start: int) -> dict[str, int]:
    """The offset of the value of every member of the object that opens at ``object_start``, by key."""
    direct = list(_direct_tokens(text, object_start))
    members: dict[str, int] = {}
    for position in range(2, len(direct)):
        key_token = direct[position - 2][1]
        if direct[position - 1][1] != ":" or not key_token.startswith('"'):
            continue
        try:
            key = json.loads(key_token)
        except ValueError:
            continue
        members[str(key)] = direct[position][0]
    return members


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


def location_steps(location: str) -> list[str | int]:
    """``action[1].do[0]`` as ``["action", 1, "do", 0]``."""
    return [int(index) if index else name for name, index in _STEP.findall(location)]


class LocationIndex:
    """
    文件中每個 linter 位置的偏移量
    The offsets of what the linter locations of one document name. Each container of the text is scanned at
    most once, however many findings point into it.
    """

    def __init__(self, text: str, dict_root: bool) -> None:
        self._text = text
        self._dict_root = dict_root
        self._elements: dict[int, list[int]] = {}
        self._members: dict[int, dict[str, int]] = {}

    def offset(self, location: str) -> int | None:
        """
        The offset where the value ``location`` names starts. A location that goes deeper than the text can
        be followed gives the deepest value found; one whose root is missing gives None.
        """
        steps = location_steps(location)
        current = self._root(steps[0]) if steps else None
        if current is None:
            return None
        shift = 0
        for step in steps[1:]:
            if step == _ARGUMENT_SLOTS and self._text[current] == "[":
                shift = 1
                continue
            following = self._child(current, step, shift)
            if following is None:
                break
            current = following
            shift = 0
        return current

    def line(self, location: str) -> int:
        """The zero-based line of ``location``; 0 when it cannot be found."""
        offset = self.offset(location)
        return 0 if offset is None else self._text.count("\n", 0, offset)

    def _root(self, name: str | int) -> int | None:
        if name == _ACTION_ROOT:
            return _array_start(self._text, self._dict_root)
        if name == _META_ROOT and self._dict_root:
            first = next(_tokens(self._text), None)
            return None if first is None else self._member(first[0], _META_ROOT)
        return None

    def _child(self, offset: int, step: str | int, shift: int) -> int | None:
        """The value one step below the value at ``offset``."""
        if isinstance(step, int):
            return self._element(offset, step + shift)
        if self._text[offset] == "[":
            # A name below an action is one of its keyword arguments.
            slots = [slot for slot in self.elements(offset)[1:3] if self._text[slot] == "{"]
            return self._member(slots[0], step) if slots else None
        return self._member(offset, step)

    def elements(self, offset: int) -> list[int]:
        """The offsets of the elements of the array at ``offset`` (empty for another value)."""
        if self._text[offset] != "[":
            return []
        if offset not in self._elements:
            self._elements[offset] = _element_offsets(self._text, offset)
        return self._elements[offset]

    def _element(self, offset: int, index: int) -> int | None:
        elements = self.elements(offset)
        return elements[index] if 0 <= index < len(elements) else None

    def _member(self, offset: int, key: str) -> int | None:
        if self._text[offset] != "{":
            return None
        if offset not in self._members:
            self._members[offset] = _member_offsets(self._text, offset)
        return self._members[offset].get(key)
