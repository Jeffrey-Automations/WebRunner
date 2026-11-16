"""
CODEOWNERS-style file → test → team 對映表。
When a failing test pages someone at 3am, the question "who owns this?"
should have a deterministic answer. This module provides:

* :class:`OwnersFile` — parses a CODEOWNERS-format file (Github semantics).
* :class:`OwnersMap` — adds a per-test override layer (a small YAML/JSON
  file your team controls separately).
* Lookup helpers + bulk audit ("which tests have no owner?").

:func:`codeowners_lines` and :func:`pattern_matches` are the one CODEOWNERS
reader of the package; ``test_blame_owner`` and ``test_debt_dashboard`` use them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TestOwnersMapError(WebRunnerException):
    """Raised on malformed CODEOWNERS / override file / lookup args."""

    __test__ = False  # domain exception, not a pytest test class


# ---------- CODEOWNERS parser -----------------------------------------

@dataclass
class CodeownersRule:
    """One CODEOWNERS line."""

    pattern: str
    owners: list[str] = field(default_factory=list)


@dataclass
class OwnersFile:
    """Parsed CODEOWNERS body. Lookups use *last-matching* glob (Github)."""

    rules: list[CodeownersRule] = field(default_factory=list)

    def lookup(self, path: str) -> list[str]:
        """Return the owners of the last rule matching ``path`` (empty when none matches).
        Raises ``TestOwnersMapError`` for an empty or non-string path.
        """
        if not isinstance(path, str) or not path:
            raise TestOwnersMapError("path must be non-empty string")
        winner: list[str] = []
        for rule in self.rules:
            if pattern_matches(rule.pattern, path):
                winner = list(rule.owners)
        return winner


# A "#" that follows whitespace starts a trailing comment ("@owner#1" keeps its "#"). The match
# starts at the "#" itself, so it is linear; r"\s+#.*$" restarted inside every whitespace run.
_TRAILING_COMMENT_RE = re.compile(r"(?<=\s)#")


def codeowners_lines(text: str) -> list[tuple[str, list[str]]]:
    """
    ``(pattern, owners)`` for every rule line of a CODEOWNERS body, in file order. Comment lines,
    trailing comments and lines that name no owner are dropped; the owners keep their ``@``.
    """
    if not isinstance(text, str):
        raise TestOwnersMapError(
            f"parse_codeowners expects str, got {type(text).__name__}"
        )
    lines: list[tuple[str, list[str]]] = []
    for raw in text.splitlines():
        # Strip trailing comments (but keep '#' inside owners like @owner#1)
        comment = _TRAILING_COMMENT_RE.search(raw)
        line = (raw[:comment.start()] if comment else raw).strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        lines.append((parts[0], parts[1:]))
    return lines


def parse_codeowners(text: str) -> OwnersFile:
    """Parse a CODEOWNERS-format string."""
    return OwnersFile(rules=[
        CodeownersRule(pattern=pattern, owners=owners) for pattern, owners in codeowners_lines(text)
    ])


def load_codeowners_file(path: str | Path) -> OwnersFile:
    """Read and parse a CODEOWNERS file from disk."""
    p = Path(path)
    if not p.exists():
        raise TestOwnersMapError(f"file not found: {p}")
    return parse_codeowners(p.read_text(encoding="utf-8"))


def pattern_matches(pattern: str, path: str) -> bool:
    """
    Whether the CODEOWNERS ``pattern`` owns the ``/``-separated ``path``, as GitHub reads it.

    ``*`` stays inside one path segment and ``**`` crosses them (``**/`` also matches no directory);
    a leading ``/`` anchors the pattern at the root, otherwise it may start at any directory. A
    pattern that ends in ``/``, or whose last segment has no ``*``, names a file or a directory and
    owns everything below it (``/apps/github`` owns ``apps/github/hook.py``); one whose last segment
    has a ``*`` owns only what that segment matches (``docs/*`` does not own ``docs/guide/intro.md``).
    """
    if pattern == "*":
        return True
    pat = pattern.rstrip("/")
    regex = (re.escape(pat)
             .replace(r"\*\*/", "(?:.*/)?")
             .replace(r"\*\*", ".*")
             .replace(r"\*", "[^/]*"))
    if pat.startswith("/"):
        regex = "^" + regex[1:]
    else:
        regex = "(^|/)" + regex
    names_a_directory = pattern.endswith("/") or "*" not in pat.rsplit("/", 1)[-1]
    regex += "(/|$)" if names_a_directory else "$"
    return re.search(regex, path) is not None


