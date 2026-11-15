"""
流程控制的條件
Conditions of the control-flow commands: closed JSON objects, never evaluated as code.

==============================================  =====================================================
``{"var": "name.path", "op": "eq", "value": 1}``  compare a variable (``op`` defaults to ``truthy``)
``{"succeeds": ["WR_command", {...}]}``           run one action; true when it does not fail
``{"all": [condition, ...]}``                     every condition holds (stops at the first that does not)
``{"any": [condition, ...]}``                     one condition holds (stops at the first that does)
``{"not": condition}``                            the condition does not hold
``true`` / ``false`` / ``"${flag}"``              the value itself, after placeholder expansion
==============================================  =====================================================

Operators: ``eq``, ``ne``, ``gt``, ``ge``, ``lt``, ``le``, ``contains``, ``in``, ``startswith``, ``endswith``,
``exists``, ``truthy``, ``falsy``. A variable that is not set is false for ``exists`` and ``truthy``, true for
``falsy``, and an error for the comparisons.
"""
from __future__ import annotations

import operator
from typing import Any, Callable

from je_web_runner.utils.flow.variables import FlowError, VariableStore, is_missing
from je_web_runner.utils.test_record.test_record_class import mark_handled, track_records

RunAction = Callable[[Any], Any]

_COMPARISONS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
    "contains": lambda actual, expected: expected in actual,
    "in": lambda actual, expected: actual in expected,
    "startswith": lambda actual, expected: str(actual).startswith(str(expected)),
    "endswith": lambda actual, expected: str(actual).endswith(str(expected)),
}
_PRESENCE: dict[str, Callable[[Any], bool]] = {
    "exists": lambda actual: not is_missing(actual),
    "truthy": lambda actual: not is_missing(actual) and bool(actual),
    "falsy": lambda actual: is_missing(actual) or not actual,
}
OPERATORS = tuple(sorted({*_COMPARISONS, *_PRESENCE}))
_KINDS = ("var", "succeeds", "all", "any", "not")


def compare(store: VariableStore, var: str, op: str = "truthy", value: Any = None) -> bool:
    """
    Whether the variable ``var`` (a name or a ``name.key.0`` path) satisfies ``op`` against ``value``;
    placeholders in ``value`` are expanded.

    :raises FlowError: for an unknown operator, a comparison on a variable that is not set, or values
             that cannot be compared (``"a" > 1``).
    """
    if not isinstance(var, str) or not var:
        raise FlowError(f"a condition's var must be a variable name, got {var!r}")
    actual = store.resolve(var)
    if op in _PRESENCE:
        return _PRESENCE[op](actual)
    if op not in _COMPARISONS:
        raise FlowError(f"unknown condition operator {op!r}; known: {', '.join(OPERATORS)}")
    if is_missing(actual):
        raise FlowError(f"condition compares ${{{var}}}, which is not set")
    try:
        return bool(_COMPARISONS[op](actual, store.expand(value)))
    except TypeError as error:
        raise FlowError(f"condition {var} {op} {value!r} cannot be compared: {error}") from error


def _succeeds(action: Any, run_action: RunAction) -> bool:
    with track_records() as records:
        try:
            run_action(action)
        except Exception:  # pylint: disable=broad-exception-caught  # whether it fails is the question
            mark_handled(records)  # a failure here is an answer, not a failure of the run
            return False
    return True


def _conditions(value: Any, kind: str) -> list:
    if not isinstance(value, list):
        raise FlowError(f"{kind!r} takes a list of conditions, got {value!r}")
    return value


def evaluate(condition: Any, store: VariableStore, run_action: RunAction) -> bool:
    """
    條件是否成立
    Whether ``condition`` holds. ``run_action`` runs the action of a ``succeeds`` condition and raises
    when it fails.

    :raises FlowError: when the condition is not one of the shapes this module documents.
    """
    if not isinstance(condition, dict):
        return bool(store.expand(condition))
    kinds = [kind for kind in _KINDS if kind in condition]
    if len(kinds) != 1:
        raise FlowError(f"a condition has exactly one of {', '.join(_KINDS)}; got {sorted(condition)}")
    kind = kinds[0]
    if kind == "var":
        return compare(store, condition["var"], condition.get("op", "truthy"), condition.get("value"))
    if kind == "succeeds":
        return _succeeds(condition["succeeds"], run_action)
    if kind == "not":
        return not evaluate(condition["not"], store, run_action)
    results = (evaluate(part, store, run_action) for part in _conditions(condition[kind], kind))
    return all(results) if kind == "all" else any(results)
