"""
測試治理類命令轉接(第二部分)
Command adapters for the test-governance libraries, part 2: test ownership, categorisation, cost, debt,
duplicates, naming, ROI, scheduling, and the trend reports (a11y, failure clusters, perf drift, run trend).

Like part 1 (``_commands_governance``), every command takes JSON values or the path of a file and returns
JSON values; none of them needs a browser.
"""
from __future__ import annotations

# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it

from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import to_plain


# ---------- shared helpers ------------------------------------------------

def _codeowners_text(text: str | None, path: str | None) -> str:
    """The CODEOWNERS body: ``text`` when given, else the file at ``path``, else empty."""
    if text is not None:
        return text
    return Path(path).read_text(encoding="utf-8") if path else ""


def _rows(factory: Callable[..., Any], values: Any, error: type[Exception]) -> list[Any]:
    """One ``factory(**row)`` per object of the list ``values``; ``error`` on a wrong shape."""
    from je_web_runner.utils.executor._commands_governance import build_dataclass
    if not isinstance(values, list):
        raise error(f"expected a list of objects, got {type(values).__name__}")
    return [build_dataclass(factory, row, error) for row in values]


# ---------- test_blame_owner ---------------------------------------------

def _owner_verdict(test_path: str, codeowners: str, blame: list[dict[str, Any]] | None,
                   fallbacks: tuple[str, str]) -> Any:
    from je_web_runner.utils.test_blame_owner.owner import BlameLine, BlameOwnerError, parse_codeowners, resolve_owner
    return resolve_owner(
        test_path,
        codeowners=parse_codeowners(codeowners),
        blame=_rows(BlameLine, blame or [], BlameOwnerError),
        head_author=fallbacks[0],
        default=fallbacks[1],
    )


def wr_test_blame_owner_codeowners(
    test_path: str, codeowners_text: str | None = None, codeowners_path: str | None = None,
) -> list[str]:
    """List the owners a CODEOWNERS body (given as text or as a file path) names for ``test_path``."""
    from je_web_runner.utils.test_blame_owner.owner import owners_from_codeowners, parse_codeowners
    rules = parse_codeowners(_codeowners_text(codeowners_text, codeowners_path))
    return owners_from_codeowners(rules, test_path)


def wr_test_blame_owner_resolve(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    test_path: str, codeowners_text: str | None = None, codeowners_path: str | None = None,
    blame: list[dict[str, Any]] | None = None, head_author: str = "", default: str = "",
) -> Any:
    """
    Decide who to ping for a failing test: CODEOWNERS, then blame, then the last committer, then a default.

    ``blame`` is a list of ``{"author", "commit"}`` lines the caller already has; no git command is run.
    Returns ``primary``, ``backups`` and the ``source`` that decided. (Six inputs: the four sources of the
    lookup, CODEOWNERS in either form; the project's limit is seven.)
    """
    codeowners = _codeowners_text(codeowners_text, codeowners_path)
    return to_plain(_owner_verdict(test_path, codeowners, blame, (head_author, default)))


def wr_test_blame_owner_assert_has_owner(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    test_path: str, codeowners_text: str | None = None, codeowners_path: str | None = None,
    blame: list[dict[str, Any]] | None = None, head_author: str = "", default: str = "",
) -> str:
    """Fail when no owner can be found for ``test_path``; returns the primary owner."""
    from je_web_runner.utils.test_blame_owner.owner import assert_has_owner
    codeowners = _codeowners_text(codeowners_text, codeowners_path)
    verdict = _owner_verdict(test_path, codeowners, blame, (head_author, default))
    assert_has_owner(verdict)
    return str(verdict.primary)


# ---------- test_categorizer ---------------------------------------------

def wr_test_categorizer_categorize(actions: list[Any]) -> list[str]:
    """
    Tag an action list by what it does: smoke, regression, perf, a11y, security, payment, visual, api.
    Actions inside blocks count too.
    """
    from je_web_runner.utils.test_categorizer.categorizer import categorize_actions
    return categorize_actions(actions)


def wr_test_categorizer_categorize_file(path: str) -> Any:
    """Tag the action file at ``path`` (a list or an object document); returns its ``tags`` and ``action_count``."""
    from je_web_runner.utils.test_categorizer.categorizer import categorize_file
    return to_plain(categorize_file(path))


