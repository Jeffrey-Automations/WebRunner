"""Tests for the web-platform command adapters (``_commands_web_platform_a``)."""
from __future__ import annotations

import base64
import gzip
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.background_sync_assert.sync import BackgroundSyncAssertError
from je_web_runner.utils.compression_streams.streams import CompressionStreamsError
from je_web_runner.utils.compute_pressure.pressure import ComputePressureError
from je_web_runner.utils.cookie_store_api.store import CookieStoreApiError
from je_web_runner.utils.credential_management.credentials import CredentialManagementError
from je_web_runner.utils.exception.exceptions import WebRunnerException, WebRunnerWebDriverIsNoneException
from je_web_runner.utils.executor import _commands_web_platform_a as adapters
from je_web_runner.utils.file_system_access.mock import FileSystemAccessError
from je_web_runner.utils.indexed_db_explorer.explorer import IndexedDbExplorerError
from je_web_runner.utils.notifications_audit.audit import NotificationsAuditError
from je_web_runner.utils.payment_request_assert.payment import PaymentRequestAssertError
from je_web_runner.utils.pip_assert.pip import PipAssertError
from je_web_runner.utils.popover_assert.popover import PopoverAssertError
from je_web_runner.utils.speculation_rules.rules import SpeculationRulesError
from je_web_runner.utils.speech_api_assert.assertions import SpeechApiAssertError
from je_web_runner.utils.sse_assert.stream import SseAssertError
from je_web_runner.utils.storage_buckets.buckets import StorageBucketsError

ASSIGNED_PACKAGES = {
    "background_sync_assert", "compression_streams", "compute_pressure", "cookie_store_api",
    "credential_management", "cross_tab_sync", "file_system_access", "indexed_db_explorer",
    "notifications_audit", "payment_request_assert", "pip_assert", "popover_assert", "speculation_rules",
    "speech_api_assert", "sse_assert", "storage_buckets",
}
COMMANDS = adapters.WEB_PLATFORM_A_COMMANDS

SYNC_LOG = {
    "registered": ["outbox"],
    "fired": [{"tag": "outbox", "lastChance": False, "ts": 10}, {"tag": "outbox", "lastChance": True, "ts": 20}],
}
PRESSURE_LOG = {
    "reactions": [{"name": "pause-video", "level": "critical", "ts": 5}],
    "fires": ["serious", "critical"],
    "disconnectCount": 1,
}
COOKIES = [
    {"name": "sid", "value": "abc", "sameSite": "lax", "secure": True},
    {"name": "theme", "value": "dark", "secure": False},
]
CHANGES = [{"changed": [{"name": "sid", "value": "new"}], "deleted": ["old"], "timestamp_ms": 12.5}]
CREDENTIAL_LOG = {
    "stored": [{"id": "amy@example.com", "type": "password", "password": "", "provider": ""}],
    "gets": [{"mediation": "required", "password": True}],
    "preventCount": 1,
}
WRITES = [
    {"file_name": "notes.txt", "sequence": 2, "data": " world"},
    {"file_name": "notes.txt", "sequence": 1, "data": "hello"},
]
IDB = {
    "name": "todo-db", "exists": True, "version": 3,
    "stores": {"todos": {
        "key_path": "id", "auto_increment": True, "index_names": ["by_done"],
        "records": [{"id": 1, "title": "milk", "done": False}, {"id": 2, "title": "tea", "done": True}],
        "keys": [1, 2],
    }},
}
NOTIFICATIONS = {
    "permission_requests": [{"timestamp_ms": 5000, "user_gesture": True, "result": "granted", "page_age_ms": 5000}],
    "notifications": [{"timestamp_ms": 6000, "title": "Order shipped", "body": "On its way", "tag": "order-1"}],
}
PAYMENT_LOG = {
    "constructed": [{
        "methodData": [{"supportedMethods": "https://apple.com/apple-pay"}],
        "details": {"total": {"label": "Total", "amount": {"currency": "USD", "value": "9.99"}}},
        "options": {"requestShipping": True},
    }],
    "completed": [{"status": "success"}],
}
PIP_EVENTS = [
    {"kind": "enter", "mode": "document", "ts": 1, "width": 400, "height": 300},
    {"kind": "enter", "mode": "video", "ts": 2},
    {"kind": "exit", "mode": "video", "ts": 3},
]
POPOVERS = [
    {"kind": "auto", "id": "menu", "open": True, "invoker": "menu-button"},
    {"kind": "dialog", "id": "confirm", "open": False, "modal": False},
]
PRERENDER_LOG = {
    "events": [{"kind": "prerenderingchange", "prerendering": False, "time": 12.0}], "fires": {"pageview": 1},
}
UTTERANCES = [{"text": "Your order is ready", "lang": "en-US", "rate": 1, "pitch": 1, "volume": 0.8}]
SSE_TEXT = 'id: 1\nevent: tick\ndata: {"price": 10, "symbol": "WR"}\n\nid: 2\ndata: done\n\n'
BUCKETS = {"supported": True, "buckets": [
    {"name": "inbox", "idb_databases": ["mail"], "cache_names": [], "durability": "strict"},
    {"name": "drafts", "idb_databases": ["draft-db"], "cache_names": ["v1"], "durability": "relaxed"},
]}


