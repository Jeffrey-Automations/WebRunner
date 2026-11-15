"""
依命令簽章檢查動作的參數
Linter rules that compare an action's arguments with the signature of its command: a keyword the command
does not take (usually a typo), a required parameter that is not given, more positional values than the
command has parameters.

A command that takes ``**kwargs`` or ``*args`` accepts anything of that kind, and a command whose
signature Python cannot read (some builtins) is not checked.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Mapping

from je_web_runner.utils.flow.structure import keyword_arguments

_POSITIONAL = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
_NAMED = (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
Parameters = list[inspect.Parameter]


def _finding(rule: str, message: str, location: str) -> dict[str, Any]:
    return {"rule": rule, "severity": "warning", "message": message, "location": location}


def _parameters(command: Callable[..., Any]) -> Parameters | None:
    """The parameters of ``command``, or None when Python cannot read its signature."""
    try:
        return list(inspect.signature(command).parameters.values())
    except (TypeError, ValueError):
        return None


def _positional_values(action: list) -> list:
    """The positional values of ``[name, [values]]`` / ``[name, [values], {kwargs}]``."""
    return list(action[1]) if len(action) > 1 and isinstance(action[1], (list, tuple)) else []


def _takes(parameters: Parameters, kind: Any) -> bool:
    return any(parameter.kind is kind for parameter in parameters)


def _unknown_keywords(action: list, parameters: Parameters) -> list[str]:
    """Messages for the keywords of ``action`` its command has no parameter for."""
    if _takes(parameters, inspect.Parameter.VAR_KEYWORD):
        return []
    named = sorted(parameter.name for parameter in parameters if parameter.kind in _NAMED)
    known = ", ".join(named) or "none"
    return [f"{action[0]!r} takes no argument {key!r} (it takes: {known})"
            for key in keyword_arguments(action) if key not in named]


def _too_many_values(action: list, parameters: Parameters) -> list[str]:
    """A message when ``action`` gives more positional values than its command has parameters for."""
    positional = [parameter for parameter in parameters if parameter.kind in _POSITIONAL]
    given = len(_positional_values(action))
    if _takes(parameters, inspect.Parameter.VAR_POSITIONAL) or given <= len(positional):
        return []
    return [f"{action[0]!r} takes {len(positional)} positional argument(s), {given} given"]


def _missing_required(action: list, parameters: Parameters) -> list[str]:
    """Messages for the required parameters ``action`` gives neither by position nor by keyword."""
    positional = [parameter.name for parameter in parameters if parameter.kind in _POSITIONAL]
    given = set(positional[:len(_positional_values(action))]) | set(keyword_arguments(action))
    return [f"{action[0]!r} needs the argument {parameter.name!r}" for parameter in parameters
            if parameter.default is inspect.Parameter.empty
            and parameter.kind in (*_POSITIONAL, inspect.Parameter.KEYWORD_ONLY)
            and parameter.name not in given]


def argument_findings(location: str, action: list, command: Callable[..., Any]) -> list[dict[str, Any]]:
    """The findings for the arguments ``action`` gives ``command``; ``action`` is well-formed."""
    parameters = _parameters(command)
    if parameters is None:
        return []
    checks = (("unknown_argument", _unknown_keywords), ("too_many_arguments", _too_many_values),
              ("missing_argument", _missing_required))
    return [_finding(rule, message, location) for rule, check in checks for message in check(action, parameters)]


def all_argument_findings(actions: list[tuple[str, Any]],
                          commands: Mapping[str, Callable[..., Any]]) -> list[dict[str, Any]]:
    """The argument findings of every ``(location, action)`` whose command is in ``commands``."""
    findings: list[dict[str, Any]] = []
    for location, action in actions:
        command = commands.get(action[0])
        if command is not None:
            findings.extend(argument_findings(location, action, command))
    return findings
