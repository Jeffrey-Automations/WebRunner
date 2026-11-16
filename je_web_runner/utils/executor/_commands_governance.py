"""
測試治理類命令轉接(第一部分)
Command adapters for the test-governance libraries, part 1: refactor hints, repro stability, commit-message
triggers, failure clustering, flake scoring and quarantine, the flakiness graveyard, ledger bisect, mutation
generation, PR risk, pre-merge gates, quarantine age, SLA tracking and snapshot approval.

These libraries work on ledgers, registries and lists of results, not on a browser. Every command takes
JSON values (or the path of a JSON file) and returns JSON values. Part 2 is ``_commands_governance_2``.
"""
from __future__ import annotations

# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import to_plain


# ---------- shared helpers ------------------------------------------------

def moment_of(text: str | None) -> datetime | None:
    """An ISO timestamp as a timezone-aware datetime (UTC when it names no zone); ``None`` stays ``None``."""
    if text is None:
        return None
    moment = datetime.fromisoformat(text)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _day_of(text: str | None) -> date | None:
    return date.fromisoformat(text) if text else None


def build_dataclass(factory: Callable[..., Any], values: Any, error: type[Exception]) -> Any:
    """``factory(**values)``; ``error`` is raised when ``values`` is not an object or names an unknown field."""
    if not isinstance(values, dict):
        raise error(f"{factory.__name__} needs an object, got {type(values).__name__}")
    try:
        return factory(**values)
    except TypeError as failure:
        raise error(f"{factory.__name__}: {failure}") from failure


def _change_registry(library: Any, path: str, change: Callable[[Any], Any]) -> Any:
    """Load the registry file at ``path`` with ``library``, apply ``change`` to it, save it back."""
    registry = library.load(path)
    result = change(registry)
    library.save(path, registry)
    return result


# ---------- action_refactor_suggester ------------------------------------

def action_refactor_suggester_analyze(actions: list[dict[str, Any]]) -> Any:
    """
    Find refactor smells in a list of step objects: hard sleeps, positional XPath, repeated locators.

    Each step is an object with ``action_name`` and, where it applies, ``by``, ``by_value``, ``value`` and
    ``expected``. Returns the suggestions, warnings first.
    """
    from je_web_runner.utils.action_refactor_suggester.suggest import analyze
    return to_plain(analyze(actions))


def action_refactor_suggester_markdown(actions: list[dict[str, Any]]) -> str:
    """Render the refactor suggestions for a list of step objects as markdown."""
    from je_web_runner.utils.action_refactor_suggester.suggest import analyze, report_markdown
    return report_markdown(analyze(actions))


def action_refactor_suggester_assert_clean(actions: list[dict[str, Any]]) -> Any:
    """Fail when a list of step objects has a warning or error level refactor suggestion."""
    from je_web_runner.utils.action_refactor_suggester.suggest import analyze, assert_no_warns_or_errors
    suggestions = analyze(actions)
    assert_no_warns_or_errors(suggestions)
    return to_plain(suggestions)


# ---------- bug_repro_stability ------------------------------------------

def _recorded_outcome(item: Any) -> Any:
    from je_web_runner.utils.bug_repro_stability.stability import BugReproStabilityError, RunOutcome
    if isinstance(item, bool):
        return RunOutcome(passed=item)
    if not isinstance(item, dict):
        raise BugReproStabilityError(f"an outcome is true/false or an object, got {type(item).__name__}")
    return RunOutcome(
        passed=bool(item.get("passed")),
        error_signature=item.get("error_signature"),
        duration_seconds=float(item.get("duration_seconds") or 0.0),
    )


def _stability_report(outcomes: list[Any]) -> Any:
    from je_web_runner.utils.bug_repro_stability.stability import BugReproStabilityError, repeat
    if not isinstance(outcomes, list) or not outcomes:
        raise BugReproStabilityError("outcomes must be a non-empty list")
    recorded = [_recorded_outcome(item) for item in outcomes]
    return repeat(lambda index: recorded[index], attempts=len(recorded))


