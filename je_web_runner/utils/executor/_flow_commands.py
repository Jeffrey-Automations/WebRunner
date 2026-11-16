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
from je_web_runner.utils.flow import blocks, dataset, subflow
from je_web_runner.utils.flow.variables import VariableStore
from je_web_runner.utils.test_object import locator_file

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


def _use_row(executor: Any) -> Callable[..., Any]:
    @functools.wraps(dataset.use_row)
    def command(*args: Any, **kwargs: Any) -> Any:
        return dataset.use_row(executor.variables, *args, **kwargs)

    signature = inspect.signature(dataset.use_row)
    command.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=list(signature.parameters.values())[1:])
    return command


def _load_locators(executor: Any) -> Callable[..., Any]:
    def load_locators(path: str) -> list:
        """
        載入共用的定位器檔
        Load a locator file (``{name: {"by": ..., "value": ...}}``) and return the names it defines.
        The recorded-name commands of both backends then find those elements by name. A relative
        ``path`` starts at the action file that is running.
        """
        return locator_file.load_locators(executor.files.resolve_data(path, "WR_load_locators"))

    return load_locators


def _store_method(name: str) -> Bound:
    """
    A table entry for a method of the executor's variable store. The store is looked up at every call: a
    list run by the async executor has its own (``Executor.isolated_variables``).
    """
    method = getattr(VariableStore, name)
    signature = inspect.signature(method)
    public = signature.replace(parameters=list(signature.parameters.values())[1:])

    def factory(executor: Any) -> Callable[..., Any]:
        @functools.wraps(method)
        def command(*args: Any, **kwargs: Any) -> Any:
            return getattr(executor.variables, name)(*args, **kwargs)

        command.__signature__ = public  # type: ignore[attr-defined]  # without ``self``
        return command

    return Bound(factory)


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
    "WR_set_var": _store_method("set"),
    "WR_get_var": _store_method("get"),
    "WR_unset_var": _store_method("unset"),
    "WR_clear_vars": _store_method("clear"),
    "WR_list_vars": _store_method("names"),
    "WR_capture": Bound(_capture),
    "WR_use_row": Bound(_use_row),
    "WR_load_locators": Bound(_load_locators),
    "WR_save_locator": locator_file.save_locator,
    "WR_if": _block(blocks.run_if),
    "WR_for_each": _block(blocks.for_each),
    "WR_repeat": _block(blocks.repeat),
    "WR_while": _block(blocks.run_while),
    "WR_try": _block(blocks.run_try),
    "WR_retry_block": _block(blocks.retry_block),
    "WR_call_file": _block(subflow.call_file),
    "WR_fail": _block(blocks.fail),
    "WR_set_fail_fast": Bound(lambda executor: executor.set_fail_fast),
    "WR_assert_var": _block(blocks.assert_var),
}
