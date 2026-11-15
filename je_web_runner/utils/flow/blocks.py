"""
流程控制區塊
The control-flow blocks of the action-file language. Each takes the executor first; the command table binds
it. A block's actions run through ``executor.run_nested``, so the gates, the retry policy and placeholder
expansion apply to every nested action, and the first one that fails fails the block.
"""
from __future__ import annotations

import time
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerAssertException, describe_error
from je_web_runner.utils.flow.conditions import compare, evaluate
from je_web_runner.utils.flow.variables import FlowError, is_missing
from je_web_runner.utils.test_record.test_record_class import mark_handled, track_records

MAX_ITERATIONS = 100_000
MAX_BLOCK_RETRIES = 100
ERROR_VARIABLE = "error"
_SHOWN_LENGTH = 200


def _count(value: Any, what: str, executor: Any, minimum: int = 0, maximum: int = MAX_ITERATIONS) -> int:
    """``value`` (after placeholder expansion) as an integer within the allowed range."""
    expanded = executor.variables.expand(value)
    if isinstance(expanded, bool) or not isinstance(expanded, int) or not minimum <= expanded <= maximum:
        raise FlowError(f"{what} must be an integer from {minimum} to {maximum}, got {expanded!r}")
    return expanded


def _holds(executor: Any, condition: Any) -> bool:
    return evaluate(condition, executor.variables, executor.attempt)


def run_if(executor: Any, condition: Any, then: list | None = None, otherwise: list | None = None) -> list:
    """
    條件成立時執行 ``then``，否則執行 ``otherwise``
    Run the actions of ``then`` when ``condition`` holds, those of ``otherwise`` when it does not; return
    what the actions that ran returned. ``condition`` is a condition object: ``{"var": "name", "op": "eq",
    "value": 1}``, ``{"succeeds": [action]}``, ``{"all": [...]}``, ``{"any": [...]}`` or ``{"not": ...}``.
    """
    branch = then if _holds(executor, condition) else otherwise
    return executor.run_nested(branch or [])


def for_each(executor: Any, items: Any, do: list, var: str = "item", index_var: str | None = None) -> int:
    """
    對清單的每個項目執行一次 ``do``
    Run the actions of ``do`` once per element of ``items`` (a list, or a ``${name}`` that holds one), with
    the element as the variable ``var`` and, when ``index_var`` is given, its position from 0. Both
    variables end with the loop. Return the number of rounds.
    """
    elements = executor.variables.expand(items)
    if not isinstance(elements, (list, tuple)):
        raise FlowError(f"WR_for_each items must be a list, got {type(elements).__name__}")
    for index, element in enumerate(elements):
        scope = {var: element} if index_var is None else {var: element, index_var: index}
        with executor.variables.scope(scope):
            executor.run_nested(do)
    return len(elements)


def repeat(executor: Any, times: Any, do: list, index_var: str | None = None) -> int:
    """
    把 ``do`` 執行 ``times`` 次
    Run the actions of ``do`` ``times`` times, with the round number from 0 as the variable ``index_var``
    when it is given. Return the number of rounds.
    """
    rounds = _count(times, "WR_repeat times", executor)
    for index in range(rounds):
        with executor.variables.scope({} if index_var is None else {index_var: index}):
            executor.run_nested(do)
    return rounds


def run_while(executor: Any, condition: Any, do: list, max_iterations: Any) -> int:
    """
    條件成立時重複執行 ``do``
    Run the actions of ``do`` for as long as ``condition`` holds and return the number of rounds.
    ``max_iterations`` is required: the loop fails when the condition still holds after that many rounds.
    """
    limit = _count(max_iterations, "WR_while max_iterations", executor, minimum=1)
    rounds = 0
    while _holds(executor, condition):
        if rounds >= limit:
            raise FlowError(f"WR_while: the condition still holds after {limit} rounds")
        executor.run_nested(do)
        rounds += 1
    return rounds


def run_try(executor: Any, do: list, on_error: list | None = None, always: list | None = None) -> dict:
    """
    執行 ``do``；失敗時執行 ``on_error``，最後一定執行 ``always``
    Run the actions of ``do``. When one fails and ``on_error`` is given, run its actions with the failure
    text as the variable ``error``, and this action passes; without ``on_error`` the failure stays a
    failure. The actions of ``always`` run in every case. Return ``{"failed": bool, "error": text or
    None}``.
    """
    outcome: dict[str, Any] = {"failed": False, "error": None}
    try:
        with track_records() as records:
            try:
                executor.run_nested(do)
            # The block decides what a failure of its actions means, whatever raised it.
            except Exception as error:  # pylint: disable=broad-exception-caught
                if on_error is None:
                    raise
                mark_handled(records)  # handled here, so not a failure in the reports
                outcome = {"failed": True, "error": describe_error(error)}
        if outcome["failed"]:
            with executor.variables.scope({ERROR_VARIABLE: outcome["error"]}):
                executor.run_nested(on_error or [])
    finally:
        executor.run_nested(always or [])
    return outcome


def retry_block(executor: Any, do: list, retries: Any = 1, backoff: float = 0.0) -> int:
    """
    整個區塊失敗時從頭重跑
    Run the actions of ``do``; when one fails, start the block again from its first action, up to
    ``retries`` more times, waiting ``backoff`` seconds times the attempt number in between. Return the
    number of attempts made. The last failure fails this action.
    """
    extra = _count(retries, "WR_retry_block retries", executor, maximum=MAX_BLOCK_RETRIES)
    if isinstance(backoff, bool) or not isinstance(backoff, (int, float)) or backoff < 0:
        raise FlowError(f"WR_retry_block backoff must be a number of seconds, got {backoff!r}")
    for attempt in range(1, extra + 2):
        with track_records() as records:
            try:
                executor.run_nested(do)
                return attempt
            # Any failure starts the block again; the last attempt's failure is the block's failure.
            except Exception:  # pylint: disable=broad-exception-caught
                if attempt > extra:
                    raise
                mark_handled(records)  # retried, so not a failure in the reports
        time.sleep(backoff * attempt)
    raise FlowError("WR_retry_block ended without an attempt")  # unreachable: the range is never empty


def fail(_executor: Any, message: str = "WR_fail") -> None:
    """
    讓這個動作失敗
    Fail this action with ``message``.
    """
    raise FlowError(str(message))


def assert_var(executor: Any, var: str, op: str = "truthy", value: Any = None) -> bool:
    """
    斷言變數符合條件
    Fail unless the variable ``var`` (a name or a ``name.key.0`` path) satisfies ``op`` against ``value``.
    Operators: ``eq``, ``ne``, ``gt``, ``ge``, ``lt``, ``le``, ``contains``, ``in``, ``startswith``,
    ``endswith``, ``exists``, ``truthy`` (the default), ``falsy``.
    """
    if not compare(executor.variables, var, op, value):
        actual = executor.variables.resolve(var)
        shown = "not set" if is_missing(actual) else repr(actual)[:_SHOWN_LENGTH]
        expected = "" if value is None else f" {executor.variables.expand(value)!r}"[:_SHOWN_LENGTH]
        raise WebRunnerAssertException(f"variable {var} is {shown}; expected {op}{expected}")
    return True
