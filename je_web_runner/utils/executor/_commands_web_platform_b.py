"""
Web 平台 API 斷言的命令轉接層
Command adapters for the web-platform assertion libraries: 3-D Secure flows, View Transitions, Wake Lock,
Web Locks, Web Push, Web Share, WebAuthn, WebCodecs, WebGPU pixels, WebHID, WebRTC, Web Serial, WebSocket
and WebTransport frames, WebUSB.

Most libraries check a log that a shim in the page collects: ``..._install`` puts the library's shim into the
current page (after it loaded, before the feature is used; a navigation removes it), ``..._harvest`` reads
the log back, and the assert commands take that log as an argument, so a saved log needs no browser. The
WebSocket and WebTransport commands keep one recorder each for the run: ``..._record`` adds frames,
``..._reset`` empties it.
"""
# pylint: disable=import-outside-toplevel  # a library loads on first use; importing je_web_runner stays fast
from __future__ import annotations

from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import selenium_driver, to_plain

_DRAIN = "return window.{0} ? window.{0}.{1}() : [];"
_DRAIN_TWO = "return window.{0} ? {{{1}: window.{0}.{2}(), {3}: window.{0}.{4}()}} : {{{1}: [], {3}: []}};"
_PUSH = "if (!window.{0}) {{ return false; }} window.{0}.{1}(arguments[0], arguments[1]); return true;"
_VIEW_TRANSITIONS_HARVEST = "return window.__wr_vt_log__ || [];"
_WAKE_LOCK_HARVEST = _DRAIN.format("__wr_wakelock__", "drain")
_WEB_PUSH_HARVEST = _DRAIN_TWO.format("__wr_push__", "subscriptions", "drainSubs", "notifications", "drainShown")
_WEB_SHARE_HARVEST = _DRAIN_TWO.format("__wr_share__", "shares", "drainShares", "fallbacks", "drainFallbacks")
_WEBAUTHN_HARVEST = _DRAIN_TWO.format("__wr_webauthn__", "created", "drainCreated", "requested", "drainRequested")
_WEBCODECS_HARVEST = "return window.__wr_codec__ ? window.__wr_codec__.drain(arguments[0]) : [];"
_WEBGPU_CAPTURE = ("const done = arguments[arguments.length - 1];"
                   " ({0})(arguments[0]).then(done, (error) => done({{error: String(error)}}));")
_WEBHID_PUSH = "return window.__wr_hid__ ? window.__wr_hid__.pushReport(...arguments) : false;"
_WEBHID_HARVEST = _DRAIN.format("__wr_hid__", "drainOutgoing")
_WEBSERIAL_PUSH = _PUSH.format("__wr_serial__", "pushInbound")
_WEBSERIAL_HARVEST = _DRAIN.format("__wr_serial__", "drainOutbound")
_WEBUSB_QUEUE = _PUSH.format("__wr_usb__", "queueIn")
_WEBUSB_HARVEST = _DRAIN.format("__wr_usb__", "drainOutgoing")

_STATE: dict[str, Any] = {}


def _run(command: str, script: str, *args: Any) -> Any:
    """Run one of the fixed scripts above, or a library's own, in the current page."""
    return selenium_driver(command).execute_script(script, *args)


def _devices(devices: Any, error: type[Exception]) -> list[dict[str, Any]]:
    """Check that each fake device is an object with integer ``vendor_id`` and ``product_id``."""
    if not isinstance(devices, list) or not all(
            isinstance(item, dict) and isinstance(item.get("vendor_id"), int)
            and isinstance(item.get("product_id"), int) for item in devices):
        raise error("devices must be a list of objects with integer vendor_id and product_id")
    return devices


def _three_d_secure_flow(flow: dict[str, Any]) -> Any:
    """Build the library's ``Flow`` from its JSON form."""
    from je_web_runner.utils.three_d_secure_flow.flow import Flow, ThreeDSecureFlowError, TransStatus
    if not isinstance(flow, dict):
        raise ThreeDSecureFlowError("flow must be an object")
    try:
        return Flow(**{**flow, "trans_status": TransStatus(str(flow.get("trans_status", "U")))})
    except (TypeError, ValueError) as error:
        raise ThreeDSecureFlowError(f"malformed flow: {error}") from error


def three_d_secure_flow_classify(flow: dict[str, Any]) -> str:
    """Name the branch a 3-D Secure checkout took: frictionless_ok, challenge_ok, rejected, fallback, incomplete.

    :param flow: ``{"trans_status": "Y"|"N"|"C"|"R"|"A"|"U", "challenge_shown": bool, "cres_submitted": bool,
        "order_finalized": bool, "error_displayed": str, "pan_last4": str}``
    """
    from je_web_runner.utils.three_d_secure_flow.flow import classify
    return str(classify(_three_d_secure_flow(flow)).value)


