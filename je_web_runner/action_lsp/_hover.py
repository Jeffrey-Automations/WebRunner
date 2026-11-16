"""
命令名稱上的 hover
Hover on a command name: the command's signature and docstring as Markdown.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from je_web_runner.action_lsp._commands import hover_markdown
from je_web_runner.action_lsp._cursor import is_action, scan
from je_web_runner.action_lsp._positions import _string_end
from je_web_runner.action_lsp._text import range_between


def hover(text: str, offset: int, commands: Mapping[str, Any]) -> dict[str, Any] | None:
    """
    游標所在命令的說明
    The hover for the cursor at ``offset``: Markdown about the command when the cursor is on the name string
    of an action (its quotes included) and the command is registered, else None.
    """
    if offset < len(text) and text[offset] == '"' and not scan(text, offset).in_string:
        # On the opening quote: the string starts here.
        offset += 1
    context = scan(text, offset)
    frames = context.frames
    if context.string_start is None or not frames:
        return None
    if frames[-1].index != 0 or not is_action(frames, len(frames) - 1):
        return None
    end = _string_end(text, context.string_start)
    try:
        name = json.loads(text[context.string_start:end])
    except ValueError:
        return None
    if not isinstance(name, str) or name not in commands:
        return None
    return {
        "contents": {"kind": "markdown", "value": hover_markdown(name, commands[name])},
        "range": range_between(text, context.string_start, end),
    }