@pytest.fixture(name="driver")
def driver_fixture() -> Any:
    """A fake Selenium driver the adapters get from ``selenium_driver``."""
    fake = MagicMock()
    with patch.object(adapters, "selenium_driver", return_value=fake):
        yield fake


@pytest.fixture(autouse=True)
def reset_sse_recorder() -> None:
    """The SSE recorder is module state: every test starts with an empty one."""
    adapters.sse_assert_reset()


def run(name: str, *args: Any, **kwargs: Any) -> Any:
    """Call a command by its action-file name and check the result is JSON."""
    result = COMMANDS[name](*args, **kwargs)
    json.dumps(result)
    return result


def script_of(driver: Any) -> str:
    """The script the last ``execute_script`` call ran."""
    return str(driver.execute_script.call_args.args[0])


# ---------- tables ---------------------------------------------------------

def test_tables_are_consistent() -> None:
    prefixes = tuple(f"WR_{package}_" for package in ASSIGNED_PACKAGES)
    covered = {package for package in ASSIGNED_PACKAGES if any(name.startswith(f"WR_{package}_") for name in COMMANDS)}
    assert covered | set(adapters.PYTHON_ONLY) == ASSIGNED_PACKAGES
    assert not covered & set(adapters.PYTHON_ONLY)
    assert adapters.NETWORK_COMMANDS <= set(COMMANDS)
    for name, function in COMMANDS.items():
        assert name.startswith(prefixes), name
        assert name == name.lower().replace("wr_", "WR_", 1), name
        assert (function.__doc__ or "").strip(), name
    assert all(reason.strip() for reason in adapters.PYTHON_ONLY.values())


def test_page_commands_need_a_browser() -> None:
    wrapper = MagicMock(current_webdriver=None)
    with patch("je_web_runner.utils.executor._command_helpers.webdriver_wrapper_instance", wrapper):
        with pytest.raises(WebRunnerWebDriverIsNoneException, match="WR_pip_assert_install"):
            run("WR_pip_assert_install")


@pytest.mark.parametrize("name", [
    "WR_background_sync_assert_harvest", "WR_credential_management_harvest", "WR_payment_request_assert_harvest",
    "WR_pip_assert_harvest", "WR_speech_api_assert_harvest",
])
def test_harvest_without_recorder_says_so(driver: Any, name: str) -> None:
    driver.execute_script.return_value = None
    with pytest.raises(WebRunnerException, match="install command"):
        run(name)


@pytest.mark.parametrize("name, marker", [
    ("WR_background_sync_assert_install", "__wr_bg_sync__"),
    ("WR_cookie_store_api_install_listener", "__wr_cs__"),
    ("WR_notifications_audit_install", "__wr_notif_log__"),
    ("WR_pip_assert_install", "__wr_pip__"),
    ("WR_speculation_rules_install", "__wr_spec__"),
    ("WR_speech_api_assert_install", "__wr_speech__"),
])
def test_install_runs_the_library_script(driver: Any, name: str, marker: str) -> None:
    assert run(name) is True
    driver.execute_script.assert_called_once()
    assert marker in script_of(driver)


# ---------- background_sync_assert -----------------------------------------

def test_background_sync_harvest_and_check(driver: Any) -> None:
    driver.execute_script.return_value = SYNC_LOG
    harvested = run("WR_background_sync_assert_harvest")
    assert harvested == SYNC_LOG
    assert "drainRegistered" in script_of(driver)
    log = run("WR_background_sync_assert_check", harvested, "outbox", at_least=2, require_retry=True)
    assert log["fired"][1] == {"tag": "outbox", "last_chance": True, "ts_ms": 20}