def three_d_secure_flow_assert(flow: dict[str, Any], expected: str | None = None, error_contains: str = "") -> str:
    """Fail when a 3-D Secure checkout finalised a rejected card, skipped part of the challenge, did not end in
    the ``expected`` outcome, or was rejected without ``error_contains`` in its error; returns the outcome.
    """
    from je_web_runner.utils.three_d_secure_flow import flow as library
    built = _three_d_secure_flow(flow)
    library.assert_no_silent_finalize(built)
    library.assert_challenge_branch_complete(built)
    if expected is not None:
        if expected not in [outcome.value for outcome in library.Outcome]:
            raise library.ThreeDSecureFlowError(f"unknown expected outcome {expected!r}")
        library.assert_outcome(built, expected=library.Outcome(expected))
    library.assert_user_message_for(built, contains=error_contains)
    return str(library.classify(built).value)


def view_transitions_install() -> bool:
    """Start recording every ``document.startViewTransition`` call of the current page."""
    from je_web_runner.utils.view_transitions.transitions import build_instrumentation_script
    _run("WR_view_transitions_install", build_instrumentation_script())
    return True


def view_transitions_harvest() -> list[dict[str, Any]]:
    """Read the raw log of the view transitions the current page recorded."""
    return list(to_plain(_run("WR_view_transitions_harvest", _VIEW_TRANSITIONS_HARVEST) or []))


def view_transitions_assert(
        log: list[dict[str, Any]], max_duration_ms: float | None = None, max_cls: float = 0.1,
        max_single_shift: float = 0.05, group: str | None = None) -> list[dict[str, Any]]:
    """Fail when a recorded view transition did not finish, ran longer than ``max_duration_ms``, shifted the
    layout too much, or none animated the group ``group``; returns one record per transition.

    :param log: ``[{"id": "vt_1", "startedAt": 0, "finishedAt": 180, "durationMs": 180, "error": null,
        "layoutShifts": 0.01, "maxShiftValue": 0.01, "groups": ["hero"]}, ...]`` (the harvested log)
    """
    from je_web_runner.utils.view_transitions import transitions as library
    runs = library.parse_log(log)
    library.assert_all_finished(runs)
    if max_duration_ms is not None:
        library.assert_under_duration(runs, max_duration_ms=max_duration_ms)
    library.assert_cls_under(runs, max_cls=max_cls, max_single_shift=max_single_shift)
    if group is not None:
        library.assert_group_present(runs, group)
    return list(to_plain(runs))


def wake_lock_assert_install() -> bool:
    """Start recording the current page's ``navigator.wakeLock`` requests and releases."""
    from je_web_runner.utils.wake_lock_assert.lock import INSTALL_SCRIPT
    _run("WR_wake_lock_assert_install", INSTALL_SCRIPT)
    return True


def wake_lock_assert_harvest() -> list[dict[str, Any]]:
    """Take the wake-lock events the current page recorded (this empties the page's list)."""
    return list(to_plain(_run("WR_wake_lock_assert_harvest", _WAKE_LOCK_HARVEST) or []))


def wake_lock_assert_check(
        events: list[dict[str, Any]], released_by_app: bool = False, re_acquired: bool = False) -> dict[str, Any]:
    """Fail when the page never took a wake lock or never released one; returns the acquire and release counts.

    :param events: ``[{"kind": "acquire"|"release", "type": "screen", "ts": 0, "by": "app"|"os"}, ...]``
    :param released_by_app: also require a release made by the page itself, not only by the system
    :param re_acquired: also require a new acquire after the last release by the system
    """
    from je_web_runner.utils.wake_lock_assert import lock as library
    log = library.parse_log(events)
    library.assert_acquired(log)
    library.assert_no_leak(log)
    if released_by_app:
        library.assert_released_by_app(log)
    if re_acquired:
        library.assert_re_acquired_after_visibility(log)
    return {"acquired_count": log.acquired_count, "released_count": log.released_count}


def web_locks_install() -> bool:
    """Start recording the current page's ``navigator.locks.request`` calls."""
    from je_web_runner.utils.web_locks.locks import INSTALL_LISTENER_SCRIPT
    _run("WR_web_locks_install", INSTALL_LISTENER_SCRIPT)
    return True


def web_locks_harvest() -> list[dict[str, Any]]:
    """Read the raw Web Locks log the current page recorded."""
    from je_web_runner.utils.web_locks.locks import HARVEST_LOG_SCRIPT
    return list(to_plain(_run("WR_web_locks_harvest", HARVEST_LOG_SCRIPT) or []))


