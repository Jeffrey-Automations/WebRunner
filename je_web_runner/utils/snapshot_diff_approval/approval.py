"""
Visual / text snapshot diff + approval workflow.

Maintains an on-disk register of snapshots with three states:

* **baseline** — committed reference. CI diffs against this.
* **pending** — produced by a test run that doesn't match the baseline;
  needs human review before promotion to baseline.
* **rejected** — explicitly rejected (kept for audit / blame).

A pending or rejected entry keeps the hash of the baseline it was compared
with (``baseline_sha256``), so the baseline stays in force until a candidate
is approved: later runs are still diffed against it, and a run that matches
it again clears a pending candidate.

Workflow helpers: ``capture``, ``compare`` (returns ``DiffResult``),
``approve``, ``reject``, ``list_pending``. Bytes/text comparison only —
visual pixel diff is delegated to [[visual_ai]].
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SnapshotDiffApprovalError(WebRunnerException):
    """Raised on malformed input or invalid state transitions."""


class Status(str, Enum):
    """Review state of a snapshot in the registry."""
    BASELINE = "baseline"
    PENDING = "pending"
    REJECTED = "rejected"


@dataclass
class SnapshotEntry:
    """One snapshot in the registry: its content hash, review state and who reviewed it."""
    name: str
    sha256: str
    status: Status
    updated_at: str
    approved_by: str = ""
    note: str = ""
    baseline_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return the fields as a plain dict, with the ``status`` enum replaced by its string value."""
        return {**asdict(self), "status": self.status.value}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def _hash(payload: bytes) -> str:
    if not isinstance(payload, (bytes, bytearray)):
        raise SnapshotDiffApprovalError("payload must be bytes")
    return hashlib.sha256(bytes(payload)).hexdigest()


@dataclass
class DiffResult:
    """Baseline hash and new hash of one snapshot, as compared by a test run."""
    name: str
    baseline_sha: str
    head_sha: str

    @property
    def changed(self) -> bool:
        """True when the new hash differs from the baseline hash."""
        return self.baseline_sha != self.head_sha


def load(path: str) -> dict[str, SnapshotEntry]:
    """Read the registry file into a ``name -> SnapshotEntry`` dict.
    A missing file gives an empty registry; entries that are not objects are skipped.
    Raises ``SnapshotDiffApprovalError`` when the file is not a JSON object or an entry
    has an unknown status.
    """
    if not isinstance(path, str) or not path:
        raise SnapshotDiffApprovalError("path must be non-empty string")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except ValueError as error:
        raise SnapshotDiffApprovalError(f"registry file {path!r} is not JSON: {error}") from error
    if not isinstance(raw, dict):
        raise SnapshotDiffApprovalError(
            f"registry file {path!r} must contain a JSON object"
        )
    out: dict[str, SnapshotEntry] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            continue
        out[name] = SnapshotEntry(
            name=name,
            sha256=str(item.get("sha256") or ""),
            status=_status_of(item.get("status", Status.PENDING.value), name),
            updated_at=str(item.get("updated_at") or _now()),
            approved_by=str(item.get("approved_by") or ""),
            note=str(item.get("note") or ""),
            baseline_sha256=str(item.get("baseline_sha256") or ""),
        )
    return out


_STATUS_BY_VALUE = {status.value: status for status in Status}


def _status_of(value: Any, name: str) -> Status:
    """The :class:`Status` named ``value``; raises ``SnapshotDiffApprovalError`` for an unknown one."""
    status = _STATUS_BY_VALUE.get(value) if isinstance(value, str) else None
    if status is None:
        raise SnapshotDiffApprovalError(
            f"snapshot {name!r} has status {value!r}; known: {sorted(_STATUS_BY_VALUE)}"
        )
    return status


def _baseline_of(entry: SnapshotEntry | None) -> str:
    """The baseline hash in force for ``entry``: its own when it is the baseline, else the one it kept."""
    if entry is None:
        return ""
    return entry.sha256 if entry.status == Status.BASELINE else entry.baseline_sha256