def test_background_sync_check_fails() -> None:
    with pytest.raises(BackgroundSyncAssertError, match="never registered"):
        run("WR_background_sync_assert_check", SYNC_LOG, "other")
    with pytest.raises(BackgroundSyncAssertError, match="expected >= 3"):
        run("WR_background_sync_assert_check", SYNC_LOG, "outbox", at_least=3)
    with pytest.raises(BackgroundSyncAssertError, match="lastChance"):
        run("WR_background_sync_assert_check", SYNC_LOG, "outbox", forbid_last_chance=True)
    assert run("WR_background_sync_assert_check", {"registered": ["later"]}, "later", at_least=0)["fired"] == []


# ---------- compression_streams --------------------------------------------

def test_compression_streams_round_trip() -> None:
    packed = base64.b64encode(gzip.compress(b"hello hello hello hello")).decode("ascii")
    assert run("WR_compression_streams_decompress", packed) == {"text": "hello hello hello hello", "size": 23}
    assert run("WR_compression_streams_assert_round_trip", "hello hello hello hello", packed, "gzip") is True
    with pytest.raises(CompressionStreamsError, match="round-trip mismatch"):
        run("WR_compression_streams_assert_round_trip", "something else", packed)
    with pytest.raises(CompressionStreamsError, match="decompression failed"):
        run("WR_compression_streams_assert_round_trip", "hello", packed, "deflate")


def test_compression_streams_rejects_bad_input() -> None:
    with pytest.raises(CompressionStreamsError, match="not base64"):
        run("WR_compression_streams_decompress", "***")
    with pytest.raises(CompressionStreamsError, match="expected one of"):
        run("WR_compression_streams_decompress", "aGk=", "zip")


def test_compression_streams_ratio() -> None:
    assert run("WR_compression_streams_assert_ratio", 1000, 250, 0.5) == pytest.approx(0.25)
    with pytest.raises(CompressionStreamsError, match="exceeds"):
        run("WR_compression_streams_assert_ratio", 1000, 800, 0.5)


def test_compression_streams_compress_in_page(driver: Any) -> None:
    driver.execute_script.return_value = "H4sIAAAA"
    assert run("WR_compression_streams_compress", "payload", "deflate-raw") == "H4sIAAAA"
    script, algorithm, text = driver.execute_script.call_args.args
    assert script.startswith("return (") and script.endswith(")(arguments[0], arguments[1]);")
    assert (algorithm, text) == ("deflate-raw", "payload")
    with pytest.raises(CompressionStreamsError):
        run("WR_compression_streams_compress", "payload", "lzma")


# ---------- compute_pressure -----------------------------------------------

def test_compute_pressure_assert() -> None:
    log = run("WR_compute_pressure_assert", PRESSURE_LOG, "serious", "pause-video", require_disconnect=True)
    assert log["reactions"] == [{"name": "pause-video", "level": "critical", "ts_ms": 5}]
    assert log["fires"] == ["serious", "critical"]
    quiet = {"reactions": [], "fires": ["fair"]}
    assert run("WR_compute_pressure_assert", quiet, "critical", only_if_fired=True)["disconnect_count"] == 0


def test_compute_pressure_assert_fails() -> None:
    with pytest.raises(ComputePressureError, match="no reaction"):
        run("WR_compute_pressure_assert", PRESSURE_LOG, "critical", "other-name")
    with pytest.raises(ComputePressureError, match="never throttled"):
        run("WR_compute_pressure_assert", {"reactions": [], "fires": ["critical"]}, only_if_fired=True)
    with pytest.raises(ComputePressureError, match="never disconnected"):
        run("WR_compute_pressure_assert", {**PRESSURE_LOG, "disconnectCount": 0}, require_disconnect=True)
    with pytest.raises(ComputePressureError, match="expected one of"):
        run("WR_compute_pressure_assert", PRESSURE_LOG, "extreme")


# ---------- cookie_store_api -----------------------------------------------

def test_cookie_store_api_harvest(driver: Any) -> None:
    driver.execute_script.return_value = COOKIES
    cookies = run("WR_cookie_store_api_harvest")
    assert [(cookie["name"], cookie["same_site"], cookie["secure"]) for cookie in cookies] == [
        ("sid", "lax", True), ("theme", "strict", False),
    ]
    assert script_of(driver).startswith("return (async function")
    driver.execute_script.return_value = None
    assert run("WR_cookie_store_api_harvest") == []


