"""
執行基礎設施類函式庫的命令轉接層（第二部分）
Command adapters for the run-infrastructure libraries, part two: locator health, the route coverage map,
driver pinning, impact analysis, Kubernetes shard manifests, pipeline definitions, the directory watcher,
the workspace lock, the live dashboard's data and session-to-test conversion. Part one is ``_commands_infra``.

Every command takes and returns JSON values. The pipeline runner, the watch loop and the dashboard server
need a callable or a long-lived server, so the commands here cover what is data: load and check a
definition, take and compare snapshots, read the numbers the dashboard shows.
"""
from __future__ import annotations
# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it

from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import to_plain

_ACTIONS_GLOB = "**/*.json"


def _sorted_lists(table: dict[str, Any]) -> dict[str, list[str]]:
    """A ``{key: set}`` table as ``{key: sorted list}``, keys in order."""
    return {key: sorted(table[key]) for key in sorted(table)}


# ---------- locator_health ----------------------------------------------

def _locator_findings(path: str, pattern: str) -> list[Any]:
    """The locators of one action file, or of every file matching ``pattern`` under a directory."""
    from je_web_runner.utils.locator_health.health_report import scan_action_file, scan_project
    target = Path(path)
    return scan_project(target, pattern) if target.is_dir() else scan_action_file(target)


def _locator_report(path: str, pattern: str, threshold: int, weakest_limit: int) -> Any:
    from je_web_runner.utils.locator_health.health_report import build_health_report
    return build_health_report(
        _locator_findings(path, pattern), threshold=threshold, weakest_limit=weakest_limit,
    )


def locator_health_scan(
    path: str, pattern: str = _ACTIONS_GLOB, threshold: int = 60, weakest_limit: int = 10,
) -> dict[str, Any]:
    """
    Score every locator in an action file, or in the action files under a directory.

    ``path`` is a file or a directory (searched with the glob ``pattern``); a locator scoring under
    ``threshold`` counts as weak.
    Returns ``{total, weak, strong, average_score, threshold, findings, weakest, fallback_offenders}``.
    """
    return to_plain(_locator_report(path, pattern, threshold, weakest_limit))


def locator_health_markdown(
    path: str, pattern: str = _ACTIONS_GLOB, threshold: int = 60, weakest_limit: int = 10,
) -> str:
    """The locator health report of a file or directory as Markdown, ready for a pull-request comment."""
    from je_web_runner.utils.locator_health.health_report import render_health_markdown
    return render_health_markdown(_locator_report(path, pattern, threshold, weakest_limit))


def locator_health_suggest(
    path: str, pattern: str = _ACTIONS_GLOB, only_below: int | None = None,
) -> list[dict[str, Any]]:
    """
    Suggest stabler locators for an action file or directory (an XPath on ``@id`` becomes ``ID``...).

    ``only_below`` skips locators already scoring at least that much. Nothing is rewritten.
    Returns ``[{file_path, action_index, from_strategy, from_value, to_strategy, to_value, rationale}]``.
    """
    from je_web_runner.utils.locator_health.health_report import suggest_upgrades
    return to_plain(suggest_upgrades(_locator_findings(path, pattern), only_below=only_below))


def locator_health_assert(
    path: str, pattern: str = _ACTIONS_GLOB, threshold: int = 60, max_weak: int = 0,
) -> dict[str, Any]:
    """
    Fail when more than ``max_weak`` locators of a file or directory score under ``threshold``.

    Returns the report of ``WR_locator_health_scan`` when the check passes.
    """
    from je_web_runner.utils.locator_health.health_report import LocatorHealthError
    report = _locator_report(path, pattern, threshold, 10)
    if report.weak > max_weak:
        worst = [f"{finding.strategy}={finding.value!r} ({finding.score})" for finding in report.weakest[:5]]
        raise LocatorHealthError(
            f"{report.weak} locator(s) score under {threshold} (allowed {max_weak}); weakest: {worst}"
        )
    return to_plain(report)


# ---------- coverage_map ------------------------------------------------

def _coverage(directory: str, glob: str, normalise_params: bool) -> Any:
    from je_web_runner.utils.coverage_map.coverage import build_coverage_map
    return build_coverage_map(directory, glob=glob, normalise_params=normalise_params)