def bug_repro_stability_summarize(outcomes: list[Any]) -> Any:
    """
    Classify recorded attempts of one test as deterministic, flaky or non_reproducible.

    ``outcomes`` lists the attempts in order: ``true``/``false`` for passed, or objects with ``passed``,
    ``error_signature`` and ``duration_seconds``. Returns the repro percentage, streaks and error counts.
    """
    return to_plain(_stability_report(outcomes))


def bug_repro_stability_markdown(outcomes: list[Any]) -> str:
    """Render the repro-stability summary of recorded attempts as markdown."""
    from je_web_runner.utils.bug_repro_stability.stability import report_markdown
    return report_markdown(_stability_report(outcomes))


def bug_repro_stability_assert_deterministic(outcomes: list[Any]) -> Any:
    """Fail unless every recorded attempt failed (the bug reproduces every time)."""
    from je_web_runner.utils.bug_repro_stability.stability import assert_deterministic
    report = _stability_report(outcomes)
    assert_deterministic(report)
    return to_plain(report)


def bug_repro_stability_assert_min_repro_pct(outcomes: list[Any], minimum: float) -> Any:
    """Fail when fewer than ``minimum`` percent of the recorded attempts failed."""
    from je_web_runner.utils.bug_repro_stability.stability import assert_min_repro_pct
    report = _stability_report(outcomes)
    assert_min_repro_pct(report, minimum=minimum)
    return to_plain(report)


# ---------- commit_msg_trigger -------------------------------------------

def commit_msg_trigger_parse(message: str) -> Any:
    """Read the CI directives of a commit message: skip, buckets, labels, shard and linked tickets."""
    from je_web_runner.utils.commit_msg_trigger.trigger import parse
    return to_plain(parse(message))


def commit_msg_trigger_should_run_job(message: str, job_name: str) -> bool:
    """Whether the commit message lets the CI job ``job_name`` run."""
    from je_web_runner.utils.commit_msg_trigger.trigger import parse, should_run_job
    return should_run_job(parse(message), job_name)


def commit_msg_trigger_assigned_shard(message: str, total_shards: int) -> int | None:
    """The 0-based shard the commit message asks for out of ``total_shards``, or ``null`` when it names none."""
    from je_web_runner.utils.commit_msg_trigger.trigger import assigned_shard, parse
    return assigned_shard(parse(message), total_shards)


def commit_msg_trigger_assert_no_skip(message: str) -> Any:
    """Fail when the commit message asks to skip CI."""
    from je_web_runner.utils.commit_msg_trigger.trigger import assert_no_skip, parse
    plan = parse(message)
    assert_no_skip(plan)
    return to_plain(plan)


# ---------- failure_cluster_dbscan ---------------------------------------

def _dbscan_clusters(records: list[dict[str, Any]], eps: float, min_samples: int) -> list[Any]:
    from je_web_runner.utils.failure_cluster_dbscan.cluster import FailureClusterDbscanError, FailureRecord, cluster
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise FailureClusterDbscanError("records must be a list of {test_name, message} objects")
    rows = [
        FailureRecord(test_name=str(row.get("test_name") or ""), message=str(row.get("message") or ""))
        for row in records
    ]
    return cluster(rows, eps=eps, min_samples=min_samples)


def failure_cluster_dbscan_cluster(records: list[dict[str, Any]], eps: float = 0.3, min_samples: int = 2) -> Any:
    """
    Group failures whose messages are near-identical, largest group first.

    ``records`` is a list of ``{"test_name", "message"}``. Each group gives its ``representative`` message,
    the ``members`` (test names) and its ``size``; a failure like no other is a group of one.
    """
    return [
        {"representative": group.representative, "members": list(group.members), "size": group.size}
        for group in _dbscan_clusters(records, eps, min_samples)
    ]


def failure_cluster_dbscan_assert_root_causes_at_most(
    records: list[dict[str, Any]], max_clusters: int, eps: float = 0.3, min_samples: int = 2,
) -> int:
    """Fail when the failures form more than ``max_clusters`` groups of two or more; returns the group count."""
    from je_web_runner.utils.failure_cluster_dbscan.cluster import assert_root_causes_at_most
    clusters = _dbscan_clusters(records, eps, min_samples)
    assert_root_causes_at_most(clusters, max_clusters=max_clusters)
    return sum(1 for group in clusters if group.size >= 2)