def test_cookie_store_api_assert() -> None:
    records = run("WR_cookie_store_api_assert", COOKIES, present="sid", value="abc", absent="tracker")
    assert records[0]["value"] == "abc"
    with pytest.raises(CookieStoreApiError, match="want 'zzz'"):
        run("WR_cookie_store_api_assert", COOKIES, present="sid", value="zzz")
    with pytest.raises(CookieStoreApiError, match="unexpectedly present"):
        run("WR_cookie_store_api_assert", COOKIES, absent="theme")
    with pytest.raises(CookieStoreApiError, match="non-secure"):
        run("WR_cookie_store_api_assert", COOKIES, secure_only=True)


def test_cookie_store_api_changes(driver: Any) -> None:
    driver.execute_script.return_value = CHANGES
    events = run("WR_cookie_store_api_changes")
    assert events[0]["deleted"] == ["old"] and events[0]["changed"][0]["name"] == "sid"
    assert run("WR_cookie_store_api_assert_change", events, "old")["timestamp_ms"] == pytest.approx(12.5)
    assert run("WR_cookie_store_api_assert_change", CHANGES, "sid")["changed"][0]["value"] == "new"
    with pytest.raises(CookieStoreApiError, match="no change event"):
        run("WR_cookie_store_api_assert_change", CHANGES, "theme")


# ---------- credential_management ------------------------------------------

def test_credential_management_install(driver: Any) -> None:
    assert run("WR_credential_management_install", [{"id": "amy@example.com", "provider": "https://idp.test"}]) is True
    script, seed = driver.execute_script.call_args.args
    assert "__wr_cm__" in script
    assert seed == {"credentials": [
        {"id": "amy@example.com", "type": "password", "name": "", "password": "", "provider": "https://idp.test"},
    ]}
    with pytest.raises(CredentialManagementError, match="non-empty id"):
        run("WR_credential_management_install", [{"name": "no id"}])
    with pytest.raises(CredentialManagementError, match="must be an object"):
        run("WR_credential_management_install", ["amy"])


def test_credential_management_harvest_and_assert(driver: Any) -> None:
    driver.execute_script.return_value = CREDENTIAL_LOG
    harvested = run("WR_credential_management_harvest")
    assert harvested == CREDENTIAL_LOG
    log = run(
        "WR_credential_management_assert", harvested, stored_id="amy@example.com",
        prevent_silent_access=1, mediation="required", forbid_password=True,
    )
    assert log["prevent_count"] == 1 and log["stored"][0]["id"] == "amy@example.com"


def test_credential_management_assert_fails() -> None:
    with pytest.raises(CredentialManagementError, match="never called credentials.store"):
        run("WR_credential_management_assert", CREDENTIAL_LOG, stored_id="bob@example.com")
    with pytest.raises(CredentialManagementError, match="expected >= 2"):
        run("WR_credential_management_assert", CREDENTIAL_LOG, prevent_silent_access=2)
    with pytest.raises(CredentialManagementError, match="expected 'silent'"):
        run("WR_credential_management_assert", CREDENTIAL_LOG, mediation="silent")
    leaked = {"stored": [{"id": "amy", "password": "hunter2"}]}
    with pytest.raises(CredentialManagementError, match="plaintext password"):
        run("WR_credential_management_assert", leaked, forbid_password=True)


# ---------- file_system_access ---------------------------------------------

def test_file_system_access_install(driver: Any) -> None:
    files = [{"name": "notes.txt", "contents": "hello"}]
    assert run("WR_file_system_access_install", files, save_suggested_name="out.txt") is True
    script = script_of(driver)
    assert '"name": "notes.txt"' in script and '"mime_type": "text/plain"' in script and '"out.txt"' in script
    with pytest.raises(FileSystemAccessError, match="non-empty string"):
        run("WR_file_system_access_install", [{"contents": "nameless"}])
    with pytest.raises(FileSystemAccessError, match="must be an object"):
        run("WR_file_system_access_install", ["notes.txt"])


def test_file_system_access_harvest_and_assert(driver: Any) -> None:
    driver.execute_script.return_value = WRITES
    writes = run("WR_file_system_access_harvest")
    assert writes == WRITES
    found = run("WR_file_system_access_assert", writes, file_name="notes.txt", contains="wor")
    assert found == {"match": WRITES[0], "combined": "hello world"}
    assert run("WR_file_system_access_assert", [], no_writes=True) == {"match": None, "combined": ""}


