"""
動作清單的變數與 ``${name}`` 展開
Variables of an action run, and the ``${name}`` placeholders that read them.

A placeholder is ``${name}``, ``${name.key.0}`` (a key of a dict, an index of a list) or ``${ENV.KEY}`` (an
environment variable). The executor expands them in the arguments of an action just before the command is
called, so a value stored by one action can be used by a later one.

A placeholder that names nothing known is left as it is: ``${ROW.col}`` outside a dataset run belongs to
``WR_run_with_dataset``, and a
JavaScript template literal in a script argument must reach the browser unchanged. A known variable whose path
does not exist is an error, because that is a mistake in the action file.
"""
from __future__ import annotations

import contextlib
import os
import re
from typing import Any, Iterator

from je_web_runner.utils.exception.exceptions import WebRunnerException

ENV_NAMESPACE = "ENV"
# Namespaces a variable cannot take: ``${ENV.KEY}`` reads the environment, ``${ROW.col}`` a dataset row.
RESERVED_NAMES = frozenset({ENV_NAMESPACE, "ROW"})

_NAME_RE = re.compile(r"[A-Za-z_]\w*")
_PLACEHOLDER_RE = re.compile(r"\$\{([A-Za-z_]\w*(?:\.\w+)*)\}")
_MISSING: Any = object()


class FlowError(WebRunnerException):
    """Raised for a bad variable name or a placeholder path that does not exist."""


def _child(value: Any, part: str, path: str) -> Any:
    """``value[part]`` for a dict key or a list index; raises :class:`FlowError` when there is none."""
    if isinstance(value, dict) and part in value:
        return value[part]
    if isinstance(value, (list, tuple)) and part.isdigit() and int(part) < len(value):
        return value[int(part)]
    raise FlowError(f"${{{path}}}: {part!r} is not in the value before it")


class VariableStore:
    """
    一次執行的變數
    The variables of a run. ``set`` writes where the name already lives, else in the outermost frame, so a
    value set inside a block is still there after it; :meth:`scope` adds a frame whose names end with it.
    """

    def __init__(self) -> None:
        self._frames: list[dict[str, Any]] = [{}]

    def copy(self) -> "VariableStore":
        """A new store holding the variables visible now, in one frame; later changes are its own."""
        duplicate = VariableStore()
        for frame in self._frames:
            duplicate._frames[0].update(frame)  # pylint: disable=protected-access
        return duplicate

    def _frame_of(self, name: str) -> dict[str, Any] | None:
        for frame in reversed(self._frames):
            if name in frame:
                return frame
        return None

    def set(self, name: str, value: Any = None, local: bool = False) -> Any:
        """
        設定變數
        Store ``value`` under ``name`` for later actions to read as ``${name}``; return the value.
        ``local`` puts a new name in the innermost frame, so it ends with the block that is running.

        :raises FlowError: when ``name`` is not an identifier, or is ``ENV`` or ``ROW``.
        """
        if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
            raise FlowError(f"variable name must be an identifier, got {name!r}")
        if name in RESERVED_NAMES:
            raise FlowError(f"{name!r} is reserved: ${{{name}.…}} is not a variable")
        frame = self._frame_of(name)
        if frame is None:
            frame = self._frames[-1] if local else self._frames[0]
        frame[name] = value
        return value

    def bind(self, name: str, value: Any, local: bool = False) -> None:
        """
        Set ``name`` without the checks of :meth:`set`: how the runner itself provides the reserved
        ``ROW``. ``local`` writes to the innermost frame, else to the outermost.
        """
        (self._frames[-1] if local else self._frames[0])[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """
        讀取變數
        Return the variable ``name``, or ``default`` when it is not set.
        """
        frame = self._frame_of(name)
        return default if frame is None else frame[name]

    def has(self, name: str) -> bool:
        """Whether ``name`` is set."""
        return self._frame_of(name) is not None

    def unset(self, name: str) -> bool:
        """
        移除變數
        Remove the variable ``name``; return whether it was set.
        """
        frame = self._frame_of(name)
        if frame is None:
            return False
        del frame[name]
        return True

    def clear(self) -> None:
        """
        清除所有變數
        Remove every variable.
        """
        for frame in self._frames:
            frame.clear()

    def names(self) -> list[str]:
        """
        列出變數名稱
        Return the names that are set, sorted. Values are not returned: they may be secrets.
        """
        return sorted({name for frame in self._frames for name in frame})

    @contextlib.contextmanager
    def scope(self, values: dict[str, Any] | None = None) -> Iterator[None]:
        """Add a frame holding ``values`` for the ``with`` block; its names end with the block."""
        self._frames.append(dict(values or {}))
        try:
            yield
        finally:
            self._frames.pop()

    def resolve(self, path: str) -> Any:
        """
        The value ``path`` (``name``, ``name.key.0``, ``ENV.KEY``) names, or the module's missing marker
        when its first part is not a variable; see :func:`is_missing`.

        :raises FlowError: when the variable exists but the rest of the path does not.
        """
        root, *parts = path.split(".")
        if root == ENV_NAMESPACE:
            return os.environ.get(parts[0], _MISSING) if len(parts) == 1 else _MISSING
        frame = self._frame_of(root)
        if frame is None:
            return _MISSING
        value = frame[root]
        for part in parts:
            value = _child(value, part, path)
        return value

    def _expand_text(self, text: str) -> Any:
        whole = _PLACEHOLDER_RE.fullmatch(text)
        if whole:
            # The whole string is one placeholder: keep the value's type (a number, a list …).
            value = self.resolve(whole.group(1))
            return text if value is _MISSING else value

        def replace(match: re.Match[str]) -> str:
            value = self.resolve(match.group(1))
            return match.group(0) if value is _MISSING else str(value)

        return _PLACEHOLDER_RE.sub(replace, text)

    def expand(self, data: Any) -> Any:
        """
        展開佔位符
        Return ``data`` with every known placeholder replaced, in strings, dict values, lists and tuples.
        A string that is exactly one placeholder becomes the value itself; inside a longer string the value
        is inserted as text. Unknown placeholders stay.
        """
        if isinstance(data, str):
            return self._expand_text(data) if "${" in data else data
        if isinstance(data, dict):
            return {key: self.expand(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self.expand(item) for item in data]
        if isinstance(data, tuple):
            return tuple(self.expand(item) for item in data)
        return data


def is_missing(value: Any) -> bool:
    """Whether ``value`` is what :meth:`VariableStore.resolve` returns for an unknown placeholder."""
    return value is _MISSING