def web_locks_assert(
        log: list[dict[str, Any]], name: str | None = None, expected_acquired: int | None = None,
        if_available_refused: bool = False) -> list[dict[str, Any]]:
    """Fail when a recorded lock was never released, or the lock ``name`` was held twice at once, was not
    acquired ``expected_acquired`` times, or had no refused ``ifAvailable`` request; returns the lock events.

    :param log: ``[{"id": "1", "name": "cart", "outcome": "acquired"|"released"|"unavailable",
        "if_available": false, "time": 1.5}, ...]``
    """
    from je_web_runner.utils.web_locks import locks as library
    events = library.parse_log(log)
    library.assert_no_deadlock(events)
    if name is not None:
        library.assert_serialised(events, name=name)
        if expected_acquired is not None:
            library.assert_acquired_count(events, name=name, expected=expected_acquired)
        if if_available_refused:
            library.assert_if_available_unavailable(events, name=name)
    return list(to_plain(events))


def web_push_assert_install() -> bool:
    """Start recording the current page's push subscriptions and the notifications it shows."""
    from je_web_runner.utils.web_push_assert.push import INSTALL_SCRIPT
    _run("WR_web_push_assert_install", INSTALL_SCRIPT)
    return True


def web_push_assert_harvest() -> dict[str, Any]:
    """Take the push subscriptions and notifications the current page recorded (this empties its lists)."""
    return dict(to_plain(_run("WR_web_push_assert_harvest", _WEB_PUSH_HARVEST)))


def web_push_assert_check(
        log: dict[str, Any], vapid_public_key: str = "", require_notification: bool = False,
        body_contains: str = "") -> dict[str, Any]:
    """Fail when a push subscription is not user-visible-only, used another key than ``vapid_public_key``, or
    has an unknown push service; with ``require_notification`` also when no notification (containing
    ``body_contains``) was shown. Returns the normalised log.

    :param log: ``{"subscriptions": [{"applicationServerKey": "...", "userVisibleOnly": true, "endpoint": "..."}],
        "notifications": [{"title": "...", "body": "...", "tag": "..."}]}``
    """
    from je_web_runner.utils.web_push_assert import push as library
    parsed = library.parse_log(log)
    if vapid_public_key:
        library.assert_subscribed_with_vapid(parsed, vapid_public_key=vapid_public_key)
    library.assert_user_visible_only(parsed)
    library.assert_endpoint_recognised(parsed)
    if require_notification:
        library.assert_notification_shown(parsed, body_contains=body_contains)
    return dict(to_plain(parsed))


def web_share_assert_install(reject: bool = False, can_share: bool = True, can_share_files: bool = True) -> bool:
    """Replace the current page's ``navigator.share`` with a recorder; ``reject`` makes every share fail as if
    the user cancelled, ``can_share`` / ``can_share_files`` set what ``navigator.canShare`` answers.
    """
    from je_web_runner.utils.web_share_assert.share import INSTALL_SCRIPT
    settings = {"reject": bool(reject), "canShare": bool(can_share), "canShareFiles": bool(can_share_files)}
    _run("WR_web_share_assert_install", INSTALL_SCRIPT, settings)
    return True


def web_share_assert_harvest() -> dict[str, Any]:
    """Take the share calls and fallback marks the current page recorded (this empties its lists)."""
    return dict(to_plain(_run("WR_web_share_assert_harvest", _WEB_SHARE_HARVEST)))


def web_share_assert_check(
        log: dict[str, Any], expected_origin: str = "", field: str = "", fallback: bool = False) -> dict[str, Any]:
    """Fail when the page never shared (with ``fallback``: never showed its fallback UI), shared a URL of
    another origin than ``expected_origin``, or left ``field`` (title, text, url) empty. Returns
    the normalised log.

    :param log: ``{"shares": [{"title": "...", "text": "...", "url": "...", "filesCount": 0}],
        "fallbacks": [{"id": "copy-link", "ts": 0}]}``
    """
    from je_web_runner.utils.web_share_assert import share as library
    parsed = library.parse_log(log)
    if fallback:
        library.assert_fallback_shown(parsed)
    else:
        library.assert_shared(parsed)
    if expected_origin:
        library.assert_url_origin(parsed, expected_origin=expected_origin)
    if field:
        library.assert_has_field(parsed, field=field)
    return dict(to_plain(parsed))


def webauthn_mock_build_credential(user_handle: str, rp_id: str, sign_count: int = 0) -> dict[str, Any]:
    """Make a passkey record for a test user of the site ``rp_id``, as ``WR_webauthn_mock_install`` takes."""
    from je_web_runner.utils.webauthn_mock.mock import build_credential
    return dict(to_plain(build_credential(user_handle, rp_id, sign_count=sign_count)))