def test_file_system_access_assert_fails() -> None:
    with pytest.raises(FileSystemAccessError, match="no write matched"):
        run("WR_file_system_access_assert", WRITES, contains="goodbye")
    with pytest.raises(FileSystemAccessError, match="unexpected write"):
        run("WR_file_system_access_assert", WRITES, no_writes=True)
    with pytest.raises(FileSystemAccessError, match="at least one of"):
        run("WR_file_system_access_assert", WRITES)


# ---------- indexed_db_explorer --------------------------------------------

def test_indexed_db_explorer_harvest(driver: Any) -> None:
    driver.execute_script.return_value = IDB
    snapshot = run("WR_indexed_db_explorer_harvest", "todo-db")
    assert snapshot["stores"]["todos"]["keys"] == [1, 2] and snapshot["version"] == 3
    script = script_of(driver)
    assert script.startswith("return (async function") and 'const dbName = "todo-db";' in script
    assert run("WR_indexed_db_explorer_assert", snapshot, "todos", minimum=2) == {
        "name": "todo-db", "stores": ["todos"], "records": 2,
    }
    with pytest.raises(IndexedDbExplorerError, match="non-empty string"):
        run("WR_indexed_db_explorer_harvest", "")


def test_indexed_db_explorer_diff() -> None:
    after = {"name": "todo-db", "exists": True, "stores": {
        "todos": {"records": [{"id": 1}]}, "tags": {"records": []},
    }}
    assert run("WR_indexed_db_explorer_diff", IDB, after) == {
        "added_stores": ["tags"], "removed_stores": [],
        "record_count_changes": {"todos": {"before": 2, "after": 1}},
    }


def test_indexed_db_explorer_assert() -> None:
    assert run("WR_indexed_db_explorer_assert", IDB)["records"] is None
    with pytest.raises(IndexedDbExplorerError, match="does not exist"):
        run("WR_indexed_db_explorer_assert", {"name": "gone", "exists": False})
    with pytest.raises(IndexedDbExplorerError, match="has 2 records"):
        run("WR_indexed_db_explorer_assert", IDB, "todos", maximum=1)
    with pytest.raises(IndexedDbExplorerError, match="not in snapshot"):
        run("WR_indexed_db_explorer_assert", IDB, "users")


def test_indexed_db_explorer_assert_record() -> None:
    record = run("WR_indexed_db_explorer_assert_record", IDB, "todos", key=2, index="by_done", record={"done": True})
    assert record == {"id": 2, "title": "tea", "done": True}
    assert run("WR_indexed_db_explorer_assert_record", IDB, "todos", key=1) is None
    with pytest.raises(IndexedDbExplorerError, match="key 9 not present"):
        run("WR_indexed_db_explorer_assert_record", IDB, "todos", key=9)
    with pytest.raises(IndexedDbExplorerError, match="index 'by_title'"):
        run("WR_indexed_db_explorer_assert_record", IDB, "todos", index="by_title")
    with pytest.raises(IndexedDbExplorerError, match="no record"):
        run("WR_indexed_db_explorer_assert_record", IDB, "todos", record={"title": "coffee"})


# ---------- notifications_audit --------------------------------------------

def test_notifications_audit_harvest_and_assert(driver: Any) -> None:
    driver.execute_script.return_value = NOTIFICATIONS
    log = run("WR_notifications_audit_harvest")
    assert log["permission_requests"][0]["result"] == "granted"
    assert log["notifications"][0]["require_interaction"] is False
    checked = run("WR_notifications_audit_assert", log, min_page_age_ms=3000, unique_tags=True)
    assert checked == log
    shown = run("WR_notifications_audit_assert_shown", log, title_contains="shipped", tag="order-1")
    assert shown["body"] == "On its way"


def test_notifications_audit_assert_fails() -> None:
    with pytest.raises(NotificationsAuditError, match="want >= 8000"):
        run("WR_notifications_audit_assert", NOTIFICATIONS, min_page_age_ms=8000)
    on_load = {
        "permission_requests": [{"timestamp_ms": 10, "user_gesture": False, "result": "denied"}],
        "notifications": [
            {"timestamp_ms": 50, "title": "Hi", "tag": "a"}, {"timestamp_ms": 60, "title": "Yo", "tag": "a"},
        ],
    }
    with pytest.raises(NotificationsAuditError, match="without user gesture"):
        run("WR_notifications_audit_assert", on_load)
    with pytest.raises(NotificationsAuditError, match="after denial"):
        run("WR_notifications_audit_assert", on_load, require_gesture=False)
    with pytest.raises(NotificationsAuditError, match="tags reused"):
        run("WR_notifications_audit_assert", on_load, require_gesture=False, no_spam_after_deny=False, unique_tags=True)
    with pytest.raises(NotificationsAuditError, match="no notification matched"):
        run("WR_notifications_audit_assert_shown", NOTIFICATIONS, body_contains="refund")