def coverage_map_build(
    directory: str, glob: str = _ACTIONS_GLOB, normalise_params: bool = True,
) -> dict[str, Any]:
    """
    Index the action files under a directory by the URL routes they navigate to.

    Numeric and UUID path segments become ``:id`` unless ``normalise_params`` is false.
    Returns ``{routes_by_file: {file: [routes]}, files_by_route: {route: [files]}}``.
    """
    coverage = _coverage(directory, glob, normalise_params)
    return {
        "routes_by_file": _sorted_lists(coverage.routes_by_file),
        "files_by_route": _sorted_lists(coverage.files_by_route),
    }


def coverage_map_uncovered(
    directory: str, declared_routes: list[str], glob: str = _ACTIONS_GLOB, normalise_params: bool = True,
) -> list[str]:
    """The ``declared_routes`` that no action file under ``directory`` navigates to."""
    return _coverage(directory, glob, normalise_params).uncovered(declared_routes)


def coverage_map_markdown(
    directory: str, declared_routes: list[str] | None = None,
    glob: str = _ACTIONS_GLOB, normalise_params: bool = True,
) -> str:
    """A Markdown table of route, test count and files; for ``declared_routes`` or every route found."""
    from je_web_runner.utils.coverage_map.coverage import render_markdown
    return render_markdown(_coverage(directory, glob, normalise_params), declared_routes)


def coverage_map_assert_covered(
    directory: str, declared_routes: list[str], glob: str = _ACTIONS_GLOB, normalise_params: bool = True,
) -> dict[str, list[str]]:
    """
    Fail when one of ``declared_routes`` has no action file navigating to it.

    Returns ``{route: [files]}`` for the declared routes when all are covered.
    """
    from je_web_runner.utils.coverage_map.coverage import CoverageMapError, coverage_for_routes
    coverage = _coverage(directory, glob, normalise_params)
    missing = coverage.uncovered(declared_routes)
    if missing:
        raise CoverageMapError(f"{len(missing)} route(s) have no test: {missing}")
    return coverage_for_routes(coverage, declared_routes)


# ---------- driver_pin --------------------------------------------------

def driver_pin_platform() -> str:
    """This machine's platform marker in a pin file: win, mac-arm64, mac-x64, linux or linux-arm64."""
    from je_web_runner.utils.driver_pin.pinner import current_platform_marker
    return current_platform_marker()


def driver_pin_load(pin_file: str) -> list[dict[str, Any]]:
    """
    Read and validate a driver pin file (``.webrunner/drivers.json``).

    Returns its drivers ``{name, version, url, archive_format, binary_inside, platforms, cache_subdir}``,
    each with ``matches_current_platform``.
    """
    from je_web_runner.utils.driver_pin.pinner import load_pinfile
    return [
        {**to_plain(pinned), "matches_current_platform": pinned.matches_current_platform()}
        for pinned in load_pinfile(pin_file)
    ]


def driver_pin_install(pin_file: str, browser: str, cache_dir: str = ".webrunner/drivers") -> str | None:
    """
    Make sure the driver a pin file names for ``browser`` is in the cache, downloading it when missing.

    ``browser`` is firefox, chrome, chromium or edge. The archive comes from the URL in the pin file and is
    unpacked under ``cache_dir``. Returns the driver binary's path, or null when the pin file has no entry
    for this browser and platform.
    """
    from je_web_runner.utils.driver_pin.pinner import install_for_browser
    binary = install_for_browser(pin_file, browser, cache_dir=cache_dir)
    return None if binary is None else str(binary)


# ---------- impact_analysis ---------------------------------------------

def _impact_index(directory: str, glob: str, cache_path: str | None) -> Any:
    from je_web_runner.utils.impact_analysis.indexer import build_index
    return build_index(directory, glob=glob, cache_path=cache_path)


def impact_analysis_index(
    directory: str, glob: str = _ACTIONS_GLOB, cache_path: str | None = None,
) -> dict[str, Any]:
    """
    Index the action files under a directory by the locators, URLs, templates and commands they use.

    ``cache_path`` names a JSON cache that is read and rewritten so unchanged files are not parsed again.
    Returns ``{by_locator, by_url, by_template, by_command}``, each ``{name: [files]}``.
    """
    index = _impact_index(directory, glob, cache_path)
    return {
        "by_locator": _sorted_lists(index.by_locator),
        "by_url": _sorted_lists(index.by_url),
        "by_template": _sorted_lists(index.by_template),
        "by_command": _sorted_lists(index.by_command),
    }


