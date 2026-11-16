"""
呼叫另一個動作檔
Sub-flows: one action file calling another with parameters.

A relative path is taken from the directory of the file that makes the call (the working directory when no
file is running). The called file must be below the working directory or below the directory of the file the
run started from, so an action file cannot reach arbitrary paths with ``..``; a file that is already running
cannot be called again, which would never end.
"""
from __future__ import annotations

import contextlib
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from je_web_runner.utils.flow.variables import FlowError
from je_web_runner.utils.test_record.test_record_class import record_file

MAX_CALL_DEPTH = 20


class FileStack:
    """The action files that are running in this context, outermost first."""

    def __init__(self) -> None:
        # Per context: every thread of ``--parallel`` and every list of ``--parallel-mode async`` has
        # its own chain of calls.
        self._running: ContextVar[tuple[Path, ...]] = ContextVar(f"webrunner_files_{id(self)}", default=())

    @property
    def _stack(self) -> tuple[Path, ...]:
        return self._running.get()

    @property
    def current(self) -> Path | None:
        """The file whose actions are running now, or None outside any file."""
        return self._stack[-1] if self._stack else None

    @contextlib.contextmanager
    def scope(self, path: str | Path) -> Iterator[Path]:
        """Mark ``path`` as the running file for the ``with`` block."""
        resolved = Path(path).resolve()
        token = self._running.set((*self._stack, resolved))
        try:
            with record_file(str(resolved)):  # the reports group the records by this file
                yield resolved
        finally:
            self._running.reset(token)

    def _roots(self) -> list[Path]:
        roots = [Path.cwd().resolve()]
        if self._stack:
            roots.append(self._stack[0].parent)
        return roots

    def resolve_data(self, path: str, what: str) -> Path:
        """
        The file ``path`` names for the running file to read (``what`` words the error): relative to
        the running file, inside the allowed directories, and existing.
        """
        if not isinstance(path, str) or not path.strip():
            raise FlowError(f"{what} path must be a file path, got {path!r}")
        base = self.current.parent if self.current is not None else Path.cwd()
        target = (base / path).resolve()
        if not any(target.is_relative_to(root) for root in self._roots()):
            raise FlowError(
                f"{what}: {path!r} is outside the working directory and the directory of the file "
                "the run started from")
        if not target.is_file():
            raise FlowError(f"{what}: no such file: {target}")
        return target

    def resolve_call(self, path: str) -> Path:
        """
        The file ``path`` names for a call made now.

        :raises FlowError: when the path is empty, leaves the allowed directories, is not a file, is
                 already running, or the calls are nested too deep.
        """
        target = self.resolve_data(path, "WR_call_file")
        if target in self._stack:
            raise FlowError(f"WR_call_file: {target} is already running; a file cannot call itself")
        if len(self._stack) >= MAX_CALL_DEPTH:
            raise FlowError(f"WR_call_file: more than {MAX_CALL_DEPTH} files deep")
        return target


def call_file(executor: Any, path: str, params: dict[str, Any] | None = None) -> list:
    """
    執行另一個動作檔的動作
    Run the actions of another action file here and return what each returned. ``params`` become
    variables the called file reads as ``${name}``; they end with the call, as do the ``meta.vars``
    defaults of the called file for names ``params`` left out. A relative ``path`` is taken
    from the directory of the file making the call. The first action that fails stops the called file and
    fails this action.
    """
    if params is not None and not isinstance(params, dict):
        raise FlowError(f"WR_call_file params must be an object of name: value, got {params!r}")
    target = executor.files.resolve_call(path)
    document = executor.settings.read_json(str(target))
    with executor.files.scope(target), executor.variables.scope(params):
        # The called file's meta applies: its default vars fill what params left out, for this call.
        return executor.run_nested(executor.document_actions(document, scoped=True))