# ---------- payment_request_assert -----------------------------------------

def test_payment_request_assert_install(driver: Any) -> None:
    assert run("WR_payment_request_assert_install", {"payerEmail": "amy@example.com"}) is True
    script, canned = driver.execute_script.call_args.args
    assert "__wr_payment__" in script and canned == {"payerEmail": "amy@example.com"}
    run("WR_payment_request_assert_install")
    assert driver.execute_script.call_args.args[1] == {}
    with pytest.raises(PaymentRequestAssertError, match="must be an object"):
        run("WR_payment_request_assert_install", "basic-card")


def test_payment_request_assert_harvest_and_check(driver: Any) -> None:
    driver.execute_script.return_value = PAYMENT_LOG
    harvested = run("WR_payment_request_assert_harvest")
    assert harvested == PAYMENT_LOG
    log = run(
        "WR_payment_request_assert_check", harvested, method="https://apple.com/apple-pay",
        currency="USD", completed="success", shipping_required=True,
    )
    assert log["completed"] == [{"status": "success"}]
    assert log["constructed"][0]["options"] == {"requestShipping": True}


def test_payment_request_assert_check_fails() -> None:
    with pytest.raises(PaymentRequestAssertError, match="no PaymentRequest declared support"):
        run("WR_payment_request_assert_check", PAYMENT_LOG, method="https://google.com/pay")
    with pytest.raises(PaymentRequestAssertError, match="!= 'EUR'"):
        run("WR_payment_request_assert_check", PAYMENT_LOG, currency="EUR")
    with pytest.raises(PaymentRequestAssertError, match="expected 'fail'"):
        run("WR_payment_request_assert_check", PAYMENT_LOG, completed="fail")
    with pytest.raises(PaymentRequestAssertError, match="requestShipping"):
        run("WR_payment_request_assert_check", {"constructed": [{"options": {}}]}, shipping_required=True)


# ---------- pip_assert -----------------------------------------------------

def test_pip_assert_harvest_and_check(driver: Any) -> None:
    driver.execute_script.return_value = PIP_EVENTS
    harvested = run("WR_pip_assert_harvest")
    assert harvested == PIP_EVENTS
    log = run("WR_pip_assert_check", harvested, "video", exited_cleanly=True, min_size=[320, 240])
    assert log["events"][0] == {"kind": "enter", "mode": "document", "ts_ms": 1, "width": 400, "height": 300}
    assert len(run("WR_pip_assert_check", [], entered=False)["events"]) == 0


def test_pip_assert_check_fails() -> None:
    with pytest.raises(PipAssertError, match="never entered video"):
        run("WR_pip_assert_check", PIP_EVENTS[:1])
    with pytest.raises(PipAssertError, match="dangling"):
        run("WR_pip_assert_check", PIP_EVENTS, "document", exited_cleanly=True)
    with pytest.raises(PipAssertError, match="expected >= 800x600"):
        run("WR_pip_assert_check", PIP_EVENTS, min_size=[800, 600])
    with pytest.raises(PipAssertError, match=r"\[width, height\]"):
        run("WR_pip_assert_check", PIP_EVENTS, min_size=[800])
    with pytest.raises(PipAssertError, match="expected one of"):
        run("WR_pip_assert_check", PIP_EVENTS, "window")


# ---------- popover_assert -------------------------------------------------

def test_popover_assert_harvest_and_check(driver: Any) -> None:
    driver.execute_script.return_value = POPOVERS
    states = run("WR_popover_assert_harvest")
    assert script_of(driver).startswith("return (function()")
    assert [(state["id"], state["kind"], state["open"]) for state in states] == [
        ("menu", "auto", True), ("confirm", "dialog", False),
    ]
    assert run("WR_popover_assert_check", states, open_id="menu", closed_id="confirm") == states
    assert run("WR_popover_assert_invoker", states, "menu", "menu-button") is True


