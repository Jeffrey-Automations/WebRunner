"""
Action JSON linter：警告反模式（舊命令名、寫死 URL、危險 script 等）。
Action JSON linter that warns about common anti-patterns. Findings are
``{rule, severity, message, location}`` dicts; severity is ``warning`` or
``info``. Actions inside blocks (``WR_if``, the loops, ``WR_try`` …) and in
``meta.setup`` / ``meta.teardown`` are checked like top-level ones; the rules
of the action-file language are in :mod:`je_web_runner.utils.linter.flow_rules`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.linter.flow_rules import every_action, flow_findings
from je_web_runner.utils.linter.migration import LEGACY_TO_NEW
from je_web_runner.utils.linter.script_commands import ARBITRARY_SCRIPT_COMMANDS
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ActionLinterError(WebRunnerException):
    """Raised when the input cannot be read or parsed."""


# Map legacy → suggested replacement: the names the migration rewrites (aliases added in fix #3-#11),
# plus the one that has no single replacement and is therefore only reported.
_LEGACY_NAMES: dict[str, str] = {
    **LEGACY_TO_NEW,
    "WR_element_get_select": (
        "WR_element_select_by_value / WR_element_select_by_index "
        "/ WR_element_select_by_visible_text"
    ),
}

_DANGEROUS_SCRIPT_COMMANDS = ARBITRARY_SCRIPT_COMMANDS

_HARDCODED_URL_RE = re.compile(r"https?://[^\s${}]+")


def _walk_args(value: Any, location: str, findings: list[dict[str, Any]]) -> None:
    """Recursively scan args for hard-coded URLs."""
    if isinstance(value, str):
        if _HARDCODED_URL_RE.search(value) and "${ENV." not in value and "${ROW." not in value:
            findings.append({
                "rule": "hardcoded_url",
                "severity": "warning",
                "message": f"hard-coded URL {value!r}; consider ${{ENV.X}}",
                "location": location,
            })
        return
    if isinstance(value, dict):
        for key, sub in value.items():
            _walk_args(sub, f"{location}.{key}", findings)
        return
    if isinstance(value, (list, tuple)):
        for index, sub in enumerate(value):
            _walk_args(sub, f"{location}[{index}]", findings)


def _check_name_rules(action: list, location: str, findings: list[dict[str, Any]]) -> None:
    """The rules that look at one action's name and argument slots; ``action`` is well-formed."""
    name = action[0]

    if name in _LEGACY_NAMES:
        findings.append({
            "rule": "legacy_name",
            "severity": "warning",
            "message": f"{name!r} is a legacy alias; prefer {_LEGACY_NAMES[name]!r}",
            "location": location,
        })

    if name in _DANGEROUS_SCRIPT_COMMANDS:
        findings.append({
            "rule": "arbitrary_script",
            "severity": "warning",
            "message": f"{name!r} runs arbitrary script; gate with WR_set_allow_arbitrary_script",
            "location": location,
        })

    if len(action) >= 2 and action[1] == {}:
        findings.append({
            "rule": "empty_kwargs",
            "severity": "info",
            "message": f"{name!r} called with empty {{}}; drop the kwargs slot",
            "location": location,
        })


def _check_action(action: Any, index: int, findings: list[dict[str, Any]]) -> None:
    location = f"action[{index}]"
    if not isinstance(action, list) or not action or not isinstance(action[0], str):
        # The validator covers structural problems; the linter only adds
        # advisory findings for well-formed inputs.
        return
    _check_name_rules(action, location, findings)
    # The walk goes through the whole action, so URLs of nested actions are found here too.
    for slot_index in range(1, len(action)):
        _walk_args(action[slot_index], f"{location}.args[{slot_index - 1}]", findings)


def _check_nested(action_list: list[Any], prefix: str, findings: list[dict[str, Any]]) -> None:
    """Apply the name rules to the actions inside blocks; ``top_level`` ones were checked already."""
    top_level = {f"{prefix}[{index}]" for index in range(len(action_list))}
    for location, action in every_action(action_list, prefix):
        if location not in top_level:
            _check_name_rules(action, location, findings)


def _known_commands() -> dict[str, Any] | None:
    """The registered commands by name, or None when the executor cannot be imported."""
    try:
        from je_web_runner.utils.executor.action_executor import executor
    except Exception as error:  # pylint: disable=broad-except
        web_runner_logger.warning(f"action linter: executor unavailable: {error!r}")
        return None
    return {name: command for name, command in executor.event_dict.items() if isinstance(name, str)}


def _check_hook(meta: dict[str, Any], key: str, findings: list[dict[str, Any]]) -> None:
    """The name rules for the actions of ``meta.setup`` / ``meta.teardown``."""
    actions = meta.get(key)
    if isinstance(actions, list):
        for location, action in every_action(actions, f"meta.{key}"):
            _check_name_rules(action, location, findings)


def _check_duplicates(action_list: list[Any], findings: list[dict[str, Any]]) -> None:
    """Flag two identical consecutive actions."""
    for index in range(1, len(action_list)):
        if action_list[index] == action_list[index - 1]:
            findings.append({
                "rule": "duplicate_consecutive",
                "severity": "info",
                "message": f"action[{index}] is identical to action[{index - 1}]",
                "location": f"action[{index}]",
            })


def lint_action(data: Any) -> list[dict[str, Any]]:
    """Walk an action structure and return the findings list."""
    findings: list[dict[str, Any]] = []
    meta: Any = {}
    if isinstance(data, dict):
        action_list = data.get("webdriver_wrapper")
        meta = data.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}
        if not (meta.get("tags") or []):
            findings.append({
                "rule": "missing_tags",
                "severity": "info",
                "message": "no meta.tags declared; tag-based filters won't pick this file up",
                "location": "meta",
            })
    else:
        action_list = data
    if not isinstance(action_list, list):
        return findings
    for index, action in enumerate(action_list):
        _check_action(action, index, findings)
    _check_nested(action_list, "action", findings)
    for key in ("setup", "teardown"):
        _check_hook(meta, key, findings)
    _check_duplicates(action_list, findings)
    findings.extend(flow_findings(action_list, meta, _known_commands()))
    return findings


def lint_action_file(path: str) -> list[dict[str, Any]]:
    """Read ``path`` (UTF-8 JSON) and lint the contents."""
    file_path = Path(path)
    if not file_path.exists():
        raise ActionLinterError(f"action file not found: {path}")
    try:
        with open(file_path, encoding="utf-8") as action_file:
            data = json.load(action_file)
    except ValueError as error:
        raise ActionLinterError(f"action file not valid JSON: {path}") from error
    web_runner_logger.info(f"lint_action_file: {path}")
    return lint_action(data)


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate ``{warning: N, info: M}`` for reporting."""
    counts: dict[str, int] = {"warning": 0, "info": 0}
    for finding in findings:
        sev = finding.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    return counts
