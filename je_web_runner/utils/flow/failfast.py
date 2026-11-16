"""
第一個失敗後跳過其餘動作
Fail-fast: once an action of a list has failed, the actions after it are not run.

By default a failed action is recorded and the next one runs. With fail-fast on, the remaining actions of
that list are recorded as skipped instead, except the ``meta.teardown`` actions, which still run. It applies
to the actions of a list being run (``execute_action``, a file), not to a single ``execute_one`` call, and a
block already stops at its first failure either way.

The run that is in progress is kept per context (:mod:`contextvars`): each thread of ``--parallel`` and each
list of ``--parallel-mode async`` has its own, and a worker thread started with ``asyncio.to_thread`` sees
the run of the list that started it.
"""
from __future__ import annotations

import contextlib
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException

SKIPPED_TEXT = "skipped: an earlier action of this list failed (fail-fast)"
_NO_TEARDOWN = 1 << 62


@dataclass
class _Run:
    """One list being run: where it is, and whether one of its actions has failed."""

    active: bool = False
    enabled: bool = False
    depth: int = 0
    index: int = 0
    tripped: bool = False
    teardown_from: int = _NO_TEARDOWN


class FailFast:
    """Tracks, per context, the list that is running and whether one of its actions has failed."""

    def __init__(self) -> None:
        self.enabled = False
        self._current: ContextVar[_Run | None] = ContextVar(f"webrunner_fail_fast_{id(self)}", default=None)

    def _state(self) -> _Run:
        """The run of this context, or an inactive one when no list is running here."""
        return self._current.get() or _Run()

    @property
    def nested(self) -> bool:
        """Whether an action is running now, so the next one to start is inside it (a block)."""
        return self._state().depth > 0

    @contextlib.contextmanager
    def run(self, enabled: bool | None = None) -> Iterator[None]:
        """
        The run of one list. ``enabled`` overrides the executor's setting for this list (``meta.fail_fast``).
        A list run from inside an action (``WR_execute_action``) is part of that action, not a new run.
        """
        state = self._state()
        if state.depth > 0 or state.active:
            yield
            return
        token = self._current.set(_Run(active=True, enabled=self.enabled if enabled is None else bool(enabled)))
        try:
            yield
        finally:
            self._current.reset(token)

    def set_teardown_count(self, total: int, teardown: int) -> None:
        """Tell the running list that its last ``teardown`` of ``total`` actions run even after a failure."""
        state = self._state()
        if state.active and state.depth == 0:
            state.teardown_from = total - teardown

    @contextlib.contextmanager
    def step(self) -> Iterator[None]:
        """
        One action. Raises instead of entering when an earlier action of the list failed and this one is
        not a teardown action; notes a failure of this one.
        """
        state = self._state()
        top = state.active and state.depth == 0
        if top:
            index = state.index
            state.index += 1
            if state.enabled and state.tripped and index < state.teardown_from:
                raise WebRunnerExecuteException(SKIPPED_TEXT)
        state.depth += 1
        try:
            yield
        except Exception:
            if top:
                state.tripped = True
            raise
        finally:
            state.depth -= 1
