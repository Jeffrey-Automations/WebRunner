"""Tests for the governance command adapters (``_commands_governance`` and ``_commands_governance_2``)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor import _commands_governance as part_one
from je_web_runner.utils.executor import _commands_governance_2 as part_two

COMMANDS = {**part_one.GOVERNANCE_COMMANDS, **part_two.GOVERNANCE_2_COMMANDS}
PACKAGES = (
    "action_refactor_suggester", "bug_repro_stability", "commit_msg_trigger", "failure_cluster_dbscan",
    "flake_detector", "flakiness_graveyard", "git_bisect_flake", "mutation_testing", "pr_risk_score",
    "pre_merge_gate_dsl", "quarantine_age_report", "repro_minimizer", "sla_tracker",
    "snapshot_diff_approval", "test_blame_owner", "test_categorizer", "test_cost_estimator",
    "test_debt_dashboard", "test_dup_dry", "test_naming_lint", "test_owners_map", "test_roi_scorer",
    "test_scheduler", "a11y_trend", "failure_cluster", "perf_drift", "trend_dashboard",
)


def run(command: str, /, **kwargs: Any) -> Any:
    """Call a command the way the executor does and check its result is JSON."""
    result = COMMANDS[command](**kwargs)
    json.dumps(result)
    return result


def write_json(path: Path, document: Any) -> str:
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


# ---------- tables --------------------------------------------------------

def test_tables_are_consistent():
    python_only = {**part_one.PYTHON_ONLY, **part_two.PYTHON_ONLY}
    assert not set(part_one.GOVERNANCE_COMMANDS) & set(part_two.GOVERNANCE_2_COMMANDS)
    for package in PACKAGES:
        has_command = any(name.startswith(f"WR_{package}_") for name in COMMANDS)
        assert has_command or package in python_only, package
    assert set(python_only) <= set(PACKAGES)
    assert all(reason.strip() for reason in python_only.values())
    for name, function in COMMANDS.items():
        assert any(name.startswith(f"WR_{package}_") for package in PACKAGES), name
        assert name == name.lower().replace("wr_", "WR_", 1), name
        assert (function.__doc__ or "").strip(), name
    assert part_one.NETWORK_COMMANDS <= set(part_one.GOVERNANCE_COMMANDS)
    assert part_two.NETWORK_COMMANDS <= set(part_two.GOVERNANCE_2_COMMANDS)


def test_every_command_is_exercised_here():
    source = Path(__file__).read_text(encoding="utf-8")
    missing = [name for name in COMMANDS if f'"{name}"' not in source]
    assert missing == []


def test_moment_of_defaults_to_utc():
    assert part_one.moment_of(None) is None
    assert part_one.moment_of("2026-01-01T00:00:00").utcoffset().total_seconds() == 0
    assert part_one.moment_of("2026-01-01T00:00:00+08:00").utcoffset().total_seconds() == 8 * 3600


# ---------- action_refactor_suggester ------------------------------------

def test_action_refactor_suggester():
    smelly = [{"action_name": "sleep"}, {"action_name": "click", "by": "xpath", "by_value": "//div[3]/span"}]
    clean = [{"action_name": "click", "by": "id", "by_value": "ok"}]
    found = run("WR_action_refactor_suggester_analyze", actions=smelly)
    assert {item["rule"] for item in found} == {"no-hard-sleep", "no-positional-xpath"}
    assert found[0]["severity"] == "warn"
    assert "no-hard-sleep" in run("WR_action_refactor_suggester_markdown", actions=smelly)
    assert run("WR_action_refactor_suggester_assert_clean", actions=clean) == []
    with pytest.raises(WebRunnerException, match="warnings/errors"):
        run("WR_action_refactor_suggester_assert_clean", actions=smelly)


# ---------- bug_repro_stability ------------------------------------------

def test_bug_repro_stability():
    mixed = [False, True, {"passed": False, "error_signature": "E1", "duration_seconds": 1.5}]
    report = run("WR_bug_repro_stability_summarize", outcomes=mixed)
    assert (report["attempts"], report["failures"], report["category"]) == (3, 2, "flaky")
    assert report["errors"] == {"(unspecified)": 1, "E1": 1}
    assert "flaky" in run("WR_bug_repro_stability_markdown", outcomes=mixed)
    always = run("WR_bug_repro_stability_assert_deterministic", outcomes=[False, False])
    assert always["category"] == "deterministic"
    with pytest.raises(WebRunnerException, match="expected deterministic"):
        run("WR_bug_repro_stability_assert_deterministic", outcomes=mixed)
    assert run("WR_bug_repro_stability_assert_min_repro_pct", outcomes=mixed, minimum=50)["failures"] == 2
    with pytest.raises(WebRunnerException, match="below threshold"):
        run("WR_bug_repro_stability_assert_min_repro_pct", outcomes=mixed, minimum=90)
    with pytest.raises(WebRunnerException, match="non-empty list"):
        run("WR_bug_repro_stability_summarize", outcomes=[])


# ---------- commit_msg_trigger -------------------------------------------

def test_commit_msg_trigger():
    message = "Fix login [ci e2e] [ci shard=2/4] [smoke] closes #12"
    plan = run("WR_commit_msg_trigger_parse", message=message)
    assert plan == {"skip": False, "only_buckets": ["e2e"], "labels": ["smoke"], "shard": [2, 4],
                    "tickets": ["#12"]}
    assert run("WR_commit_msg_trigger_should_run_job", message=message, job_name="e2e") is True
    assert run("WR_commit_msg_trigger_should_run_job", message=message, job_name="unit") is False
    assert run("WR_commit_msg_trigger_assigned_shard", message=message, total_shards=4) == 1
    assert run("WR_commit_msg_trigger_assigned_shard", message="plain", total_shards=4) is None
    assert run("WR_commit_msg_trigger_assert_no_skip", message=message)["skip"] is False
    with pytest.raises(WebRunnerException, match="skip ci"):
        run("WR_commit_msg_trigger_assert_no_skip", message="docs only [skip ci]")


# ---------- failure_cluster_dbscan ---------------------------------------

def test_failure_cluster_dbscan():
    records = [
        {"test_name": "a", "message": "TimeoutError waiting for element login button"},
        {"test_name": "b", "message": "TimeoutError waiting for element login button 123"},
        {"test_name": "c", "message": "Database connection refused by host"},
    ]
    groups = run("WR_failure_cluster_dbscan_cluster", records=records)
    assert [group["size"] for group in groups] == [2, 1]
    assert groups[0]["members"] == ["a", "b"]
    assert run("WR_failure_cluster_dbscan_assert_root_causes_at_most", records=records, max_clusters=1) == 1
    two_causes = records + [{"test_name": "d", "message": "Database connection refused by host 7"}]
    with pytest.raises(WebRunnerException, match="non-singleton"):
        run("WR_failure_cluster_dbscan_assert_root_causes_at_most", records=two_causes, max_clusters=1)
    with pytest.raises(WebRunnerException, match="list of"):
        run("WR_failure_cluster_dbscan_cluster", records=["not an object"])


# ---------- flake_detector -----------------------------------------------

def test_flake_detector_scores(tmp_path):
    runs = [{"path": "t1", "passed": passed} for passed in (True, False, True, False)]
    runs += [{"path": "t2", "passed": True}] * 3
    ledger = write_json(tmp_path / "ledger.json", {"runs": runs})
    scores = run("WR_flake_detector_scores", runs=runs)
    assert scores["t1"]["is_flaky"] is True
    assert scores["t1"]["flake_score"] == pytest.approx(0.5)
    assert run("WR_flake_detector_scores", ledger_path=ledger)["t2"]["is_flaky"] is False
    assert run("WR_flake_detector_flaky_paths", ledger_path=ledger) == ["t1"]
    with pytest.raises(WebRunnerException, match="ledger_path or runs"):
        run("WR_flake_detector_scores")


def test_flake_detector_quarantine(tmp_path):
    flaky = [{"path": "t1", "passed": passed} for passed in (True, False, True, False)]
    ledger = write_json(tmp_path / "ledger.json", {"runs": flaky})
    registry = str(tmp_path / "quarantine.json")
    assert run("WR_flake_detector_quarantine_flaky", ledger_path=ledger, registry_path=registry) == ["t1"]
    listed = run("WR_flake_detector_quarantine_list", registry_path=registry)
    assert [entry["test_id"] for entry in listed] == ["t1"]
    assert run("WR_flake_detector_assert_not_quarantined", registry_path=registry, test_id="t2") is None
    with pytest.raises(WebRunnerException, match="is quarantined"):
        run("WR_flake_detector_assert_not_quarantined", registry_path=registry, test_id="t1")
    stable = write_json(tmp_path / "stable.json", {"runs": [{"path": "t1", "passed": True}] * 5})
    assert run("WR_flake_detector_release_if_stable", ledger_path=stable, registry_path=registry) == ["t1"]
    assert run("WR_flake_detector_quarantine_list", registry_path=registry) == []


# ---------- flakiness_graveyard ------------------------------------------

def test_flakiness_graveyard(tmp_path):
    path = str(tmp_path / "graveyard.json")
    entry = run("WR_flakiness_graveyard_register_flake", path=path, test_name="t1", owner="amy",
                today="2026-01-01")
    assert (entry["status"], entry["quarantined_at"], entry["owner"]) == ("quarantined", "2026-01-01", "amy")
    assert [row["test_name"] for row in run("WR_flakiness_graveyard_list", path=path)] == ["t1"]
    due = run("WR_flakiness_graveyard_due_for_burial", path=path, days=30, today="2026-03-01")
    assert [row["test_name"] for row in due] == ["t1"]
    assert run("WR_flakiness_graveyard_assert_none_due", path=path, today="2026-01-10") is None
    with pytest.raises(WebRunnerException, match="due for burial"):
        run("WR_flakiness_graveyard_assert_none_due", path=path, today="2026-03-01")
    assert run("WR_flakiness_graveyard_revive", path=path, test_name="t1")["status"] == "revived"
    run("WR_flakiness_graveyard_register_flake", path=path, test_name="t1", today="2026-03-02")
    assert run("WR_flakiness_graveyard_bury", path=path, test_name="t1")["status"] == "buried"
    assert run("WR_flakiness_graveyard_list", path=path)[0]["status"] == "buried"
    with pytest.raises(WebRunnerException, match="already buried"):
        run("WR_flakiness_graveyard_revive", path=path, test_name="t1")


# ---------- git_bisect_flake ---------------------------------------------

def test_git_bisect_flake(tmp_path):
    entries = [
        {"commit": "c1", "test_id": "t", "passed": True},
        {"commit": "c2", "test_id": "t", "passed": True},
        {"commit": "c3", "test_id": "t", "passed": False},
    ]
    order = ["c1", "c2", "c3"]
    result = run("WR_git_bisect_flake_bisect", commit_order=order, test_id="t", entries=entries)
    assert (result["last_good_commit"], result["first_bad_commit"], result["method"]) == ("c2", "c3", "ledger")
    ledger = write_json(tmp_path / "ledger.json", {"runs": [
        {"commit": row["commit"], "path": "t", "passed": row["passed"]} for row in entries
    ]})
    from_file = run("WR_git_bisect_flake_bisect", commit_order=order, test_id="t", ledger_path=ledger)
    assert from_file["first_bad_commit"] == "c3"
    assert "First bad commit: `c3`" in run(
        "WR_git_bisect_flake_markdown", commit_order=order, test_id="t", entries=entries,
    )
    with pytest.raises(WebRunnerException, match="ledger_path or entries"):
        run("WR_git_bisect_flake_bisect", commit_order=order, test_id="t")


# ---------- mutation_testing ---------------------------------------------

def test_mutation_testing():
    actions = [["WR_to_url", {"url": "https://a.test"}], ["WR_click", {"test_object_name": "button"}]]
    mutations = run("WR_mutation_testing_generate", actions=actions, types=["url_change", "locator_swap"])
    assert [item["type"] for item in mutations] == ["url_change", "locator_swap"]
    assert len(run("WR_mutation_testing_generate", actions=actions)) > len(mutations)
    mutated = run("WR_mutation_testing_apply", actions=actions, mutation=mutations[0])
    assert mutated[0][1]["url"] == "https://example.invalid/mut"
    assert actions[0][1]["url"] == "https://a.test"
    with pytest.raises(WebRunnerException, match="unknown mutation type"):
        run("WR_mutation_testing_generate", actions=actions, types=["nonsense"])
    with pytest.raises(WebRunnerException, match="'type' and 'action_index'"):
        run("WR_mutation_testing_apply", actions=actions, mutation={})
    assert run("WR_mutation_testing_assert_min_score", killed=9, total=10) == pytest.approx(0.9)
    with pytest.raises(WebRunnerException, match="below minimum"):
        run("WR_mutation_testing_assert_min_score", killed=1, total=10)


# ---------- pr_risk_score ------------------------------------------------

def test_pr_risk_score():
    risky = {
        "flaky_tests_touched": 5, "total_tests_touched": 5, "avg_flake_score": 1.0,
        "impacted_modules": 10, "repo_modules": 10, "impacted_critical_paths": 4,
        "fragile_locators_touched": 3, "total_locators_touched": 3,
        "lines_added": 100, "lines_covered": 0, "migration_files_changed": 2, "security_files_changed": 2,
    }
    report = run("WR_pr_risk_score_score", signals=risky)
    assert (report["score"], report["level"]) == (100.0, "critical")
    assert run("WR_pr_risk_score_score", signals={}, weights={"flake": 5.0})["level"] == "low"
    merged = run("WR_pr_risk_score_aggregate", per_file=[{"lines_added": 10, "repo_modules": 5},
                                                         {"lines_added": 5}])
    assert (merged["lines_added"], merged["repo_modules"]) == (15, 5)
    assert "PR risk" in run("WR_pr_risk_score_markdown", signals=risky)
    assert run("WR_pr_risk_score_assert_below", signals={})["score"] == pytest.approx(0.0)
    with pytest.raises(WebRunnerException, match="reaches 75"):
        run("WR_pr_risk_score_assert_below", signals=risky)
    with pytest.raises(WebRunnerException, match="PrSignals"):
        run("WR_pr_risk_score_score", signals={"bogus": 1})


# ---------- pre_merge_gate_dsl -------------------------------------------

def test_pre_merge_gate_dsl():
    rules = [{"when": "facts.has_path('src/*')", "require": ["two_reviewers"]}]
    one_review = {"files_changed": ["src/a.py"], "review_approvals": 1}
    result = run("WR_pre_merge_gate_dsl_evaluate", rules=rules, facts=one_review)
    assert result["passed"] is False
    assert result["failures"] == ["[two_reviewers] need 2 reviewers, have 1"]
    two_reviews = {**one_review, "review_approvals": 2}
    assert run("WR_pre_merge_gate_dsl_assert_passes", rules=rules, facts=two_reviews)["passed"] is True
    with pytest.raises(WebRunnerException, match="pre-merge gate failed"):
        run("WR_pre_merge_gate_dsl_assert_passes", rules=rules, facts=one_review)


# ---------- quarantine_age_report ----------------------------------------

def test_quarantine_age_report(tmp_path):
    old = {"test_id": "t1", "quarantined_at": "2026-01-01T00:00:00Z", "reason": "flaky"}
    recent = {"test_id": "t2", "quarantined_at": "2026-05-25T00:00:00Z"}
    now = "2026-06-01T00:00:00Z"
    report = run("WR_quarantine_age_report_build", entries=[old, recent], now=now)
    assert report["by_tier"] == {"abandoned": 1, "lingering": 1}
    assert report["abandoned"] == ["t1"]
    assert report["entries"][1]["age_days"] == pytest.approx(7.0)
    registry = write_json(tmp_path / "quarantine.json", {"entries": [old, recent]})
    assert run("WR_quarantine_age_report_build", registry_path=registry, now=now)["total_entries"] == 2
    assert "Abandoned" in run("WR_quarantine_age_report_markdown", registry_path=registry, now=now)
    assert run("WR_quarantine_age_report_assert_no_abandoned", entries=[recent], now=now)["abandoned"] == []
    with pytest.raises(WebRunnerException, match="abandoned quarantine"):
        run("WR_quarantine_age_report_assert_no_abandoned", registry_path=registry, now=now)
    with pytest.raises(WebRunnerException, match="registry_path or entries"):
        run("WR_quarantine_age_report_build")


# ---------- sla_tracker --------------------------------------------------

def test_sla_tracker(tmp_path):
    runs = [
        {"suite": "s", "time": "2026-01-05T10:00:00Z", "duration_seconds": 100, "passed": True},
        {"suite": "s", "time": "2026-01-06T10:00:00Z", "duration_seconds": 900},
    ]
    report = run("WR_sla_tracker_compute", runs=runs, max_duration_seconds=600, target_pass_pct=50)
    assert (report["overall_pct"], report["overall_runs"], report["passed"]) == (50.0, 2, True)
    assert [bucket["label"] for bucket in report["buckets"]] == ["2026-W02"]
    ledger = write_json(tmp_path / "ledger.json", {"runs": runs})
    daily = run("WR_sla_tracker_compute", runs=ledger, max_duration_seconds=600, target_pass_pct=50,
                bucket="day")
    assert [bucket["pct"] for bucket in daily["buckets"]] == [100.0, 0.0]
    assert "SLA" in run("WR_sla_tracker_markdown", runs=runs, max_duration_seconds=600, target_pass_pct=50)
    met = run("WR_sla_tracker_assert_meets", runs=runs, max_duration_seconds=600, target_pass_pct=50)
    assert met["passed"] is True
    with pytest.raises(WebRunnerException, match="SLA breach"):
        run("WR_sla_tracker_assert_meets", runs=runs, max_duration_seconds=600, target_pass_pct=90)


# ---------- snapshot_diff_approval ---------------------------------------

def test_snapshot_diff_approval(tmp_path):
    path = str(tmp_path / "snapshots.json")
    first = run("WR_snapshot_diff_approval_capture", path=path, name="home", text="v1")
    assert (first["baseline_sha"], first["changed"]) == ("", True)
    assert [entry["name"] for entry in run("WR_snapshot_diff_approval_list_pending", path=path)] == ["home"]
    with pytest.raises(WebRunnerException, match="pending review"):
        run("WR_snapshot_diff_approval_assert_no_pending", path=path)
    approved = run("WR_snapshot_diff_approval_approve", path=path, name="home", reviewer="amy")
    assert (approved["status"], approved["approved_by"]) == ("baseline", "amy")
    assert run("WR_snapshot_diff_approval_assert_no_pending", path=path) is None
    assert run("WR_snapshot_diff_approval_capture", path=path, name="home", text="v1")["changed"] is False
    payload = tmp_path / "page.bin"
    payload.write_bytes(b"v2")
    assert run("WR_snapshot_diff_approval_capture", path=path, name="home",
               payload_path=str(payload))["changed"] is True
    rejected = run("WR_snapshot_diff_approval_reject", path=path, name="home", reviewer="bob", note="no")
    assert (rejected["status"], rejected["note"]) == ("rejected", "no")
    with pytest.raises(WebRunnerException, match="text or payload_path"):
        run("WR_snapshot_diff_approval_capture", path=path, name="home")


# ---------- test_blame_owner ---------------------------------------------

def test_test_blame_owner(tmp_path):
    codeowners = "tests/* @qa @lead\n"
    target = "tests/test_a.py"
    assert run("WR_test_blame_owner_codeowners", test_path=target, codeowners_text=codeowners) == ["qa", "lead"]
    by_file = run("WR_test_blame_owner_resolve", test_path=target,
                  codeowners_path=str(_text_file(tmp_path / "CODEOWNERS", codeowners)))
    assert by_file == {"primary": "qa", "backups": ["lead"], "source": "codeowners"}
    blame = [{"author": "amy"}, {"author": "amy"}, {"author": "bob", "commit": "c1"}]
    by_blame = run("WR_test_blame_owner_resolve", test_path=target, blame=blame, default="team")
    assert (by_blame["primary"], by_blame["backups"], by_blame["source"]) == ("amy", ["bob"], "blame")
    assert run("WR_test_blame_owner_assert_has_owner", test_path=target, default="team") == "team"
    with pytest.raises(WebRunnerException, match="no owner found"):
        run("WR_test_blame_owner_assert_has_owner", test_path=target)


def _text_file(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ---------- test_categorizer ---------------------------------------------

def test_test_categorizer(tmp_path):
    actions = [["WR_to_url", {"url": "https://a.test"}], ["WR_assert_title", {"title": "Home"}]]
    assert run("WR_test_categorizer_categorize", actions=actions) == ["smoke"]
    assert run("WR_test_categorizer_categorize", actions=[{"WR_perf_metrics": {}}]) == ["perf"]
    action_file = write_json(tmp_path / "login.json", actions)
    assigned = run("WR_test_categorizer_categorize_file", path=action_file)
    assert (assigned["tags"], assigned["action_count"]) == (["smoke"], 2)
    folder = run("WR_test_categorizer_categorize_dir", directory=str(tmp_path))
    assert len(folder["assignments"]) == 1
    assert folder["distribution"] == {"total_tests": 1, "untagged_tests": 0, "by_tag": {"smoke": 1}}
    with pytest.raises(WebRunnerException, match="file not found"):
        run("WR_test_categorizer_categorize_file", path=str(tmp_path / "missing.json"))
    with pytest.raises(WebRunnerException, match="not a directory"):
        run("WR_test_categorizer_categorize_dir", directory=action_file)


# ---------- test_cost_estimator ------------------------------------------

def test_test_cost_estimator(tmp_path):
    runs = [
        {"test_id": "t1", "runner": "hosted", "duration_seconds": 120},
        {"test_id": "t2", "runner": "mystery", "duration_seconds": 60},
    ]
    cards = [{"runner": "hosted", "usd_per_minute": 0.5}]
    estimate = run("WR_test_cost_estimator_estimate", runs=runs, rate_cards=cards)
    assert (estimate["total_usd"], estimate["unknown_runners"]) == (1.0, ["mystery"])
    assert estimate["by_test"] == {"t1": 1.0}
    ledger = write_json(tmp_path / "ledger.json", {"runs": [{"path": "t1", "duration_seconds": 60}]})
    local = run("WR_test_cost_estimator_estimate", ledger_path=ledger)
    assert (local["total_runs"], local["total_usd"], local["total_grams_co2"]) == (1, 0.0, 2.0)
    assert "Test cost estimate" in run("WR_test_cost_estimator_markdown", runs=runs, rate_cards=cards)
    with pytest.raises(WebRunnerException, match="ledger_path or runs"):
        run("WR_test_cost_estimator_estimate")


# ---------- test_debt_dashboard ------------------------------------------

def test_test_debt_dashboard(tmp_path):
    marker = "TO" + "DO"
    python_file = _text_file(tmp_path / "test_sample.py", (
        "import pytest\n\n"
        "@pytest.mark.skip(reason='broken')\n"
        "def test_one():\n"
        f"    return 1  # {marker}: mend later\n"
    ))
    action_file = write_json(tmp_path / "flow.json", [{"_skip": True, "_reason": "wip"}, {"WR_quit": {}}])
    owners = str(_text_file(tmp_path / "CODEOWNERS", "*.py @py-team\n"))
    report = run("WR_test_debt_dashboard_scan", root=str(tmp_path), codeowners_path=owners)
    assert report["by_kind"] == {"skip": 1, "todo": 1, "json_skip": 1}
    assert report["by_owner"] == {"@py-team": 2, "(unowned)": 1}
    in_python = run("WR_test_debt_dashboard_scan_file", path=str(python_file))
    assert [(item["kind"], item["test_name"], item["reason"]) for item in in_python] == [
        ("skip", "test_one", "broken"), ("todo", "test_one", "mend later"),
    ]
    in_json = run("WR_test_debt_dashboard_scan_file", path=action_file)
    assert [(item["kind"], item["line"], item["reason"]) for item in in_json] == [("json_skip", 1, "wip")]
    assert "Test debt (3 items)" in run("WR_test_debt_dashboard_markdown", root=str(tmp_path))
    assert run("WR_test_debt_dashboard_assert_under_age_limit", root=str(tmp_path), max_days=1) == 3
    with pytest.raises(WebRunnerException, match="older than 0"):
        run("WR_test_debt_dashboard_assert_under_age_limit", root=str(tmp_path), max_days=0)


# ---------- test_dup_dry -------------------------------------------------

def test_test_dup_dry():
    click = {"action_name": "click", "by_value": "#go"}
    open_page = {"action_name": "open", "url": "https://a.test"}
    specs = [
        {"name": "a", "actions": [open_page, click]},
        {"name": "b", "actions": [open_page, click]},
        {"name": "c", "actions": [open_page, click, {"action_name": "type", "by_value": "#name"}]},
        {"name": "d", "actions": [open_page, click, {"action_name": "type", "by_value": "#mail"}]},
    ]
    groups = run("WR_test_dup_dry_find_duplicates", specs=specs)
    assert [group["test_names"] for group in groups] == [["a", "b"]]
    overlaps = run("WR_test_dup_dry_find_prefix_overlap", specs=specs, min_prefix=2)
    assert overlaps == [{"a": "c", "b": "d", "common_prefix_len": 2}]
    assert run("WR_test_dup_dry_assert_no_duplicates", specs=specs[1:]) is None
    with pytest.raises(WebRunnerException, match="duplicate-action group"):
        run("WR_test_dup_dry_assert_no_duplicates", specs=specs)
    with pytest.raises(WebRunnerException, match="DupSpec"):
        run("WR_test_dup_dry_find_duplicates", specs=[{"title": "wrong field"}])


# ---------- test_naming_lint ---------------------------------------------

def test_test_naming_lint():
    good = "test_should_login_when_valid"
    findings = run("WR_test_naming_lint_lint", names=[good, "login_works"])
    assert findings == [{"rule": "missing-prefix", "test": "login_works",
                         "message": "test function name must start with 'test_'"}]
    assert run("WR_test_naming_lint_lint", names=[good], convention="given_when_then")[0]["rule"] == (
        "violates-given_when_then"
    )
    assert run("WR_test_naming_lint_assert_clean", names=[good]) is None
    with pytest.raises(WebRunnerException, match="naming finding"):
        run("WR_test_naming_lint_assert_clean", names=["login_works"])
    with pytest.raises(WebRunnerException, match="unknown convention"):
        run("WR_test_naming_lint_lint", names=[good], convention="nonsense")


# ---------- test_owners_map ----------------------------------------------

def test_test_owners_map(tmp_path):
    codeowners = "tests/ @qa\n"
    assert run("WR_test_owners_map_owners_for", test_id="tests/a.json", codeowners_text=codeowners) == ["@qa"]
    assert run("WR_test_owners_map_owners_for", test_id="tests/a.json", codeowners_text=codeowners,
               overrides={"tests/a.json": ["@me"]}) == ["@me"]
    audit = run("WR_test_owners_map_audit", test_ids=["tests/a.json", "other/b.json"],
                codeowners_path=str(_text_file(tmp_path / "CODEOWNERS", codeowners)))
    assert audit == {"total_tests": 2, "unowned": ["other/b.json"], "by_owner": {"@qa": 1}, "passed": False}
    assert run("WR_test_owners_map_assert_no_unowned", test_ids=["tests/a.json"],
               codeowners_text=codeowners) is None
    with pytest.raises(WebRunnerException, match="1 unowned tests"):
        run("WR_test_owners_map_assert_no_unowned", test_ids=["other/b.json"], codeowners_text=codeowners)


# ---------- test_roi_scorer ----------------------------------------------

def test_test_roi_scorer():
    metrics = [
        {"name": "dead", "runs": 100, "duration_seconds": 60},
        {"name": "good", "runs": 100, "real_failures": 10, "duration_seconds": 1,
         "unique_lines_covered": 200, "days_since_last_real_failure": 0},
    ]
    scores = run("WR_test_roi_scorer_score", metrics=metrics)
    assert [(item["name"], item["verdict"]) for item in scores] == [
        ("good", "keep"), ("dead", "consider-removing"),
    ]
    assert scores[1]["score"] == pytest.approx(0.11)
    candidates = run("WR_test_roi_scorer_removal_candidates", metrics=metrics)
    assert [item["name"] for item in candidates] == ["dead"]
    with pytest.raises(WebRunnerException, match="weights must sum"):
        run("WR_test_roi_scorer_score", metrics=metrics, weights={"find_rate": 1.0})


# ---------- test_scheduler -----------------------------------------------

def test_test_scheduler(tmp_path):
    candidates = [
        {"test_id": "a", "duration_seconds": 10, "fail_rate": 0.5},
        {"test_id": "b", "duration_seconds": 100, "fail_rate": 0.1},
        {"test_id": "c", "duration_seconds": 10, "impact_score": 1.0},
    ]
    schedule = run("WR_test_scheduler_schedule", candidates=candidates, time_budget_seconds=25)
    assert (schedule["selected"], schedule["skipped"], schedule["leftover_seconds"]) == (["c", "a"], ["b"], 5.0)
    assert "Test schedule" in run("WR_test_scheduler_markdown", candidates=candidates, time_budget_seconds=25)
    with pytest.raises(WebRunnerException, match="overrun time budget"):
        run("WR_test_scheduler_schedule", candidates=candidates, time_budget_seconds=25, pinned_test_ids=["b"])
    ledger = write_json(tmp_path / "ledger.json", {"runs": [
        {"path": "t1", "passed": False, "duration_seconds": 30},
        {"path": "t1", "passed": True, "duration_seconds": 10},
    ]})
    built = run("WR_test_scheduler_candidates_from_ledger", ledger_path=ledger, cloud_tests=["t1"])
    assert len(built) == 1
    assert (built[0]["test_id"], built[0]["duration_seconds"], built[0]["fail_rate"]) == ("t1", 20.0, 0.5)
    assert built[0]["needs_cloud_session"] is True
    assert run("WR_test_scheduler_schedule", candidates=built, time_budget_seconds=60)["selected"] == ["t1"]


# ---------- a11y_trend ---------------------------------------------------

def test_a11y_trend(tmp_path):
    history = [{"timestamp": "2026-01-01T10:00:00", "violations": [
        {"impact": "critical", "nodes": [{}, {}]}, {"impact": "minor"},
    ]}]
    expected = [{"label": "2026-01-01", "impacts": {"critical": 2, "minor": 1}, "total": 3}]
    assert run("WR_a11y_trend_aggregate", history=history) == expected
    history_file = write_json(tmp_path / "history.json", history)
    assert run("WR_a11y_trend_aggregate", history_path=history_file) == expected
    written = run("WR_a11y_trend_write_dashboard", output_path=str(tmp_path / "out" / "a11y.html"),
                  history=history, title="Access <trend>")
    assert "Access &lt;trend&gt;" in Path(written).read_text(encoding="utf-8")
    with pytest.raises(WebRunnerException, match="history or history_path"):
        run("WR_a11y_trend_aggregate")


# ---------- failure_cluster ----------------------------------------------

def test_failure_cluster():
    assert run("WR_failure_cluster_normalise", message="Timeout at line 42 0xDEADBEEF") == (
        "timeout at line <n> <hex>"
    )
    failures = [
        {"function_name": "f", "exception": "Timeout at line 42", "file_path": "a.json"},
        {"function_name": "g", "exception": "Timeout at line 77", "file_path": "b.json"},
        {"function_name": "h", "exception": "Other problem"},
    ]
    clusters = run("WR_failure_cluster_cluster", failures=failures)
    assert [(group["count"], group["files"]) for group in clusters] == [(2, ["a.json", "b.json"]), (1, [])]
    assert len(run("WR_failure_cluster_cluster", failures=failures, top_n=1)) == 1
    with pytest.raises(WebRunnerException, match="must be dicts"):
        run("WR_failure_cluster_cluster", failures=["text"])


# ---------- perf_drift ---------------------------------------------------

def test_perf_drift():
    assert run("WR_perf_drift_percentile", values=[1, 2, 3, 4, 5], pct=50) == pytest.approx(3.0)
    slower = {"lcp": [100, 100, 100, 100, 200, 200]}
    report = run("WR_perf_drift_detect", metrics=slower, baseline_window=4, recent_window=2)
    assert report["has_regressions"] is True
    assert (report["metrics"][0]["metric"], report["metrics"][0]["direction"]) == ("lcp", "regressed")
    faster = run("WR_perf_drift_detect", metrics=slower, baseline_window=4, recent_window=2,
                 higher_is_better=["lcp"])
    assert faster["metrics"][0]["direction"] == "improved"
    steady = {"lcp": [100] * 6}
    assert run("WR_perf_drift_assert_no_regression", metrics=steady, baseline_window=4,
               recent_window=2) is None
    with pytest.raises(WebRunnerException, match="perf regression"):
        run("WR_perf_drift_assert_no_regression", metrics=slower, baseline_window=4, recent_window=2)


# ---------- trend_dashboard ----------------------------------------------

def test_trend_dashboard(tmp_path):
    runs = [
        {"time": "2026-01-01T10:00:00", "passed": True, "duration_seconds": 2},
        {"time": "2026-01-01T11:00:00", "passed": False},
    ]
    trend = run("WR_trend_dashboard_compute", runs=runs)
    assert trend["totals"] == {"passed": 1, "failed": 1, "total": 2, "pass_rate": 0.5}
    assert trend["daily"][0]["label"] == "2026-01-01"
    ledger = write_json(tmp_path / "ledger.json", {"runs": runs})
    assert run("WR_trend_dashboard_compute", ledger_path=ledger) == trend
    written = run("WR_trend_dashboard_write", output_path=str(tmp_path / "trend.html"), ledger_path=ledger)
    assert "2026-01-01" in Path(written).read_text(encoding="utf-8")
    with pytest.raises(WebRunnerException, match="ledger_path or runs"):
        run("WR_trend_dashboard_compute")
