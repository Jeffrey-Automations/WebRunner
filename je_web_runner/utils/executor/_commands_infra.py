"""
執行基礎設施類函式庫的命令轉接層（第一部分）
Command adapters for the run-infrastructure libraries, part one: adaptive retry, the process supervisor,
smart waits, the cross-shard throttler, chaos planning, the feature-flag matrix, the persona matrix,
persistent Chrome profiles and download verification. Part two is ``_commands_infra_2``.

Every command takes and returns JSON values. Several of these libraries wrap a caller-supplied callable
(retry a function, run a step under chaos, run a file per persona); an action file has no callable to pass,
so the commands here cover the data side: classify an error text, plan a schedule, build a matrix, roll up
results. Nothing in this module starts a browser, starts a process from an argument, or kills one.
"""
from __future__ import annotations
# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it

import re
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import selenium_driver, to_plain

_STATE: dict[str, Any] = {}
_SLOT_FILE_NAME = re.compile(r"slot-\d+\.lock")
_DOWNLOAD_READERS = {
    "csv": "read_csv_rows",
    "json": "read_json_file",
    "pdf": "extract_pdf_text",
    "xlsx": "read_excel_rows",
}


def _build(factory: Callable[..., Any], values: dict[str, Any] | None, error_type: type[Exception]) -> Any:
    """``factory(**values)``, with an unknown or missing field reported as the library's own error."""
    try:
        return factory(**(values or {}))
    except TypeError as error:
        raise error_type(f"cannot build {getattr(factory, '__name__', 'object')}: {error}") from error


# ---------- adaptive_retry ----------------------------------------------

def _retry_decision(
    error_text: str, attempt: int, policy: dict[str, Any] | None,
    ledger_path: str | None, file_path: str | None,
) -> dict[str, Any]:
    from je_web_runner.utils.adaptive_retry.policy import AdaptiveRetryError, RetryPolicy
    from je_web_runner.utils.run_ledger.classifier import classify
    used_policy = _build(RetryPolicy, policy, AdaptiveRetryError)
    category = classify(error_text, ledger_path=ledger_path, file_path=file_path)
    will_retry = attempt <= used_policy.budget_for(category)
    return {
        "attempt": attempt,
        "category": category,
        "will_retry": will_retry,
        "sleep_seconds": used_policy.backoff_for(attempt) if will_retry else 0.0,
    }


def adaptive_retry_decide(
    error_text: str, attempt: int = 1, policy: dict[str, Any] | None = None,
    ledger_path: str | None = None, file_path: str | None = None,
) -> dict[str, Any]:
    """
    Classify an error text and say whether the adaptive retry policy would retry it.

    ``attempt`` is the 1-based attempt that just failed. ``policy`` overrides the budgets:
    ``transient_max``, ``flaky_max``, ``environment_max``, ``real_max``, ``base_backoff``, ``max_backoff``.
    With ``ledger_path`` and ``file_path`` a file the run ledger knows as flaky is classified ``flaky``.
    Returns ``{attempt, category, will_retry, sleep_seconds}``.
    """
    return _retry_decision(error_text, attempt, policy, ledger_path, file_path)


def adaptive_retry_assert_retryable(
    error_text: str, attempt: int = 1, policy: dict[str, Any] | None = None,
    ledger_path: str | None = None, file_path: str | None = None,
) -> dict[str, Any]:
    """
    Fail unless the adaptive retry policy would retry this error at this attempt.

    Takes the arguments of ``WR_adaptive_retry_decide`` and returns the same decision.
    """
    from je_web_runner.utils.adaptive_retry.policy import AdaptiveRetryError
    decision = _retry_decision(error_text, attempt, policy, ledger_path, file_path)
    if not decision["will_retry"]:
        raise AdaptiveRetryError(
            f"{decision['category']} failure is not retried at attempt {attempt}: {error_text[:200]}"
        )
    return decision