def impact_analysis_affected(
    directory: str, locators: list[str] | None = None, urls: list[str] | None = None,
    templates: list[str] | None = None, commands: list[str] | None = None,
) -> list[str]:
    """
    The action files under a directory that use any of the changed names.

    ``locators``, ``templates`` and ``commands`` match exactly; ``urls`` are fragments matched inside the
    URLs a file navigates to.
    """
    from je_web_runner.utils.impact_analysis.indexer import affected_action_files
    index = _impact_index(directory, _ACTIONS_GLOB, None)
    return affected_action_files(index, locators=locators, urls=urls, templates=templates, commands=commands)


def impact_analysis_select(
    files: list[str], directory: str, affected_by: list[str], cache_path: str | None = None,
) -> list[str]:
    """
    Keep, in their order, the ``files`` that the ``affected_by`` names reach.

    ``affected_by`` entries are ``KIND:VALUE`` with KIND one of locator, url, template, command, or
    ``@path`` naming a file with one such entry per line. ``directory`` is the tree that is indexed.
    """
    from je_web_runner.utils.impact_analysis.selection import select_by_impact
    return select_by_impact(files, directory, affected_by=affected_by, cache_path=cache_path)


# ---------- k8s_runner --------------------------------------------------

def _shard_config(config: dict[str, Any]) -> Any:
    from je_web_runner.utils.k8s_runner.manifest import K8sRunnerError, ShardJobConfig
    try:
        return ShardJobConfig(**config)
    except TypeError as error:
        raise K8sRunnerError(f"invalid shard job config: {error}") from error


