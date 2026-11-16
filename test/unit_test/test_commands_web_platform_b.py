"""Tests for the web-platform command adapters (``_commands_web_platform_b``): no browser, no network."""
from __future__ import annotations

import base64
import importlib
import json
from unittest.mock import MagicMock

import pytest

from je_web_runner.utils.exception.exceptions import WebRunnerException, WebRunnerWebDriverIsNoneException
from je_web_runner.utils.executor import _commands_web_platform_b as commands

PACKAGES = (
    "three_d_secure_flow", "view_transitions", "wake_lock_assert", "web_locks", "web_push_assert",
    "web_share_assert", "webauthn_mock", "webcodecs_assert", "webgpu_pixel_verify", "webhid_mock",
    "webrtc_assert", "webserial_mock", "websocket_assert", "webtransport_assert", "webusb_mock",
)
RUN = commands.WEB_PLATFORM_B_COMMANDS


def _library_script(module: str, name: str) -> str:
    return str(getattr(importlib.import_module(f"je_web_runner.utils.{module}"), name))


@pytest.fixture(name="driver")
def _driver(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """A fake Selenium driver behind ``selenium_driver``."""
    driver = MagicMock()
    monkeypatch.setattr(commands, "selenium_driver", MagicMock(return_value=driver))
    return driver


@pytest.fixture(autouse=True)
def _reset_recorders() -> None:
    RUN["WR_websocket_assert_reset"]()
    RUN["WR_webtransport_assert_reset"]()


# ---------- tables ------------------------------------------------------

def test_every_package_is_covered_and_tables_are_consistent() -> None:
    assert len(RUN) == 54
    for package in PACKAGES:
        has_command = any(name.startswith(f"WR_{package}_") for name in RUN)
        assert has_command or package in commands.PYTHON_ONLY, package
    for name, function in RUN.items():
        assert any(name.startswith(f"WR_{package}_") for package in PACKAGES), name
        assert name == name.lower().replace("wr_", "WR_", 1)
        assert callable(function) and (function.__doc__ or "").strip(), name
    assert set(commands.PYTHON_ONLY) <= set(PACKAGES)
    assert all(reason.strip() for reason in commands.PYTHON_ONLY.values())
    assert commands.NETWORK_COMMANDS <= set(RUN)


def test_browser_command_without_a_browser_names_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    from je_web_runner.utils.executor import _command_helpers
    monkeypatch.setattr(_command_helpers.webdriver_wrapper_instance, "current_webdriver", None)
    with pytest.raises(WebRunnerWebDriverIsNoneException, match="WR_web_locks_harvest"):
        RUN["WR_web_locks_harvest"]()


# ---------- install / harvest through the browser -----------------------

@pytest.mark.parametrize("command, module, script, kwargs, script_args, expected", [
    ("WR_view_transitions_install", "view_transitions.transitions", "_INSTRUMENT_JS", {}, (), True),
    ("WR_wake_lock_assert_install", "wake_lock_assert.lock", "INSTALL_SCRIPT", {}, (), True),
    ("WR_web_locks_install", "web_locks.locks", "INSTALL_LISTENER_SCRIPT", {}, (), True),
    ("WR_web_push_assert_install", "web_push_assert.push", "INSTALL_SCRIPT", {}, (), True),
    ("WR_web_share_assert_install", "web_share_assert.share", "INSTALL_SCRIPT", {"reject": True},
     ({"reject": True, "canShare": True, "canShareFiles": True},), True),
    ("WR_webcodecs_assert_install", "webcodecs_assert.assertions", "HARVEST_SCRIPT", {}, (), True),
    ("WR_webhid_mock_install", "webhid_mock.mock", "INSTALL_SCRIPT",
     {"devices": [{"vendor_id": 1133, "product_id": 49948, "product_name": "Pad"}]},
     ([{"vendor_id": 1133, "product_id": 49948, "product_name": "Pad"}],),
     [{"vendor_id": 1133, "product_id": 49948, "product_name": "Pad"}]),
    ("WR_webserial_mock_install", "webserial_mock.mock", "INSTALL_SCRIPT", {"vendor_id": 9025},
     ({"vendor_id": 9025, "product_id": None},), {"vendor_id": 9025, "product_id": None}),
    ("WR_webusb_mock_install", "webusb_mock.mock", "INSTALL_SCRIPT",
     {"devices": [{"vendor_id": 1155, "product_id": 22336, "serial_number": "A1"}]},
     ([{"vendor_id": 1155, "product_id": 22336, "product_name": "", "serial_number": "A1"}],),
     [{"vendor_id": 1155, "product_id": 22336, "product_name": "", "serial_number": "A1"}]),
])
def test_install_runs_the_library_script(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        driver: MagicMock, command: str, module: str, script: str, kwargs: dict, script_args: tuple,
        expected: object) -> None:
    assert RUN[command](**kwargs) == expected
    driver.execute_script.assert_called_once_with(_library_script(module, script), *script_args)
    assert json.dumps(expected)


@pytest.mark.parametrize("command, marker, harvested", [
    ("WR_view_transitions_harvest", "__wr_vt_log__", [{"id": "vt_1", "startedAt": 1.0}]),
    ("WR_wake_lock_assert_harvest", "__wr_wakelock__.drain()", [{"kind": "acquire", "ts": 5}]),
    ("WR_web_locks_harvest", "__wr_locks__", [{"id": "1", "name": "cart", "outcome": "acquired"}]),
    ("WR_web_push_assert_harvest", "__wr_push__.drainShown()", {"subscriptions": [], "notifications": []}),
    ("WR_web_share_assert_harvest", "__wr_share__.drainFallbacks()", {"shares": [{"url": "u"}], "fallbacks": []}),
    ("WR_webauthn_mock_harvest", "__wr_webauthn__.drainRequested()", {"created": [{}], "requested": []}),
    ("WR_webhid_mock_harvest", "__wr_hid__.drainOutgoing()", [{"reportId": 1, "data": [1]}]),
    ("WR_webserial_mock_harvest", "__wr_serial__.drainOutbound()", [[79, 75, 10]]),
    ("WR_webusb_mock_harvest", "__wr_usb__.drainOutgoing()", [{"kind": "transferOut", "endpoint": 2, "data": []}]),
])
def test_harvest_reads_the_page_log(driver: MagicMock, command: str, marker: str, harvested: object) -> None:
    driver.execute_script.return_value = harvested
    assert RUN[command]() == harvested
    assert marker in driver.execute_script.call_args.args[0]
    assert json.dumps(harvested)


def test_list_harvest_of_a_page_without_the_shim_is_empty(driver: MagicMock) -> None:
    driver.execute_script.return_value = None
    assert RUN["WR_wake_lock_assert_harvest"]() == []
    assert RUN["WR_webcodecs_assert_harvest"]() == []


def test_webcodecs_harvest_passes_the_kind(driver: MagicMock) -> None:
    driver.execute_script.return_value = [{"type": "key", "timestamp": 0}]
    assert RUN["WR_webcodecs_assert_harvest"]("audio") == [{"type": "key", "timestamp": 0}]
    assert driver.execute_script.call_args.args[1] == "audio"
    with pytest.raises(WebRunnerException):
        RUN["WR_webcodecs_assert_harvest"]("subtitles")


# ---------- three_d_secure_flow -----------------------------------------

def test_three_d_secure_flow_classify_and_assert() -> None:
    challenge = {"trans_status": "C", "challenge_shown": True, "cres_submitted": True, "order_finalized": True}
    assert RUN["WR_three_d_secure_flow_classify"](challenge) == "challenge_ok"
    assert RUN["WR_three_d_secure_flow_assert"](challenge, expected="challenge_ok") == "challenge_ok"
    rejected = {"trans_status": "R", "error_displayed": "Card declined"}
    assert RUN["WR_three_d_secure_flow_assert"](rejected, "rejected", "declined") == "rejected"
    assert json.dumps(RUN["WR_three_d_secure_flow_classify"](rejected))


@pytest.mark.parametrize("flow, kwargs", [
    ({"trans_status": "R", "order_finalized": True}, {}),
    ({"trans_status": "C", "challenge_shown": True}, {}),
    ({"trans_status": "Y", "order_finalized": True}, {"expected": "challenge_ok"}),
    ({"trans_status": "N", "error_displayed": "oops"}, {"error_contains": "declined"}),
    ({"trans_status": "Y"}, {"expected": "nonsense"}),
    ({"trans_status": "Z"}, {}),
    ({"trans_status": "Y", "unknown_key": 1}, {}),
    (["Y"], {}),
])
def test_three_d_secure_flow_assert_fails(flow: object, kwargs: dict) -> None:
    from je_web_runner.utils.three_d_secure_flow.flow import ThreeDSecureFlowError
    with pytest.raises(ThreeDSecureFlowError):
        RUN["WR_three_d_secure_flow_assert"](flow, **kwargs)


# ---------- view_transitions --------------------------------------------

VT_LOG = [{"id": "vt_1", "startedAt": 0, "finishedAt": 180, "durationMs": 180, "error": None,
           "layoutShifts": 0.01, "maxShiftValue": 0.01, "groups": ["hero"]}]


def test_view_transitions_assert_passes() -> None:
    runs = RUN["WR_view_transitions_assert"](VT_LOG, max_duration_ms=300, group="hero")
    assert runs[0]["id"] == "vt_1" and runs[0]["duration_ms"] == 180.0
    assert json.dumps(runs)


@pytest.mark.parametrize("log, kwargs", [
    ([], {}),
    (VT_LOG, {"max_duration_ms": 100}),
    (VT_LOG, {"max_cls": 0.001}),
    (VT_LOG, {"group": "footer"}),
    ([{**VT_LOG[0], "error": "AbortError"}], {}),
])
def test_view_transitions_assert_fails(log: list, kwargs: dict) -> None:
    from je_web_runner.utils.view_transitions.transitions import ViewTransitionsError
    with pytest.raises(ViewTransitionsError):
        RUN["WR_view_transitions_assert"](log, **kwargs)


# ---------- wake_lock_assert --------------------------------------------

def test_wake_lock_assert_check() -> None:
    from je_web_runner.utils.wake_lock_assert.lock import WakeLockAssertError
    events = [{"kind": "acquire", "ts": 1}, {"kind": "release", "ts": 2, "by": "os"},
              {"kind": "acquire", "ts": 3}, {"kind": "release", "ts": 4, "by": "app"}]
    result = RUN["WR_wake_lock_assert_check"](events, released_by_app=True, re_acquired=True)
    assert result == {"acquired_count": 2, "released_count": 2}
    assert json.dumps(result)
    for bad, kwargs in (
            ([], {}),
            ([{"kind": "acquire"}], {}),
            (events[:2], {"released_by_app": True}),
            (events[:2], {"re_acquired": True}),
    ):
        with pytest.raises(WakeLockAssertError):
            RUN["WR_wake_lock_assert_check"](bad, **kwargs)


# ---------- web_locks ---------------------------------------------------

def test_web_locks_assert() -> None:
    from je_web_runner.utils.web_locks.locks import WebLocksError
    log = [
        {"id": "1", "name": "cart", "outcome": "requested", "time": 1.0},
        {"id": "1", "name": "cart", "outcome": "acquired", "time": 0.5},
        {"id": "2", "name": "cart", "outcome": "unavailable", "if_available": True, "time": 0.6},
        {"id": "1", "name": "cart", "outcome": "released", "time": 4.0},
    ]
    events = RUN["WR_web_locks_assert"](log, name="cart", expected_acquired=1, if_available_refused=True)
    assert [event["outcome"] for event in events] == ["acquired", "unavailable", "released"]
    assert json.dumps(events)
    overlap = [log[1], {"id": "3", "name": "cart", "outcome": "acquired"}, log[3],
               {"id": "3", "name": "cart", "outcome": "released"}]
    for bad, kwargs in (
            (log[:2], {}),
            (overlap, {"name": "cart"}),
            (log, {"name": "cart", "expected_acquired": 2}),
            ([log[1], log[3]], {"name": "cart", "if_available_refused": True}),
            ({"not": "a list"}, {}),
    ):
        with pytest.raises(WebLocksError):
            RUN["WR_web_locks_assert"](bad, **kwargs)


# ---------- web_push_assert ---------------------------------------------

def test_web_push_assert_check() -> None:
    from je_web_runner.utils.web_push_assert.push import WebPushAssertError
    subscription = {"applicationServerKey": "BEl62iUYgUivx-_w", "userVisibleOnly": True,
                    "endpoint": "https://fcm.googleapis.com/fcm/send/abc"}
    log = {"subscriptions": [subscription], "notifications": [{"title": "Order", "body": "Shipped today"}]}
    result = RUN["WR_web_push_assert_check"](
        log, vapid_public_key="BEl62iUYgUivx-_w", require_notification=True, body_contains="Shipped")
    assert result["subscriptions"][0]["user_visible_only"] is True
    assert result["notifications"][0]["body"] == "Shipped today"
    assert json.dumps(result)
    for bad, kwargs in (
            (log, {"vapid_public_key": "another-key"}),
            ({"subscriptions": [{**subscription, "userVisibleOnly": False}]}, {}),
            ({"subscriptions": [{**subscription, "endpoint": "https://push.evil.example/x"}]}, {}),
            ({"subscriptions": [subscription]}, {"require_notification": True}),
            (log, {"require_notification": True, "body_contains": "Refunded"}),
            ([], {}),
    ):
        with pytest.raises(WebPushAssertError):
            RUN["WR_web_push_assert_check"](bad, **kwargs)


# ---------- web_share_assert --------------------------------------------

def test_web_share_assert_check() -> None:
    from je_web_runner.utils.web_share_assert.share import WebShareAssertError
    log = {"shares": [{"title": "Shoes", "url": "https://shop.example/p/1", "filesCount": 0}], "fallbacks": []}
    result = RUN["WR_web_share_assert_check"](log, expected_origin="https://shop.example", field="title")
    assert result["shares"] == [{"title": "Shoes", "text": None, "url": "https://shop.example/p/1", "files_count": 0}]
    assert json.dumps(result)
    fallback = RUN["WR_web_share_assert_check"]({"fallbacks": [{"id": "copy-link", "ts": 7}]}, fallback=True)
    assert fallback["fallbacks"] == [{"id": "copy-link", "ts_ms": 7}]
    for bad, kwargs in (
            ({"shares": []}, {}),
            (log, {"expected_origin": "https://other.example"}),
            (log, {"field": "text"}),
            (log, {"field": "files"}),
            (log, {"fallback": True}),
    ):
        with pytest.raises(WebShareAssertError):
            RUN["WR_web_share_assert_check"](bad, **kwargs)


# ---------- webauthn_mock -----------------------------------------------

def test_webauthn_mock_build_and_install(driver: MagicMock) -> None:
    from je_web_runner.utils.webauthn_mock.mock import INSTALL_SCRIPT, WebauthnMockError
    credential = RUN["WR_webauthn_mock_build_credential"]("alice", "shop.example", sign_count=3)
    assert credential["signCount"] == 3 and credential["id"]
    assert credential["id"] == RUN["WR_webauthn_mock_build_credential"]("alice", "shop.example")["id"]
    assert json.dumps(credential)
    assert RUN["WR_webauthn_mock_install"]([credential]) == 1
    driver.execute_script.assert_called_once_with(INSTALL_SCRIPT, [credential])
    with pytest.raises(WebauthnMockError):
        RUN["WR_webauthn_mock_install"]([{"publicKeyB64": "no id"}])
    with pytest.raises(WebauthnMockError):
        RUN["WR_webauthn_mock_build_credential"]("", "shop.example")


def test_webauthn_mock_assert() -> None:
    from je_web_runner.utils.webauthn_mock.mock import WebauthnMockError
    log = {"created": [{"publicKey": {"authenticatorSelection": {"userVerification": "required"}}}],
           "requested": [{"publicKey": {"userVerification": "required"}}]}
    result = RUN["WR_webauthn_mock_assert"](log, signed_in=True, user_verification="required")
    assert result == {"created": 1, "requested": 1}
    assert json.dumps(result)
    for bad, kwargs in (
            ({"requested": log["requested"]}, {}),
            ({"created": log["created"]}, {"signed_in": True}),
            (log, {"user_verification": "discouraged"}),
            (log, {"user_verification": "always"}),
    ):
        with pytest.raises(WebauthnMockError):
            RUN["WR_webauthn_mock_assert"](bad, **kwargs)


# ---------- webcodecs_assert --------------------------------------------

def test_webcodecs_assert_check() -> None:
    from je_web_runner.utils.webcodecs_assert.assertions import WebcodecsAssertError
    chunks = [
        {"type": "key" if index == 0 else "delta", "timestamp": index * 33_333, "byteLength": 900,
         "codec": "avc1.42001f", "width": 1280, "height": 720}
        for index in range(4)
    ]
    result = RUN["WR_webcodecs_assert_check"](
        chunks, codec="avc1.42001f", resolution=[1280, 720], max_keyframe_gap=3, min_fps=29)
    assert result["count"] == 4 and result["codecs"] == ["avc1.42001f"]
    assert result["framerate"] == pytest.approx(30.0, abs=0.1)
    assert json.dumps(result)
    for kwargs in ({"codec": "vp09.00.10.08"}, {"resolution": [1920, 1080]}, {"max_keyframe_gap": 2},
                   {"min_fps": 60}):
        with pytest.raises(WebcodecsAssertError):
            RUN["WR_webcodecs_assert_check"](chunks, **kwargs)
    with pytest.raises(ValueError):
        RUN["WR_webcodecs_assert_check"](chunks, resolution=[1280])


# ---------- webgpu_pixel_verify -----------------------------------------

def _frame(*pixels: tuple[int, int, int, int]) -> dict:
    raw = bytes(value for pixel in pixels for value in pixel)
    return {"width": 2, "height": 2, "rgba_b64": base64.b64encode(raw).decode("ascii")}


COLOURS = _frame((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 255, 255))
GREY = _frame(*[(10, 10, 10, 255)] * 4)


def test_webgpu_pixel_verify_capture(driver: MagicMock) -> None:
    from je_web_runner.utils.webgpu_pixel_verify.pixel import WebgpuPixelVerifyError
    driver.execute_async_script.return_value = COLOURS
    assert RUN["WR_webgpu_pixel_verify_capture"]("#scene") == COLOURS
    script, selector = driver.execute_async_script.call_args.args
    assert selector == "#scene" and "getContext('webgpu')" in script and "#scene" not in script
    driver.execute_async_script.return_value = {"error": "Error: canvas not found: #scene"}
    with pytest.raises(WebgpuPixelVerifyError, match="canvas not found"):
        RUN["WR_webgpu_pixel_verify_capture"]("#scene")


def test_webgpu_pixel_verify_assert() -> None:
    from je_web_runner.utils.webgpu_pixel_verify.pixel import WebgpuPixelVerifyError
    result = RUN["WR_webgpu_pixel_verify_assert"](COLOURS, channel="r", min_value=100, max_value=200)
    assert result == {"width": 2, "height": 2, "mean_rgba": {"r": 127.5, "g": 127.5, "b": 127.5, "a": 255.0}}
    assert json.dumps(result)
    assert RUN["WR_webgpu_pixel_verify_assert"](GREY, allow_solid_color=True)["mean_rgba"]["r"] == 10.0
    for bad, kwargs in (
            (GREY, {}),
            (_frame(*[(1, 2, 3, 0)] * 4), {}),
            (COLOURS, {"channel": "r", "min_value": 200, "max_value": 255}),
            ({"width": 2, "height": 2, "rgba_b64": "AAAA"}, {}),
    ):
        with pytest.raises(WebgpuPixelVerifyError):
            RUN["WR_webgpu_pixel_verify_assert"](bad, **kwargs)


def test_webgpu_pixel_verify_assert_similar() -> None:
    from je_web_runner.utils.webgpu_pixel_verify.pixel import WebgpuPixelVerifyError
    assert RUN["WR_webgpu_pixel_verify_assert_similar"](COLOURS, COLOURS) == 0.0
    assert RUN["WR_webgpu_pixel_verify_assert_similar"](COLOURS, GREY, max_diff=1.0) > 0.3
    with pytest.raises(WebgpuPixelVerifyError):
        RUN["WR_webgpu_pixel_verify_assert_similar"](COLOURS, GREY)


# ---------- webhid_mock -------------------------------------------------

def test_webhid_mock_push_report(driver: MagicMock) -> None:
    from je_web_runner.utils.webhid_mock.mock import WebhidMockError
    driver.execute_script.return_value = True
    assert RUN["WR_webhid_mock_push_report"](1, [0, 255], device_index=1) is True
    assert driver.execute_script.call_args.args[1:] == (1, 1, [0, 255])
    driver.execute_script.return_value = None
    assert RUN["WR_webhid_mock_push_report"](1, [0]) is False
    with pytest.raises(WebhidMockError):
        RUN["WR_webhid_mock_push_report"](1, [256])
    with pytest.raises(WebhidMockError):
        RUN["WR_webhid_mock_install"]([{"vendor_id": "1133", "product_id": 1}])
    with pytest.raises(WebhidMockError):
        RUN["WR_webhid_mock_install"]([{"vendor_id": 70000, "product_id": 1}])


def test_webhid_mock_assert_output() -> None:
    from je_web_runner.utils.webhid_mock.mock import WebhidMockError
    reports = [{"reportId": 0, "data": [1, 2, 3]}, {"reportId": 2, "data": [9]}]
    result = RUN["WR_webhid_mock_assert_output"](reports, expected_count=2, contains=[2, 3])
    assert result == [{"report_id": 0, "data": [1, 2, 3]}, {"report_id": 2, "data": [9]}]
    assert json.dumps(result)
    with pytest.raises(WebhidMockError):
        RUN["WR_webhid_mock_assert_output"](reports, expected_count=1)
    with pytest.raises(WebhidMockError):
        RUN["WR_webhid_mock_assert_output"](reports, contains=[3, 2])


# ---------- webrtc_assert -----------------------------------------------

SNAPSHOT = {
    "connectionState": "connected", "iceConnectionState": "completed", "signalingState": "stable",
    "localSdp": "v=0\r\na=rtpmap:111 opus/48000/2\r\n", "remoteSdp": "v=0\r\na=rtpmap:96 VP8/90000\r\n",
    "remoteTracks": [{"kind": "video", "readyState": "live", "label": "camera"}],
}
STATS = [
    {"type": "inbound-rtp", "kind": "video", "packetsReceived": 1000, "packetsLost": 5, "bytesReceived": 64000},
    {"type": "outbound-rtp", "kind": "audio", "packetsSent": 500, "bytesSent": 8000},
    {"type": "candidate-pair", "state": "succeeded"},
]


def test_webrtc_assert_connected() -> None:
    from je_web_runner.utils.webrtc_assert.peer import WebRtcAssertError
    result = RUN["WR_webrtc_assert_connected"](SNAPSHOT, track_kind="video", codec="opus")
    assert result["connection_state"] == "connected" and result["remote_tracks"][0]["label"] == "camera"
    assert json.dumps(result)
    for bad, kwargs in (
            ({**SNAPSHOT, "connectionState": "failed"}, {}),
            ({**SNAPSHOT, "iceConnectionState": "melted"}, {}),
            (SNAPSHOT, {"track_kind": "audio"}),
            (SNAPSHOT, {"codec": "opus", "codec_side": "remote"}),
    ):
        with pytest.raises(WebRtcAssertError):
            RUN["WR_webrtc_assert_connected"](bad, **kwargs)


def test_webrtc_assert_stats() -> None:
    from je_web_runner.utils.webrtc_assert.peer import WebRtcAssertError
    result = RUN["WR_webrtc_assert_stats"](STATS, direction="inbound", kind="video", min_bytes=1000)
    assert {"direction": "inbound", "kind": "video", "packets": 1000, "packets_lost": 5, "bytes": 64000,
            "jitter": 0.0} in result
    assert len(result) == 2 and json.dumps(result)
    for kwargs in ({"max_loss_ratio": 0.001}, {"direction": "outbound", "kind": "audio", "min_bytes": 9000},
                   {"direction": "inbound", "kind": "audio", "min_bytes": 1}):
        with pytest.raises(WebRtcAssertError):
            RUN["WR_webrtc_assert_stats"](STATS, **kwargs)


# ---------- webserial_mock ----------------------------------------------

def test_webserial_mock_push_and_assert_lines(driver: MagicMock) -> None:
    from je_web_runner.utils.webserial_mock.mock import WebserialMockError
    driver.execute_script.return_value = True
    assert RUN["WR_webserial_mock_push_lines"](["OK"], newline="\r\n") is True
    assert driver.execute_script.call_args.args[1] == [79, 75, 13, 10]
    chunks = [[65, 84, 10], [65, 84, 43, 71, 10]]
    assert RUN["WR_webserial_mock_assert_lines"](chunks, expected=["AT", "AT+G"]) is True
    assert json.dumps(chunks)
    with pytest.raises(WebserialMockError):
        RUN["WR_webserial_mock_assert_lines"](chunks, expected=["AT"])
    with pytest.raises(WebserialMockError):
        RUN["WR_webserial_mock_push_lines"]("not a list")
    with pytest.raises(WebserialMockError):
        RUN["WR_webserial_mock_install"](vendor_id=70000)


# ---------- websocket_assert --------------------------------------------

WS_URL = "wss://chat.example/socket"
WS_FRAMES = [
    {"direction": "sent", "url": WS_URL, "payload": '{"op": "subscribe", "topic": "prices"}'},
    {"direction": "received", "url": WS_URL, "payload": '{"op": "publish", "topic": "prices", "value": 3}'},
    {"direction": "received", "url": "wss://other.example/feed", "payload": "ping", "opcode": 9},
]


def test_websocket_assert_record_and_list() -> None:
    from je_web_runner.utils.websocket_assert.frames import WebSocketAssertError
    assert RUN["WR_websocket_assert_record"](WS_FRAMES) == 3
    received = RUN["WR_websocket_assert_frames"](direction="received", url_match=r"other\.example")
    assert [(frame["payload"], frame["opcode"]) for frame in received] == [("ping", 9)]
    assert json.dumps(RUN["WR_websocket_assert_frames"]())
    assert RUN["WR_websocket_assert_reset"]() is True
    assert RUN["WR_websocket_assert_frames"]() == []
    with pytest.raises(WebSocketAssertError):
        RUN["WR_websocket_assert_record"]([{"direction": "sideways", "url": WS_URL, "payload": "x"}])
    with pytest.raises(WebSocketAssertError):
        RUN["WR_websocket_assert_record"]("frames")


def test_websocket_assert_checks_pass_and_fail() -> None:
    from je_web_runner.utils.websocket_assert.frames import WebSocketAssertError
    with pytest.raises(WebSocketAssertError):
        RUN["WR_websocket_assert_frame_count"]()
    RUN["WR_websocket_assert_record"](WS_FRAMES)
    assert RUN["WR_websocket_assert_frame_count"](minimum=2, maximum=2, direction="received") == 2
    assert RUN["WR_websocket_assert_payload_contains"]("subscribe", direction="sent")["url"] == WS_URL
    assert RUN["WR_websocket_assert_json_shape"](["op", "value"])["direction"] == "received"
    assert RUN["WR_websocket_assert_pubsub"]("subscribe", "publish") is True
    for command, args in (
            ("WR_websocket_assert_frame_count", {"maximum": 1}),
            ("WR_websocket_assert_payload_contains", {"needle": "unsubscribe"}),
            ("WR_websocket_assert_json_shape", {"required_keys": ["missing"]}),
            ("WR_websocket_assert_pubsub", {"subscribe_contains": "publish", "publish_contains": "ping"}),
            ("WR_websocket_assert_pubsub", {"subscribe_contains": "", "publish_contains": "ping"}),
    ):
        with pytest.raises(WebSocketAssertError):
            RUN[command](**args)


# ---------- webtransport_assert -----------------------------------------

WT_FRAMES = [
    {"direction": "sent", "payload": "hello"},
    {"direction": "received", "channel": "datagram", "payload_hex": "00ff10"},
    {"direction": "received", "channel": "stream", "stream_id": 4, "payload": '{"seq": 1,'},
    {"direction": "received", "channel": "stream", "stream_id": 4, "payload": ' "done": true}', "fin": True},
    {"direction": "sent", "channel": "stream", "stream_id": 8, "payload": "partial"},
]


def test_webtransport_assert_record_and_list() -> None:
    from je_web_runner.utils.webtransport_assert.streams import WebTransportAssertError
    assert RUN["WR_webtransport_assert_record"](WT_FRAMES) == 5
    datagrams = RUN["WR_webtransport_assert_frames"](channel="datagram")
    assert [frame["payload_b64"] for frame in datagrams] == [b"hello".hex(), "00ff10"]
    assert datagrams[0]["payload_text"] == "hello"
    assert len(RUN["WR_webtransport_assert_frames"](direction="received", stream_id=4)) == 2
    assert json.dumps(RUN["WR_webtransport_assert_frames"]())
    assert RUN["WR_webtransport_assert_reset"]() is True
    assert RUN["WR_webtransport_assert_frames"]() == []
    for bad in ([{"direction": "received", "channel": "stream", "payload": "no stream id"}],
                [{"direction": "sent", "payload_hex": "zz"}], [{"direction": "up", "payload": "x"}], "frames"):
        with pytest.raises(WebTransportAssertError):
            RUN["WR_webtransport_assert_record"](bad)


def test_webtransport_assert_checks_pass_and_fail() -> None:
    from je_web_runner.utils.webtransport_assert.streams import WebTransportAssertError
    with pytest.raises(WebTransportAssertError):
        RUN["WR_webtransport_assert_datagram_count"]()
    RUN["WR_webtransport_assert_record"](WT_FRAMES)
    assert RUN["WR_webtransport_assert_datagram_count"](minimum=2, maximum=2) == 2
    assert RUN["WR_webtransport_assert_stream_complete"](4) == '{"seq": 1, "done": true}'
    found = RUN["WR_webtransport_assert_payload_contains"]("done", channel="stream")
    assert found["stream_id"] == 4 and found["fin"] is True
    for command, args in (
            ("WR_webtransport_assert_datagram_count", {"direction": "sent", "minimum": 2}),
            ("WR_webtransport_assert_stream_complete", {"stream_id": 8, "direction": "sent"}),
            ("WR_webtransport_assert_stream_complete", {"stream_id": 99}),
            ("WR_webtransport_assert_payload_contains", {"needle": "absent"}),
    ):
        with pytest.raises(WebTransportAssertError):
            RUN[command](**args)


# ---------- webusb_mock -------------------------------------------------

def test_webusb_mock_queue_in(driver: MagicMock) -> None:
    from je_web_runner.utils.webusb_mock.mock import WebusbMockError
    driver.execute_script.return_value = True
    assert RUN["WR_webusb_mock_queue_in"]([1, 2], endpoint=3) is True
    assert driver.execute_script.call_args.args[1:] == ("in_3", [1, 2])
    driver.execute_script.return_value = False
    assert RUN["WR_webusb_mock_queue_in"]([7]) is False
    assert driver.execute_script.call_args.args[1:] == ("controlIn", [7])
    for bad in ([300], ["1"], "12"):
        with pytest.raises(WebusbMockError):
            RUN["WR_webusb_mock_queue_in"](bad)
    with pytest.raises(WebusbMockError):
        RUN["WR_webusb_mock_install"]([{"vendor_id": 1155}])


def test_webusb_mock_assert_out() -> None:
    from je_web_runner.utils.webusb_mock.mock import WebusbMockError
    calls = [{"kind": "transferOut", "endpoint": 2, "data": [1, 2, 3]},
             {"kind": "controlOut", "setup": {"request": 9, "value": 1}, "data": []}]
    transfer = RUN["WR_webusb_mock_assert_out"](calls, endpoint=2, contains=[2, 3])
    assert transfer == {"kind": "transferOut", "endpoint": 2, "setup": None, "data": [1, 2, 3]}
    assert RUN["WR_webusb_mock_assert_out"](calls, request=9)["setup"] == {"request": 9, "value": 1}
    assert json.dumps(transfer)
    for kwargs in ({"endpoint": 5}, {"endpoint": 2, "contains": [9]}, {"request": 1}):
        with pytest.raises(WebusbMockError):
            RUN["WR_webusb_mock_assert_out"](calls, **kwargs)
    with pytest.raises(WebusbMockError):
        RUN["WR_webusb_mock_assert_out"](calls[:1])
