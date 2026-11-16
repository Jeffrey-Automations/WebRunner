"""
逐步執行動作清單
Stepping through an action list: pause before each action, look at the variables, go on.

The CLI's ``--step`` installs a :class:`Stepper` on the executor. It pauses before every top-level action of
a list and at every ``WR_breakpoint``; at a pause the operator answers on the console:

``n`` (or Enter)  run this action and pause before the next
``c``             continue without pausing, until a ``WR_breakpoint``
``v``             show the variables
``q``             stop: the actions that have not run are recorded as not run

Without a stepper ``WR_breakpoint`` does nothing, so one left in a file cannot hang a CI run. When the
console is closed (input ends) the stepper continues without pausing.
"""
from __future__ import annotations

from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.flow.variables import VariableStore

ABORTED_TEXT = "not run: stopped by the operator while stepping"
PROMPT = "[n]ext  [c]ontinue  [v]ars  [q]uit > "
_HELP = "n or Enter: run this action; c: continue to the next WR_breakpoint; v: variables; q: stop"
_VALUE_LENGTH = 100
_NEXT = frozenset({"", "n", "next"})
_CONTINUE = frozenset({"c", "continue"})
_VARIABLES = frozenset({"v", "vars"})
_QUIT = frozenset({"q", "quit"})


class Stepper:
    """Pauses a run for the operator; ``read`` asks a question on the console and ``write`` prints a line."""

    def __init__(self, read: Callable[[str], str] | None = None,
                 write: Callable[[str], Any] | None = None) -> None:
        # The console functions are looked up now, not when the class was defined.
        self._read = input if read is None else read
        self._write = print if write is None else write
        self.stepping = True
        self.aborted = False

    def before(self, action: Any, variables: VariableStore, nested: bool) -> None:
        """
        Called before every action. Pauses before a top-level action while stepping; an action inside a
        block runs with its block.

        :raises WebRunnerExecuteException: for every action after the operator chose to stop.
        """
        if self.aborted:
            raise WebRunnerExecuteException(ABORTED_TEXT)
        if self.stepping and not nested:
            self._pause(f"next: {action}", variables)

    def breakpoint(self, message: str, variables: VariableStore) -> bool:
        """Pause at a ``WR_breakpoint``, whether stepping or continuing; return True."""
        self._pause(f"breakpoint: {message}" if message else "breakpoint", variables)
        return True

    def _show(self, variables: VariableStore) -> None:
        names = variables.names()
        if not names:
            self._write("(no variables)")
        for name in names:
            self._write(f"  {name} = {repr(variables.get(name))[:_VALUE_LENGTH]}")

    def _answer(self) -> str:
        """The operator's answer, or ``c`` when the console is closed."""
        try:
            return self._read(PROMPT).strip().lower()
        except EOFError:
            self._write("input ended; continuing without pausing")
            return "c"

    def _pause(self, title: str, variables: VariableStore) -> None:
        self._write(title)
        while True:
            answer = self._answer()
            if answer in _NEXT:
                self.stepping = True
                return
            if answer in _CONTINUE:
                self.stepping = False
                return
            if answer in _QUIT:
                self.aborted = True
                raise WebRunnerExecuteException(ABORTED_TEXT)
            if answer in _VARIABLES:
                self._show(variables)
            else:
                self._write(_HELP)