def save(path: str, registry: dict[str, SnapshotEntry]) -> None:
    """Write the registry to ``path`` as JSON, sorted by snapshot name."""
    if not isinstance(path, str) or not path:
        raise SnapshotDiffApprovalError("path must be non-empty string")
    serialised = {name: e.to_dict() for name, e in registry.items()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(serialised, fh, indent=2, sort_keys=True)


def capture(
    registry: dict[str, SnapshotEntry], *, name: str, payload: bytes,
) -> DiffResult:
    """Compare ``payload`` against baseline. If no baseline exists, the
    snapshot enters as ``pending``; a mismatch enters as ``pending`` too and
    keeps the baseline it was compared with. A payload that matches the
    baseline changes nothing, except that it clears a pending candidate."""
    if not name:
        raise SnapshotDiffApprovalError("name must be non-empty")
    head = _hash(payload)
    existing = registry.get(name)
    baseline = _baseline_of(existing)
    if not baseline:
        registry[name] = SnapshotEntry(
            name=name, sha256=head, status=Status.PENDING,
            updated_at=_now(),
        )
        return DiffResult(name=name, baseline_sha="", head_sha=head)
    if baseline != head:
        if existing is None or existing.status != Status.REJECTED or existing.sha256 != head:
            registry[name] = SnapshotEntry(
                name=name, sha256=head, status=Status.PENDING,
                updated_at=_now(), note="auto-captured on mismatch",
                baseline_sha256=baseline,
            )
    elif existing is not None and existing.status == Status.PENDING:
        registry[name] = SnapshotEntry(
            name=name, sha256=baseline, status=Status.BASELINE,
            updated_at=_now(), note="matches the baseline again",
        )
    return DiffResult(name=name, baseline_sha=baseline, head_sha=head)


def approve(
    registry: dict[str, SnapshotEntry], *, name: str, reviewer: str,
) -> SnapshotEntry:
    """Promote the pending snapshot ``name`` to baseline and record ``reviewer``.
    Raises ``SnapshotDiffApprovalError`` when the snapshot is unknown or not pending,
    or when ``reviewer`` is empty.
    """
    entry = registry.get(name)
    if entry is None:
        raise SnapshotDiffApprovalError(f"unknown snapshot {name!r}")
    if entry.status != Status.PENDING:
        raise SnapshotDiffApprovalError(
            f"snapshot {name!r} is not pending (status={entry.status.value})"
        )
    if not reviewer:
        raise SnapshotDiffApprovalError("reviewer must be non-empty")
    entry.status = Status.BASELINE
    entry.approved_by = reviewer
    entry.updated_at = _now()
    entry.baseline_sha256 = ""
    return entry


def reject(
    registry: dict[str, SnapshotEntry], *, name: str,
    reviewer: str, note: str = "",
) -> SnapshotEntry:
    """Mark the snapshot ``name`` as rejected, recording ``reviewer`` and an optional note.
    The baseline the rejected candidate was compared with stays in force for later captures.
    Raises ``SnapshotDiffApprovalError`` when the snapshot is unknown or ``reviewer`` is empty.
    """
    entry = registry.get(name)
    if entry is None:
        raise SnapshotDiffApprovalError(f"unknown snapshot {name!r}")
    if not reviewer:
        raise SnapshotDiffApprovalError("reviewer must be non-empty")
    entry.status = Status.REJECTED
    entry.approved_by = reviewer
    entry.updated_at = _now()
    if note:
        entry.note = note
    return entry


def list_pending(registry: dict[str, SnapshotEntry]) -> list[SnapshotEntry]:
    """Return the entries still waiting for review."""
    return [e for e in registry.values() if e.status == Status.PENDING]


def assert_no_pending(registry: dict[str, SnapshotEntry]) -> None:
    """Raise ``SnapshotDiffApprovalError`` naming every snapshot still pending review."""
    pending = list_pending(registry)
    if pending:
        names = [e.name for e in pending]
        raise SnapshotDiffApprovalError(
            f"{len(pending)} snapshot(s) pending review: {names}"
        )