# ---------- flake_detector -----------------------------------------------

def flake_detector_scores(
    ledger_path: str | None = None, runs: list[dict[str, Any]] | None = None,
    half_life_days: float = 7.0, min_runs: int = 3, threshold: float = 0.25,
) -> Any:
    """
    Score every test of a run ledger for flakiness, recent failures weighing more.

    Give ``runs`` (a list of ``{"path", "passed", "time"}``) or the ``ledger_path`` of a ``{"runs": [...]}``
    file. Returns an object keyed by test path with runs, pass rate, ``flake_score`` and ``is_flaky``.
    """
    from je_web_runner.utils.flake_detector.detector import (
        FlakeDetectorError, compute_flake_scores, compute_flake_scores_from_runs,
    )
    settings: dict[str, Any] = {"half_life_days": half_life_days, "min_runs": min_runs, "threshold": threshold}
    if runs is not None:
        return to_plain(compute_flake_scores_from_runs(runs, **settings))
    if ledger_path is None:
        raise FlakeDetectorError("give ledger_path or runs")
    return to_plain(compute_flake_scores(ledger_path, **settings))


def flake_detector_flaky_paths(
    ledger_path: str, half_life_days: float = 7.0, min_runs: int = 3, threshold: float = 0.25,
) -> list[str]:
    """List the tests of a run ledger that are flaky, worst first."""
    from je_web_runner.utils.flake_detector.detector import flaky_paths
    return flaky_paths(ledger_path, half_life_days=half_life_days, min_runs=min_runs, threshold=threshold)


def flake_detector_quarantine_flaky(
    ledger_path: str, registry_path: str,
    half_life_days: float = 7.0, min_runs: int = 3, threshold: float = 0.25,
) -> list[str]:
    """Add the newly flaky tests of a run ledger to the quarantine registry file; returns the added ids."""
    from je_web_runner.utils.flake_detector.detector import quarantine_flaky
    return quarantine_flaky(
        ledger_path, registry_path, half_life_days=half_life_days, min_runs=min_runs, threshold=threshold,
    )


def flake_detector_release_if_stable(
    ledger_path: str, registry_path: str,
    half_life_days: float = 7.0, release_threshold: float = 0.05, min_runs_since: int = 5,
) -> list[str]:
    """Remove from the quarantine registry file the tests that turned stable; returns the released ids."""
    from je_web_runner.utils.flake_detector.detector import release_if_stable
    return release_if_stable(
        ledger_path, registry_path, half_life_days=half_life_days,
        release_threshold=release_threshold, min_runs_since=min_runs_since,
    )


def flake_detector_quarantine_list(registry_path: str) -> Any:
    """List the entries of a quarantine registry file, highest flake score first."""
    from je_web_runner.utils.flake_detector.detector import QuarantineRegistry
    return to_plain(QuarantineRegistry(registry_path).list())


def flake_detector_assert_not_quarantined(registry_path: str, test_id: str) -> None:
    """Fail when ``test_id`` is in the quarantine registry file."""
    from je_web_runner.utils.flake_detector.detector import FlakeDetectorError, QuarantineRegistry
    entry = QuarantineRegistry(registry_path).get(test_id)
    if entry is not None:
        raise FlakeDetectorError(f"test {test_id!r} is quarantined: {entry.reason}")


# ---------- flakiness_graveyard ------------------------------------------

def flakiness_graveyard_register_flake(
    path: str, test_name: str, owner: str = "", ticket_url: str = "", today: str | None = None,
) -> Any:
    """
    Record a flake of ``test_name`` in the graveyard registry file (created when missing).

    ``today`` is an ISO date, the current day when omitted. Returns the test's entry.
    """
    from je_web_runner.utils.flakiness_graveyard import graveyard
    return to_plain(_change_registry(graveyard, path, lambda registry: graveyard.register_flake(
        registry, test_name, owner=owner, ticket_url=ticket_url, today=_day_of(today),
    )))


def flakiness_graveyard_revive(path: str, test_name: str) -> Any:
    """Mark a quarantined test of the graveyard registry file as revived; returns its entry."""
    from je_web_runner.utils.flakiness_graveyard import graveyard
    return to_plain(_change_registry(graveyard, path, lambda registry: graveyard.revive(registry, test_name)))


