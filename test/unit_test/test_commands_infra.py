"""Tests for the run-infrastructure command adapters (``_commands_infra`` and ``_commands_infra_2``)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.adaptive_retry.policy import AdaptiveRetryError
from je_web_runner.utils.chaos_hooks.chaos import ChaosHooksError
from je_web_runner.utils.chrome_profile.profile_manager import ChromeProfileError
from je_web_runner.utils.download_verify.verifier import DownloadVerifyError
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException
from je_web_runner.utils.executor import _commands_infra as infra
from je_web_runner.utils.executor import _commands_infra_2 as infra_2
from je_web_runner.utils.flag_matrix.matrix import FlagMatrixError
from je_web_runner.utils.persona_runner.runner import PersonaRunnerError
from je_web_runner.utils.process_supervisor.supervisor import OrphanFinding
from je_web_runner.utils.smart_wait.smart_wait import SmartWaitError
from je_web_runner.utils.throttler.throttler import ThrottlerError

ASSIGNED_PACKAGES = {
    "adaptive_retry",
    "browser_pool",
    "process_supervisor",
    "smart_wait",
    "throttler",
    "chaos_hooks",
    "db_snapshot",
    "flag_matrix",
    "persona_runner",
    "chrome_profile",
    "download_verify",
    "locator_health",
    "coverage_map",
    "driver_pin",
    "fanout",
    "impact_analysis",
    "k8s_runner",
    "pipeline",
    "synthetic_monitoring",
    "watch_mode",
    "workspace_lock",
    "live_dashboard",
    "session_to_test",
}

MODULES = (
    (infra.INFRA_COMMANDS, infra.PYTHON_ONLY, infra.NETWORK_COMMANDS),
    (infra_2.INFRA_2_COMMANDS, infra_2.PYTHON_ONLY, infra_2.NETWORK_COMMANDS),
)


def _write_json(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _package_of(command: str) -> str | None:
    matches = [name for name in ASSIGNED_PACKAGES if command.startswith(f"WR_{name}_")]
    return max(matches, key=len) if matches else None


@pytest.fixture(name="actions_dir")
def _actions_dir(tmp_path: Path) -> Path:
    """Two action files: a login flow with a weak XPath, and a checkout flow."""
    directory = tmp_path / "actions"
    _write_json(
        directory / "login.json",
        [
            ["WR_to_url", {"url": "https://shop.example/login"}],
            ["WR_SaveTestObject", {"test_object_name": "//*[@id='login-button']", "object_type": "XPATH"}],
            ["WR_SaveTestObject", {"test_object_name": "user-name", "object_type": "ID"}],
        ],
    )
    _write_json(
        directory / "checkout.json",
        [
            ["WR_to_url", {"url": "https://shop.example/orders/42/checkout?step=1"}],
            ["WR_SaveTestObject", {"test_object_name": "pay-now", "object_type": "ID"}],
        ],
    )
    return directory


# ---------- module tables -----------------------------------------------


def test_tables_are_consistent():
    covered: set[str] = set()
    for commands, python_only, network in MODULES:
        assert set(network) <= set(commands)
        assert not set(python_only) - ASSIGNED_PACKAGES
        covered |= set(python_only)
        for name, function in commands.items():
            package = _package_of(name)
            assert package is not None, name
            assert name == name.lower().replace("wr_", "WR_", 1), name
            assert (function.__doc__ or "").strip(), name
            covered.add(package)
        assert all(reason.strip().endswith(".") for reason in python_only.values())
    assert covered == ASSIGNED_PACKAGES
    assert not set(infra.INFRA_COMMANDS) & set(infra_2.INFRA_2_COMMANDS)
    assert infra_2.NETWORK_COMMANDS == frozenset({"WR_driver_pin_install"})


# ---------- adaptive_retry ----------------------------------------------


def test_adaptive_retry_decide_classifies_and_budgets():
    decide = infra.INFRA_COMMANDS["WR_adaptive_retry_decide"]
    transient = decide("TimeoutError('page load')", attempt=2)
    assert transient == {"attempt": 2, "category": "transient", "will_retry": True, "sleep_seconds": 0.5}
    assert json.loads(json.dumps(transient)) == transient
    real = decide("AssertionError('total was 3')")
    assert (real["category"], real["will_retry"], real["sleep_seconds"]) == ("real", False, 0.0)
    assert decide("TimeoutError()", attempt=2, policy={"transient_max": 1})["will_retry"] is False


def test_adaptive_retry_decide_rejects_unknown_policy_field():
    with pytest.raises(AdaptiveRetryError):
        infra.adaptive_retry_decide("TimeoutError()", policy={"retries": 3})


def test_adaptive_retry_assert_retryable():
    check = infra.INFRA_COMMANDS["WR_adaptive_retry_assert_retryable"]
    assert check("503 Service Unavailable")["category"] == "transient"
    with pytest.raises(AdaptiveRetryError):
        check("AssertionError('wrong title')")
    with pytest.raises(AdaptiveRetryError):
        check("503 Service Unavailable", attempt=4)


def test_adaptive_retry_backoff():
    backoff = infra.INFRA_COMMANDS["WR_adaptive_retry_backoff"]
    assert backoff(attempts=6) == [0.25, 0.5, 1.0, 2.0, 4.0, 4.0]
    assert backoff(attempts=3, policy={"base_backoff": 1, "max_backoff": 2}) == [1, 2, 2]


# ---------- process_supervisor ------------------------------------------


def test_process_supervisor_list_orphans_filters_driver_names():
    processes = [
        OrphanFinding(pid=11, name="chromedriver.exe", command_line="chromedriver.exe --port=1"),
        OrphanFinding(pid=12, name="explorer.exe"),
        OrphanFinding(pid=13, name="GeckoDriver"),
    ]
    target = "je_web_runner.utils.process_supervisor.supervisor.default_lister"
    with patch(target, return_value=processes):
        found = infra.INFRA_COMMANDS["WR_process_supervisor_list_orphans"]()
        only_gecko = infra.process_supervisor_list_orphans(names=["geckodriver"])
    assert found == [
        {"pid": 11, "name": "chromedriver.exe", "command_line": "chromedriver.exe --port=1"},
        {"pid": 13, "name": "GeckoDriver", "command_line": ""},
    ]
    assert json.dumps(found)
    assert [row["pid"] for row in only_gecko] == [13]


# ---------- smart_wait --------------------------------------------------


def _driver_answering(in_flight: int, last_route_change: int) -> MagicMock:
    def execute_script(script: str, *_args: object) -> object:
        answers = {
            "return (window.__wrWaitDocument || 0);": 1,
            "return (window.__wrFetchInflight || 0);": in_flight,
            "return (window.__wrLastRouteChange || 0);": last_route_change,
            "return Date.now();": 10_000,
        }
        return answers.get(script)

    driver = MagicMock()
    driver.execute_script.side_effect = execute_script
    return driver


def test_smart_wait_install_hooks_runs_the_two_fixed_scripts():
    driver = _driver_answering(0, 0)
    with patch.object(infra, "selenium_driver", return_value=driver) as lookup:
        assert infra.INFRA_COMMANDS["WR_smart_wait_install_hooks"]() is True
    lookup.assert_called_once_with("WR_smart_wait_install_hooks")
    scripts = [call.args[0] for call in driver.execute_script.call_args_list]
    assert len(scripts) == 2
    assert "__wrFetchHook" in scripts[0] and "__wrHistoryHook" in scripts[1]


def test_smart_wait_fetch_idle_passes_and_times_out():
    wait = infra.INFRA_COMMANDS["WR_smart_wait_fetch_idle"]
    with patch.object(infra, "selenium_driver", return_value=_driver_answering(0, 0)):
        assert wait(quiet_for=0.0, timeout=2.0, poll=0.01) is True
    with patch.object(infra, "selenium_driver", return_value=_driver_answering(2, 0)):
        with pytest.raises(SmartWaitError):
            wait(quiet_for=0.0, timeout=0.05, poll=0.01)


def test_smart_wait_route_stable_passes_and_times_out():
    wait = infra.INFRA_COMMANDS["WR_smart_wait_route_stable"]
    with patch.object(infra, "selenium_driver", return_value=_driver_answering(0, 1_000)):
        assert wait(quiet_for=0.4, timeout=2.0, poll=0.01) is True
    with patch.object(infra, "selenium_driver", return_value=_driver_answering(0, 9_990)):
        with pytest.raises(SmartWaitError):
            wait(quiet_for=0.4, timeout=0.05, poll=0.01)


def test_smart_wait_needs_a_browser():
    target = "je_web_runner.utils.executor._command_helpers.webdriver_wrapper_instance"
    with patch(target) as wrapper:
        wrapper.current_webdriver = None
        with pytest.raises(WebRunnerWebDriverIsNoneException):
            infra.smart_wait_fetch_idle()


# ---------- throttler ---------------------------------------------------


@pytest.fixture(name="throttle_dir")
def _throttle_dir(tmp_path: Path):
    infra.throttler_reset()
    yield tmp_path / "throttle"
    infra.throttler_reset()


def test_throttler_configure_acquire_release(throttle_dir: Path):
    commands = infra.INFRA_COMMANDS
    configured = commands["WR_throttler_configure"]("payments", 1, base_dir=str(throttle_dir))
    assert configured == {"name": "payments", "capacity": 1, "base_dir": str(throttle_dir)}
    slot = commands["WR_throttler_acquire"]("payments", timeout=1.0)
    assert Path(slot) == throttle_dir / "payments" / "slot-0.lock"
    assert Path(slot).is_file()
    assert json.dumps(slot)
    with pytest.raises(ThrottlerError):
        commands["WR_throttler_acquire"]("payments", timeout=0.0)
    assert commands["WR_throttler_release"]("payments", slot) is True
    assert not Path(slot).exists()
    assert commands["WR_throttler_acquire"]("payments", timeout=1.0) == slot


def test_throttler_release_refuses_other_files(throttle_dir: Path):
    infra.throttler_configure("search", 2, base_dir=str(throttle_dir))
    outsider = throttle_dir / "notes.txt"
    outsider.parent.mkdir(parents=True, exist_ok=True)
    outsider.write_text("keep me", encoding="utf-8")
    with pytest.raises(ThrottlerError):
        infra.throttler_release("search", str(outsider))
    with pytest.raises(ThrottlerError):
        infra.throttler_release("search", str(throttle_dir / "search" / "slot-0.lock.bak"))
    assert outsider.read_text(encoding="utf-8") == "keep me"


def test_throttler_reset_forgets_services(throttle_dir: Path):
    infra.throttler_configure("search", 2, base_dir=str(throttle_dir))
    assert infra.INFRA_COMMANDS["WR_throttler_reset"]() is True
    with pytest.raises(ThrottlerError):
        infra.throttler_acquire("search", timeout=0.0)
    with pytest.raises(ThrottlerError):
        infra.throttler_configure("search", 0)


# ---------- chaos_hooks -------------------------------------------------


def test_chaos_hooks_fault_types():
    faults = infra.INFRA_COMMANDS["WR_chaos_hooks_fault_types"]()
    assert "network_offline" in faults and "mid_flow_reload" in faults


def test_chaos_hooks_plan_is_seeded_and_plain():
    plan_chaos = infra.INFRA_COMMANDS["WR_chaos_hooks_plan"]
    steps = ["open", "login", "search", "add to cart", "pay"]
    plan = plan_chaos(steps, faults=["network_offline"], fault_rate=1.0, skip_last=1, seed=7)
    assert plan["events"] == [
        {"step_index": index, "step_name": steps[index], "fault": "network_offline"} for index in (1, 2, 3)
    ]
    assert plan["skipped"] == [0, 4]
    assert plan["seed"] == 7
    assert plan["description"].startswith("step 1 (login): network_offline")
    assert json.loads(json.dumps(plan)) == plan
    assert plan_chaos(steps, seed=3) == plan_chaos(steps, seed=3)
    assert plan_chaos(steps, fault_rate=0.0)["description"] == "no chaos planned"


def test_chaos_hooks_plan_rejects_bad_input():
    with pytest.raises(ChaosHooksError):
        infra.chaos_hooks_plan(["a", "b"], faults=["meteor_strike"])
    with pytest.raises(ChaosHooksError):
        infra.chaos_hooks_plan(["a", "b"], fault_rate=1.5)


# ---------- flag_matrix -------------------------------------------------


def test_flag_matrix_build_applies_constraints_and_pins():
    build = infra.INFRA_COMMANDS["WR_flag_matrix_build"]
    flags = {"checkout": ["v1", "v2"], "dark_mode": [True, False]}
    matrix = build(
        flags,
        forbid=[[["checkout", "v2"], ["dark_mode", True]]],
        pinned=[{"checkout": "v1", "dark_mode": False}],
    )
    assert matrix["combos"][0] == {"checkout": "v1", "dark_mode": False}
    assert {"checkout": "v2", "dark_mode": True} not in matrix["combos"]
    assert (matrix["total_possible"], matrix["pinned_count"], matrix["constrained_out"]) == (4, 1, 1)
    assert len(matrix["combos"]) == 3
    assert json.loads(json.dumps(matrix)) == matrix
    required = build(flags, require=[[["checkout", "v2"], ["dark_mode", False]]], sample_size=2, seed=1)
    assert required["sampled"] is True and len(required["combos"]) == 2


def test_flag_matrix_build_rejects_bad_input():
    with pytest.raises(FlagMatrixError):
        infra.flag_matrix_build({"checkout": ["v1"]}, forbid=[["checkout", "v1"]])
    with pytest.raises(FlagMatrixError):
        infra.flag_matrix_build({"checkout": []})


FLAG_RESULTS = [
    {"combo": {"checkout": "v1", "dark_mode": True}, "passed": True, "duration_seconds": 2.0},
    {"combo": {"checkout": "v2", "dark_mode": True}, "passed": False, "error": "pay button missing"},
    {"combo": {"checkout": "v2", "dark_mode": False}, "passed": False, "duration_seconds": 1.0},
]


def test_flag_matrix_summarise():
    summary = infra.INFRA_COMMANDS["WR_flag_matrix_summarise"](FLAG_RESULTS)
    assert (summary["total"], summary["passed"], summary["failed"]) == (3, 1, 2)
    assert summary["average_seconds"] == 1.0
    assert summary["smallest_failing_subset"] == ["checkout='v2'"]
    assert summary["failures"][0]["error"] == "pay button missing"
    assert json.dumps(summary)
    with pytest.raises(FlagMatrixError):
        infra.flag_matrix_summarise([{"combo": {}, "ok": True}])


def test_flag_matrix_assert_all_passed():
    check = infra.INFRA_COMMANDS["WR_flag_matrix_assert_all_passed"]
    assert check(FLAG_RESULTS[:1])["failed"] == 0
    with pytest.raises(FlagMatrixError, match="checkout='v2'"):
        check(FLAG_RESULTS)


# ---------- persona_runner ----------------------------------------------

PERSONA_RESULTS = [
    {"persona": "admin", "action_file": "billing.json", "passed": True},
    {"persona": "guest", "action_file": "billing.json", "passed": False, "error": "403"},
    {"persona": "admin", "action_file": "search.json", "passed": True, "duration_seconds": 1.5},
    {"persona": "guest", "action_file": "search.json", "passed": True},
]


def test_persona_runner_summarise():
    summary = infra.INFRA_COMMANDS["WR_persona_runner_summarise"](PERSONA_RESULTS)
    assert (summary["total"], summary["passed"], summary["failed"]) == (4, 3, 1)
    assert summary["by_persona"]["guest"] == {"passed": 1, "failed": 1}
    assert summary["persona_only_failures"] == ["guest"]
    assert summary["file_only_failures"] == []
    assert "| guest | 1 | 1 |" in summary["markdown"]
    assert json.dumps(summary)
    with pytest.raises(PersonaRunnerError):
        infra.persona_runner_summarise([{"persona": "admin", "file": "x.json", "passed": True}])


def test_persona_runner_assert_all_passed():
    check = infra.INFRA_COMMANDS["WR_persona_runner_assert_all_passed"]
    assert check([row for row in PERSONA_RESULTS if row["passed"]])["failed"] == 0
    with pytest.raises(PersonaRunnerError, match="guest"):
        check(PERSONA_RESULTS)


# ---------- chrome_profile ----------------------------------------------


@pytest.fixture(name="profile_dir")
def _profile_dir(tmp_path: Path) -> Path:
    profile = tmp_path / "profile"
    (profile / "Default" / "Cache").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("cookie-db", encoding="utf-8")
    (profile / "Default" / "Cache" / "blob").write_text("cached", encoding="utf-8")
    (profile / "Local State").write_text("{}", encoding="utf-8")
    (profile / "SingletonLock").write_text("", encoding="utf-8")
    return profile


def test_chrome_profile_options(tmp_path: Path):
    profile = tmp_path / "new-profile"
    options = infra.INFRA_COMMANDS["WR_chrome_profile_options"](
        str(profile),
        flags={"headless": True, "window_size": [1280, 720], "extra_args": ["--mute-audio"]},
    )
    assert "--headless=new" in options["arguments"]
    assert "--window-size=1280,720" in options["arguments"]
    assert f"--user-data-dir={profile}" in options["arguments"]
    assert "--mute-audio" in options["arguments"]
    assert options["experimental_options"]["excludeSwitches"] == ["enable-automation"]
    assert json.dumps(options)
    assert profile.is_dir()
    with pytest.raises(ChromeProfileError):
        infra.chrome_profile_options(str(profile), flags={"stealth_level": 9})


def test_chrome_profile_cleanup_locks(profile_dir: Path):
    statuses = infra.INFRA_COMMANDS["WR_chrome_profile_cleanup_locks"](str(profile_dir))
    assert statuses == ["removed SingletonLock"]
    assert not (profile_dir / "SingletonLock").exists()
    assert (profile_dir / "Default" / "Cookies").is_file()
    assert infra.chrome_profile_cleanup_locks(str(profile_dir)) == []


def test_chrome_profile_snapshot_and_sync_back(profile_dir: Path, tmp_path: Path):
    snapshot_dir = tmp_path / "profile_snap"
    snapshot = infra.INFRA_COMMANDS["WR_chrome_profile_snapshot"](str(profile_dir), str(snapshot_dir))
    assert snapshot == str(snapshot_dir)
    assert (snapshot_dir / "Default" / "Cookies").read_text(encoding="utf-8") == "cookie-db"
    assert not (snapshot_dir / "Default" / "Cache").exists()
    assert not (snapshot_dir / "SingletonLock").exists()
    assert infra.chrome_profile_snapshot(str(profile_dir), str(snapshot_dir), full_copy=True) == snapshot
    assert (snapshot_dir / "Default" / "Cache" / "blob").is_file()

    (snapshot_dir / "Default" / "Cookies").write_text("fresh-login", encoding="utf-8")
    statuses = infra.INFRA_COMMANDS["WR_chrome_profile_sync_back"](str(snapshot_dir), str(profile_dir))
    assert "copied Default/Cookies" in statuses and "copied Local State" in statuses
    assert json.dumps(statuses)
    assert (profile_dir / "Default" / "Cookies").read_text(encoding="utf-8") == "fresh-login"


def test_chrome_profile_snapshot_refuses_unsafe_targets(profile_dir: Path, tmp_path: Path):
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "thesis.txt").write_text("irreplaceable", encoding="utf-8")
    with pytest.raises(ChromeProfileError):
        infra.chrome_profile_snapshot(str(profile_dir), str(documents))
    with pytest.raises(ChromeProfileError):
        infra.chrome_profile_snapshot(str(profile_dir), str(tmp_path))
    with pytest.raises(ChromeProfileError):
        infra.chrome_profile_snapshot(str(profile_dir), str(profile_dir))
    assert (documents / "thesis.txt").read_text(encoding="utf-8") == "irreplaceable"
    with pytest.raises(ChromeProfileError):
        infra.chrome_profile_sync_back(str(tmp_path / "missing"), str(profile_dir))


# ---------- download_verify ---------------------------------------------


@pytest.fixture(name="downloads")
def _downloads(tmp_path: Path) -> Path:
    directory = tmp_path / "downloads"
    directory.mkdir()
    (directory / "orders.csv").write_text("id,total\n1,9.50\n2,12.00\n", encoding="utf-8")
    (directory / "report.json").write_text('{"name": "Q3", "rows": [1, 2]}', encoding="utf-8")
    (directory / "video.mp4.crdownload").write_text("partial", encoding="utf-8")
    return directory


def test_download_verify_wait(downloads: Path):
    wait = infra.INFRA_COMMANDS["WR_download_verify_wait"]
    found = wait(str(downloads), pattern=r"\.csv$", timeout=5.0, poll_interval=0.01, stable_for=0.0)
    assert found == str((downloads / "orders.csv").resolve())
    assert json.dumps(found)
    with pytest.raises(DownloadVerifyError):
        wait(str(downloads), pattern=r"\.mp4", timeout=0.05, poll_interval=0.01, stable_for=0.0)


def test_download_verify_sha256(downloads: Path):
    expected = hashlib.sha256((downloads / "orders.csv").read_bytes()).hexdigest()
    assert infra.INFRA_COMMANDS["WR_download_verify_sha256"](str(downloads / "orders.csv")) == expected
    with pytest.raises(DownloadVerifyError):
        infra.download_verify_sha256(str(downloads / "missing.bin"))


PIN = {
    "name": "chromedriver",
    "version": "131.0.1",
    "url": "https://drivers.example/chromedriver.zip",
    "archive_format": "zip",
    "binary_inside": "chromedriver.exe",
}

SHARD_CONFIG = {
    "name_prefix": "nightly",
    "image": "registry.example/webrunner:1.2",
    "total_shards": 2,
    "actions_dir": "/work/actions",
    "namespace": "qa",
    "env": {"BASE_URL": "https://staging.example"},
}

PIPELINE = {
    "stages": [
        {"name": "lint", "files": ["actions/*.json"], "continue_on_failure": True},
        {"name": "smoke", "files": ["actions/smoke/*.json"]},
    ]
}


@pytest.fixture(name="ledger")
def _ledger(tmp_path: Path) -> str:
    return _write_json(
        tmp_path / "ledger.json",
        {
            "runs": [
                {"path": "login.json", "passed": True, "time": "2026-11-14T09:00:00"},
                {"path": "login.json", "passed": False, "time": "2026-11-15T09:00:00"},
                {"path": "pay.json", "passed": True, "time": "2026-11-15T09:05:00"},
                {"path": "pay.json", "passed": True, "time": "2026-11-15T10:05:00"},
            ]
        },
    )


GENERIC_EVENTS = [
    {"kind": "navigate", "url": "https://shop.example/login"},
    {"kind": "input", "target": "#user", "value": "alice"},
    {"kind": "click", "target": {"by": "id", "value": "submit"}},
    {"kind": "hover", "target": "#menu"},
]
