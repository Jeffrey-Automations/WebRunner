"""
動作檔語言的命令
The commands of the action-file language: variables an action list sets, reads and captures. The executor
expands ``${name}`` in the arguments of every other command from the same store
(:class:`je_web_runner.utils.flow.VariableStore`).
"""
from __future__ import annotations

from typing import Any, Callable

from je_web_runner.utils.executor._bound import Bound

# Commands whose arguments hold actions to run later. The executor leaves their placeholders alone: each
# nested action is expanded when it runs, with the values of that moment, not of the moment its block started.
DEFERRED_EXPANSION = frozenset({
    "WR_execute_action",
    "WR_run_with_dataset",
    "WR_capture",
})


def _capture(executor: Any) -> Callable[..., Any]:
    def capture(name: str, action: list) -> Any:
        """
        執行一個動作並把回傳值存成變數
        Run ``action`` and store what it returned as the variable ``name``; return that value. When the
        action fails, this action fails and the variable is left as it was.
        """
        return executor.variables.set(name, executor.execute_one(action))

    return capture


FLOW_COMMANDS: dict[str, Any] = {
    "WR_set_var": Bound(lambda executor: executor.variables.set),
    "WR_get_var": Bound(lambda executor: executor.variables.get),
    "WR_unset_var": Bound(lambda executor: executor.variables.unset),
    "WR_clear_vars": Bound(lambda executor: executor.variables.clear),
    "WR_list_vars": Bound(lambda executor: executor.variables.names),
    "WR_capture": Bound(_capture),
}