def flakiness_graveyard_bury(path: str, test_name: str) -> Any:
    """Mark a quarantined test of the graveyard registry file as buried; returns its entry."""
    from je_web_runner.utils.flakiness_graveyard import graveyard
    return to_plain(_change_registry(graveyard, path, lambda registry: graveyard.bury(registry, test_name)))


def flakiness_graveyard_list(path: str) -> Any:
    """List the entries of the graveyard registry file."""
    from je_web_runner.utils.flakiness_graveyard.graveyard import load
    return to_plain(load(path))


def flakiness_graveyard_due_for_burial(path: str, days: int = 30, today: str | None = None) -> Any:
    """List the quarantined tests of the graveyard registry file that have not flaked for ``days`` days."""
    from je_web_runner.utils.flakiness_graveyard.graveyard import due_for_burial, load
    return to_plain(due_for_burial(load(path), days=days, today=_day_of(today)))


def flakiness_graveyard_assert_none_due(path: str, days: int = 30, today: str | None = None) -> None:
    """Fail when a quarantined test of the graveyard registry file is due for burial."""
    from je_web_runner.utils.flakiness_graveyard.graveyard import FlakinessGraveyardError, due_for_burial, load
    due = due_for_burial(load(path), days=days, today=_day_of(today))
    if due:
        raise FlakinessGraveyardError(
            f"{len(due)} test(s) due for burial after {days} days: {[entry.test_name for entry in due]}"
        )


# ---------- git_bisect_flake ---------------------------------------------

def _bisect_result(
    commit_order: list[str], test_id: str, ledger_path: str | None, entries: list[dict[str, Any]] | None,
) -> Any:
    from je_web_runner.utils.git_bisect_flake.bisect import (
        GitBisectFlakeError, LedgerEntry, bisect_from_ledger, load_ledger,
    )
    if entries is not None:
        rows = [
            LedgerEntry(
                commit=str(row.get("commit") or ""), test_id=str(row.get("test_id") or row.get("path") or ""),
                passed=bool(row.get("passed")), time=str(row.get("time") or ""),
            )
            for row in entries if isinstance(row, dict)
        ]
    elif ledger_path is not None:
        rows = load_ledger(ledger_path)
    else:
        raise GitBisectFlakeError("give ledger_path or entries")
    return bisect_from_ledger(rows, commit_order, test_id)


def git_bisect_flake_bisect(
    commit_order: list[str], test_id: str,
    ledger_path: str | None = None, entries: list[dict[str, Any]] | None = None,
) -> Any:
    """
    Find the commit where ``test_id`` went from passing to failing, from recorded runs only.

    ``commit_order`` lists the commits oldest first. Give ``entries`` (``{"commit", "test_id", "passed"}``
    rows) or the ``ledger_path`` of a ``{"runs": [...]}`` file. Nothing is checked out or re-run.
    """
    return to_plain(_bisect_result(commit_order, test_id, ledger_path, entries))


def git_bisect_flake_markdown(
    commit_order: list[str], test_id: str,
    ledger_path: str | None = None, entries: list[dict[str, Any]] | None = None,
) -> str:
    """Render the recorded-runs bisect of ``test_id`` as markdown."""
    from je_web_runner.utils.git_bisect_flake.bisect import report_markdown
    return report_markdown(_bisect_result(commit_order, test_id, ledger_path, entries))


# ---------- mutation_testing ---------------------------------------------

def _mutation_type(name: Any) -> Any:
    from je_web_runner.utils.mutation_testing.mutator import MutationTestingError, MutationType
    try:
        return MutationType(name)
    except ValueError as failure:
        known = [kind.value for kind in MutationType]
        raise MutationTestingError(f"unknown mutation type {name!r}; known: {known}") from failure


