"""
Test-blame ownership lookup.

Given a test name and the project's ``CODEOWNERS`` (GitHub style) plus
``git blame`` history for the test file, decide who to ping when the
test fails. Falls back through:

1. Closest matching CODEOWNERS rule for the test path.
2. Author with the most lines remaining in the test (from blame).
3. Most-recent committer (HEAD).
4. Project-wide default owner (caller-supplied).

CODEOWNERS is read by the parser and the matcher of ``test_owners_map``
(:func:`~je_web_runner.utils.test_owners_map.owners.pattern_matches`); the
owners are returned here without their leading ``@``.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.test_owners_map.owners import codeowners_lines, pattern_matches


class BlameOwnerError(WebRunnerException):
    """Raised on malformed inputs."""


@dataclass
class BlameLine:
    """Author and commit of one line of ``git blame`` output."""
    author: str = ""
    commit: str = ""


@dataclass
class CodeownersRule:
    """One CODEOWNERS line: a path pattern and the owners it names."""
    pattern: str
    owners: list[str] = field(default_factory=list)


def parse_codeowners(text: str) -> list[CodeownersRule]:
    """Parse CODEOWNERS text into rules in file order, dropping comments, lines
    without an owner and the leading ``@`` of each owner.
    Raises ``BlameOwnerError`` when ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise BlameOwnerError("CODEOWNERS text must be a string")
    return [CodeownersRule(pattern=pattern, owners=[o.lstrip("@") for o in owners])
            for pattern, owners in codeowners_lines(text)]


def owners_from_codeowners(
    rules: Sequence[CodeownersRule], test_path: str,
) -> list[str]:
    """The *last* matching rule wins, per GitHub semantics."""
    if not isinstance(test_path, str) or not test_path:
        raise BlameOwnerError("test_path must be non-empty")
    selected: CodeownersRule | None = None
    for rule in rules:
        if pattern_matches(rule.pattern, test_path):
            selected = rule
    return list(selected.owners) if selected else []


def owners_from_blame(
    blame: Iterable[BlameLine],
) -> list[str]:
    """Return up to three authors, those with the most blamed lines first."""
    counts = Counter(b.author for b in blame if b.author)
    return [name for name, _ in counts.most_common(3)]


@dataclass
class OwnerVerdict:
    """Who to notify for a test, the backups, and which source decided it."""
    primary: str
    backups: list[str] = field(default_factory=list)
    source: str = ""   # "codeowners" | "blame" | "head" | "default"


def resolve_owner(
    test_path: str,
    *,
    codeowners: Sequence[CodeownersRule] = (),
    blame: Sequence[BlameLine] = (),
    head_author: str = "",
    default: str = "",
) -> OwnerVerdict:
    """Apply the priority chain to produce a single primary owner."""
    co = owners_from_codeowners(codeowners, test_path)
    if co:
        return OwnerVerdict(primary=co[0], backups=co[1:], source="codeowners")
    bl = owners_from_blame(blame)
    if bl:
        return OwnerVerdict(primary=bl[0], backups=bl[1:], source="blame")
    if head_author:
        return OwnerVerdict(primary=head_author, source="head")
    if default:
        return OwnerVerdict(primary=default, source="default")
    raise BlameOwnerError(
        f"no owner found for {test_path!r} — supply a `default`"
    )


def assert_has_owner(verdict: OwnerVerdict) -> None:
    """Raise ``BlameOwnerError`` when the verdict names no primary owner."""
    if not verdict.primary:
        raise BlameOwnerError(
            "verdict.primary is empty — every test must have an owner"
        )
