"""
動作檔語言的命令
The commands of the action-file language: variables an action list sets, reads and captures, and the blocks
that decide which actions run (:mod:`je_web_runner.utils.flow.blocks`). The executor expands ``${name}`` in
the arguments of every other command from the same store (:class:`je_web_runner.utils.flow.VariableStore`).
"""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from je_web_runner.utils.executor._bound import Bound
from je_web_runner.utils.flow import blocks

# Commands whose arguments hold actions to run later. The executor leaves their placeholders alone: each
# nested action is expanded when it runs, with the values of that moment, not of the moment its block started.
# The blocks expand their own remaining arguments (``items``, ``times``, a condition's ``value``).
DEFERRED_EXPANSION = frozenset({
    "WR_execute_action",
    "WR_run_with_dataset",
    "WR_capture",
    "WR_if",
    "WR_for_each",
    "WR_repeat",
    "WR_while",
    "WR_try",
    "WR_retry_block",
    "WR_assert_var",
})


def _capture(executor: Any) -> Callable[..., Any]:
    def capture(name: str, action: list) -> Any:
        """
        執行一個動作並把回傳值存成變數
        Run ``action`` and store what it returned as the variable ``name``; return that value. When the
        action fails, this action fails and the variable is left as it was.
        """
        return executor.variables.set(name, executor.run_nested([action])[0])

    return capture


def _block(function: Callable[..., Any]) -> Bound:
    """A table entry for a block function whose first parameter is the executor."""
    signature = inspect.signature(function)
    public = signature.replace(parameters=list(signature.parameters.values())[1:])

    def factory(executor: Any) -> Callable[..., Any]:
        @functools.wraps(function)
        def command(*args: Any, **kwargs: Any) -> Any:
            return function(executor, *args, **kwargs)

        command.__signature__ = public  # type: ignore[attr-defined]  # what the command reference shows
        return command

    return Bound(factory)


FLOW_COMMANDS: dict[str, Any] = {
    "WR_set_var": Bound(lambda executor: executor.variables.set),
    "WR_get_var": Bound(lambda executor: executor.variables.get),
    "WR_unset_var": Bound(lambda executor: executor.variables.unset),
    "WR_clear_vars": Bound(lambda executor: executor.variables.clear),
    "WR_list_vars": Bound(lambda executor: executor.variables.names),
    "WR_capture": Bound(_capture),
    "WR_if": _block(blocks.run_if),
    "WR_for_each": _block(blocks.for_each),
    "WR_repeat": _block(blocks.repeat),
    "WR_while": _block(blocks.run_while),
    "WR_try": _block(blocks.run_try),
    "WR_retry_block": _block(blocks.retry_block),
    "WR_fail": _block(blocks.fail),
    "WR_assert_var": _block(blocks.assert_var),
}