def mutation_testing_generate(
    actions: list[Any], types: list[str] | None = None, seed: int | None = None, max_per_type: int | None = None,
) -> Any:
    """
    List the mutations that can sabotage an action list (locator swap, timeout shrink, removal, ...).

    ``types`` limits the mutation types; ``max_per_type`` caps each one, picked by ``seed``.
    """
    from je_web_runner.utils.mutation_testing.mutator import MutationType, generate_mutations
    kinds = [_mutation_type(name) for name in types] if types is not None else list(MutationType)
    return to_plain(generate_mutations(actions, kinds, seed=seed, max_per_type=max_per_type))


def mutation_testing_apply(actions: list[Any], mutation: dict[str, Any]) -> Any:
    """Return a copy of an action list with one mutation (as ``WR_mutation_testing_generate`` returns) applied."""
    from je_web_runner.utils.mutation_testing.mutator import Mutation, MutationTestingError, apply_mutation
    if not isinstance(mutation, dict) or "type" not in mutation or "action_index" not in mutation:
        raise MutationTestingError("mutation must be an object with 'type' and 'action_index'")
    return to_plain(apply_mutation(actions, Mutation(
        type=_mutation_type(mutation["type"]),
        action_index=int(mutation["action_index"]),
        description=str(mutation.get("description") or ""),
        original=mutation.get("original"),
        mutated=mutation.get("mutated"),
    )))


def mutation_testing_assert_min_score(killed: int, total: int, minimum: float = 0.8) -> float:
    """Fail when ``killed / total`` mutations is below ``minimum``; returns the mutation score."""
    from je_web_runner.utils.mutation_testing.mutator import MutationScore, MutationTestingError, assert_min_score
    if total < 0 or not 0 <= killed <= max(total, 0):
        raise MutationTestingError("need 0 <= killed <= total")
    score = MutationScore(
        total=total, killed=killed, survived=total - killed,
        score=round(killed / total, 4) if total else 0.0,
    )
    assert_min_score(score, minimum)
    return score.score


# ---------- pr_risk_score ------------------------------------------------

def _risk_report(signals: dict[str, Any], weights: dict[str, float] | None) -> Any:
    from je_web_runner.utils.pr_risk_score.scorer import PrRiskScoreError, PrSignals, RiskWeights, score_pr
    risk_weights = None if weights is None else build_dataclass(RiskWeights, weights, PrRiskScoreError)
    return score_pr(build_dataclass(PrSignals, signals, PrRiskScoreError), risk_weights)


def pr_risk_score_score(signals: dict[str, Any], weights: dict[str, float] | None = None) -> Any:
    """
    Turn the signals of a pull request into a 0-100 risk score with a level and reasons.

    ``signals`` holds counts such as ``flaky_tests_touched``, ``total_tests_touched``, ``impacted_modules``,
    ``repo_modules``, ``lines_added``, ``lines_covered``; ``weights`` overrides the weight of a signal group.
    """
    return to_plain(_risk_report(signals, weights))


def pr_risk_score_aggregate(per_file: list[dict[str, Any]]) -> Any:
    """Sum per-file signal objects into the one signals object ``WR_pr_risk_score_score`` takes."""
    from je_web_runner.utils.pr_risk_score.scorer import aggregate_signals
    return to_plain(aggregate_signals(per_file))


def pr_risk_score_markdown(signals: dict[str, Any], weights: dict[str, float] | None = None) -> str:
    """Render the risk score of a pull request's signals as markdown."""
    from je_web_runner.utils.pr_risk_score.scorer import report_markdown
    return report_markdown(_risk_report(signals, weights))


def pr_risk_score_assert_below(
    signals: dict[str, Any], block_at: float = 75.0, weights: dict[str, float] | None = None,
) -> Any:
    """Fail when the risk score of a pull request's signals reaches ``block_at``."""
    from je_web_runner.utils.pr_risk_score.scorer import PrRiskScoreError
    report = _risk_report(signals, weights)
    if report.is_blocking(block_at):
        raise PrRiskScoreError(f"PR risk {report.score} ({report.level}) reaches {block_at}: {report.reasons}")
    return to_plain(report)


# ---------- pre_merge_gate_dsl -------------------------------------------

def _gate_result(rules: list[dict[str, Any]], facts: dict[str, Any]) -> Any:
    from je_web_runner.utils.pre_merge_gate_dsl.gate import PreMergeGateDslError, PrFacts, evaluate, parse_rules
    return evaluate(parse_rules(rules), build_dataclass(PrFacts, facts, PreMergeGateDslError))


