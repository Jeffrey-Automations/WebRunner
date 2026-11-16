"""
依游標位置給出補全
Completion that depends on where the cursor is: command names in the first element of an action, parameter
names on a key of its keyword arguments, variable names after ``${`` in a string value, nothing elsewhere.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from je_web_runner.action_lsp._commands import parameters
from je_web_runner.action_lsp._cursor import (
    ARRAY,
    KEY,
    OBJECT,
    VALUE,
    CursorContext,
    is_action,
    keys_after,
    keyword_command,
    scan,
)
from je_web_runner.action_lsp._positions import _string_end
from je_web_runner.action_lsp._text import range_between
from je_web_runner.utils.flow.structure import defined_variables
from je_web_runner.utils.linter.flow_rules import every_action

# LSP CompletionItemKind.
_KIND_VARIABLE = 6
_KIND_PROPERTY = 10
_KIND_KEYWORD = 14
COMMAND_DETAIL = "WebRunner action command"
_PLACEHOLDER_OPEN = "${"
_HOOK_KEYS = ("setup", "teardown")


@dataclass(frozen=True)
class CompletionSource:
    """What completion draws from: the command names, the commands by name, the document's variables."""
    names: Sequence[str]
    commands: Mapping[str, Any]
    variables: Sequence[str]


@dataclass(frozen=True)
class _Slot:
    """The text a completion replaces (``start`` to ``end``) and whether it sits inside a string."""
    text: str
    start: int
    end: int
    quoted: bool

    def item(self, label: str, kind: int, detail: str) -> dict[str, Any]:
        """A completion item that puts ``label`` in the slot."""
        new_text = label if self.quoted else json.dumps(label)
        return {
            "label": label,
            "kind": kind,
            "detail": detail,
            "insertText": new_text,
            "textEdit": {"range": range_between(self.text, self.start, self.end), "newText": new_text},
        }


def document_variables(data: Any) -> list[str]:
    """
    文件定義的變數名稱
    The variable names a parsed action document defines: the keys of ``meta.vars`` and what any action
    (top-level, nested, or of ``meta.setup`` / ``meta.teardown``) sets, captures or loops over.
    """
    meta = data.get("meta") if isinstance(data, dict) else None
    meta = meta if isinstance(meta, dict) else {}
    names = {str(key) for key in meta["vars"]} if isinstance(meta.get("vars"), dict) else set()
    blocks = [data.get("webdriver_wrapper") if isinstance(data, dict) else data]
    blocks.extend(meta.get(key) for key in _HOOK_KEYS)
    for block in blocks:
        if isinstance(block, list):
            for _location, action in every_action(block):
                names.update(defined_variables(action))
    return sorted(names)


def _whole_string_slot(text: str, context: CursorContext, offset: int) -> _Slot:
    """The slot for a name: the whole string the cursor is in, or the cursor itself outside a string."""
    if context.string_start is None:
        return _Slot(text, offset, offset, quoted=False)
    end = _string_end(text, context.string_start) - 1
    closed = end >= offset and text[end] == '"' and "\n" not in text[offset:end]
    return _Slot(text, context.string_start + 1, end if closed else offset, quoted=True)


def _starting_with(names: Iterable[str], typed: str) -> list[str]:
    return [name for name in names if name.startswith(typed)]


def _command_items(slot: _Slot, typed: str, source: CompletionSource) -> list[dict[str, Any]]:
    return [slot.item(name, _KIND_KEYWORD, COMMAND_DETAIL) for name in _starting_with(source.names, typed)]


def _parameter_items(text: str, context: CursorContext, offset: int,
                     source: CompletionSource) -> list[dict[str, Any]]:
    """The parameters of the command whose keyword arguments the cursor is in, those already written left out."""
    frames = context.frames
    command = keyword_command(frames, len(frames) - 1)
    if command is None or command not in source.commands:
        return []
    after = offset if context.string_start is None else context.string_start
    present = set(frames[-1].keys) | set(keys_after(text, after, context.in_string))
    declared = parameters(source.commands[command])
    slot = _whole_string_slot(text, context, offset)
    return [slot.item(name, _KIND_PROPERTY, declared[name])
            for name in _starting_with(declared, context.typed) if name not in present]


def _variable_items(text: str, context: CursorContext, offset: int,
                    source: CompletionSource) -> list[dict[str, Any]]:
    """The document's variables, when the cursor is inside a ``${`` that is still open."""
    opened = context.typed.rfind(_PLACEHOLDER_OPEN)
    if opened == -1:
        return []
    typed = context.typed[opened + len(_PLACEHOLDER_OPEN):]
    if "}" in typed or "\n" in typed:
        return []
    slot = _Slot(text, offset - len(typed), offset, quoted=True)
    return [slot.item(name, _KIND_VARIABLE, "variable") for name in _starting_with(source.variables, typed)]


def completion_items(text: str, offset: int, source: CompletionSource) -> list[dict[str, Any]]:
    """
    游標位置的補全項目
    The completion items for the cursor at ``offset`` of ``text``; empty where nothing can be completed.
    """
    context = scan(text, offset)
    frames = context.frames
    if not frames:
        return []
    frame = frames[-1]
    if frame.kind == ARRAY and frame.index == 0 and is_action(frames, len(frames) - 1):
        if context.in_string or not frame.filled:
            return _command_items(_whole_string_slot(text, context, offset), context.typed, source)
        return []
    if frame.kind == OBJECT and frame.state == KEY:
        return _parameter_items(text, context, offset, source)
    if context.in_string and (frame.kind == ARRAY or frame.state == VALUE):
        return _variable_items(text, context, offset, source)
    return []