def adaptive_retry_backoff(attempts: int = 5, policy: dict[str, Any] | None = None) -> list[float]:
    """
    The seconds the adaptive retry policy sleeps after each of the first ``attempts`` failed attempts.

    ``policy`` takes ``base_backoff`` and ``max_backoff`` (and the budgets, which do not change the delays).
    """
    from je_web_runner.utils.adaptive_retry.policy import AdaptiveRetryError, RetryPolicy
    used_policy = _build(RetryPolicy, policy, AdaptiveRetryError)
    return [used_policy.backoff_for(attempt) for attempt in range(1, attempts + 1)]


# ---------- process_supervisor ------------------------------------------

def process_supervisor_list_orphans(names: list[str] | None = None) -> list[dict[str, Any]]:
    """
    List the running WebDriver processes (chromedriver, geckodriver, msedgedriver, IEDriverServer).

    ``names`` replaces the process names looked for. Read-only: nothing is stopped.
    Returns ``[{pid, name, command_line}]``.
    """
    from je_web_runner.utils.process_supervisor import supervisor
    watcher = supervisor.ProcessSupervisor(lister=supervisor.default_lister)
    return to_plain(watcher.list_orphans(names or supervisor.KNOWN_DRIVER_NAMES))


# ---------- smart_wait --------------------------------------------------

def _smart_wait(command: str, waiter_name: str, quiet_for: float, timeout: float, poll: float) -> bool:
    from je_web_runner.utils.smart_wait import smart_wait
    waiter = getattr(smart_wait, waiter_name)
    waiter(selenium_driver(command), quiet_for=quiet_for, timeout=timeout, poll=poll)
    return True


def smart_wait_install_hooks() -> bool:
    """
    Install the fetch / XHR counter and the history-change hook in the current page.

    The two wait commands install them too; call this right after navigation so requests that start
    before the first wait are counted.
    """
    from je_web_runner.utils.smart_wait.smart_wait import install_hooks
    install_hooks(selenium_driver("WR_smart_wait_install_hooks"))
    return True


def smart_wait_fetch_idle(quiet_for: float = 0.5, timeout: float = 10.0, poll: float = 0.1) -> bool:
    """
    Wait until the page has had no fetch / XHR request in flight for ``quiet_for`` seconds.

    Fails when that does not happen within ``timeout`` seconds.
    """
    return _smart_wait("WR_smart_wait_fetch_idle", "wait_for_fetch_idle", quiet_for, timeout, poll)


def smart_wait_route_stable(quiet_for: float = 0.4, timeout: float = 10.0, poll: float = 0.1) -> bool:
    """
    Wait until a single-page app has not changed its route for ``quiet_for`` seconds.

    Watches ``history.pushState`` / ``replaceState``, ``popstate`` and ``hashchange``; fails when the route
    keeps changing for ``timeout`` seconds.
    """
    return _smart_wait("WR_smart_wait_route_stable", "wait_for_spa_route_stable", quiet_for, timeout, poll)


# ---------- throttler ---------------------------------------------------

def _throttler() -> Any:
    """The throttler the ``WR_throttler_*`` commands share, created on first use."""
    if "throttler" not in _STATE:
        from je_web_runner.utils.throttler.throttler import ServiceThrottler
        _STATE["throttler"] = ServiceThrottler()
    return _STATE["throttler"]


def throttler_configure(
    name: str, capacity: int, base_dir: str | None = None, stale_after: float = 600.0,
) -> dict[str, Any]:
    """
    Declare a service that at most ``capacity`` runs (shards, processes) may use at the same time.

    Slots are files under ``base_dir`` (default ``.webrunner/throttle``), so every process pointing at the
    same directory shares the limit. A slot older than ``stale_after`` seconds is taken back.
    """
    throttler = _throttler()
    if base_dir is not None:
        throttler.base_dir = base_dir
    throttler.configure(name=name, capacity=capacity, stale_after=stale_after)
    return {"name": name, "capacity": capacity, "base_dir": throttler.base_dir}