def pre_merge_gate_dsl_evaluate(rules: list[dict[str, Any]], facts: dict[str, Any]) -> Any:
    """
    Check a pull request's facts against pre-merge rules; returns ``passed`` and the ``failures``.

    A rule is ``{"when": "facts.is_docs_only" | "facts.has_path('src/**')", "require": [names]}`` with the
    requirements ``pr_title_has_jira``, ``one_reviewer``, ``two_reviewers``, ``no_failing_checks``,
    ``no_flake_regression``, ``small_pr``. ``facts`` holds ``title``, ``files_changed``, ``additions``,
    ``deletions``, ``review_approvals``, ``failing_checks``, ``flake_score_delta``, ``labels``.
    """
    return to_plain(_gate_result(rules, facts))


def pre_merge_gate_dsl_assert_passes(rules: list[dict[str, Any]], facts: dict[str, Any]) -> Any:
    """Fail when a pull request's facts break a pre-merge rule."""
    from je_web_runner.utils.pre_merge_gate_dsl.gate import assert_gate_passes
    result = _gate_result(rules, facts)
    assert_gate_passes(result)
    return to_plain(result)


# ---------- quarantine_age_report ----------------------------------------

def _age_report(registry_path: str | None, entries: list[dict[str, Any]] | None, now: str | None) -> Any:
    from je_web_runner.utils.quarantine_age_report.report import (
        QuarantineAgeReportError, age_entries, build_report, load_and_age,
    )
    if entries is not None:
        return build_report(age_entries(entries, now=moment_of(now)))
    if registry_path is None:
        raise QuarantineAgeReportError("give registry_path or entries")
    return load_and_age(registry_path, now=moment_of(now))


def quarantine_age_report_build(
    registry_path: str | None = None, entries: list[dict[str, Any]] | None = None, now: str | None = None,
) -> Any:
    """
    Report how long each quarantined test has been parked: fresh, lingering, stale or abandoned.

    Give ``entries`` (``{"test_id", "quarantined_at", ...}`` rows) or the ``registry_path`` of a quarantine
    registry file. ``now`` is an ISO timestamp, the current time when omitted.
    """
    return to_plain(_age_report(registry_path, entries, now))


def quarantine_age_report_markdown(
    registry_path: str | None = None, entries: list[dict[str, Any]] | None = None,
    now: str | None = None, top_n: int = 10,
) -> str:
    """Render the quarantine age report as markdown."""
    from je_web_runner.utils.quarantine_age_report.report import report_markdown
    return report_markdown(_age_report(registry_path, entries, now), top_n=top_n)


def quarantine_age_report_assert_no_abandoned(
    registry_path: str | None = None, entries: list[dict[str, Any]] | None = None, now: str | None = None,
) -> Any:
    """Fail when a test has been quarantined for 90 days or more."""
    from je_web_runner.utils.quarantine_age_report.report import assert_no_abandoned
    report = _age_report(registry_path, entries, now)
    assert_no_abandoned(report)
    return to_plain(report)


# ---------- sla_tracker --------------------------------------------------

def _sla_report(target: tuple[float, float], runs: list[dict[str, Any]] | str,
                bucket: str, suite: str | None) -> Any:
    from je_web_runner.utils.sla_tracker.tracker import SlaTarget, SuiteRun, compute_sla, load_runs
    if isinstance(runs, str):
        rows = load_runs(runs)
    else:
        rows = [
            SuiteRun(
                suite=str(row.get("suite") or row.get("path") or ""),
                started_at=moment_of(row.get("time") or row.get("started_at")),  # type: ignore[arg-type]
                duration_seconds=float(row.get("duration_seconds") or 0.0),
                passed=bool(row.get("passed", True)),
            )
            for row in runs if isinstance(row, dict)
        ]
    sla_target = SlaTarget(max_duration_seconds=target[0], target_pass_pct=target[1])
    return compute_sla(rows, sla_target, bucket=bucket, suite=suite)


