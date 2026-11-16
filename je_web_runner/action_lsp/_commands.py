"""
命令的簽章與說明
What the language server says about a command: its signature, its docstring, the parameters an action can
name.
"""
from __future__ import annotations

import inspect
from typing import Any

from je_web_runner.utils.linter.action_linter import _LEGACY_NAMES

_NAMEABLE = (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)


class _Bare(str):
    """An annotation kept as source text (``from __future__ import annotations``), shown without quotes."""

    def __repr__(self) -> str:
        return str(self)


def _bare(annotation: Any) -> Any:
    return _Bare(annotation) if isinstance(annotation, str) else annotation


def _signature(command: Any) -> inspect.Signature | None:
    """The signature of ``command``, None when Python cannot tell (some builtins, a non-callable)."""
    try:
        signature = inspect.signature(command)
    except (TypeError, ValueError):
        return None
    return signature.replace(
        parameters=[parameter.replace(annotation=_bare(parameter.annotation))
                    for parameter in signature.parameters.values()],
        return_annotation=_bare(signature.return_annotation),
    )


def parameters(command: Any) -> dict[str, str]:
    """The parameters of ``command`` an action can pass by name, each with its declaration."""
    signature = _signature(command)
    if signature is None:
        return {}
    return {name: str(parameter) for name, parameter in signature.parameters.items()
            if parameter.kind in _NAMEABLE}


def single_replacement(name: str) -> str | None:
    """The modern name of a legacy command, None when it has none or the table offers several."""
    replacement = _LEGACY_NAMES.get(name)
    if replacement is None or not replacement.isidentifier():
        return None
    return replacement


def hover_markdown(name: str, command: Any) -> str:
    """Markdown for ``command``: its signature in a code block, a legacy note, then its docstring."""
    signature = _signature(command)
    parts = [f"```python\n{name}{signature if signature is not None else '(...)'}\n```"]
    if name in _LEGACY_NAMES:
        parts.append(f"Legacy alias; prefer `{_LEGACY_NAMES[name]}`.")
    documentation = inspect.getdoc(command)
    if documentation:
        parts.append(documentation)
    return "\n\n".join(parts)
