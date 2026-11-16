"""
區塊命令裡的巢狀動作
Where the block commands keep the actions they run, for tools that read an action file without running it
(the linter, the validator): ``WR_if`` under ``then`` / ``otherwise``, the loops under ``do``, and so on.
"""
from __future__ import annotations

from typing import Any, Iterator

# Arguments that hold a list of actions, per command.
BLOCK_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "WR_if": ("then", "otherwise"),
    "WR_for_each": ("do",),
    "WR_repeat": ("do",),
    "WR_while": ("do",),
    "WR_try": ("do", "on_error", "always"),
    "WR_retry_block": ("do",),
}
# Arguments that hold one action.
ACTION_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "WR_capture": ("action",),
}
# Arguments that hold a condition, which may hold ``{"succeeds": action}``.
CONDITION_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "WR_if": ("condition",),
    "WR_while": ("condition",),
}
# Arguments that name a variable the block defines for its actions.
DEFINED_VARIABLES: dict[str, tuple[str, ...]] = {
    "WR_for_each": ("var", "index_var"),
    "WR_repeat": ("index_var",),
}
FOR_EACH_DEFAULT_VARIABLE = "item"


def keyword_arguments(action: Any) -> dict[str, Any]:
    """The keyword arguments of ``action`` (``[name, {...}]`` or ``[name, [...], {...}]``), else empty."""
    if not isinstance(action, list):
        return {}
    for slot in action[1:3]:
        if isinstance(slot, dict):
            return slot
    return {}


def trailing_keyword_arguments(action: list[Any]) -> dict[str, Any]:
    """
    The keyword arguments of the list ``action``, as the read-only tools take them: the third slot when it
    is a dict, else the second, else empty. Unlike :func:`keyword_arguments`, the third slot wins when both
    are dicts.
    """
    if len(action) >= 3 and isinstance(action[2], dict):
        return action[2]
    if len(action) >= 2 and isinstance(action[1], dict):
        return action[1]
    return {}


def _condition_actions(condition: Any, location: str) -> Iterator[tuple[str, Any]]:
    """``(location, action)`` for every ``succeeds`` action inside a condition tree."""
    if not isinstance(condition, dict):
        return
    if "succeeds" in condition:
        yield f"{location}.succeeds", condition["succeeds"]
    if "not" in condition:
        yield from _condition_actions(condition["not"], f"{location}.not")
    for kind in ("all", "any"):
        parts = condition.get(kind)
        if isinstance(parts, list):
            for index, part in enumerate(parts):
                yield from _condition_actions(part, f"{location}.{kind}[{index}]")


def nested_actions(action: Any, location: str) -> Iterator[tuple[str, Any]]:
    """
    ``(location, nested action)`` for every action ``action`` holds directly: the entries of its blocks,
    its single-action argument, the ``succeeds`` actions of its condition. Entries of a block that is not
    a list are not yielded; :func:`misshapen_blocks` reports those.
    """
    if not isinstance(action, list) or not action or not isinstance(action[0], str):
        return
    arguments = keyword_arguments(action)
    for key in BLOCK_ARGUMENTS.get(action[0], ()):
        block = arguments.get(key)
        if isinstance(block, list):
            for index, nested in enumerate(block):
                yield f"{location}.{key}[{index}]", nested
    for key in ACTION_ARGUMENTS.get(action[0], ()):
        if key in arguments:
            yield f"{location}.{key}", arguments[key]
    for key in CONDITION_ARGUMENTS.get(action[0], ()):
        yield from _condition_actions(arguments.get(key), f"{location}.{key}")


def misshapen_blocks(action: Any) -> list[str]:
    """The block arguments of ``action`` that are present but not a list."""
    if not isinstance(action, list) or not action or not isinstance(action[0], str):
        return []
    arguments = keyword_arguments(action)
    return [key for key in BLOCK_ARGUMENTS.get(action[0], ())
            if arguments.get(key) is not None and not isinstance(arguments[key], list)]


def defined_variables(action: Any) -> list[str]:
    """The variable names ``action`` defines: what it sets or captures, and what a loop gives its actions."""
    if not isinstance(action, list) or not action or not isinstance(action[0], str):
        return []
    name = action[0]
    arguments = keyword_arguments(action)
    names: list[Any] = []
    if name in ("WR_set_var", "WR_capture"):
        positional = action[1] if len(action) > 1 and isinstance(action[1], list) and action[1] else []
        names.append(arguments.get("name", positional[0] if positional else None))
    names.extend(arguments.get(key) for key in DEFINED_VARIABLES.get(name, ()))
    if name == "WR_for_each" and "var" not in arguments:
        names.append(FOR_EACH_DEFAULT_VARIABLE)
    if name == "WR_try" and arguments.get("on_error") is not None:
        names.append("error")
    if name == "WR_call_file" and isinstance(arguments.get("params"), dict):
        names.extend(arguments["params"])
    return [value for value in names if isinstance(value, str)]