def test_popover_assert_check_fails() -> None:
    with pytest.raises(PopoverAssertError, match="exists but is closed"):
        run("WR_popover_assert_check", POPOVERS, open_id="confirm")
    with pytest.raises(PopoverAssertError, match="unexpectedly open"):
        run("WR_popover_assert_check", POPOVERS, closed_id="menu")
    with pytest.raises(PopoverAssertError, match="expected no open popovers"):
        run("WR_popover_assert_check", POPOVERS, none_open=True)
    modal = {"kind": "dialog", "open": True, "modal": True}
    with pytest.raises(PopoverAssertError, match="multiple modal"):
        run("WR_popover_assert_check", [{**modal, "id": "one"}, {**modal, "id": "two"}])
    with pytest.raises(PopoverAssertError, match="want 'other-button'"):
        run("WR_popover_assert_invoker", POPOVERS, "menu", "other-button")
    with pytest.raises(PopoverAssertError, match="unknown popover kind"):
        run("WR_popover_assert_check", [{"kind": "tooltip"}])


# ---------- speculation_rules ----------------------------------------------

def test_speculation_rules_build_tag() -> None:
    tag = run(
        "WR_speculation_rules_build_tag",
        prefetch=[{"urls": ["/next"], "eagerness": "eager"}],
        prerender=[{"source": "document", "where": {"href_matches": "/product/*"}}],
    )
    assert tag.startswith('<script type="speculationrules">') and tag.endswith("</script>")
    assert json.loads(tag[len('<script type="speculationrules">'):-len("</script>")]) == {
        "prefetch": [{"source": "list", "urls": ["/next"], "eagerness": "eager"}],
        "prerender": [{"source": "document", "where": {"href_matches": "/product/*"}, "eagerness": "moderate"}],
    }
    with pytest.raises(SpeculationRulesError, match="requires urls"):
        run("WR_speculation_rules_build_tag", prefetch=[{"source": "list"}])
    with pytest.raises(SpeculationRulesError, match="must be an object"):
        run("WR_speculation_rules_build_tag", prerender=["/next"])
    with pytest.raises(SpeculationRulesError, match="at least one rule list"):
        run("WR_speculation_rules_build_tag")


def test_speculation_rules_harvest_and_assert(driver: Any) -> None:
    driver.execute_script.return_value = PRERENDER_LOG
    log = run("WR_speculation_rules_harvest")
    assert log == PRERENDER_LOG
    assert run("WR_speculation_rules_assert", log, no_double_fire=["pageview"], fire_counts={"pageview": 1}) == log


def test_speculation_rules_assert_fails() -> None:
    with pytest.raises(SpeculationRulesError, match="no prerenderingchange"):
        run("WR_speculation_rules_assert", {"events": [], "fires": {}})
    twice = {"events": [], "fires": {"pageview": 2}}
    with pytest.raises(SpeculationRulesError, match="more than once"):
        run("WR_speculation_rules_assert", twice, activated=False, no_double_fire=["pageview"])
    with pytest.raises(SpeculationRulesError, match="fired 2 times, want 1"):
        run("WR_speculation_rules_assert", twice, activated=False, fire_counts={"pageview": 1})


# ---------- speech_api_assert ----------------------------------------------

def test_speech_api_assert_push_and_harvest(driver: Any) -> None:
    driver.execute_script.return_value = True
    assert run("WR_speech_api_assert_push_transcript", "open settings") is True
    script, text = driver.execute_script.call_args.args
    assert "pushTranscript(arguments[0])" in script and text == "open settings"
    driver.execute_script.return_value = [{"text": "Hi", "lang": "en-GB", "volume": 0}]
    assert run("WR_speech_api_assert_harvest") == [
        {"text": "Hi", "lang": "en-GB", "rate": 1.0, "pitch": 1.0, "volume": 0.0},
    ]
    driver.execute_script.return_value = None
    with pytest.raises(WebRunnerException, match="install command"):
        run("WR_speech_api_assert_push_transcript", "open settings")


def test_speech_api_assert_check() -> None:
    spoken = run("WR_speech_api_assert_check", UTTERANCES, text_contains="order", lang="en-US", volume_range=[0.5, 1])
    assert spoken[0]["volume"] == pytest.approx(0.8)
    assert run("WR_speech_api_assert_check", [], no_speech=True) == []
    with pytest.raises(SpeechApiAssertError, match="no utterance contained"):
        run("WR_speech_api_assert_check", UTTERANCES, text_contains="refund")
    with pytest.raises(SpeechApiAssertError, match="expected 'zh-TW'"):
        run("WR_speech_api_assert_check", UTTERANCES, lang="zh-TW")
    with pytest.raises(SpeechApiAssertError, match="expected no speech"):
        run("WR_speech_api_assert_check", UTTERANCES, no_speech=True)
    with pytest.raises(SpeechApiAssertError, match="outside volume band"):
        run("WR_speech_api_assert_check", UTTERANCES, volume_range=[0, 0.5])
    with pytest.raises(SpeechApiAssertError, match=r"\[min, max\]"):
        run("WR_speech_api_assert_check", UTTERANCES, volume_range=[0.5])


