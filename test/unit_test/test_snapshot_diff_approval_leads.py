"""snapshot_diff_approval: a mismatch keeps the baseline, a rejection leaves it in force; bad files raise."""
import hashlib
import json

import pytest

from je_web_runner.utils.snapshot_diff_approval.approval import (
    SnapshotDiffApprovalError,
    Status,
    approve,
    capture,
    list_pending,
    load,
    reject,
    save,
)

GOOD = b"approved rendering"
BAD = b"broken rendering"
GOOD_SHA = hashlib.sha256(GOOD).hexdigest()
BAD_SHA = hashlib.sha256(BAD).hexdigest()


def _registry_with_baseline():
    registry = {}
    capture(registry, name="hero", payload=GOOD)
    approve(registry, name="hero", reviewer="alice")
    return registry


def test_a_second_mismatch_is_still_compared_with_the_baseline():
    registry = _registry_with_baseline()
    capture(registry, name="hero", payload=BAD)
    again = capture(registry, name="hero", payload=BAD)
    assert (again.baseline_sha, again.head_sha, again.changed) == (GOOD_SHA, BAD_SHA, True)


def test_a_rejected_candidate_leaves_the_baseline_in_force():
    registry = _registry_with_baseline()
    capture(registry, name="hero", payload=BAD)
    rejected = reject(registry, name="hero", reviewer="bob", note="regression")
    assert (rejected.status, rejected.sha256) == (Status.REJECTED, BAD_SHA)
    back_to_good = capture(registry, name="hero", payload=GOOD)
    assert (back_to_good.baseline_sha, back_to_good.changed) == (GOOD_SHA, False)
    assert list_pending(registry) == []
    still_bad = capture(registry, name="hero", payload=BAD)
    assert (still_bad.baseline_sha, still_bad.changed) == (GOOD_SHA, True)


def test_a_run_that_matches_the_baseline_again_clears_the_pending_candidate():
    registry = _registry_with_baseline()
    capture(registry, name="hero", payload=BAD)
    result = capture(registry, name="hero", payload=GOOD)
    assert result.changed is False
    assert (registry["hero"].status, registry["hero"].sha256) == (Status.BASELINE, GOOD_SHA)


def test_the_kept_baseline_survives_a_save_and_a_load(tmp_path):
    registry = _registry_with_baseline()
    capture(registry, name="hero", payload=BAD)
    path = str(tmp_path / "snapshots.json")
    save(path, registry)
    result = capture(load(path), name="hero", payload=BAD)
    assert result.baseline_sha == GOOD_SHA


def test_approving_the_candidate_makes_it_the_baseline():
    registry = _registry_with_baseline()
    capture(registry, name="hero", payload=BAD)
    approve(registry, name="hero", reviewer="alice")
    assert capture(registry, name="hero", payload=BAD).changed is False
    assert capture(registry, name="hero", payload=GOOD).baseline_sha == BAD_SHA


def test_registry_that_is_not_json(tmp_path):
    path = tmp_path / "snapshots.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SnapshotDiffApprovalError, match="not JSON"):
        load(str(path))


def test_registry_entry_with_an_unknown_status(tmp_path):
    path = tmp_path / "snapshots.json"
    path.write_text(json.dumps({"hero": {"sha256": "x", "status": "maybe"}}), encoding="utf-8")
    with pytest.raises(SnapshotDiffApprovalError, match="maybe"):
        load(str(path))
