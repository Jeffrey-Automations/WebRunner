"""
改寫文件的功能：格式化與快速修正
The features that change the document: formatting it, and the quick fix that replaces a legacy command name.
"""
from __future__ import annotations

import json
from typing import Any

from je_web_runner.action_lsp._commands import single_replacement
from je_web_runner.action_lsp._diagnostics import LintResult, finding_diagnostic, lint_text
from je_web_runner.action_lsp._positions import _string_end
from je_web_runner.action_lsp._text import range_between
from je_web_runner.utils.action_formatter.formatter import ActionFormatterError, format_text

LEGACY_RULE = "legacy_name"
QUICK_FIX = "quickfix"


def formatting_edits(text: str) -> list[dict[str, Any]]:
    """
    整份文件的格式化編輯
    One edit that replaces the whole document with its formatted form; none when it is formatted already or
    the formatter cannot take it (not valid JSON, not a list of actions).
    """
    try:
        formatted = format_text(text)
    except ActionFormatterError:
        return []
    if formatted == text:
        return []
    return [{"range": range_between(text, 0, len(text)), "newText": formatted}]


def _name_edit(text: str, result: LintResult, finding: dict[str, Any]) -> dict[str, Any] | None:
    """The edit that gives the action of a ``legacy_name`` finding its modern name, None when there is none."""
    action = result.index.offset(str(finding.get("location", "")))
    elements = result.index.elements(action) if action is not None else []
    if not elements or text[elements[0]] != '"':
        return None
    start = elements[0]
    end = _string_end(text, start)
    try:
        name = json.loads(text[start:end])
    except ValueError:
        return None
    replacement = single_replacement(name) if isinstance(name, str) else None
    if replacement is None:
        return None
    return {"range": range_between(text, start, end), "newText": json.dumps(replacement),
            "title": f"Replace {name!r} with {replacement!r}"}


def _same_diagnostic(sent: dict[str, Any], built: dict[str, Any]) -> bool:
    """Whether a diagnostic the client sent back is the one built from a finding."""
    if sent.get("code") != LEGACY_RULE or sent.get("message") != built["message"]:
        return False
    sent_range = sent.get("range")
    start = sent_range.get("start") if isinstance(sent_range, dict) else None
    if not isinstance(start, dict) or start.get("line") != built["range"]["start"]["line"]:
        return False
    data = sent.get("data")
    # A client that kept ``data`` tells two identical names on one line apart; one that dropped it gets both.
    return not isinstance(data, dict) or data.get("location") in (None, built["data"]["location"])


def legacy_name_fixes(text: str, uri: str, diagnostics: list[Any]) -> list[dict[str, Any]]:
    """
    舊命令名稱的快速修正
    A quick fix for each ``legacy_name`` diagnostic in ``diagnostics`` whose command has exactly one modern
    name: it replaces the command name in the document.
    """
    sent = [entry for entry in diagnostics if isinstance(entry, dict) and entry.get("code") == LEGACY_RULE]
    if not sent:
        return []
    result = lint_text(text)
    candidates = []
    for finding in result.findings:
        edit = _name_edit(text, result, finding) if finding.get("rule") == LEGACY_RULE else None
        if edit is not None:
            candidates.append((finding_diagnostic(finding, result.index), edit))
    fixes = []
    for entry in sent:
        edits = [edit for built, edit in candidates if _same_diagnostic(entry, built)]
        if edits:
            fixes.append({
                "title": edits[0]["title"],
                "kind": QUICK_FIX,
                "diagnostics": [entry],
                "isPreferred": True,
                "edit": {"changes": {uri: [{"range": edit["range"], "newText": edit["newText"]}
                                           for edit in edits]}},
            })
    return fixes