def throttler_acquire(name: str, timeout: float = 30.0) -> str:
    """
    Take one slot of a configured service, waiting up to ``timeout`` seconds for a free one.

    Returns the slot's path; pass it to ``WR_throttler_release`` when done.
    """
    return str(_throttler().get(name).acquire(timeout=timeout))


def throttler_release(name: str, slot: str) -> bool:
    """
    Give back a slot ``WR_throttler_acquire`` returned for the service ``name``.

    Only a slot file of that service is accepted.
    """
    from je_web_runner.utils.throttler.throttler import ThrottlerError
    semaphore = _throttler().get(name)
    slot_path = Path(slot)
    service_dir = Path(semaphore.base_dir) / semaphore.name
    if slot_path.parent.resolve() != service_dir.resolve() or not _SLOT_FILE_NAME.fullmatch(slot_path.name):
        raise ThrottlerError(f"{slot!r} is not a slot of service {name!r}")
    semaphore.release(slot_path)
    return True


def throttler_reset() -> bool:
    """Forget every service ``WR_throttler_configure`` declared (slot files already taken are kept)."""
    _STATE.pop("throttler", None)
    return True


# ---------- chaos_hooks -------------------------------------------------

def chaos_hooks_fault_types() -> list[str]:
    """The fault names ``WR_chaos_hooks_plan`` can schedule."""
    from je_web_runner.utils.chaos_hooks.chaos import ChaosFaultType
    return [fault.value for fault in ChaosFaultType]


def chaos_hooks_plan(  # pylint: disable=too-many-arguments,too-many-positional-arguments  # project limit is 7
    step_names: list[str], faults: list[str] | None = None, fault_rate: float = 0.2,
    max_events: int | None = None, skip_first: int = 1, skip_last: int = 0, seed: int | None = None,
) -> dict[str, Any]:
    """
    Decide, reproducibly, which steps of a flow get which fault (offline, slow network, reload...).

    Each step outside the first ``skip_first`` and last ``skip_last`` gets a fault from ``faults`` (default:
    all of them) with probability ``fault_rate``; the same ``seed`` gives the same plan. This only plans:
    apply each event with the network / reload commands before its step.
    Returns ``{events: [{step_index, step_name, fault}], seed, skipped, description}``.
    """
    from je_web_runner.utils.chaos_hooks.chaos import ChaosFaultType, ChaosHooksError, plan_chaos
    try:
        chosen = list(ChaosFaultType) if faults is None else [ChaosFaultType(name) for name in faults]
    except ValueError as error:
        raise ChaosHooksError(f"unknown fault type: {error}") from error
    plan = plan_chaos(
        step_names, faults=chosen, fault_rate=fault_rate, max_events=max_events,
        skip_first=skip_first, skip_last=skip_last, seed=seed,
    )
    return {**to_plain(plan), "description": plan.describe()}


# ---------- flag_matrix -------------------------------------------------

def _flag_constraints(pairs: list[Any] | None, maker: Callable[[Any], Any]) -> list[Any]:
    from je_web_runner.utils.flag_matrix.matrix import FlagMatrixError
    try:
        return [maker(pair) for pair in pairs or []]
    except (TypeError, ValueError) as error:
        raise FlagMatrixError(
            f"a constraint is [[flag, value], [flag, value]]: {error}"
        ) from error


def flag_matrix_build(  # pylint: disable=too-many-arguments,too-many-positional-arguments  # project limit is 7
    flags: dict[str, list[Any]], forbid: list[Any] | None = None, require: list[Any] | None = None,
    pinned: list[dict[str, Any]] | None = None, sample_size: int | None = None, seed: int | None = None,
) -> dict[str, Any]:
    """
    Build the feature-flag combinations to test from ``{flag: [variants]}``.

    ``forbid`` lists pairs ``[[flag_a, value_a], [flag_b, value_b]]`` that must not appear together;
    ``require`` lists pairs meaning "when flag_a is value_a, flag_b must be value_b". ``pinned`` combos
    always come first; ``sample_size`` caps the total with a sample that ``seed`` makes reproducible.
    Returns ``{combos, total_possible, pinned_count, constrained_out, sampled, seed}``.
    """
    from je_web_runner.utils.flag_matrix import matrix
    specs = [matrix.FlagSpec(name=name, variants=variants) for name, variants in flags.items()]
    constraints = _flag_constraints(forbid, matrix.forbid) + _flag_constraints(require, matrix.require)
    built = matrix.build_matrix(
        specs, constraints=constraints, pinned=pinned or [], sample_size=sample_size, seed=seed,
    )
    return to_plain(built)