# ---------- sse_assert -----------------------------------------------------

def test_sse_assert_parse() -> None:
    events = run("WR_sse_assert_parse", SSE_TEXT)
    assert [(event["event"], event["id"], event["data"]) for event in events] == [
        ("tick", "1", '{"price": 10, "symbol": "WR"}'), ("message", "2", "done"),
    ]
    with pytest.raises(SseAssertError, match="expects str"):
        run("WR_sse_assert_parse", 5)


def test_sse_assert_recorder() -> None:
    assert run("WR_sse_assert_feed", "event: tick\ndata: one\n") == {"parsed": 0, "total": 0}
    assert run("WR_sse_assert_feed", "\ndata: two\n\n") == {"parsed": 2, "total": 2}
    assert [event["data"] for event in run("WR_sse_assert_events")] == ["one", "two"]
    assert [event["data"] for event in run("WR_sse_assert_events", "tick")] == ["one"]
    assert run("WR_sse_assert_count", event_type="tick", maximum=1) == 1
    assert run("WR_sse_assert_data", contains="tw")["data"] == "two"
    assert run("WR_sse_assert_reset") is True
    assert run("WR_sse_assert_events") == []
    with pytest.raises(SseAssertError, match="out of range"):
        run("WR_sse_assert_count")


def test_sse_assert_text_form_leaves_the_recorder_alone() -> None:
    assert run("WR_sse_assert_count", SSE_TEXT, minimum=2, maximum=2) == 2
    matched = run("WR_sse_assert_data", SSE_TEXT, "tick", json_keys=["price", "symbol"], increasing_ids=True)
    assert matched["id"] == "1"
    assert run("WR_sse_assert_data", SSE_TEXT, increasing_ids=True) is None
    assert run("WR_sse_assert_events") == []


def test_sse_assert_fails() -> None:
    with pytest.raises(SseAssertError, match="out of range"):
        run("WR_sse_assert_count", SSE_TEXT, "tick", minimum=2)
    with pytest.raises(SseAssertError, match="containing 'missing'"):
        run("WR_sse_assert_data", SSE_TEXT, contains="missing")
    with pytest.raises(SseAssertError, match="had keys"):
        run("WR_sse_assert_data", SSE_TEXT, json_keys=["volume"])
    with pytest.raises(SseAssertError, match="not strictly increasing"):
        run("WR_sse_assert_data", "id: 2\ndata: a\n\nid: 2\ndata: b\n\n", increasing_ids=True)


# ---------- storage_buckets ------------------------------------------------

def test_storage_buckets_harvest_and_assert(driver: Any) -> None:
    driver.execute_script.return_value = BUCKETS
    report = run("WR_storage_buckets_harvest")
    assert script_of(driver).startswith("return (async function")
    assert [bucket["name"] for bucket in report["buckets"]] == ["inbox", "drafts"]
    checked = run("WR_storage_buckets_assert", report, bucket="inbox", durability="strict", allowed=["inbox", "drafts"])
    assert checked == report
    assert run("WR_storage_buckets_assert_isolated", report, "mail", "inbox") is True


def test_storage_buckets_assert_fails() -> None:
    with pytest.raises(StorageBucketsError, match="not supported"):
        run("WR_storage_buckets_assert", {"supported": False, "buckets": []})
    with pytest.raises(StorageBucketsError, match="not present"):
        run("WR_storage_buckets_assert", BUCKETS, bucket="archive")
    with pytest.raises(StorageBucketsError, match="want 'relaxed'"):
        run("WR_storage_buckets_assert", BUCKETS, bucket="inbox", durability="relaxed")
    with pytest.raises(StorageBucketsError, match="unexpected buckets"):
        run("WR_storage_buckets_assert", BUCKETS, allowed=["inbox"])
    with pytest.raises(StorageBucketsError, match="not in expected bucket"):
        run("WR_storage_buckets_assert_isolated", BUCKETS, "orders", "drafts")
    leaking = {"supported": True, "buckets": [
        {"name": "inbox", "idb_databases": ["mail"]}, {"name": "drafts", "idb_databases": ["mail"]},
    ]}
    with pytest.raises(StorageBucketsError, match="also found in"):
        run("WR_storage_buckets_assert_isolated", leaking, "mail", "inbox")