def webauthn_mock_install(credentials: list[dict[str, Any]]) -> int:
    """Replace the current page's ``navigator.credentials`` with an authenticator that answers with these
    passkeys (records from ``WR_webauthn_mock_build_credential``); returns how many were installed.
    """
    from je_web_runner.utils.webauthn_mock.mock import INSTALL_SCRIPT, WebauthnMockError
    if not isinstance(credentials, list) or not all(
            isinstance(item, dict) and item.get("id") for item in credentials):
        raise WebauthnMockError("credentials must be a list of objects with an id")
    _run("WR_webauthn_mock_install", INSTALL_SCRIPT, credentials)
    return len(credentials)


def webauthn_mock_harvest() -> dict[str, Any]:
    """Take the registration and sign-in ceremonies the current page started (this empties its lists)."""
    return dict(to_plain(_run("WR_webauthn_mock_harvest", _WEBAUTHN_HARVEST)))


def webauthn_mock_assert(
        log: dict[str, Any], registered: bool = True, signed_in: bool = False,
        user_verification: str | None = None) -> dict[str, int]:
    """Fail when the page did not start a registration (``registered``) or a sign-in (``signed_in``), or a
    ceremony asked for another level than ``user_verification`` (required, preferred, discouraged).

    :param log: ``{"created": [options of each credentials.create], "requested": [options of each get]}``
    """
    from je_web_runner.utils.webauthn_mock import mock as library
    parsed = library.parse_log(log)
    if registered:
        library.assert_registered(parsed)
    if signed_in:
        library.assert_signed_in(parsed)
    if user_verification is not None:
        library.assert_user_verification(parsed, level=user_verification)
    return {"created": len(parsed.created), "requested": len(parsed.requested)}


def webcodecs_assert_install() -> bool:
    """Add ``window.__wr_codec__`` to the current page; the page's encoder output callback has to call
    ``__wr_codec__.record("video"|"audio", chunk, metadata)``.
    """
    from je_web_runner.utils.webcodecs_assert.assertions import HARVEST_SCRIPT
    _run("WR_webcodecs_assert_install", HARVEST_SCRIPT)
    return True


def webcodecs_assert_harvest(kind: str = "video") -> list[dict[str, Any]]:
    """Take the encoded ``video`` or ``audio`` chunks the current page recorded (this empties that list)."""
    from je_web_runner.utils.webcodecs_assert.assertions import WebcodecsAssertError
    if kind not in ("video", "audio"):
        raise WebcodecsAssertError("kind must be 'video' or 'audio'")
    return list(to_plain(_run("WR_webcodecs_assert_harvest", _WEBCODECS_HARVEST, kind) or []))


def webcodecs_assert_check(
        chunks: list[dict[str, Any]], codec: str | None = None, resolution: list[int] | None = None,
        max_keyframe_gap: int | None = None, min_fps: float | None = None) -> dict[str, Any]:
    """Fail when encoded chunks miss the expected codec, ``resolution`` ([width, height]), key-frame spacing or
    frame rate; each is checked only when given. Returns the count, codecs and estimated frame rate.

    :param chunks: ``[{"type": "key"|"delta", "timestamp": microseconds, "byteLength": 0,
        "codec": "avc1.42001f", "width": 1280, "height": 720}, ...]``
    """
    from je_web_runner.utils.webcodecs_assert import assertions as library
    parsed = library.parse_chunks(chunks)
    if codec is not None:
        library.assert_codec(parsed, codec)
    if resolution is not None:
        library.assert_resolution(parsed, **dict(zip(("width", "height"), resolution, strict=True)))
    if max_keyframe_gap is not None:
        library.assert_keyframe_interval(parsed, max_gap=max_keyframe_gap)
    if min_fps is not None:
        library.assert_framerate_at_least(parsed, min_fps=min_fps)
    codecs = sorted({chunk.codec for chunk in parsed if chunk.codec})
    return {"count": len(parsed), "codecs": codecs, "framerate": library.estimate_framerate(parsed)}


def webgpu_pixel_verify_capture(selector: str) -> dict[str, Any]:
    """Read the pixels of the WebGPU ``<canvas>`` matching a CSS selector in the current page, as the frame
    ``{"width": int, "height": int, "rgba_b64": base64 of the raw RGBA bytes}`` the other commands take.
    """
    from je_web_runner.utils.webgpu_pixel_verify.pixel import HARVEST_SCRIPT, WebgpuPixelVerifyError, parse_frame
    script = _WEBGPU_CAPTURE.format(HARVEST_SCRIPT.strip().rstrip(";"))
    frame = selenium_driver("WR_webgpu_pixel_verify_capture").execute_async_script(script, str(selector))
    if isinstance(frame, dict) and frame.get("error"):
        raise WebgpuPixelVerifyError(f"canvas capture failed: {frame['error']}")
    parse_frame(frame)
    return dict(to_plain(frame))