def _flag_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    from je_web_runner.utils.flag_matrix import matrix
    outcomes = [_build(matrix.ComboResult, row, matrix.FlagMatrixError) for row in results]
    report = matrix.summarise_results(outcomes)
    return {**to_plain(report), "smallest_failing_subset": matrix.smallest_failing_subset(report.failures)}


def flag_matrix_summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Roll up the outcome of each flag combination and name the flag values that explain the failures.

    ``results`` is a list of ``{combo, passed, duration_seconds?, error?}``.
    Returns ``{total, passed, failed, failures, average_seconds, smallest_failing_subset}``, the last one
    being the fewest ``flag=value`` entries that cover every failing combo.
    """
    return _flag_summary(results)


def flag_matrix_assert_all_passed(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Fail when any flag combination in ``results`` did not pass, naming the flag values behind the failures.

    Takes the ``results`` of ``WR_flag_matrix_summarise`` and returns the same summary.
    """
    from je_web_runner.utils.flag_matrix.matrix import FlagMatrixError
    summary = _flag_summary(results)
    if summary["failed"]:
        raise FlagMatrixError(
            f"{summary['failed']} of {summary['total']} flag combos failed; "
            f"smallest failing subset: {summary['smallest_failing_subset']}"
        )
    return summary


# ---------- persona_runner ----------------------------------------------

def _persona_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    from je_web_runner.utils.persona_runner import runner
    outcomes = [_build(runner.PersonaCaseResult, row, runner.PersonaRunnerError) for row in results]
    summary = runner.summarise(outcomes)
    return {**to_plain(summary), "markdown": runner.summary_markdown(summary)}


def persona_runner_summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Roll up a persona-by-file run: which personas fail alone, which files fail for everyone.

    ``results`` is a list of ``{persona, action_file, passed, duration_seconds?, error?, notes?}``.
    Returns ``{total, passed, failed, by_persona, persona_only_failures, file_only_failures, markdown}``.
    """
    return _persona_summary(results)


def persona_runner_assert_all_passed(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Fail when any persona / file pair in ``results`` did not pass.

    Takes the ``results`` of ``WR_persona_runner_summarise`` and returns the same summary.
    """
    from je_web_runner.utils.persona_runner.runner import PersonaRunnerError
    summary = _persona_summary(results)
    if summary["failed"]:
        raise PersonaRunnerError(
            f"{summary['failed']} of {summary['total']} persona cases failed; "
            f"persona-specific: {summary['persona_only_failures']}, "
            f"failing for every persona: {summary['file_only_failures']}"
        )
    return summary


# ---------- chrome_profile ----------------------------------------------

def _check_snapshot_target(profile_dir: Path, snapshot_dir: Path) -> None:
    """Refuse a snapshot directory whose replacement would delete something that is not a snapshot."""
    from je_web_runner.utils.chrome_profile.profile_manager import ChromeProfileError
    profile = profile_dir.resolve()
    snapshot = snapshot_dir.resolve()
    if snapshot == profile or snapshot in profile.parents:
        raise ChromeProfileError(f"snapshot_dir {snapshot} contains the profile; choose another directory")
    if not snapshot.is_dir() or not any(snapshot.iterdir()):
        return
    if not (snapshot / "Default").exists() and not (snapshot / "Local State").exists():
        raise ChromeProfileError(
            f"snapshot_dir {snapshot} exists and is not a Chrome profile snapshot; refusing to replace it"
        )