def sla_tracker_compute(
    runs: list[dict[str, Any]] | str, max_duration_seconds: float, target_pass_pct: float,
    bucket: str = "week", suite: str | None = None,
) -> Any:
    """
    Compute the share of suite runs that finished within ``max_duration_seconds``, per week or day.

    ``runs`` is a list of ``{"suite", "time", "duration_seconds", "passed"}`` rows, or the path of a
    ``{"runs": [...]}`` ledger file. ``passed`` in the result says whether the overall share meets
    ``target_pass_pct``; ``suite`` keeps one suite only.
    """
    return to_plain(_sla_report((max_duration_seconds, target_pass_pct), runs, bucket, suite))


def sla_tracker_markdown(
    runs: list[dict[str, Any]] | str, max_duration_seconds: float, target_pass_pct: float,
    bucket: str = "week", suite: str | None = None,
) -> str:
    """Render the SLA report of suite runs (rows, or the path of a ledger file) as markdown."""
    from je_web_runner.utils.sla_tracker.tracker import report_markdown
    return report_markdown(_sla_report((max_duration_seconds, target_pass_pct), runs, bucket, suite))


def sla_tracker_assert_meets(
    runs: list[dict[str, Any]] | str, max_duration_seconds: float, target_pass_pct: float,
    suite: str | None = None,
) -> Any:
    """Fail when fewer than ``target_pass_pct`` percent of suite runs finished within the duration."""
    from je_web_runner.utils.sla_tracker.tracker import assert_meets_sla
    report = _sla_report((max_duration_seconds, target_pass_pct), runs, "week", suite)
    assert_meets_sla(report)
    return to_plain(report)


# ---------- snapshot_diff_approval ---------------------------------------

def snapshot_diff_approval_capture(
    path: str, name: str, text: str | None = None, payload_path: str | None = None,
) -> dict[str, Any]:
    """
    Compare a snapshot with its approved baseline in the registry file at ``path`` and record a mismatch.

    The snapshot is ``text``, or the bytes of the file at ``payload_path``. A snapshot with no baseline, or
    one that differs, is stored as pending. Returns ``baseline_sha``, ``head_sha`` and ``changed``.
    """
    from je_web_runner.utils.snapshot_diff_approval import approval
    if text is not None:
        payload = text.encode("utf-8")
    elif payload_path is not None:
        payload = Path(payload_path).read_bytes()
    else:
        raise approval.SnapshotDiffApprovalError("give text or payload_path")
    diff = _change_registry(
        approval, path, lambda registry: approval.capture(registry, name=name, payload=payload),
    )
    return {"name": diff.name, "baseline_sha": diff.baseline_sha, "head_sha": diff.head_sha,
            "changed": diff.changed}


def snapshot_diff_approval_approve(path: str, name: str, reviewer: str) -> Any:
    """Promote the pending snapshot ``name`` of the registry file to baseline; returns its entry."""
    from je_web_runner.utils.snapshot_diff_approval import approval
    return to_plain(_change_registry(
        approval, path, lambda registry: approval.approve(registry, name=name, reviewer=reviewer),
    ))


def snapshot_diff_approval_reject(path: str, name: str, reviewer: str, note: str = "") -> Any:
    """Mark the snapshot ``name`` of the registry file as rejected; returns its entry."""
    from je_web_runner.utils.snapshot_diff_approval import approval
    return to_plain(_change_registry(
        approval, path, lambda registry: approval.reject(registry, name=name, reviewer=reviewer, note=note),
    ))


def snapshot_diff_approval_list_pending(path: str) -> Any:
    """List the snapshots of the registry file that wait for review."""
    from je_web_runner.utils.snapshot_diff_approval.approval import list_pending, load
    return to_plain(list_pending(load(path)))


def snapshot_diff_approval_assert_no_pending(path: str) -> None:
    """Fail when a snapshot of the registry file waits for review."""
    from je_web_runner.utils.snapshot_diff_approval.approval import assert_no_pending, load
    assert_no_pending(load(path))


# ---------- tables --------------------------------------------------------