def webgpu_pixel_verify_assert(
        frame: dict[str, Any], channel: str | None = None, min_value: float = 0.0, max_value: float = 255.0,
        allow_solid_color: bool = False) -> dict[str, Any]:
    """Fail when a captured frame is fully transparent, one solid colour (unless ``allow_solid_color``), or
    the mean of ``channel`` (r, g, b, a) is outside ``min_value``..``max_value``; returns size and means.
    """
    from je_web_runner.utils.webgpu_pixel_verify import pixel as library
    parsed = library.parse_frame(frame)
    library.assert_no_fully_transparent(parsed)
    if not allow_solid_color:
        library.assert_no_solid_color(parsed)
    if channel is not None:
        library.assert_mean_in_band(parsed, channel=channel, min_value=min_value, max_value=max_value)
    means = dict(zip("rgba", library.mean_rgba(parsed), strict=True))
    return {"width": parsed.width, "height": parsed.height, "mean_rgba": means}


def webgpu_pixel_verify_assert_similar(
        frame: dict[str, Any], reference: dict[str, Any], max_diff: float = 0.05) -> float:
    """Fail when a captured frame differs from a reference frame by more than ``max_diff`` (0 to 1)."""
    from je_web_runner.utils.webgpu_pixel_verify.pixel import assert_similar, parse_frame, tile_diff_score
    first, second = parse_frame(frame), parse_frame(reference)
    assert_similar(first, second, max_diff=max_diff)
    return float(tile_diff_score(first, second))


