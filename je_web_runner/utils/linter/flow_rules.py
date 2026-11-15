"""
動作檔語言的 lint 規則
Linter rules for the action-file language: unknown commands, blocks of the wrong shape, a ``WR_while``
without a limit, and placeholders that no action of the file defines.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Iterable

from je_web_runner.utils.flow.structure import (
    defined_variables,
    keyword_arguments,
    misshapen_blocks,
    nested_actions,
)
from je_web_runner.utils.flow.variables import RESERVED_NAMES
from je_web_runner.utils.linter.argument_rules import all_argument_findings

_PLACEHOLDER_ROOT_RE = re.compile(r"\$\{([A-Za-z_]\w*)[.}]")
# Arguments whose strings are code for the browser: ``${x}`` there is a JavaScript template literal.
_SCRIPT_ARGUMENTS = frozenset({"script", "expression", "source", "js"})


def _finding(rule: str, severity: str, message: str, location: str) -> dict[str, Any]:
    return {"rule": rule, "severity": severity, "message": message, "location": location}


def _walk(action_list: list, prefix: str) -> Iterable[tuple[str, Any]]:
    """``(location, action)`` for every action of ``action_list``, nested ones included, in order."""
    for index, action in enumerate(action_list):
        location = f"{prefix}[{index}]"
        yield location, action
        yield from _walk_nested(action, location)


def _walk_nested(action: Any, location: str) -> Iterable[tuple[str, Any]]:
    for nested_location, nested in nested_actions(action, location):
        yield nested_location, nested
        yield from _walk_nested(nested, nested_location)


def every_action(action_list: list, prefix: str = "action") -> list[tuple[str, Any]]:
    """Every well-formed action of the list with its location, the actions inside blocks included."""
    return [(location, action) for location, action in _walk(action_list, prefix)
            if isinstance(action, list) and action and isinstance(action[0], str)]


def _used_roots(value: Any, key: str | None = None) -> set[str]:
    """The first names of the placeholders in ``value``, script arguments left out."""
    if isinstance(value, str):
        return set() if key in _SCRIPT_ARGUMENTS else set(_PLACEHOLDER_ROOT_RE.findall(value))
    if isinstance(value, dict):
        return set().union(*(_used_roots(sub, name) for name, sub in value.items())) if value else set()
    if isinstance(value, (list, tuple)):
        return set().union(*(_used_roots(sub, key) for sub in value)) if value else set()
    return set()


def _structure_findings(location: str, action: list, known: frozenset[str] | None) -> list[dict[str, Any]]:
    name = action[0]
    findings = []
    if known is not None and name not in known:
        findings.append(_finding(
            "unknown_command", "warning",
            f"{name!r} is not a registered command (fine if a package or add_command_to_executor adds it)",
            location))
    for key in misshapen_blocks(action):
        findings.append(_finding(
            "block_shape", "warning", f"{name!r} {key} must be a list of actions", location))
    if name == "WR_while" and "max_iterations" not in keyword_arguments(action):
        findings.append(_finding(
            "while_without_limit", "warning", "'WR_while' needs max_iterations; it fails without one", location))
    return findings


def flow_findings(action_list: list, meta: dict[str, Any] | None = None,
                  known_commands: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """
    The findings of the language rules for ``action_list`` (and the ``setup`` / ``teardown`` / ``vars`` of
    ``meta``). ``known_commands`` enables the unknown-command rule; None leaves it out. When it maps
    each name to its command, the arguments are checked against the command's signature too.
    """
    meta = meta if isinstance(meta, dict) else {}
    known = None if known_commands is None else frozenset(known_commands)
    actions = []
    for prefix, block in (("meta.setup", meta.get("setup")), ("action", action_list),
                          ("meta.teardown", meta.get("teardown"))):
        if isinstance(block, list):
            actions.extend(every_action(block, prefix))
    defined = set(RESERVED_NAMES)
    if isinstance(meta.get("vars"), dict):
        defined.update(meta["vars"])
    for _location, action in actions:
        defined.update(defined_variables(action))
    findings: list[dict[str, Any]] = []
    for location, action in actions:
        findings.extend(_structure_findings(location, action, known))
        for root in sorted(_used_roots(action[1:]) - defined):
            findings.append(_finding(
                "undefined_variable", "info",
                f"${{{root}}} is not set by this file; it stays as written unless a caller or --var sets it",
                location))
    if isinstance(known_commands, Mapping):
        findings.extend(all_argument_findings(actions, known_commands))
    return findings
