"""Tests for the run-infrastructure command adapters (``_commands_infra`` and ``_commands_infra_2``)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.coverage_map.coverage import CoverageMapError
from je_web_runner.utils.download_verify.verifier import DownloadVerifyError
from je_web_runner.utils.driver_pin.pinner import DriverPinError
from je_web_runner.utils.executor import _commands_infra as infra
from je_web_runner.utils.executor import _commands_infra_2 as infra_2
from je_web_runner.utils.impact_analysis.indexer import ImpactAnalysisError
from je_web_runner.utils.k8s_runner.manifest import K8sRunnerError
from je_web_runner.utils.locator_health.health_report import LocatorHealthError
from je_web_runner.utils.pipeline.pipeline import PipelineError
from je_web_runner.utils.session_to_test.converter import SessionToTestError
from je_web_runner.utils.watch_mode.watcher import WatchModeError
from je_web_runner.utils.workspace_lock.lock import WorkspaceLockError

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


@pytest.fixture(name="throttle_dir")
def _throttle_dir(tmp_path: Path):
    infra.throttler_reset()
    yield tmp_path / "throttle"
    infra.throttler_reset()


FLAG_RESULTS = [
    {"combo": {"checkout": "v1", "dark_mode": True}, "passed": True, "duration_seconds": 2.0},
    {"combo": {"checkout": "v2", "dark_mode": True}, "passed": False, "error": "pay button missing"},
    {"combo": {"checkout": "v2", "dark_mode": False}, "passed": False, "duration_seconds": 1.0},
]

PERSONA_RESULTS = [
    {"persona": "admin", "action_file": "billing.json", "passed": True},
    {"persona": "guest", "action_file": "billing.json", "passed": False, "error": "403"},
    {"persona": "admin", "action_file": "search.json", "passed": True, "duration_seconds": 1.5},
    {"persona": "guest", "action_file": "search.json", "passed": True},
]


@pytest.fixture(name="profile_dir")
def _profile_dir(tmp_path: Path) -> Path:
    profile = tmp_path / "profile"
    (profile / "Default" / "Cache").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("cookie-db", encoding="utf-8")
    (profile / "Default" / "Cache" / "blob").write_text("cached", encoding="utf-8")
    (profile / "Local State").write_text("{}", encoding="utf-8")
    (profile / "SingletonLock").write_text("", encoding="utf-8")
    return profile


@pytest.fixture(name="downloads")
def _downloads(tmp_path: Path) -> Path:
    directory = tmp_path / "downloads"
    directory.mkdir()
    (directory / "orders.csv").write_text("id,total\n1,9.50\n2,12.00\n", encoding="utf-8")
    (directory / "report.json").write_text('{"name": "Q3", "rows": [1, 2]}', encoding="utf-8")
    (directory / "video.mp4.crdownload").write_text("partial", encoding="utf-8")
    return directory


def test_download_verify_read(downloads: Path):
    read = infra.INFRA_COMMANDS["WR_download_verify_read"]
    assert read(str(downloads / "orders.csv")) == [{"id": "1", "total": "9.50"}, {"id": "2", "total": "12.00"}]
    assert read(str(downloads / "report.json")) == {"name": "Q3", "rows": [1, 2]}
    renamed = downloads / "export.dat"
    renamed.write_text("id\n7\n", encoding="utf-8")
    assert read(str(renamed), kind="CSV") == [{"id": "7"}]
    with pytest.raises(DownloadVerifyError):
        read(str(downloads / "video.mp4.crdownload"))


def test_download_verify_assert(downloads: Path):
    check = infra.INFRA_COMMANDS["WR_download_verify_assert"]
    csv_path = str(downloads / "orders.csv")
    digest = hashlib.sha256((downloads / "orders.csv").read_bytes()).hexdigest()
    assert (
        check(
            csv_path,
            {
                "filename_pattern": r"^orders\.csv$",
                "min_size_bytes": 10,
                "sha256": digest,
                "csv_columns": ["id", "total"],
            },
        )
        is True
    )
    assert check(str(downloads / "report.json"), {"json_schema": {"name": "str", "rows": "list"}}) is True
    with pytest.raises(DownloadVerifyError):
        check(csv_path, {"csv_columns": ["id", "currency"]})
    with pytest.raises(DownloadVerifyError):
        check(csv_path, {"max_size_bytes": 3})
    with pytest.raises(DownloadVerifyError):
        check(csv_path, {"md5": "abc"})


def test_download_verify_assert_csv_rows(downloads: Path):
    count = infra.INFRA_COMMANDS["WR_download_verify_assert_csv_rows"]
    assert count(str(downloads / "orders.csv"), minimum=2, maximum=2) == 2
    with pytest.raises(DownloadVerifyError):
        count(str(downloads / "orders.csv"), minimum=3)


# ---------- locator_health ----------------------------------------------


def test_locator_health_scan_file_and_directory(actions_dir: Path):
    scan = infra_2.INFRA_2_COMMANDS["WR_locator_health_scan"]
    project = scan(str(actions_dir))
    assert project["total"] == 3
    assert project["weak"] + project["strong"] == 3
    assert project["weakest"][0]["strategy"] == "XPATH"
    assert json.loads(json.dumps(project)) == project
    single = scan(str(actions_dir / "checkout.json"))
    assert [finding["value"] for finding in single["findings"]] == ["pay-now"]
    with pytest.raises(LocatorHealthError):
        scan(str(actions_dir / "missing.json"))


def test_locator_health_markdown(actions_dir: Path):
    text = infra_2.INFRA_2_COMMANDS["WR_locator_health_markdown"](str(actions_dir))
    assert text.startswith("## Locator health report")
    assert "- **Total locators:** 3" in text


def test_locator_health_suggest(actions_dir: Path):
    suggest = infra_2.INFRA_2_COMMANDS["WR_locator_health_suggest"]
    suggestions = suggest(str(actions_dir))
    assert len(suggestions) == 1
    assert (suggestions[0]["to_strategy"], suggestions[0]["to_value"]) == ("ID", "login-button")
    assert suggestions[0]["file_path"].endswith("login.json")
    assert json.dumps(suggestions)
    assert suggest(str(actions_dir), only_below=0) == []


def test_locator_health_assert(actions_dir: Path):
    check = infra_2.INFRA_2_COMMANDS["WR_locator_health_assert"]
    assert check(str(actions_dir), threshold=0)["weak"] == 0
    with pytest.raises(LocatorHealthError):
        check(str(actions_dir), threshold=101)
    assert check(str(actions_dir), threshold=101, max_weak=3)["weak"] == 3


# ---------- coverage_map ------------------------------------------------


def test_coverage_map_build(actions_dir: Path):
    coverage = infra_2.INFRA_2_COMMANDS["WR_coverage_map_build"](str(actions_dir))
    assert sorted(coverage["files_by_route"]) == ["/login", "/orders/:id/checkout"]
    assert coverage["files_by_route"]["/login"] == [str(actions_dir / "login.json")]
    assert coverage["routes_by_file"][str(actions_dir / "checkout.json")] == ["/orders/:id/checkout"]
    assert json.loads(json.dumps(coverage)) == coverage
    raw = infra_2.coverage_map_build(str(actions_dir), normalise_params=False)
    assert "/orders/42/checkout" in raw["files_by_route"]
    with pytest.raises(CoverageMapError):
        infra_2.coverage_map_build(str(actions_dir / "nope"))


def test_coverage_map_uncovered_and_markdown(actions_dir: Path):
    uncovered = infra_2.INFRA_2_COMMANDS["WR_coverage_map_uncovered"]
    assert uncovered(str(actions_dir), ["/login", "/refunds", "/admin"]) == ["/admin", "/refunds"]
    markdown = infra_2.INFRA_2_COMMANDS["WR_coverage_map_markdown"]
    assert "| `/login` | 1 |" in markdown(str(actions_dir))
    assert "| `/refunds` | 0 | _uncovered_ |" in markdown(str(actions_dir), declared_routes=["/refunds"])


def test_coverage_map_assert_covered(actions_dir: Path):
    check = infra_2.INFRA_2_COMMANDS["WR_coverage_map_assert_covered"]
    assert check(str(actions_dir), ["/login"]) == {"/login": [str(actions_dir / "login.json")]}
    with pytest.raises(CoverageMapError, match="/refunds"):
        check(str(actions_dir), ["/login", "/refunds"])


# ---------- driver_pin --------------------------------------------------

PIN = {
    "name": "chromedriver",
    "version": "131.0.1",
    "url": "https://drivers.example/chromedriver.zip",
    "archive_format": "zip",
    "binary_inside": "chromedriver.exe",
}


def test_driver_pin_platform():
    marker = infra_2.INFRA_2_COMMANDS["WR_driver_pin_platform"]()
    assert marker in {"win", "mac-arm64", "mac-x64", "linux", "linux-arm64"}


def test_driver_pin_load(tmp_path: Path):
    load = infra_2.INFRA_2_COMMANDS["WR_driver_pin_load"]
    pin_file = _write_json(tmp_path / "drivers.json", {"drivers": [PIN, {**PIN, "platforms": ["plan9"]}]})
    pins = load(pin_file)
    assert pins[0]["version"] == "131.0.1" and pins[0]["matches_current_platform"] is True
    assert pins[1]["platforms"] == ["plan9"] and pins[1]["matches_current_platform"] is False
    assert json.dumps(pins)
    bad = _write_json(tmp_path / "bad.json", {"drivers": [{**PIN, "url": "ftp://drivers.example/x.zip"}]})
    with pytest.raises(DriverPinError):
        load(bad)


def test_driver_pin_install_uses_the_cache_without_network(tmp_path: Path):
    install = infra_2.INFRA_2_COMMANDS["WR_driver_pin_install"]
    pin_file = _write_json(tmp_path / "drivers.json", {"drivers": [PIN]})
    cache = tmp_path / "cache"
    binary = cache / "chromedriver" / "131.0.1" / "chromedriver.exe"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"MZ")
    with patch("urllib.request.urlopen", side_effect=AssertionError("no network in tests")):
        assert install(pin_file, "chrome", cache_dir=str(cache)) == str(binary)
        assert install(pin_file, "firefox", cache_dir=str(cache)) is None
    with pytest.raises(DriverPinError):
        install(str(tmp_path / "missing.json"), "chrome")


# ---------- impact_analysis ---------------------------------------------


def test_impact_analysis_index(actions_dir: Path, tmp_path: Path):
    build = infra_2.INFRA_2_COMMANDS["WR_impact_analysis_index"]
    cache = tmp_path / "cache" / "impact.json"
    index = build(str(actions_dir), cache_path=str(cache))
    assert index["by_locator"]["pay-now"] == [str(actions_dir / "checkout.json")]
    assert len(index["by_command"]["WR_to_url"]) == 2
    assert index["by_template"] == {}
    assert json.loads(json.dumps(index)) == index
    assert cache.is_file()
    assert build(str(actions_dir), cache_path=str(cache)) == index
    with pytest.raises(ImpactAnalysisError):
        build(str(actions_dir / "nope"))


def test_impact_analysis_affected(actions_dir: Path):
    affected = infra_2.INFRA_2_COMMANDS["WR_impact_analysis_affected"]
    assert affected(str(actions_dir), locators=["user-name"]) == [str(actions_dir / "login.json")]
    assert affected(str(actions_dir), urls=["/orders/"]) == [str(actions_dir / "checkout.json")]
    assert len(affected(str(actions_dir), commands=["WR_SaveTestObject"])) == 2
    assert affected(str(actions_dir)) == []


def test_impact_analysis_select(actions_dir: Path):
    select = infra_2.INFRA_2_COMMANDS["WR_impact_analysis_select"]
    files = [str(actions_dir / "login.json"), str(actions_dir / "checkout.json")]
    assert select(files, str(actions_dir), ["locator:pay-now"]) == files[1:]
    assert select(files, str(actions_dir), ["command:WR_to_url"]) == files
    with pytest.raises(ImpactAnalysisError):
        select(files, str(actions_dir), ["button:pay-now"])


# ---------- k8s_runner --------------------------------------------------

SHARD_CONFIG = {
    "name_prefix": "nightly",
    "image": "registry.example/webrunner:1.2",
    "total_shards": 2,
    "actions_dir": "/work/actions",
    "namespace": "qa",
    "env": {"BASE_URL": "https://staging.example"},
}


def test_k8s_runner_render_manifests():
    manifests = infra_2.INFRA_2_COMMANDS["WR_k8s_runner_render_manifests"](SHARD_CONFIG)
    assert [job["metadata"]["name"] for job in manifests] == ["nightly-shard-1-of-2", "nightly-shard-2-of-2"]
    container = manifests[1]["spec"]["template"]["spec"]["containers"][0]
    assert container["args"] == ["--execute_dir", "/work/actions", "--shard", "2/2"]
    assert container["env"] == [{"name": "BASE_URL", "value": "https://staging.example"}]
    assert manifests[0]["metadata"]["namespace"] == "qa"
    assert json.loads(json.dumps(manifests)) == manifests


def test_k8s_runner_render_yaml_and_bad_config():
    text = infra_2.INFRA_2_COMMANDS["WR_k8s_runner_render_yaml"](SHARD_CONFIG)
    assert text.count("kind: Job") == 2 and "\n---\n" in text
    with pytest.raises(K8sRunnerError):
        infra_2.k8s_runner_render_yaml({**SHARD_CONFIG, "name_prefix": "Nightly_Run"})
    with pytest.raises(K8sRunnerError):
        infra_2.k8s_runner_render_manifests({**SHARD_CONFIG, "replicas": 3})


# ---------- pipeline ----------------------------------------------------

PIPELINE = {
    "stages": [
        {"name": "lint", "files": ["actions/*.json"], "continue_on_failure": True},
        {"name": "smoke", "files": ["actions/smoke/*.json"]},
    ]
}


def test_pipeline_load_from_object_text_and_file(tmp_path: Path):
    load = infra_2.INFRA_2_COMMANDS["WR_pipeline_load"]
    loaded = load(PIPELINE)
    assert loaded["stages"][1] == {
        "name": "smoke",
        "files": ["actions/smoke/*.json"],
        "required_status": ["passed"],
        "continue_on_failure": False,
    }
    assert json.loads(json.dumps(loaded)) == loaded
    assert load(json.dumps(PIPELINE)) == loaded
    assert load(_write_json(tmp_path / "pipeline.json", PIPELINE)) == loaded
    with pytest.raises(PipelineError):
        load({"stages": [PIPELINE["stages"][0], PIPELINE["stages"][0]]})


def test_pipeline_assert_all_passed():
    check = infra_2.INFRA_2_COMMANDS["WR_pipeline_assert_all_passed"]
    passed = [{"stage_name": "lint", "status": "passed"}, {"stage_name": "smoke", "status": "passed"}]
    assert check(passed) == 2
    with pytest.raises(PipelineError, match="smoke"):
        check([passed[0], {"stage_name": "smoke", "status": "skipped", "error": "blocked"}])
    with pytest.raises(PipelineError):
        check([{"stage": "lint", "status": "passed"}])


# ---------- watch_mode --------------------------------------------------


def test_watch_mode_snapshot_and_diff(actions_dir: Path):
    snapshot = infra_2.INFRA_2_COMMANDS["WR_watch_mode_snapshot"]
    diff = infra_2.INFRA_2_COMMANDS["WR_watch_mode_diff"]
    before = json.loads(json.dumps(snapshot(str(actions_dir))))
    assert sorted(before) == [str(actions_dir / "checkout.json"), str(actions_dir / "login.json")]
    assert before[str(actions_dir / "login.json")][1] == (actions_dir / "login.json").stat().st_size
    assert diff(before, snapshot(str(actions_dir))) == {
        "added": [],
        "removed": [],
        "changed": [],
        "has_changes": False,
    }

    (actions_dir / "login.json").write_text("[]", encoding="utf-8")
    (actions_dir / "checkout.json").unlink()
    _write_json(actions_dir / "refund.json", [])
    changes = diff(before, snapshot(str(actions_dir)))
    assert changes == {
        "added": [str(actions_dir / "refund.json")],
        "removed": [str(actions_dir / "checkout.json")],
        "changed": [str(actions_dir / "login.json")],
        "has_changes": True,
    }
    assert json.dumps(changes)


def test_watch_mode_rejects_bad_input(actions_dir: Path):
    with pytest.raises(WatchModeError):
        infra_2.watch_mode_snapshot(str(actions_dir / "nope"))
    with pytest.raises(WatchModeError):
        infra_2.watch_mode_diff({"a.json": 12}, {})


# ---------- workspace_lock ----------------------------------------------


def test_workspace_lock_build():
    lock = infra_2.INFRA_2_COMMANDS["WR_workspace_lock_build"](
        drivers=[{"name": "chromedriver", "version": "131.0.1", "platform": "win"}],
        playwright_versions={"chromium": "1200"},
        allow_distributions=["selenium"],
    )
    kinds = {entry["name"]: entry["kind"] for entry in lock["entries"]}
    assert kinds == {"selenium": "python", "chromedriver": "driver", "chromium": "playwright"}
    assert lock["entries"][1]["extras"] == {"platform": "win"}
    assert lock["python_version"].count(".") == 2
    assert json.loads(json.dumps(lock)) == lock
    with pytest.raises(WorkspaceLockError):
        infra_2.workspace_lock_build(drivers=[{"name": "chromedriver"}])


def test_workspace_lock_write_diff_and_assert(tmp_path: Path):
    commands = infra_2.INFRA_2_COMMANDS
    current = commands["WR_workspace_lock_write"](
        str(tmp_path / "locks" / "now.json"),
        drivers=[{"name": "chromedriver", "version": "131.0.1"}],
        allow_distributions=["selenium", "requests"],
    )
    assert current == str(tmp_path / "locks" / "now.json")
    document = json.loads(Path(current).read_text(encoding="utf-8"))
    assert commands["WR_workspace_lock_assert_current"](current) == {
        "python_version": document["python_version"],
        "checked": 2,
    }

    for entry in document["entries"]:
        if entry["name"] == "selenium":
            entry["version"] = "0.0.1"
    document["entries"].append({"name": "left-pad", "version": "1.0", "kind": "python"})
    stale = _write_json(tmp_path / "locks" / "stale.json", document)
    changes = commands["WR_workspace_lock_diff"](stale, current)
    assert [row["name"] for row in changes["removed"]] == ["left-pad"]
    assert changes["version_changed"][0]["from"] == "0.0.1"
    assert changes["added"] == []
    assert json.dumps(changes)
    with pytest.raises(WorkspaceLockError, match="left-pad"):
        commands["WR_workspace_lock_assert_current"](stale)


def test_workspace_lock_assert_current_python_version(tmp_path: Path):
    lock_file = _write_json(tmp_path / "old.json", {"python_version": "2.7.18", "entries": []})
    with pytest.raises(WorkspaceLockError, match="2.7.18"):
        infra_2.workspace_lock_assert_current(lock_file)
    assert infra_2.workspace_lock_assert_current(lock_file, check_python_version=False)["checked"] == 0
    with pytest.raises(WorkspaceLockError):
        infra_2.workspace_lock_diff(lock_file, str(tmp_path / "missing.json"))


# ---------- live_dashboard ----------------------------------------------


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


def test_live_dashboard_summary(ledger: str, tmp_path: Path):
    summary = infra_2.INFRA_2_COMMANDS["WR_live_dashboard_summary"]
    locators = _write_json(tmp_path / "locators.json", {"weak": 4, "average_score": 71.5})
    counts = summary(ledger_path=ledger, locator_findings_path=locators)
    assert (counts["total_runs"], counts["passed"], counts["failed"]) == (4, 3, 1)
    assert counts["pass_rate"] == 0.75
    assert (counts["weak_locators"], counts["average_locator_score"]) == (4, 71.5)
    assert counts["quarantined_tests"] == 0
    assert json.loads(json.dumps(counts)) == counts
    assert summary()["total_runs"] == 0


def test_live_dashboard_trend(ledger: str, tmp_path: Path):
    trend = infra_2.INFRA_2_COMMANDS["WR_live_dashboard_trend"]
    result = trend(ledger)
    assert len(result["daily"]) == 2
    assert json.loads(json.dumps(result)) == result
    assert trend(str(tmp_path / "missing.json"))["daily"] == []


# ---------- session_to_test ---------------------------------------------

GENERIC_EVENTS = [
    {"kind": "navigate", "url": "https://shop.example/login"},
    {"kind": "input", "target": "#user", "value": "alice"},
    {"kind": "click", "target": {"by": "id", "value": "submit"}},
    {"kind": "hover", "target": "#menu"},
]


def test_session_to_test_convert_generic_and_rrweb(tmp_path: Path):
    convert = infra_2.INFRA_2_COMMANDS["WR_session_to_test_convert"]
    converted = convert(GENERIC_EVENTS)
    assert converted["actions"] == [
        {"WR_to_url": ["https://shop.example/login"]},
        {"WR_input_to_element": ["css selector", "#user", "alice"]},
        {"WR_click_element": ["id", "submit"]},
    ]
    assert converted["stats"]["input_events"] == 4
    assert converted["stats"]["skipped_events"] == 1
    assert json.loads(json.dumps(converted)) == converted

    rrweb = [
        {"type": 4, "data": {"href": "https://shop.example/"}, "timestamp": 1},
        {"type": 3, "data": {"source": 2, "type": 2, "id": 17}, "timestamp": 2},
    ]
    from_file = convert(_write_json(tmp_path / "session.json", {"events": rrweb}))
    assert from_file["actions"][1] == {"WR_click_element": ["css selector", '[data-rrweb-id="17"]']}
    with pytest.raises(SessionToTestError):
        convert([{"kind": "hover"}])


def test_session_to_test_write(tmp_path: Path):
    write = infra_2.INFRA_2_COMMANDS["WR_session_to_test_write"]
    target = tmp_path / "out" / "login.json"
    written = write(GENERIC_EVENTS, str(target))
    assert written["path"] == str(target)
    assert written["stats"]["actions_emitted"] == 3
    assert json.dumps(written)
    assert len(json.loads(target.read_text(encoding="utf-8"))) == 3
    with pytest.raises(SessionToTestError):
        write([], str(tmp_path / "out" / "empty.json"))