def webhid_mock_install(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace the current page's ``navigator.hid`` with fake devices; returns them.

    :param devices: ``[{"vendor_id": 1133, "product_id": 49948, "product_name": "Pad"}, ...]``
    """
    from je_web_runner.utils.webhid_mock.mock import INSTALL_SCRIPT, WebhidMockError, build_mock_device
    specs = [
        build_mock_device(item["vendor_id"], item["product_id"], str(item.get("product_name") or "")).to_dict()
        for item in _devices(devices, WebhidMockError)
    ]
    _run("WR_webhid_mock_install", INSTALL_SCRIPT, specs)
    return specs


def webhid_mock_push_report(report_id: int, data: list[int], device_index: int = 0) -> bool:
    """Send an input report (byte values 0-255) from a fake HID device to the current page; False when the
    page has not opened that device.
    """
    from je_web_runner.utils.webhid_mock.mock import build_input_report
    report = build_input_report(report_id, data)
    return bool(_run("WR_webhid_mock_push_report", _WEBHID_PUSH, int(device_index), report_id, report["data"]))


def webhid_mock_harvest() -> list[dict[str, Any]]:
    """Take the output reports the current page sent to the fake HID devices (this empties the list)."""
    return list(to_plain(_run("WR_webhid_mock_harvest", _WEBHID_HARVEST) or []))


def webhid_mock_assert_output(
        reports: list[dict[str, Any]], expected_count: int | None = None,
        contains: list[int] | None = None) -> list[dict[str, Any]]:
    """Fail when the page did not send ``expected_count`` output reports, or none contains the byte sequence
    ``contains``; returns the reports.

    :param reports: ``[{"reportId": 1, "data": [1, 2, 3]}, ...]``
    """
    from je_web_runner.utils.webhid_mock.mock import assert_output_reports, parse_outgoing
    parsed = parse_outgoing(reports)
    assert_output_reports(parsed, expected_count=expected_count, contains=contains)
    return list(to_plain(parsed))


def webrtc_assert_connected(
        snapshot: dict[str, Any], track_kind: str | None = None, track_side: str = "remote",
        codec: str | None = None, codec_side: str = "local") -> dict[str, Any]:
    """Fail when an ``RTCPeerConnection`` snapshot is not connected, has no live ``track_kind`` (audio, video)
    track on ``track_side``, or its ``codec_side`` SDP does not name ``codec``; returns the snapshot.

    :param snapshot: ``{"connectionState": "connected", "iceConnectionState": "completed", "localSdp": "...",
        "remoteSdp": "...", "localTracks": [{"kind": "audio", "readyState": "live"}], "remoteTracks": [...]}``
    """
    from je_web_runner.utils.webrtc_assert import peer as library
    parsed = library.PeerSnapshot.from_dict(snapshot)
    library.assert_connected(parsed)
    if track_kind is not None:
        library.assert_track_present(parsed, track_kind, side=track_side)
    if codec is not None:
        library.assert_sdp_has_codec(parsed, codec, side=codec_side)
    return dict(to_plain(library.export_snapshot(parsed)))


def webrtc_assert_stats(
        stats_report: list[dict[str, Any]], direction: str | None = None, max_loss_ratio: float = 0.01,
        kind: str | None = None, min_bytes: int | None = None) -> list[dict[str, Any]]:
    """Fail when a ``getStats()`` report shows more packet loss than ``max_loss_ratio`` (0 to 1), or fewer than
    ``min_bytes`` for a ``direction`` (inbound, outbound) and ``kind``; returns the totals per stream.

    :param stats_report: ``[{"type": "inbound-rtp", "kind": "audio", "packetsReceived": 1000,
        "packetsLost": 2, "bytesReceived": 64000, "jitter": 0.01}, ...]``
    """
    from je_web_runner.utils.webrtc_assert import peer as library
    stats = library.aggregate_stats(stats_report)
    library.assert_no_packet_loss(stats, direction=direction, max_loss_ratio=max_loss_ratio)
    if min_bytes is not None:
        library.assert_min_bytes_flowed(stats, direction=str(direction), kind=str(kind), minimum=min_bytes)
    return list(to_plain(stats))


def webserial_mock_install(vendor_id: int | None = None, product_id: int | None = None) -> dict[str, Any]:
    """Replace the current page's ``navigator.serial`` with one fake serial port; returns the port's ids."""
    from je_web_runner.utils.webserial_mock.mock import INSTALL_SCRIPT, build_mock_port
    port = dict(to_plain(build_mock_port(vendor_id, product_id)))
    _run("WR_webserial_mock_install", INSTALL_SCRIPT, port)
    return port


def webserial_mock_push_lines(lines: list[str], newline: str = "\n") -> bool:
    """Make the fake serial port deliver text lines to the current page; False when it is not installed."""
    from je_web_runner.utils.webserial_mock.mock import encode_lines
    return bool(_run("WR_webserial_mock_push_lines", _WEBSERIAL_PUSH, encode_lines(lines, newline)))


def webserial_mock_harvest() -> list[list[int]]:
    """Take the byte chunks the current page wrote to the fake serial port (this empties the list)."""
    return list(to_plain(_run("WR_webserial_mock_harvest", _WEBSERIAL_HARVEST) or []))


def webserial_mock_assert_lines(chunks: list[list[int]], expected: list[str], newline: str = "\n") -> bool:
    """Fail when the lines the page wrote to the serial port (lists of byte values) are not ``expected``."""
    from je_web_runner.utils.webserial_mock.mock import assert_lines_written, parse_outbound
    assert_lines_written(parse_outbound(chunks), expected=expected, newline=newline)
    return True


def _websocket_recorder() -> Any:
    """The run's WebSocket frame recorder, created on first use."""
    if "websocket" not in _STATE:
        from je_web_runner.utils.websocket_assert.frames import WsFrameRecorder
        _STATE["websocket"] = WsFrameRecorder()
    return _STATE["websocket"]


def websocket_assert_reset() -> bool:
    """Forget every recorded WebSocket frame."""
    _websocket_recorder().clear()
    return True


def websocket_assert_record(frames: list[dict[str, Any]]) -> int:
    """Add WebSocket frames to the recorder; returns how many it now holds.

    :param frames: ``[{"direction": "sent"|"received", "url": "wss://...", "payload": "text", "opcode": 1}, ...]``
    """
    from je_web_runner.utils.websocket_assert.frames import WebSocketAssertError, WsFrame
    if not isinstance(frames, list) or not all(isinstance(item, dict) for item in frames):
        raise WebSocketAssertError("frames must be a list of objects")
    for item in frames:
        _websocket_recorder().record(WsFrame(
            direction=str(item.get("direction")), url=str(item.get("url") or ""),
            payload=str(item.get("payload") or ""), opcode=int(item.get("opcode", 1)),
        ))
    return len(_websocket_recorder())


def websocket_assert_frames(direction: str | None = None, url_match: str | None = None) -> list[dict[str, Any]]:
    """List the recorded WebSocket frames, optionally one direction or URLs matching a regular expression."""
    return list(to_plain(_websocket_recorder().frames(direction=direction, url_match=url_match)))


def websocket_assert_frame_count(
        minimum: int = 1, maximum: int | None = None, direction: str | None = None,
        url_match: str | None = None) -> int:
    """Fail when the number of recorded WebSocket frames is outside ``minimum``..``maximum``; returns it."""
    from je_web_runner.utils.websocket_assert.frames import assert_frame_count
    return int(assert_frame_count(
        _websocket_recorder(), direction=direction, url_match=url_match, minimum=minimum, maximum=maximum))


def websocket_assert_payload_contains(needle: str, direction: str | None = None) -> dict[str, Any]:
    """Fail when no recorded WebSocket frame's text contains ``needle``; returns the first that does."""
    from je_web_runner.utils.websocket_assert.frames import assert_payload_contains
    return dict(to_plain(assert_payload_contains(_websocket_recorder(), needle, direction=direction)))


def websocket_assert_json_shape(required_keys: list[str], direction: str | None = "received") -> dict[str, Any]:
    """Fail when no recorded WebSocket frame is a JSON object with all of ``required_keys``."""
    from je_web_runner.utils.websocket_assert.frames import assert_json_shape
    return dict(to_plain(assert_json_shape(_websocket_recorder(), required_keys, direction=direction)))


def websocket_assert_pubsub(subscribe_contains: str, publish_contains: str) -> bool:
    """Fail unless a sent frame containing ``subscribe_contains`` came before the first received frame
    containing ``publish_contains``.
    """
    from je_web_runner.utils.websocket_assert.frames import WebSocketAssertError, assert_pubsub_pattern
    if not subscribe_contains or not publish_contains:
        raise WebSocketAssertError("subscribe_contains and publish_contains must be non-empty text")
    assert_pubsub_pattern(
        _websocket_recorder(),
        subscribe_matcher=lambda frame: subscribe_contains in frame.payload,
        publish_matcher=lambda frame: publish_contains in frame.payload,
    )
    return True


def _webtransport_recorder() -> Any:
    """The run's WebTransport frame recorder, created on first use."""
    if "webtransport" not in _STATE:
        from je_web_runner.utils.webtransport_assert.streams import WtFrameRecorder
        _STATE["webtransport"] = WtFrameRecorder()
    return _STATE["webtransport"]


def _webtransport_plain(frame: Any) -> dict[str, Any]:
    """A recorded frame as JSON: the library's form (payload as hex) plus the payload decoded as text."""
    return {**to_plain(frame), "payload_text": frame.as_text()}


def webtransport_assert_reset() -> bool:
    """Forget every recorded WebTransport frame."""
    _webtransport_recorder().clear()
    return True


def webtransport_assert_record(frames: list[dict[str, Any]]) -> int:
    """Add WebTransport datagrams and stream chunks to the recorder; returns how many it now holds.

    :param frames: ``[{"direction": "sent"|"received", "channel": "datagram"|"stream", "payload": "text",
        "stream_id": 4, "fin": true}, ...]``; ``payload_hex`` instead of ``payload`` gives binary data,
        ``channel`` defaults to ``datagram``, a stream chunk needs ``stream_id``
    """
    from je_web_runner.utils.webtransport_assert.streams import DATAGRAM, WebTransportAssertError, WtFrame
    if not isinstance(frames, list) or not all(isinstance(item, dict) for item in frames):
        raise WebTransportAssertError("frames must be a list of objects")
    for item in frames:
        try:
            payload = bytes.fromhex(item["payload_hex"]) if "payload_hex" in item else str(
                item.get("payload") or "").encode("utf-8")
        except (TypeError, ValueError) as error:
            raise WebTransportAssertError(f"payload_hex is not hexadecimal text: {error}") from error
        _webtransport_recorder().record(WtFrame(
            direction=str(item.get("direction")), channel=str(item.get("channel") or DATAGRAM),
            payload=payload, stream_id=item.get("stream_id"), fin=bool(item.get("fin", False)),
        ))
    return len(_webtransport_recorder())


def webtransport_assert_frames(
        direction: str | None = None, channel: str | None = None, stream_id: int | None = None) -> list[dict[str, Any]]:
    """List the recorded WebTransport frames, optionally only one direction, channel or stream."""
    frames = _webtransport_recorder().frames(direction=direction, channel=channel, stream_id=stream_id)
    return [_webtransport_plain(frame) for frame in frames]


def webtransport_assert_datagram_count(
        minimum: int = 1, maximum: int | None = None, direction: str | None = None) -> int:
    """Fail when the number of recorded datagrams is outside ``minimum``..``maximum``; returns it."""
    from je_web_runner.utils.webtransport_assert.streams import assert_datagram_count
    return int(assert_datagram_count(
        _webtransport_recorder(), direction=direction, minimum=minimum, maximum=maximum))


def webtransport_assert_stream_complete(stream_id: int, direction: str = "received") -> str:
    """Fail when a recorded stream has no chunks or did not end with FIN; returns the stream's text."""
    from je_web_runner.utils.webtransport_assert.streams import assert_stream_complete
    data = assert_stream_complete(_webtransport_recorder(), stream_id, direction=direction)
    return data.decode("utf-8", errors="replace")


def webtransport_assert_payload_contains(
        needle: str, direction: str | None = None, channel: str | None = None) -> dict[str, Any]:
    """Fail when no recorded WebTransport frame contains the text ``needle``; returns the first that does."""
    from je_web_runner.utils.webtransport_assert.streams import assert_payload_contains
    return _webtransport_plain(assert_payload_contains(
        _webtransport_recorder(), str(needle).encode("utf-8"), direction=direction, channel=channel))


def webusb_mock_install(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace the current page's ``navigator.usb`` with fake devices; returns them.

    :param devices: ``[{"vendor_id": 1155, "product_id": 22336, "product_name": "Probe", "serial_number": "A1"}]``
    """
    from je_web_runner.utils.webusb_mock.mock import INSTALL_SCRIPT, WebusbMockError, build_mock_device
    specs = [
        build_mock_device(
            item["vendor_id"], item["product_id"], product_name=str(item.get("product_name") or ""),
            serial_number=str(item.get("serial_number") or "")).to_dict()
        for item in _devices(devices, WebusbMockError)
    ]
    _run("WR_webusb_mock_install", INSTALL_SCRIPT, specs)
    return specs


def webusb_mock_queue_in(data: list[int], endpoint: int | None = None) -> bool:
    """Queue the bytes (0-255) the fake USB device answers to the page's next ``transferIn`` on ``endpoint``,
    or next ``controlTransferIn`` when no endpoint is given; False when the mock is not installed.
    """
    from je_web_runner.utils.webusb_mock.mock import WebusbMockError
    if not isinstance(data, list) or not all(isinstance(item, int) and 0 <= item <= 255 for item in data):
        raise WebusbMockError("data must be a list of integers in 0..255")
    kind = "controlIn" if endpoint is None else f"in_{int(endpoint)}"
    return bool(_run("WR_webusb_mock_queue_in", _WEBUSB_QUEUE, kind, data))


def webusb_mock_harvest() -> list[dict[str, Any]]:
    """Take the OUT transfers the current page sent to the fake USB device (this empties the list)."""
    return list(to_plain(_run("WR_webusb_mock_harvest", _WEBUSB_HARVEST) or []))


def webusb_mock_assert_out(
        calls: list[dict[str, Any]], endpoint: int | None = None, contains: list[int] | None = None,
        request: int | None = None) -> dict[str, Any]:
    """Fail when the page made no ``transferOut`` on ``endpoint`` (holding the bytes ``contains``) or, with no
    endpoint given, no ``controlTransferOut`` (with setup ``request``); returns the matching transfer.

    :param calls: ``[{"kind": "transferOut", "endpoint": 2, "data": [1, 2]},
        {"kind": "controlOut", "setup": {"request": 9}, "data": []}]``
    """
    from je_web_runner.utils.webusb_mock import mock as library
    parsed = library.parse_outgoing(calls)
    if endpoint is None:
        return dict(to_plain(library.assert_control_out(parsed, request=request)))
    return dict(to_plain(library.assert_transfer_out(parsed, endpoint=endpoint, contains=contains)))


WEB_PLATFORM_B_COMMANDS: dict[str, Callable[..., Any]] = {
    f"WR_{function.__name__}": function for function in (
        three_d_secure_flow_classify, three_d_secure_flow_assert,
        view_transitions_install, view_transitions_harvest, view_transitions_assert,
        wake_lock_assert_install, wake_lock_assert_harvest, wake_lock_assert_check,
        web_locks_install, web_locks_harvest, web_locks_assert,
        web_push_assert_install, web_push_assert_harvest, web_push_assert_check,
        web_share_assert_install, web_share_assert_harvest, web_share_assert_check,
        webauthn_mock_build_credential, webauthn_mock_install, webauthn_mock_harvest, webauthn_mock_assert,
        webcodecs_assert_install, webcodecs_assert_harvest, webcodecs_assert_check,
        webgpu_pixel_verify_capture, webgpu_pixel_verify_assert, webgpu_pixel_verify_assert_similar,
        webhid_mock_install, webhid_mock_push_report, webhid_mock_harvest, webhid_mock_assert_output,
        webrtc_assert_connected, webrtc_assert_stats,
        webserial_mock_install, webserial_mock_push_lines, webserial_mock_harvest, webserial_mock_assert_lines,
        websocket_assert_reset, websocket_assert_record, websocket_assert_frames, websocket_assert_frame_count,
        websocket_assert_payload_contains, websocket_assert_json_shape, websocket_assert_pubsub,
        webtransport_assert_reset, webtransport_assert_record, webtransport_assert_frames,
        webtransport_assert_datagram_count, webtransport_assert_stream_complete,
        webtransport_assert_payload_contains,
        webusb_mock_install, webusb_mock_queue_in, webusb_mock_harvest, webusb_mock_assert_out,
    )
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset()