def wr_test_categorizer_categorize_dir(directory: str) -> dict[str, Any]:
    """Tag every ``*.json`` action file of a directory; returns the ``assignments`` and the tag ``distribution``."""
    from je_web_runner.utils.test_categorizer.categorizer import TestCategorizerError, aggregate, categorize_file
    folder = Path(directory)
    if not folder.is_dir():
        raise TestCategorizerError(f"not a directory: {folder}")
    assignments = [categorize_file(child) for child in sorted(folder.glob("*.json"))]
    return {"assignments": to_plain(assignments), "distribution": to_plain(aggregate(assignments))}


# ---------- test_cost_estimator ------------------------------------------

def _cost_estimate(ledger_path: str | None, runs: list[dict[str, Any]] | None,
                   rate_cards: list[dict[str, Any]] | None) -> Any:
    from je_web_runner.utils.test_cost_estimator.estimator import (
        DEFAULT_RATE_CARDS, RateCard, RunRow, TestCostEstimatorError, estimate_runs, load_runs,
    )
    if runs is not None:
        rows = [
            RunRow(
                test_id=str(row.get("test_id") or row.get("path") or ""),
                runner=str(row.get("runner") or "local"),
                duration_seconds=float(row.get("duration_seconds") or 0.0),
            )
            for row in runs if isinstance(row, dict)
        ]
    elif ledger_path is not None:
        rows = load_runs(ledger_path)
    else:
        raise TestCostEstimatorError("give ledger_path or runs")
    cards = DEFAULT_RATE_CARDS if rate_cards is None else _rows(RateCard, rate_cards, TestCostEstimatorError)
    return estimate_runs(rows, rate_cards=cards)


def wr_test_cost_estimator_estimate(
    ledger_path: str | None = None, runs: list[dict[str, Any]] | None = None,
    rate_cards: list[dict[str, Any]] | None = None,
) -> Any:
    """
    Estimate billed minutes, cost and CO2 of recorded test runs, per runner and per test.

    Give ``runs`` (``{"test_id", "runner", "duration_seconds"}`` rows) or the ``ledger_path`` of a
    ``{"runs": [...]}`` file. ``rate_cards`` is a list of ``{"runner", "usd_per_minute",
    "grams_co2_per_minute", "minimum_minutes"}``; without it only the free ``local`` runner is known.
    """
    return to_plain(_cost_estimate(ledger_path, runs, rate_cards))


def wr_test_cost_estimator_markdown(
    ledger_path: str | None = None, runs: list[dict[str, Any]] | None = None,
    rate_cards: list[dict[str, Any]] | None = None, top_tests: int = 5,
) -> str:
    """Render the cost estimate of recorded test runs as markdown."""
    from je_web_runner.utils.test_cost_estimator.estimator import estimate_markdown
    return estimate_markdown(_cost_estimate(ledger_path, runs, rate_cards), top_tests=top_tests)


# ---------- test_debt_dashboard ------------------------------------------

def _debt_owners(codeowners_path: str | None) -> Any:
    from je_web_runner.utils.test_debt_dashboard.debt import parse_codeowners
    return parse_codeowners(_codeowners_text(None, codeowners_path)) if codeowners_path else None


def _debt_report(root: str, codeowners_path: str | None) -> Any:
    from je_web_runner.utils.test_debt_dashboard.debt import scan_directory
    return scan_directory(root, owners=_debt_owners(codeowners_path))


def wr_test_debt_dashboard_scan(root: str, codeowners_path: str | None = None) -> dict[str, Any]:
    """
    List the deferred test work under a directory: skip / xfail marks, TODO comments, ``"_skip"`` steps.

    Returns the ``items`` (kind, path, line, test name, reason, age in days from the file time, owner from
    the CODEOWNERS file when given) and the counts ``by_kind`` and ``by_owner``.
    """
    report = _debt_report(root, codeowners_path)
    return {"items": to_plain(report.items), "by_kind": report.by_kind(), "by_owner": report.by_owner()}


def wr_test_debt_dashboard_scan_file(path: str, codeowners_path: str | None = None) -> Any:
    """List the deferred test work in one file: a ``*.json`` action file or a Python test file."""
    from je_web_runner.utils.test_debt_dashboard.debt import scan_action_json, scan_python_file
    scan = scan_action_json if path.lower().endswith(".json") else scan_python_file
    return to_plain(scan(path, owners=_debt_owners(codeowners_path)))