# ---------- override layer --------------------------------------------

@dataclass
class OwnersMap:
    """Combined CODEOWNERS + per-test override lookup."""

    codeowners: OwnersFile
    overrides: dict[str, list[str]] = field(default_factory=dict)

    def owners_for(self, test_id: str) -> list[str]:
        """Return the override owners of ``test_id`` when one is set, else the CODEOWNERS lookup.
        Raises ``TestOwnersMapError`` for an empty or non-string id.
        """
        if not isinstance(test_id, str) or not test_id:
            raise TestOwnersMapError("test_id must be non-empty string")
        if test_id in self.overrides:
            return list(self.overrides[test_id])
        return self.codeowners.lookup(test_id)


def load_overrides(path: str | Path) -> dict[str, list[str]]:
    """
    Load a per-test override JSON file. Schema:
    ``{"<test_id>": ["@owner1", "@owner2"], ...}``.
    """
    p = Path(path)
    if not p.exists():
        raise TestOwnersMapError(f"overrides file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as error:
        raise TestOwnersMapError(f"overrides not JSON: {error}") from error
    if not isinstance(data, dict):
        raise TestOwnersMapError("overrides JSON must be an object")
    out: dict[str, list[str]] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise TestOwnersMapError(
                f"override for {key!r} must be a list of strings"
            )
        out[key] = list(value)
    return out


# ---------- audit -----------------------------------------------------

@dataclass
class OwnerAudit:
    """Outcome of :func:`audit_unowned`."""

    total_tests: int
    unowned: list[str] = field(default_factory=list)
    by_owner: dict[str, int] = field(default_factory=dict)

    def passed(self) -> bool:
        """True when no test is left without an owner."""
        return not self.unowned


def audit_unowned(
    test_ids: Iterable[str],
    owners_map: OwnersMap,
) -> OwnerAudit:
    """Walk ``test_ids``, list any without an owner, count by owner."""
    if not isinstance(owners_map, OwnersMap):
        raise TestOwnersMapError("owners_map must be an OwnersMap")
    audit = OwnerAudit(total_tests=0)
    for test_id in test_ids:
        if not isinstance(test_id, str) or not test_id:
            continue
        audit.total_tests += 1
        owners = owners_map.owners_for(test_id)
        if not owners:
            audit.unowned.append(test_id)
            continue
        for owner in owners:
            audit.by_owner[owner] = audit.by_owner.get(owner, 0) + 1
    return audit


# ---------- assertions / formatting -----------------------------------

def assert_no_unowned(audit: OwnerAudit) -> None:
    """Raise if any test in the audit has no owner."""
    if not isinstance(audit, OwnerAudit):
        raise TestOwnersMapError("expects OwnerAudit")
    if audit.passed():
        return
    sample = ", ".join(audit.unowned[:5])
    more = "" if len(audit.unowned) <= 5 else f" (+{len(audit.unowned) - 5})"
    raise TestOwnersMapError(
        f"{len(audit.unowned)} unowned tests: {sample}{more}"
    )


def audit_markdown(audit: OwnerAudit, *, top_owners: int = 10) -> str:
    """Render a small markdown table for dashboards."""
    if not isinstance(audit, OwnerAudit):
        raise TestOwnersMapError("expects OwnerAudit")
    if top_owners < 0:
        raise TestOwnersMapError("top_owners must be >= 0")
    lines = [
        f"### Test ownership audit ({audit.total_tests} tests)",
        "",
        f"- unowned: **{len(audit.unowned)}**",
        "",
    ]
    if audit.by_owner:
        lines.append("| Owner | Tests |")
        lines.append("|-------|-------|")
        ranked = sorted(audit.by_owner.items(), key=lambda kv: -kv[1])[:top_owners]
        for owner, count in ranked:
            lines.append(f"| {owner} | {count} |")
    return "\n".join(lines) + "\n"