GOVERNANCE_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_action_refactor_suggester_analyze": action_refactor_suggester_analyze,
    "WR_action_refactor_suggester_markdown": action_refactor_suggester_markdown,
    "WR_action_refactor_suggester_assert_clean": action_refactor_suggester_assert_clean,
    "WR_bug_repro_stability_summarize": bug_repro_stability_summarize,
    "WR_bug_repro_stability_markdown": bug_repro_stability_markdown,
    "WR_bug_repro_stability_assert_deterministic": bug_repro_stability_assert_deterministic,
    "WR_bug_repro_stability_assert_min_repro_pct": bug_repro_stability_assert_min_repro_pct,
    "WR_commit_msg_trigger_parse": commit_msg_trigger_parse,
    "WR_commit_msg_trigger_should_run_job": commit_msg_trigger_should_run_job,
    "WR_commit_msg_trigger_assigned_shard": commit_msg_trigger_assigned_shard,
    "WR_commit_msg_trigger_assert_no_skip": commit_msg_trigger_assert_no_skip,
    "WR_failure_cluster_dbscan_cluster": failure_cluster_dbscan_cluster,
    "WR_failure_cluster_dbscan_assert_root_causes_at_most": failure_cluster_dbscan_assert_root_causes_at_most,
    "WR_flake_detector_scores": flake_detector_scores,
    "WR_flake_detector_flaky_paths": flake_detector_flaky_paths,
    "WR_flake_detector_quarantine_flaky": flake_detector_quarantine_flaky,
    "WR_flake_detector_release_if_stable": flake_detector_release_if_stable,
    "WR_flake_detector_quarantine_list": flake_detector_quarantine_list,
    "WR_flake_detector_assert_not_quarantined": flake_detector_assert_not_quarantined,
    "WR_flakiness_graveyard_register_flake": flakiness_graveyard_register_flake,
    "WR_flakiness_graveyard_revive": flakiness_graveyard_revive,
    "WR_flakiness_graveyard_bury": flakiness_graveyard_bury,
    "WR_flakiness_graveyard_list": flakiness_graveyard_list,
    "WR_flakiness_graveyard_due_for_burial": flakiness_graveyard_due_for_burial,
    "WR_flakiness_graveyard_assert_none_due": flakiness_graveyard_assert_none_due,
    "WR_git_bisect_flake_bisect": git_bisect_flake_bisect,
    "WR_git_bisect_flake_markdown": git_bisect_flake_markdown,
    "WR_mutation_testing_generate": mutation_testing_generate,
    "WR_mutation_testing_apply": mutation_testing_apply,
    "WR_mutation_testing_assert_min_score": mutation_testing_assert_min_score,
    "WR_pr_risk_score_score": pr_risk_score_score,
    "WR_pr_risk_score_aggregate": pr_risk_score_aggregate,
    "WR_pr_risk_score_markdown": pr_risk_score_markdown,
    "WR_pr_risk_score_assert_below": pr_risk_score_assert_below,
    "WR_pre_merge_gate_dsl_evaluate": pre_merge_gate_dsl_evaluate,
    "WR_pre_merge_gate_dsl_assert_passes": pre_merge_gate_dsl_assert_passes,
    "WR_quarantine_age_report_build": quarantine_age_report_build,
    "WR_quarantine_age_report_markdown": quarantine_age_report_markdown,
    "WR_quarantine_age_report_assert_no_abandoned": quarantine_age_report_assert_no_abandoned,
    "WR_sla_tracker_compute": sla_tracker_compute,
    "WR_sla_tracker_markdown": sla_tracker_markdown,
    "WR_sla_tracker_assert_meets": sla_tracker_assert_meets,
    "WR_snapshot_diff_approval_capture": snapshot_diff_approval_capture,
    "WR_snapshot_diff_approval_approve": snapshot_diff_approval_approve,
    "WR_snapshot_diff_approval_reject": snapshot_diff_approval_reject,
    "WR_snapshot_diff_approval_list_pending": snapshot_diff_approval_list_pending,
    "WR_snapshot_diff_approval_assert_no_pending": snapshot_diff_approval_assert_no_pending,
}

PYTHON_ONLY: dict[str, str] = {
    "repro_minimizer": (
        "Its only operation, ddmin over an action list, needs a caller-supplied runner callable that re-runs "
        "each candidate subset; nothing in it works on recorded data alone."
    ),
}

NETWORK_COMMANDS: frozenset[str] = frozenset()