def wr_test_debt_dashboard_markdown(root: str) -> str:
    """Render the count of deferred test work under a directory, per kind, as markdown."""
    from je_web_runner.utils.test_debt_dashboard.debt import report_markdown
    return report_markdown(_debt_report(root, None))


def wr_test_debt_dashboard_assert_under_age_limit(
    root: str, max_days: float, codeowners_path: str | None = None,
) -> int:
    """Fail when deferred test work under a directory is ``max_days`` old or more; returns the item count."""
    from je_web_runner.utils.test_debt_dashboard.debt import assert_under_age_limit
    report = _debt_report(root, codeowners_path)
    assert_under_age_limit(report, max_days=max_days)
    return len(report.items)


# ---------- test_dup_dry -------------------------------------------------

def _dup_specs(specs: list[dict[str, Any]]) -> list[Any]:
    from je_web_runner.utils.test_dup_dry.dedup import DupDryError, DupSpec
    return _rows(DupSpec, specs, DupDryError)


def wr_test_dup_dry_find_duplicates(specs: list[dict[str, Any]]) -> Any:
    """
    Find tests that walk the same steps.

    ``specs`` is a list of ``{"name", "actions"}``, where ``actions`` is an action list as in an action
    file (blocks included) or the older step objects with ``action_name``. Returns groups of test names
    sharing a step signature.
    """
    from je_web_runner.utils.test_dup_dry.dedup import find_duplicates
    return to_plain(find_duplicates(_dup_specs(specs)))


def wr_test_dup_dry_find_prefix_overlap(specs: list[dict[str, Any]], min_prefix: int = 5) -> Any:
    """Find pairs of tests that start with the same ``min_prefix`` or more steps, longest overlap first."""
    from je_web_runner.utils.test_dup_dry.dedup import find_prefix_overlap
    return to_plain(find_prefix_overlap(_dup_specs(specs), min_prefix=min_prefix))


def wr_test_dup_dry_assert_no_duplicates(specs: list[dict[str, Any]]) -> None:
    """Fail when two tests walk the same steps."""
    from je_web_runner.utils.test_dup_dry.dedup import assert_no_duplicates, find_duplicates
    assert_no_duplicates(find_duplicates(_dup_specs(specs)))


# ---------- test_naming_lint ---------------------------------------------

def _naming_findings(names: list[str], convention: str, max_length: int) -> list[Any]:
    from je_web_runner.utils.test_naming_lint.lint import Convention, NamingLintError, lint_many
    try:
        rule = Convention(convention)
    except ValueError as failure:
        known = [item.value for item in Convention]
        raise NamingLintError(f"unknown convention {convention!r}; known: {known}") from failure
    return lint_many(names, convention=rule, max_length=max_length)


def wr_test_naming_lint_lint(
    names: list[str], convention: str = "snake_case_should_when", max_length: int = 100,
) -> Any:
    """
    Check test function names against a naming convention; returns the findings.

    ``convention`` is ``snake_case_should_when``, ``given_when_then`` or ``camel_subject``.
    """
    return to_plain(_naming_findings(names, convention, max_length))


def wr_test_naming_lint_assert_clean(
    names: list[str], convention: str = "snake_case_should_when", max_length: int = 100,
) -> None:
    """Fail when a test function name breaks the naming convention."""
    from je_web_runner.utils.test_naming_lint.lint import assert_clean
    assert_clean(_naming_findings(names, convention, max_length))


# ---------- test_owners_map ----------------------------------------------

def _owners_map(codeowners: str, overrides: dict[str, list[str]] | None) -> Any:
    from je_web_runner.utils.test_owners_map.owners import OwnersMap, parse_codeowners
    return OwnersMap(codeowners=parse_codeowners(codeowners), overrides=dict(overrides or {}))


def _owner_audit(test_ids: list[str], codeowners: str, overrides: dict[str, list[str]] | None) -> Any:
    from je_web_runner.utils.test_owners_map.owners import audit_unowned
    return audit_unowned(test_ids, _owners_map(codeowners, overrides))


def wr_test_owners_map_owners_for(
    test_id: str, codeowners_text: str | None = None, codeowners_path: str | None = None,
    overrides: dict[str, list[str]] | None = None,
) -> list[str]:
    """
    List the owners of a test: its entry in ``overrides`` (test id to owners), else the CODEOWNERS match.

    The CODEOWNERS body is given as ``codeowners_text`` or as ``codeowners_path``.
    """
    owners: list[str] = _owners_map(_codeowners_text(codeowners_text, codeowners_path), overrides).owners_for(test_id)
    return owners


