"""
游標所在位置的語意
What the cursor of an editor is on, in an action document that may be half typed.

:func:`scan` reads the text up to the cursor and nothing after it, so a document that is not valid JSON yet
is no obstacle: it tracks strings (with their escapes), the open brackets, the element an array is at and
whether an object waits for a key or a value. The other functions say what the open brackets mean in an
action file: which array is an action, which object holds the keyword arguments of which command.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Sequence

from je_web_runner.action_lsp._positions import _tokens
from je_web_runner.utils.flow.structure import ACTION_ARGUMENTS, BLOCK_ARGUMENTS, CONDITION_ARGUMENTS

ARRAY = "["
OBJECT = "{"
# What an object waits for.
KEY = "key"
COLON = "colon"
VALUE = "value"

_WRAPPER_KEY = "webdriver_wrapper"
_META_KEY = "meta"
_HOOK_KEYS = ("setup", "teardown")
_SUCCEEDS_KEY = "succeeds"
_KEYWORD_SLOTS = (1, 2)


@dataclass
class Frame:  # pylint: disable=too-many-instance-attributes  # the scan state of an array and of an object
    """
    One bracket that is open at the cursor.

    For an array: ``index`` is the element the cursor is in, ``filled`` whether that element has content
    before the cursor, ``first`` the first element when it is a complete string. For an object: ``state`` is
    what it waits for, ``key`` the key whose value the cursor is in, ``keys`` the keys written before the
    cursor.
    """
    kind: str
    start: int
    index: int = 0
    filled: bool = False
    first: str | None = None
    state: str = KEY
    key: str | None = None
    pending: str | None = None
    keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CursorContext:
    """The open brackets at the cursor, outermost first, and the string the cursor is inside (if any)."""
    frames: tuple[Frame, ...]
    string_start: int | None = None
    typed: str = ""

    @property
    def in_string(self) -> bool:
        """Whether the cursor is inside a string."""
        return self.string_start is not None


def _closing_quote(text: str, start: int, end: int) -> int | None:
    """The offset of the quote that closes the string opened at ``start``, None when none does before ``end``."""
    index = start + 1
    while index < end:
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return index
        index += 1
    return None


def _decoded(raw: str) -> str:
    """The value of a JSON string token; the text between the quotes when it does not decode."""
    try:
        return str(json.loads(raw))
    except ValueError:
        return raw[1:-1]


def _note_string(frames: list[Frame], raw: str) -> None:
    """A complete string was read."""
    if not frames:
        return
    frame = frames[-1]
    if frame.kind == OBJECT:
        if frame.state == KEY:
            frame.pending = _decoded(raw)
            frame.state = COLON
        return
    if frame.index == 0 and not frame.filled:
        frame.first = _decoded(raw)
    frame.filled = True


def _note_separator(frame: Frame, char: str) -> None:
    """A comma, a colon or a character of a scalar was read inside ``frame``."""
    if frame.kind == ARRAY:
        if char == ",":
            frame.index += 1
            frame.filled = False
        else:
            frame.filled = True
        return
    if char == ",":
        frame.state = KEY
        frame.key = None
    elif char == ":" and frame.state == COLON and frame.pending is not None:
        frame.key = frame.pending
        frame.keys.append(frame.pending)
        frame.state = VALUE


def _note_char(frames: list[Frame], char: str, offset: int) -> None:
    """A character outside a string was read."""
    if char.isspace():
        return
    if char in "[{":
        if frames:
            frames[-1].filled = True
        frames.append(Frame(kind=char, start=offset))
    elif char in "]}":
        if frames:
            frames.pop()
    elif frames:
        _note_separator(frames[-1], char)


def scan(text: str, offset: int) -> CursorContext:
    """
    讀到游標為止，回報游標所在的括號與字串
    Read ``text`` up to ``offset`` and report the brackets that are open there and the string the cursor is
    inside. Nothing after the cursor is read, and a bracket that closes what was never opened is ignored.
    """
    frames: list[Frame] = []
    end = max(0, min(offset, len(text)))
    index = 0
    while index < end:
        char = text[index]
        if char != '"':
            _note_char(frames, char, index)
            index += 1
            continue
        close = _closing_quote(text, index, end)
        if close is None:
            return CursorContext(tuple(frames), index, text[index + 1:end])
        _note_string(frames, text[index:close + 1])
        index = close + 1
    return CursorContext(tuple(frames))


def keys_after(text: str, start: int, skip_first: bool) -> list[str]:
    """
    The keys written after ``start`` in the object that is open there. ``skip_first`` leaves out the token
    at ``start``: the string the cursor is inside.
    """
    direct = [token for _offset, token, depth in _upto_close(text, start) if depth == 0]
    if skip_first:
        direct = direct[1:]
    return [_decoded(token) for position, token in enumerate(direct[:-1])
            if token.startswith('"') and direct[position + 1] == ":"]


def _upto_close(text: str, start: int) -> list[tuple[int, str, int]]:
    """The tokens from ``start`` to the bracket that closes the container open there."""
    tokens: list[tuple[int, str, int]] = []
    for token in _tokens(text, start):
        if token[2] < 0:
            break
        tokens.append(token)
    return tokens


def is_action(frames: Sequence[Frame], depth: int) -> bool:
    """Whether ``frames[depth]`` is the array of an action, at the top level or inside a block."""
    if depth < 1 or frames[depth].kind != ARRAY:
        return False
    if frames[depth - 1].kind == ARRAY:
        return is_action_list(frames, depth - 1)
    return _holds_one_action(frames, depth - 1)


def is_action_list(frames: Sequence[Frame], depth: int) -> bool:
    """Whether ``frames[depth]`` is a list of actions: the document's, a hook's, or a block's."""
    if frames[depth].kind != ARRAY:
        return False
    if depth == 0:
        return True
    owner = frames[depth - 1]
    if owner.kind != OBJECT:
        return False
    if depth == 1:
        return owner.key == _WRAPPER_KEY
    if depth == 2 and frames[0].kind == OBJECT and frames[0].key == _META_KEY:
        return owner.key in _HOOK_KEYS
    command = keyword_command(frames, depth - 1)
    return command is not None and owner.key in BLOCK_ARGUMENTS.get(command, ())


def _holds_one_action(frames: Sequence[Frame], depth: int) -> bool:
    """Whether the value the object ``frames[depth]`` is at is a single action."""
    key = frames[depth].key
    if key == _SUCCEEDS_KEY:
        return _in_condition(frames, depth - 1)
    command = keyword_command(frames, depth)
    return command is not None and key in ACTION_ARGUMENTS.get(command, ())


def _in_condition(frames: Sequence[Frame], depth: int) -> bool:
    """Whether what is below ``frames[depth]`` is part of the condition of a block command."""
    while depth >= 1:
        command = keyword_command(frames, depth)
        if command is not None:
            return frames[depth].key in CONDITION_ARGUMENTS.get(command, ())
        depth -= 1
    return False


def keyword_command(frames: Sequence[Frame], depth: int) -> str | None:
    """The command whose keyword arguments the object ``frames[depth]`` holds, None when it holds none."""
    if depth < 1 or frames[depth].kind != OBJECT:
        return None
    owner = frames[depth - 1]
    if owner.index not in _KEYWORD_SLOTS or owner.first is None or not is_action(frames, depth - 1):
        return None
    return owner.first