def k8s_runner_render_manifests(config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Render one Kubernetes ``batch/v1`` Job per shard, each running ``--shard i/N`` of an action directory.

    ``config`` needs ``name_prefix``, ``total_shards`` and ``actions_dir``; optional are ``image`` (default
    ``k8s_runner.RUNNER_IMAGE``, a name this project does not publish: build ``docker/Runner.Containerfile``
    and push it there, or name your own image), ``namespace``, ``command``, ``env``, ``resources``,
    ``backoff_limit``, ``parallelism``, ``completions``, ``labels`` and ``extra_args``. Only renders: nothing
    is sent to a cluster.
    """
    from je_web_runner.utils.k8s_runner.manifest import render_job_manifests
    return to_plain(render_job_manifests(_shard_config(config)))


def k8s_runner_render_yaml(config: dict[str, Any]) -> str:
    """The shard Jobs of ``WR_k8s_runner_render_manifests`` as one multi-document YAML text."""
    from je_web_runner.utils.k8s_runner.manifest import render_job_yaml
    return render_job_yaml(_shard_config(config))


# ---------- pipeline ----------------------------------------------------

def pipeline_load(source: Any) -> dict[str, Any]:
    """
    Read and validate a multi-stage pipeline definition.

    ``source`` is the definition object ``{"stages": [{name, files, required_status?,
    continue_on_failure?}]}``, a path to a JSON file holding it, or its JSON text.
    Returns the definition with every default filled in.
    """
    from je_web_runner.utils.pipeline.pipeline import load_pipeline
    return to_plain(load_pipeline(source))


def pipeline_assert_all_passed(results: list[dict[str, Any]]) -> int:
    """
    Fail when any pipeline stage in ``results`` has a status other than ``passed``.

    ``results`` is a list of ``{stage_name, status, file_results?, error?}``. Returns the stage count.
    """
    from je_web_runner.utils.pipeline.pipeline import PipelineError, PipelineResult, assert_all_passed
    try:
        stages = [PipelineResult(**row) for row in results]
    except TypeError as error:
        raise PipelineError(f"a stage result is {{stage_name, status}}: {error}") from error
    assert_all_passed(stages)
    return len(stages)


# ---------- watch_mode --------------------------------------------------

def _watch_snapshot(entries: dict[str, Any]) -> Any:
    from je_web_runner.utils.watch_mode.watcher import WatchModeError, WatchSnapshot
    try:
        return WatchSnapshot(entries={path: (pair[0], pair[1]) for path, pair in entries.items()})
    except (AttributeError, IndexError, KeyError, TypeError) as error:
        raise WatchModeError(f"a snapshot is {{path: [mtime, size]}}: {error!r}") from error


def watch_mode_snapshot(directory: str, glob: str = _ACTIONS_GLOB) -> dict[str, list[Any]]:
    """
    Record the modification time and size of every file matching ``glob`` under a directory.

    Returns ``{path: [mtime, size]}``; keep it and compare a later one with ``WR_watch_mode_diff``.
    """
    from je_web_runner.utils.watch_mode.watcher import snapshot_dir
    return to_plain(snapshot_dir(directory, glob=glob).entries)


def watch_mode_diff(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """
    Compare two ``WR_watch_mode_snapshot`` results.

    Returns ``{added, removed, changed, has_changes}`` with sorted path lists.
    """
    from je_web_runner.utils.watch_mode.watcher import poll_changes
    diff = poll_changes(_watch_snapshot(previous), _watch_snapshot(current))
    return {**to_plain(diff), "has_changes": diff.has_changes}


# ---------- workspace_lock ----------------------------------------------

def _workspace_lock(
    drivers: list[dict[str, Any]] | None, playwright_versions: dict[str, str] | None,
    allow_distributions: list[str] | None,
) -> Any:
    from je_web_runner.utils.workspace_lock.lock import build_lock
    return build_lock(
        drivers=drivers, playwright_versions=playwright_versions, allow_distributions=allow_distributions,
    )


def workspace_lock_build(
    drivers: list[dict[str, Any]] | None = None, playwright_versions: dict[str, str] | None = None,
    allow_distributions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Describe this interpreter's installed packages plus the driver and Playwright versions given.

    ``drivers`` is a list of ``{name, version, ...}``, ``playwright_versions`` ``{browser: version}``;
    ``allow_distributions`` keeps only those Python packages.
    Returns ``{python_version, generated_at, entries: [{name, version, kind, extras}]}``.
    """
    return to_plain(_workspace_lock(drivers, playwright_versions, allow_distributions))


def workspace_lock_write(
    path: str, drivers: list[dict[str, Any]] | None = None,
    playwright_versions: dict[str, str] | None = None, allow_distributions: list[str] | None = None,
) -> str:
    """Write the lock of ``WR_workspace_lock_build`` to ``path`` as JSON; returns the path written."""
    from je_web_runner.utils.workspace_lock.lock import write_lock
    return str(write_lock(_workspace_lock(drivers, playwright_versions, allow_distributions), path))


def workspace_lock_diff(before_path: str, after_path: str) -> dict[str, Any]:
    """
    Compare two workspace lock files.

    Returns ``{added, removed, version_changed}``; a changed entry is ``{name, kind, from, to}``.
    """
    from je_web_runner.utils.workspace_lock.lock import diff_locks, load_lock
    return to_plain(diff_locks(load_lock(before_path), load_lock(after_path)))


def workspace_lock_assert_current(path: str, check_python_version: bool = True) -> dict[str, Any]:
    """
    Fail when this interpreter's packages differ from the Python packages a lock file pins.

    Compares only the packages the lock names (an extra installed package is not drift) and, unless
    ``check_python_version`` is false, the Python version. Returns ``{python_version, checked}``.
    """
    from je_web_runner.utils.workspace_lock import lock as lock_module
    locked = lock_module.load_lock(path)
    pinned = locked.by_kind("python")
    # An empty allow-list means "every installed package" to build_lock; "-" is no package's name.
    current = _workspace_lock(None, None, [entry.name for entry in pinned] or ["-"])
    expected = lock_module.WorkspaceLock(
        python_version=locked.python_version, generated_at=locked.generated_at, entries=pinned,
    )
    drift = {kind: rows for kind, rows in lock_module.diff_locks(expected, current).items() if rows}
    if check_python_version and locked.python_version != current.python_version:
        drift["python_version"] = [{"from": locked.python_version, "to": current.python_version}]
    if drift:
        raise lock_module.WorkspaceLockError(f"workspace differs from {path}: {to_plain(drift)}")
    return {"python_version": current.python_version, "checked": len(pinned)}


# ---------- live_dashboard ----------------------------------------------

def live_dashboard_summary(
    ledger_path: str | None = None, quarantine_path: str | None = None,
    locator_findings_path: str | None = None,
) -> dict[str, Any]:
    """
    The counts the live dashboard's overview shows, read from the files given.

    Returns ``{total_runs, passed, failed, pass_rate, flaky_tests, quarantined_tests, weak_locators,
    average_locator_score}``; a missing or unreadable file counts as empty.
    """
    from je_web_runner.utils.live_dashboard.server import DashboardConfig, build_summary
    config = DashboardConfig(
        ledger_path=ledger_path, quarantine_path=quarantine_path,
        locator_findings_path=locator_findings_path,
    )
    return to_plain(build_summary(config))


def live_dashboard_trend(ledger_path: str) -> dict[str, Any]:
    """Per-day pass and fail counts of a run ledger, as the live dashboard charts them: ``{daily, totals}``."""
    from je_web_runner.utils.live_dashboard import _data
    return to_plain(_data.load_trend(Path(ledger_path)))


# ---------- session_to_test ---------------------------------------------

def _converted_session(events: Any) -> Any:
    from je_web_runner.utils.session_to_test.converter import convert_events
    return convert_events(events)


def session_to_test_convert(events: Any) -> dict[str, Any]:
    """
    Turn a recorded user session into WebRunner actions.

    ``events`` is the event list, or a path to a JSON file holding it (or ``{"events": [...]}``): rrweb
    events (``{type, data, timestamp}``) or generic ``{kind, target, value?, url?}`` events with ``kind``
    one of navigate, click, input, submit, wait.
    Returns ``{actions, stats: {input_events, actions_emitted, skipped_events, comment_actions, reasons}}``.
    """
    return to_plain(_converted_session(events))


def session_to_test_write(events: Any, output_path: str) -> dict[str, Any]:
    """
    Convert a recorded session like ``WR_session_to_test_convert`` and write the actions to a JSON file.

    Returns ``{path, stats}``.
    """
    from je_web_runner.utils.session_to_test.converter import write_actions_json
    result = _converted_session(events)
    return {"path": str(write_actions_json(result, output_path)), "stats": to_plain(result.stats)}


INFRA_2_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_locator_health_scan": locator_health_scan,
    "WR_locator_health_markdown": locator_health_markdown,
    "WR_locator_health_suggest": locator_health_suggest,
    "WR_locator_health_assert": locator_health_assert,
    "WR_coverage_map_build": coverage_map_build,
    "WR_coverage_map_uncovered": coverage_map_uncovered,
    "WR_coverage_map_markdown": coverage_map_markdown,
    "WR_coverage_map_assert_covered": coverage_map_assert_covered,
    "WR_driver_pin_platform": driver_pin_platform,
    "WR_driver_pin_load": driver_pin_load,
    "WR_driver_pin_install": driver_pin_install,
    "WR_impact_analysis_index": impact_analysis_index,
    "WR_impact_analysis_affected": impact_analysis_affected,
    "WR_impact_analysis_select": impact_analysis_select,
    "WR_k8s_runner_render_manifests": k8s_runner_render_manifests,
    "WR_k8s_runner_render_yaml": k8s_runner_render_yaml,
    "WR_pipeline_load": pipeline_load,
    "WR_pipeline_assert_all_passed": pipeline_assert_all_passed,
    "WR_watch_mode_snapshot": watch_mode_snapshot,
    "WR_watch_mode_diff": watch_mode_diff,
    "WR_workspace_lock_build": workspace_lock_build,
    "WR_workspace_lock_write": workspace_lock_write,
    "WR_workspace_lock_diff": workspace_lock_diff,
    "WR_workspace_lock_assert_current": workspace_lock_assert_current,
    "WR_live_dashboard_summary": live_dashboard_summary,
    "WR_live_dashboard_trend": live_dashboard_trend,
    "WR_session_to_test_convert": session_to_test_convert,
    "WR_session_to_test_write": session_to_test_write,
}

PYTHON_ONLY: dict[str, str] = {
    "fanout": (
        "Fan-out runs caller-supplied Python callables in threads; an action file has no callable to pass."
    ),
    "synthetic_monitoring": (
        "A monitor is built from check callables and an alert-sink callable and keeps its state between "
        "ticks of a long-running loop; no part of it works on JSON values alone."
    ),
}

NETWORK_COMMANDS: frozenset[str] = frozenset({"WR_driver_pin_install"})