def wr_test_owners_map_audit(
    test_ids: list[str], codeowners_text: str | None = None, codeowners_path: str | None = None,
    overrides: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Count tests per owner and list the ``unowned`` ones; ``passed`` is true when every test has an owner."""
    audit = _owner_audit(test_ids, _codeowners_text(codeowners_text, codeowners_path), overrides)
    return {**to_plain(audit), "passed": audit.passed()}


def wr_test_owners_map_assert_no_unowned(
    test_ids: list[str], codeowners_text: str | None = None, codeowners_path: str | None = None,
    overrides: dict[str, list[str]] | None = None,
) -> None:
    """Fail when a test has no owner."""
    from je_web_runner.utils.test_owners_map.owners import assert_no_unowned
    assert_no_unowned(_owner_audit(test_ids, _codeowners_text(codeowners_text, codeowners_path), overrides))


# ---------- test_roi_scorer ----------------------------------------------

def _roi_scores(metrics: list[dict[str, Any]], weights: dict[str, float] | None) -> list[Any]:
    from je_web_runner.utils.executor._commands_governance import build_dataclass
    from je_web_runner.utils.test_roi_scorer.score import RoiMetrics, RoiScorerError, Weights, score_many
    roi_weights = None if weights is None else build_dataclass(Weights, weights, RoiScorerError)
    return score_many(_rows(RoiMetrics, metrics, RoiScorerError), roi_weights)


def wr_test_roi_scorer_score(metrics: list[dict[str, Any]], weights: dict[str, float] | None = None) -> Any:
    """
    Score tests 0..1 for return on investment, best first, with a keep / review / consider-removing verdict.

    A metrics object has ``name``, ``runs``, ``real_failures``, ``flake_failures``, ``duration_seconds``,
    ``unique_lines_covered``, ``days_since_last_run``, ``days_since_last_real_failure``. ``weights``
    (``find_rate``, ``cost``, ``coverage``, ``recency``) must sum to 1.
    """
    return to_plain(_roi_scores(metrics, weights))


def wr_test_roi_scorer_removal_candidates(
    metrics: list[dict[str, Any]], max_score: float = 0.3, weights: dict[str, float] | None = None,
) -> Any:
    """List the tests whose return-on-investment score is ``max_score`` or lower."""
    from je_web_runner.utils.test_roi_scorer.score import removal_candidates
    return to_plain(removal_candidates(_roi_scores(metrics, weights), max_score=max_score))


# ---------- test_scheduler -----------------------------------------------

def wr_test_scheduler_candidates_from_ledger(
    ledger_path: str, default_duration_seconds: float = 60.0, cloud_tests: list[str] | None = None,
) -> Any:
    """Build one scheduling candidate per test of a run ledger: average duration, fail rate, last-run age."""
    from je_web_runner.utils.test_scheduler.scheduler import build_candidates_from_ledger
    return to_plain(build_candidates_from_ledger(
        ledger_path, default_duration_seconds=default_duration_seconds, cloud_tests=cloud_tests,
    ))


def _schedule(candidates: list[dict[str, Any]], time_budget_seconds: float,
              cloud_slot_budget: int | None, pinned_test_ids: list[str] | None) -> Any:
    from je_web_runner.utils.test_scheduler.scheduler import TestCandidate, TestSchedulerError, schedule_tests
    return schedule_tests(
        _rows(TestCandidate, candidates, TestSchedulerError),
        time_budget_seconds=time_budget_seconds,
        cloud_slot_budget=cloud_slot_budget,
        pinned_test_ids=pinned_test_ids,
    )


def wr_test_scheduler_schedule(
    candidates: list[dict[str, Any]], time_budget_seconds: float,
    cloud_slot_budget: int | None = None, pinned_test_ids: list[str] | None = None,
) -> Any:
    """
    Pick the tests worth most per second that fit a time budget (and a cloud-session budget).

    A candidate has ``test_id``, ``duration_seconds`` and optionally ``fail_rate``, ``impact_score``,
    ``last_run_age_hours``, ``manual_priority``, ``needs_cloud_session``, ``tags``. Pinned tests are
    always taken; the command fails when they do not fit.
    """
    return to_plain(_schedule(candidates, time_budget_seconds, cloud_slot_budget, pinned_test_ids))


def wr_test_scheduler_markdown(
    candidates: list[dict[str, Any]], time_budget_seconds: float,
    cloud_slot_budget: int | None = None, pinned_test_ids: list[str] | None = None,
) -> str:
    """Render the schedule that fits the budgets as markdown."""
    from je_web_runner.utils.test_scheduler.scheduler import render_schedule_markdown
    return render_schedule_markdown(_schedule(candidates, time_budget_seconds, cloud_slot_budget, pinned_test_ids))


# ---------- a11y_trend ---------------------------------------------------

def _a11y_history(history: list[dict[str, Any]] | None, history_path: str | None) -> list[dict[str, Any]]:
    from je_web_runner.utils.a11y_trend.trend import A11yTrendError, load_history
    if history is not None:
        return history
    if history_path is None:
        raise A11yTrendError("give history or history_path")
    return load_history(history_path)


def a11y_trend_aggregate(
    history: list[dict[str, Any]] | None = None, history_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Count accessibility violations per day and impact over a history of axe runs.

    ``history`` is a list of ``{"timestamp", "violations": [{"impact", "nodes"}]}``, or ``history_path``
    names a JSON file holding one. Returns ``{"label", "impacts", "total"}`` per day.
    """
    from je_web_runner.utils.a11y_trend.trend import aggregate_history
    return [
        {"label": point.label, "impacts": dict(point.impacts), "total": point.total}
        for point in aggregate_history(_a11y_history(history, history_path))
    ]


def a11y_trend_write_dashboard(
    output_path: str, history: list[dict[str, Any]] | None = None, history_path: str | None = None,
    title: str = "A11y trend",
) -> str:
    """Write the accessibility trend of a history of axe runs as an HTML page; returns the file path."""
    from je_web_runner.utils.a11y_trend.trend import write_dashboard
    return str(write_dashboard(_a11y_history(history, history_path), output_path, title=title))


# ---------- failure_cluster ----------------------------------------------

def failure_cluster_normalise(message: str) -> str:
    """Strip timestamps, addresses, paths, numbers and quoted text from an error message."""
    from je_web_runner.utils.failure_cluster.clustering import normalise_error
    return normalise_error(message)


def failure_cluster_cluster(failures: list[dict[str, Any]], top_n: int | None = None) -> Any:
    """
    Group failures that share an error signature, largest group first.

    ``failures`` is a list of ``{"function_name", "exception", "file_path"}``. Each group gives its
    ``signature``, ``count``, a ``representative`` message and the ``files``; ``top_n`` keeps the largest.
    """
    from je_web_runner.utils.failure_cluster.clustering import cluster_failures, cluster_summary
    return to_plain(cluster_summary(cluster_failures(failures, top_n=top_n)))


# ---------- perf_drift ---------------------------------------------------

def _drift_report(metrics: Any, windows: tuple[int, int], tolerance: float,
                  higher_is_better: list[str] | None) -> Any:
    from je_web_runner.utils.perf_drift.drift import detect_drift
    return detect_drift(
        metrics, baseline_window=windows[0], recent_window=windows[1],
        tolerance=tolerance, higher_is_better=higher_is_better,
    )


def perf_drift_percentile(values: list[float], pct: float = 95.0) -> float:
    """The ``pct``-th percentile of a list of measurements."""
    from je_web_runner.utils.perf_drift.drift import percentile
    return percentile(values, pct)


def perf_drift_detect(
    metrics: dict[str, list[float]], baseline_window: int = 20, recent_window: int = 5,
    tolerance: float = 0.1, higher_is_better: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compare the recent P95 of each metric with the P95 of the runs before them.

    ``metrics`` maps a metric name to its measurements, oldest first; each needs ``baseline_window`` +
    ``recent_window`` of them. ``higher_is_better`` names the metrics where a drop is the regression.
    Returns per metric the two percentiles, the relative change and the ``direction`` (regressed /
    improved / stable), plus ``has_regressions``.
    """
    report = _drift_report(metrics, (baseline_window, recent_window), tolerance, higher_is_better)
    return {"metrics": to_plain(report.metrics), "has_regressions": report.has_regressions}


def perf_drift_assert_no_regression(
    metrics: dict[str, list[float]], baseline_window: int = 20, recent_window: int = 5,
    tolerance: float = 0.1, higher_is_better: list[str] | None = None,
) -> None:
    """Fail when the recent P95 of a metric is worse than its baseline by ``tolerance`` or more."""
    from je_web_runner.utils.perf_drift.drift import assert_no_regression
    report = _drift_report(metrics, (baseline_window, recent_window), tolerance, higher_is_better)
    assert_no_regression(report)


# ---------- trend_dashboard ----------------------------------------------

def trend_dashboard_compute(ledger_path: str | None = None, runs: list[dict[str, Any]] | None = None) -> Any:
    """
    Compute pass rate and average duration per day from recorded runs.

    Give ``runs`` (``{"time", "passed", "duration_seconds"}`` rows) or the ``ledger_path`` of a
    ``{"runs": [...]}`` file. Returns the ``daily`` rows and the ``totals``.
    """
    from je_web_runner.utils.trend_dashboard.trend import TrendDashboardError, compute_trend, compute_trend_from_runs
    if runs is not None:
        return to_plain(compute_trend_from_runs(runs))
    if ledger_path is None:
        raise TrendDashboardError("give ledger_path or runs")
    return to_plain(compute_trend(ledger_path))


def trend_dashboard_write(
    output_path: str, ledger_path: str | None = None, runs: list[dict[str, Any]] | None = None,
    title: str = "WebRunner trend",
) -> str:
    """Write the pass-rate trend of recorded runs as an HTML page; returns the file path."""
    from je_web_runner.utils.trend_dashboard.trend import write_dashboard
    return str(write_dashboard(trend_dashboard_compute(ledger_path, runs), output_path, title=title))


# ---------- tables --------------------------------------------------------

GOVERNANCE_2_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_test_blame_owner_codeowners": wr_test_blame_owner_codeowners,
    "WR_test_blame_owner_resolve": wr_test_blame_owner_resolve,
    "WR_test_blame_owner_assert_has_owner": wr_test_blame_owner_assert_has_owner,
    "WR_test_categorizer_categorize": wr_test_categorizer_categorize,
    "WR_test_categorizer_categorize_file": wr_test_categorizer_categorize_file,
    "WR_test_categorizer_categorize_dir": wr_test_categorizer_categorize_dir,
    "WR_test_cost_estimator_estimate": wr_test_cost_estimator_estimate,
    "WR_test_cost_estimator_markdown": wr_test_cost_estimator_markdown,
    "WR_test_debt_dashboard_scan": wr_test_debt_dashboard_scan,
    "WR_test_debt_dashboard_scan_file": wr_test_debt_dashboard_scan_file,
    "WR_test_debt_dashboard_markdown": wr_test_debt_dashboard_markdown,
    "WR_test_debt_dashboard_assert_under_age_limit": wr_test_debt_dashboard_assert_under_age_limit,
    "WR_test_dup_dry_find_duplicates": wr_test_dup_dry_find_duplicates,
    "WR_test_dup_dry_find_prefix_overlap": wr_test_dup_dry_find_prefix_overlap,
    "WR_test_dup_dry_assert_no_duplicates": wr_test_dup_dry_assert_no_duplicates,
    "WR_test_naming_lint_lint": wr_test_naming_lint_lint,
    "WR_test_naming_lint_assert_clean": wr_test_naming_lint_assert_clean,
    "WR_test_owners_map_owners_for": wr_test_owners_map_owners_for,
    "WR_test_owners_map_audit": wr_test_owners_map_audit,
    "WR_test_owners_map_assert_no_unowned": wr_test_owners_map_assert_no_unowned,
    "WR_test_roi_scorer_score": wr_test_roi_scorer_score,
    "WR_test_roi_scorer_removal_candidates": wr_test_roi_scorer_removal_candidates,
    "WR_test_scheduler_candidates_from_ledger": wr_test_scheduler_candidates_from_ledger,
    "WR_test_scheduler_schedule": wr_test_scheduler_schedule,
    "WR_test_scheduler_markdown": wr_test_scheduler_markdown,
    "WR_a11y_trend_aggregate": a11y_trend_aggregate,
    "WR_a11y_trend_write_dashboard": a11y_trend_write_dashboard,
    "WR_failure_cluster_normalise": failure_cluster_normalise,
    "WR_failure_cluster_cluster": failure_cluster_cluster,
    "WR_perf_drift_percentile": perf_drift_percentile,
    "WR_perf_drift_detect": perf_drift_detect,
    "WR_perf_drift_assert_no_regression": perf_drift_assert_no_regression,
    "WR_trend_dashboard_compute": trend_dashboard_compute,
    "WR_trend_dashboard_write": trend_dashboard_write,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset()