def chrome_profile_options(profile_dir: str, flags: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    The Chrome arguments and experimental options for a persistent profile with stealth settings.

    ``flags`` takes ``user_agent``, ``language``, ``window_size`` (``[width, height]``),
    ``disable_blink_features``, ``exclude_automation_switches``, ``headless`` and ``extra_args``.
    Creates ``profile_dir`` when missing. Returns ``{arguments, experimental_options}``.
    """
    from je_web_runner.utils.chrome_profile import profile_manager
    values = dict(flags or {})
    if values.get("window_size") is not None:
        values["window_size"] = tuple(values["window_size"])
    stealth = _build(profile_manager.StealthFlags, values, profile_manager.ChromeProfileError)
    options = profile_manager.build_chrome_options(Path(profile_dir), flags=stealth)
    return {
        "arguments": list(options.arguments),
        "experimental_options": to_plain(options.experimental_options),
    }


def chrome_profile_cleanup_locks(profile_dir: str) -> list[str]:
    """
    Remove the Singleton lock files a crashed Chrome leaves in a profile directory.

    Only ``SingletonLock``, ``SingletonCookie``, ``SingletonSocket``, ``lockfile`` and
    ``RunningChromeVersion`` are touched. Returns one status text per file handled.
    """
    from je_web_runner.utils.chrome_profile.profile_manager import cleanup_chrome_locks
    return cleanup_chrome_locks(Path(profile_dir))


def chrome_profile_snapshot(profile_dir: str, snapshot_dir: str, full_copy: bool = False) -> str:
    """
    Copy a Chrome profile into a disposable snapshot directory, leaving out caches and lock files.

    An earlier snapshot in ``snapshot_dir`` is replaced; a non-empty directory that is not a profile
    snapshot is refused. ``full_copy`` keeps the caches too. Returns the snapshot's path.
    """
    from je_web_runner.utils.chrome_profile.profile_manager import snapshot_chrome_profile
    _check_snapshot_target(Path(profile_dir), Path(snapshot_dir))
    return str(snapshot_chrome_profile(Path(profile_dir), Path(snapshot_dir), full_copy=full_copy))


def chrome_profile_sync_back(snapshot_dir: str, profile_dir: str) -> list[str]:
    """
    Copy the login state (cookies, login data, preferences) from a snapshot back into the profile.

    Returns one ``copied ...`` / ``skipped ...`` status text per file.
    """
    from je_web_runner.utils.chrome_profile.profile_manager import sync_chrome_profile_back
    return sync_chrome_profile_back(Path(snapshot_dir), Path(profile_dir))


# ---------- download_verify ---------------------------------------------

def download_verify_wait(
    download_dir: str, pattern: str = r".+", timeout: float = 30.0,
    poll_interval: float = 0.5, stable_for: float = 0.5,
) -> str:
    """
    Wait for a finished download whose file name matches the regular expression ``pattern``.

    A file counts as finished when its size stayed the same for ``stable_for`` seconds; partial files
    (``.crdownload``, ``.part``, ``.tmp``) are skipped. Returns the file's absolute path.
    """
    from je_web_runner.utils.download_verify.verifier import wait_for_download
    return str(wait_for_download(
        download_dir, pattern=pattern, timeout=timeout, poll_interval=poll_interval, stable_for=stable_for,
    ))


def download_verify_sha256(path: str) -> str:
    """The SHA-256 of a downloaded file, as lower-case hex."""
    from je_web_runner.utils.download_verify.verifier import sha256_of_file
    return sha256_of_file(path)


def download_verify_read(path: str, kind: str | None = None, sheet: str | int | None = None) -> Any:
    """
    Read a downloaded CSV, JSON, PDF or Excel file as JSON values.

    ``kind`` is ``csv`` / ``json`` / ``pdf`` / ``xlsx`` (default: the file's extension). CSV and Excel give
    a list of row objects keyed by the header, PDF its text, JSON its content. ``sheet`` picks an Excel
    sheet by name or index. PDF needs ``pypdf`` or ``pdfplumber``, Excel ``openpyxl``.
    """
    from je_web_runner.utils.download_verify import verifier
    chosen = (kind or Path(path).suffix.lstrip(".")).lower()
    if chosen not in _DOWNLOAD_READERS:
        raise verifier.DownloadVerifyError(
            f"cannot read kind {chosen!r}; use one of {sorted(_DOWNLOAD_READERS)}"
        )
    reader = getattr(verifier, _DOWNLOAD_READERS[chosen])
    return to_plain(reader(path, sheet=sheet) if chosen == "xlsx" else reader(path))


def download_verify_assert(path: str, checks: dict[str, Any]) -> bool:
    """
    Fail unless a downloaded file passes every check given.

    ``checks`` takes ``filename_pattern`` (regular expression), ``min_size_bytes``, ``max_size_bytes``,
    ``sha256``, ``pdf_contains``, ``csv_columns`` (list) and ``json_schema``
    (``{"key": "str" | "int" | "float" | "bool" | "list" | "dict" | "any" | {nested}}``).
    """
    from je_web_runner.utils.download_verify import verifier
    assertion = _build(verifier.DownloadAssertion, checks, verifier.DownloadVerifyError)
    verifier.assert_download(path, assertion)
    return True


def download_verify_assert_csv_rows(path: str, minimum: int | None = None, maximum: int | None = None) -> int:
    """Fail unless a downloaded CSV has between ``minimum`` and ``maximum`` data rows; returns the count."""
    from je_web_runner.utils.download_verify.verifier import assert_csv_row_count
    return assert_csv_row_count(path, minimum=minimum, maximum=maximum)


INFRA_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_adaptive_retry_decide": adaptive_retry_decide,
    "WR_adaptive_retry_assert_retryable": adaptive_retry_assert_retryable,
    "WR_adaptive_retry_backoff": adaptive_retry_backoff,
    "WR_process_supervisor_list_orphans": process_supervisor_list_orphans,
    "WR_smart_wait_install_hooks": smart_wait_install_hooks,
    "WR_smart_wait_fetch_idle": smart_wait_fetch_idle,
    "WR_smart_wait_route_stable": smart_wait_route_stable,
    "WR_throttler_configure": throttler_configure,
    "WR_throttler_acquire": throttler_acquire,
    "WR_throttler_release": throttler_release,
    "WR_throttler_reset": throttler_reset,
    "WR_chaos_hooks_fault_types": chaos_hooks_fault_types,
    "WR_chaos_hooks_plan": chaos_hooks_plan,
    "WR_flag_matrix_build": flag_matrix_build,
    "WR_flag_matrix_summarise": flag_matrix_summarise,
    "WR_flag_matrix_assert_all_passed": flag_matrix_assert_all_passed,
    "WR_persona_runner_summarise": persona_runner_summarise,
    "WR_persona_runner_assert_all_passed": persona_runner_assert_all_passed,
    "WR_chrome_profile_options": chrome_profile_options,
    "WR_chrome_profile_cleanup_locks": chrome_profile_cleanup_locks,
    "WR_chrome_profile_snapshot": chrome_profile_snapshot,
    "WR_chrome_profile_sync_back": chrome_profile_sync_back,
    "WR_download_verify_wait": download_verify_wait,
    "WR_download_verify_sha256": download_verify_sha256,
    "WR_download_verify_read": download_verify_read,
    "WR_download_verify_assert": download_verify_assert,
    "WR_download_verify_assert_csv_rows": download_verify_assert_csv_rows,
}

PYTHON_ONLY: dict[str, str] = {
    "browser_pool": (
        "The pool hands out live browser objects built by a caller-supplied factory, health check and "
        "destructor; none of that can be given or returned as JSON."
    ),
    "db_snapshot": (
        "Savepoints go through a caller-implemented database backend object; the only built-in backend is "
        "the in-memory one that exists to unit-test the workflow."
    ),
}

NETWORK_COMMANDS: frozenset[str] = frozenset()
