"""
把 linter 的發現轉成 LSP 診斷
Linter findings as LSP diagnostics. A finding sits on the line where what it is about starts: its action,
a nested action inside a block, or the argument it names. Each diagnostic carries the rule as its ``code``
and the linter location in ``data``, so a client can send it back for a quick fix.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from je_web_runner.action_lsp._positions import LocationIndex
from je_web_runner.utils.linter.action_linter import lint_action

SOURCE = "webrunner-action-lsp"
_ROOT_MESSAGE = 'Action document must be a JSON array, or an object with a "webdriver_wrapper" array.'
# LSP DiagnosticSeverity: 1 error, 2 warning, 3 information.
_ERROR = 1
_SEVERITIES = {"error": _ERROR, "warning": 2, "info": 3}
_LINE_END = 200


@dataclass
class LintResult:
    """
    The findings of one document text, or the ``problem`` that kept it from being linted; ``data`` is the
    parsed document when the text is valid JSON.
    """
    index: LocationIndex
    data: Any = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    problem: str | None = None


def lint_text(text: str) -> LintResult:
    """Parse and lint ``text``. An empty text has no findings and no problem."""
    result = LintResult(index=LocationIndex(text, False))
    if not text.strip():
        return result
    try:
        actions = json.loads(text)
    except ValueError as error:
        result.problem = f"JSON parse error: {error}"
        return result
    dict_root = isinstance(actions, dict)
    action_list = actions.get("webdriver_wrapper") if dict_root else actions
    if not isinstance(action_list, list):
        result.data = actions
        result.problem = _ROOT_MESSAGE
        return result
    return LintResult(index=LocationIndex(text, dict_root), data=actions, findings=lint_action(actions))


def diagnostic(error_message: str, line: int, severity: int) -> dict[str, Any]:
    """A diagnostic that covers ``line``."""
    return {
        "range": {
            "start": {"line": max(0, line), "character": 0},
            "end": {"line": max(0, line), "character": _LINE_END},
        },
        "severity": severity,
        "source": SOURCE,
        "message": error_message,
    }


def finding_diagnostic(finding: dict[str, Any], index: LocationIndex) -> dict[str, Any]:
    """One linter finding as a diagnostic on the line of what it is about (line 0 when that is not found)."""
    rule = str(finding.get("rule", "lint"))
    location = str(finding.get("location", ""))
    result = diagnostic(
        error_message=f"[{rule}] {finding.get('message', '')}",
        line=index.line(location),
        severity=_SEVERITIES.get(str(finding.get("severity")), 3),
    )
    result["code"] = rule
    result["data"] = {"location": location}
    return result


def result_diagnostics(result: LintResult) -> list[dict[str, Any]]:
    """
    文件的診斷清單
    The diagnostics of a linted text: one error when it is not an action document, else its lint findings.
    """
    if result.problem is not None:
        return [diagnostic(result.problem, line=0, severity=_ERROR)]
    return [finding_diagnostic(finding, result.index) for finding in result.findings]
