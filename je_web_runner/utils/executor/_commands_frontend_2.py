"""
前端檢查與瀏覽器工具的命令轉接層（第二部分）
Command adapters for the front-end checks, part two: touch gestures, the viewport meta tag, the on-screen
keyboard, geolocation / timezone / locale overrides, named tabs, page-object generation, browser state
diffs, Storybook plans, visual-diff review, the WebAuthn virtual authenticator, form auto-fill plans,
cross-browser parity, browser-extension loading and the GitHub pull-request summary comment.
Part one is ``_commands_frontend.py``.
"""
# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it
from __future__ import annotations

from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import (
    page_source,
    selenium_driver,
    selenium_only_driver,
    to_plain,
)
from je_web_runner.utils.executor._commands_frontend import _harvest, _problems

_STATE: dict[str, Any] = {}


# ---------- touch_gesture -----------------------------------------------

def _cdp_frames(frames: Any) -> list[dict[str, Any]]:
    return [frame.to_cdp() for frame in frames]


def touch_gesture_tap(point_x: float, point_y: float, hold_ms: int = 0) -> list[dict[str, Any]]:
    """
    Build the touch frames of a tap, or of a long press when ``hold_ms`` is 500 or more.

    :return: ``Input.dispatchTouchEvent`` payloads for ``WR_touch_gesture_dispatch``
    """
    from je_web_runner.utils.touch_gesture import gesture
    if hold_ms:
        return _cdp_frames(gesture.long_press(point_x, point_y, hold_ms=hold_ms))
    return _cdp_frames(gesture.tap(point_x, point_y))


def touch_gesture_swipe(
        start_x: float, start_y: float, end_x: float, end_y: float, steps: int = 8) -> dict[str, Any]:
    """
    Build the touch frames of a one-finger swipe.

    :return: ``{"frames": [Input.dispatchTouchEvent payload, ...], "distance_px": n}``
    """
    from je_web_runner.utils.touch_gesture import gesture
    frames = gesture.swipe((start_x, start_y), (end_x, end_y), steps=steps)
    return {"frames": _cdp_frames(frames), "distance_px": gesture.gesture_distance_px(frames)}


def touch_gesture_pinch(
        center_x: float, center_y: float, start_radius: float, end_radius: float, steps: int = 8,
) -> list[dict[str, Any]]:
    """
    Build the touch frames of a two-finger pinch around a point (spread when ``end_radius`` is larger).

    :return: ``Input.dispatchTouchEvent`` payloads for ``WR_touch_gesture_dispatch``
    """
    from je_web_runner.utils.touch_gesture import gesture
    centre = (center_x, center_y)
    return _cdp_frames(gesture.pinch(centre, start_radius=start_radius, end_radius=end_radius, steps=steps))


def touch_gesture_dispatch(frames: list[dict[str, Any]]) -> int:
    """Send touch frames built by the ``WR_touch_gesture_*`` commands to the current page (Chromium)."""
    from je_web_runner.utils.touch_gesture.gesture import Phase, TouchGestureError
    phases = {phase.value for phase in Phase}
    for frame in frames:
        if not isinstance(frame, dict) or frame.get("type") not in phases:
            raise TouchGestureError(f"not a touch frame: {frame!r}")
    driver = selenium_driver("WR_touch_gesture_dispatch")
    for frame in frames:
        driver.execute_cdp_cmd("Input.dispatchTouchEvent", frame)
    return len(frames)


def touch_gesture_assert_received(
        events: list[dict[str, Any]], event_type: str = "touchstart", two_finger: bool = False) -> int:
    """
    Fail unless the page recorded a touch event of ``event_type`` (and, with ``two_finger``, a two-finger one).

    :param events: ``[{"type": "touchstart"|"touchmove"|"touchend"|"touchcancel", "touchCount": n,
        "target": str}, ...]`` as the page's own listener recorded them
    :return: the number of recorded events
    """
    from je_web_runner.utils.touch_gesture import gesture
    recorded = gesture.parse_touch_events(events)
    gesture.assert_received(recorded, event_type=event_type)
    if two_finger:
        gesture.assert_two_finger(recorded)
    return len(recorded)


# ---------- viewport_audit ----------------------------------------------

def _viewport_report(html: str, notch_aware: bool) -> dict[str, Any]:
    from je_web_runner.utils.viewport_audit import audit
    meta = audit.parse_meta(html)
    checks: list[Callable[[], Any]] = [partial(audit.assert_meta_present, meta)]
    if meta is not None:
        checks.append(partial(audit.assert_responsive_width, meta))
        checks.append(partial(audit.assert_user_scalable_allowed, meta))
        if notch_aware:
            checks.append(partial(audit.assert_notch_aware, meta))
    problems = _problems(checks, audit.ViewportAuditError)
    return {
        "present": meta is not None,
        "content": meta.content if meta is not None else "",
        "parsed": dict(meta.parsed) if meta is not None else {},
        "passed": not problems,
        "problems": problems,
    }


def viewport_audit_check(html: str, notch_aware: bool = False) -> dict[str, Any]:
    """
    Report what is wrong with the ``<meta name="viewport">`` of an HTML document.

    :param notch_aware: also require ``viewport-fit=cover``
    :return: ``{"present": bool, "content": str, "parsed": {...}, "passed": bool, "problems": [message, ...]}``
    """
    return _viewport_report(html, notch_aware)


def viewport_audit_check_page(notch_aware: bool = False) -> dict[str, Any]:
    """Report what is wrong with the viewport meta tag of the current page."""
    return _viewport_report(page_source("WR_viewport_audit_check_page"), notch_aware)


def viewport_audit_assert_meta(html: str, notch_aware: bool = False) -> str:
    """Fail when an HTML document has no viewport meta tag, a fixed width or disabled pinch-zoom."""
    from je_web_runner.utils.viewport_audit import audit
    meta = audit.parse_meta(html)
    audit.assert_responsive_width(meta)
    audit.assert_user_scalable_allowed(meta)
    if notch_aware:
        audit.assert_notch_aware(meta)
    return str(meta.content) if meta is not None else ""


def viewport_audit_safe_area_page() -> dict[str, Any]:
    """Read the four computed paddings of the current page's ``<body>`` (for the safe-area check)."""
    from je_web_runner.utils.viewport_audit.audit import HARVEST_SCRIPT, parse_safe_area
    return dict(to_plain(parse_safe_area(_harvest("WR_viewport_audit_safe_area_page", HARVEST_SCRIPT))))


def viewport_audit_assert_safe_area(payload: dict[str, Any]) -> bool:
    """
    Fail when the body has no padding on any side, so a notch would cover the content.

    :param payload: ``{"padding_top": "47px", "padding_bottom": "34px", "padding_left": "0px",
        "padding_right": "0px"}`` as returned by ``WR_viewport_audit_safe_area_page``
    """
    from je_web_runner.utils.viewport_audit import audit
    audit.assert_safe_area_padding(audit.parse_safe_area(payload))
    return True


# ---------- virtual_keyboard --------------------------------------------

def virtual_keyboard_snapshot_page() -> dict[str, Any]:
    """
    Read the visual viewport of the current page; take one before and one after the keyboard shows.

    :return: ``{"viewport_width": n, "viewport_height": n, "scale": n, "offset_top": n, "keyboard_inset": str}``
    """
    from je_web_runner.utils.virtual_keyboard.keyboard import HARVEST_SCRIPT, parse_snapshot
    return dict(to_plain(parse_snapshot(_harvest("WR_virtual_keyboard_snapshot_page", HARVEST_SCRIPT))))


def virtual_keyboard_assert_shrunk(
        before: dict[str, Any], after: dict[str, Any], min_height_delta_px: float = 100) -> float:
    """
    Fail unless the visual viewport became at least ``min_height_delta_px`` shorter when the keyboard showed.

    :param before: a snapshot from ``WR_virtual_keyboard_snapshot_page``; ``after``: one with the keyboard open
    :return: how many pixels the viewport shrank
    """
    from je_web_runner.utils.virtual_keyboard import keyboard
    first = keyboard.parse_snapshot(before)
    second = keyboard.parse_snapshot(after)
    keyboard.assert_keyboard_shrunk(before=first, after=second, min_height_delta_px=min_height_delta_px)
    return float(first.viewport_height - second.viewport_height)


def virtual_keyboard_assert_inset_set(snapshot: dict[str, Any]) -> str:
    """Fail when the page did not mirror the keyboard height into ``--keyboard-inset-height``."""
    from je_web_runner.utils.virtual_keyboard import keyboard
    parsed = keyboard.parse_snapshot(snapshot)
    keyboard.assert_keyboard_inset_set(parsed)
    return str(parsed.keyboard_inset).strip()


def virtual_keyboard_assert_focused_visible(after: dict[str, Any], focused: dict[str, Any]) -> bool:
    """
    Fail when the focused element sits behind the on-screen keyboard.

    :param after: the snapshot taken with the keyboard open
    :param focused: ``{"selector": str, "top": n, "bottom": n}``, the focused element's box in CSS pixels
    """
    from je_web_runner.utils.virtual_keyboard import keyboard
    if not isinstance(focused, dict):
        raise keyboard.VirtualKeyboardError("focused must be an object")
    box = keyboard.FocusedElementBox(
        selector=str(focused.get("selector") or ""),
        top=float(focused.get("top") or 0),
        bottom=float(focused.get("bottom") or 0),
    )
    keyboard.assert_focused_visible(after=keyboard.parse_snapshot(after), focused=box)
    return True


# ---------- geo_locale ---------------------------------------------------

def geo_locale_payloads(
        latitude: float | None = None, longitude: float | None = None,
        timezone: str | None = None, locale: str | None = None, accuracy_meters: float = 50.0,
) -> dict[str, Any]:
    """
    Build the CDP commands and the Playwright context arguments of a location / timezone / locale override.

    :param timezone: IANA name such as ``"Asia/Taipei"``; ``locale``: such as ``"zh-TW"``
    :return: ``{"cdp": [{"method": str, "params": {...}}, ...], "playwright": {...}}``
    """
    from je_web_runner.utils.geo_locale import geo_locale as library
    override = library.GeoOverride(latitude, longitude, accuracy_meters, timezone, locale)
    return {"cdp": library.cdp_payloads(override), "playwright": library.playwright_context_kwargs(override)}


def geo_locale_apply(
        latitude: float | None = None, longitude: float | None = None,
        timezone: str | None = None, locale: str | None = None, accuracy_meters: float = 50.0,
) -> list[str]:
    """Override the location, timezone and locale of the running browser (Chromium); returns the CDP methods."""
    from je_web_runner.utils.geo_locale import geo_locale as library
    override = library.GeoOverride(latitude, longitude, accuracy_meters, timezone, locale)
    return library.apply_overrides(selenium_driver("WR_geo_locale_apply"), override)


# ---------- multi_tab ----------------------------------------------------

def _tabs() -> Any:
    """The one tab choreographer the ``WR_multi_tab_*`` commands share."""
    from je_web_runner.utils.multi_tab.choreographer import TabChoreographer
    if "tabs" not in _STATE:
        _STATE["tabs"] = TabChoreographer()
    return _STATE["tabs"]


def _tab_driver(command: str) -> Any:
    """The Selenium driver: the tab names stand for its window handles."""
    return selenium_only_driver(command, "Selenium window handles")


def multi_tab_register(alias: str) -> dict[str, Any]:
    """Give the current browser tab a name, so later commands can switch back to it."""
    return dict(to_plain(_tabs().register_current(_tab_driver("WR_multi_tab_register"), alias)))


def multi_tab_open(alias: str) -> dict[str, Any]:
    """Open a blank tab, switch to it and name it ``alias`` (follow with ``WR_to_url`` to load a page)."""
    return dict(to_plain(_tabs().open_new(_tab_driver("WR_multi_tab_open"), alias)))


def multi_tab_switch(alias: str) -> dict[str, Any]:
    """Switch the browser to the tab named ``alias``."""
    return dict(to_plain(_tabs().switch_to(_tab_driver("WR_multi_tab_switch"), alias)))


def multi_tab_close(alias: str) -> list[str]:
    """Close the tab named ``alias``; returns the names still known."""
    _tabs().close(_tab_driver("WR_multi_tab_close"), alias)
    return list(_tabs().aliases())


def multi_tab_reset() -> list[str]:
    """Forget every tab name (tabs stay open); returns the names that were known."""
    known = list(_tabs().aliases())
    _STATE.pop("tabs", None)
    return known


# ---------- pom_codegen --------------------------------------------------

def pom_codegen_render(html: str, class_name: str = "WebRunnerPage") -> dict[str, Any]:
    """
    Generate a Python page-object class from the ``data-testid`` / ``id`` / ``name`` elements of some HTML.

    :return: ``{"source": the module text, "elements": [{"name", "strategy", "value", "tag", "source"}, ...]}``
    """
    from je_web_runner.utils.pom_codegen import codegen
    elements = codegen.discover_elements_from_html(html)
    return {"source": codegen.render_pom_module(elements, class_name), "elements": to_plain(elements)}


def pom_codegen_render_page(class_name: str = "WebRunnerPage") -> dict[str, Any]:
    """Generate a Python page-object class from the current page (result as ``WR_pom_codegen_render``)."""
    return pom_codegen_render(page_source("WR_pom_codegen_render_page"), class_name)


# ---------- state_diff ---------------------------------------------------

def _state_diff(before: dict[str, Any], after: dict[str, Any]) -> Any:
    from je_web_runner.utils.state_diff import diff as library
    built = []
    for raw in (before, after):
        if not isinstance(raw, dict):
            raise library.StateDiffError("a state snapshot must be an object")
        built.append(library.BrowserStateSnapshot(
            cookies=dict(raw.get("cookies") or {}),
            local_storage=dict(raw.get("local_storage") or {}),
            session_storage=dict(raw.get("session_storage") or {}),
        ))
    return library.diff_states(built[0], built[1])


def state_diff_capture() -> dict[str, Any]:
    """
    Snapshot the cookies, localStorage and sessionStorage of the current page.

    :return: ``{"cookies": {name: cookie}, "local_storage": {key: value}, "session_storage": {key: value}}``
    """
    from je_web_runner.utils.state_diff.diff import capture_state
    return dict(to_plain(capture_state(selenium_driver("WR_state_diff_capture"))))


def state_diff_compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """
    List what was added, removed or changed between two snapshots from ``WR_state_diff_capture``.

    :return: ``{"has_changes": bool, "cookies": {"added": {...}, "removed": {...}, "changed": {key: [old, new]}},
        "local_storage": {...}, "session_storage": {...}}``
    """
    diff = _state_diff(before, after)
    return {"has_changes": diff.has_changes, **to_plain(diff)}


def state_diff_assert_no_change(
        before: dict[str, Any], after: dict[str, Any], allow_keys: list[str] | None = None) -> bool:
    """Fail when a cookie or storage key outside ``allow_keys`` differs between two snapshots."""
    from je_web_runner.utils.state_diff.diff import assert_no_state_change
    assert_no_state_change(_state_diff(before, after), allow_keys)
    return True


# ---------- storybook ----------------------------------------------------

def _stories(source: str | dict[str, Any], skip_examples: bool, title_prefix: str | None) -> list[Any]:
    from je_web_runner.utils.storybook import discovery
    stories = discovery.discover_stories(source, skip_examples=skip_examples)
    return discovery.filter_stories_by_kind(stories, title_prefix) if title_prefix else stories


def storybook_discover(
        source: str | dict[str, Any], skip_examples: bool = True, title_prefix: str | None = None,
) -> list[dict[str, Any]]:
    """
    List the stories of a Storybook ``index.json`` / ``stories.json`` (a file path or the parsed object).

    :param title_prefix: keep only stories whose title starts with this, e.g. ``"Components/"``
    :return: ``[{"id", "title", "name", "kind", "parameters", "iframe_path"}, ...]``
    """
    stories = _stories(source, skip_examples, title_prefix)
    return [{**to_plain(story), "iframe_path": story.iframe_path} for story in stories]


def storybook_plan_actions(
        source: str | dict[str, Any], base_url: str, run_a11y: bool = True,
        capture_screenshot: bool = True, title_prefix: str | None = None,
) -> list[list[Any]]:
    """
    Build an action list that opens every story under ``base_url``, audits it and takes a screenshot.

    :return: actions such as ``["WR_to_url", {"url": ...}]``, ready to run or to save as an action file
    """
    from je_web_runner.utils.storybook.discovery import plan_actions_for_stories
    return plan_actions_for_stories(
        _stories(source, True, title_prefix), base_url, run_a11y=run_a11y, capture_screenshot=capture_screenshot,
    )


# ---------- visual_review ------------------------------------------------

def visual_review_list(baseline_dir: str, current_dir: str) -> list[dict[str, str]]:
    """
    Pair the PNG files of a baseline and a current directory by name and say how each pair stands.

    :return: ``[{"name": str, "status": "match"|"diff"|"missing-baseline"|"missing-current"}, ...]``
    """
    from je_web_runner.utils.visual_review.review_server import list_diffs
    return list_diffs(baseline_dir, current_dir)


def visual_review_accept(baseline_dir: str, current_dir: str, name: str) -> str:
    """Accept a changed screenshot: copy ``current_dir/name`` over the baseline; returns the baseline path."""
    from je_web_runner.utils.visual_review.review_server import accept_baseline
    return str(accept_baseline(baseline_dir, current_dir, name))


def visual_review_assert_no_diffs(baseline_dir: str, current_dir: str) -> int:
    """Fail when a screenshot differs from, or is missing on either side of, its baseline; returns the count."""
    from je_web_runner.utils.visual_review.review_server import VisualReviewError, list_diffs
    pairs = list_diffs(baseline_dir, current_dir)
    pending = [f"{pair['name']} ({pair['status']})" for pair in pairs if pair["status"] != "match"]
    if pending:
        raise VisualReviewError(f"{len(pending)} screenshot(s) need review: {pending[:5]}")
    return len(pairs)


# ---------- webauthn -----------------------------------------------------

def _authenticator(authenticator_id: str) -> Any:
    from je_web_runner.utils.webauthn.virtual_authenticator import VirtualAuthenticator, WebAuthnError
    if not isinstance(authenticator_id, str) or not authenticator_id:
        raise WebAuthnError("authenticator_id must be the id WR_webauthn_enable returned")
    return VirtualAuthenticator(authenticator_id=authenticator_id)


def webauthn_enable(
        protocol: str = "ctap2", transport: str = "internal", has_resident_key: bool = True,
        has_user_verification: bool = True, is_user_verified: bool = True,
) -> dict[str, Any]:
    """
    Add a virtual passkey authenticator to the running browser (Chromium), so sign-in needs no hardware.

    :return: ``{"authenticator_id": str, "protocol": str, "transport": str, ...}``
    """
    from je_web_runner.utils.webauthn.virtual_authenticator import enable_virtual_authenticator
    return dict(to_plain(enable_virtual_authenticator(
        selenium_driver("WR_webauthn_enable"), protocol, transport,
        has_resident_key, has_user_verification, is_user_verified,
    )))


def webauthn_add_credential(authenticator_id: str, credential: dict[str, Any]) -> bool:
    """
    Put a credential into a virtual authenticator.

    :param credential: the CDP ``WebAuthn.Credential``: ``{"credentialId": base64, "isResidentCredential": bool,
        "rpId": str, "privateKey": base64, "userHandle": base64, "signCount": n}``
    """
    from je_web_runner.utils.webauthn.virtual_authenticator import add_credential
    add_credential(selenium_driver("WR_webauthn_add_credential"), _authenticator(authenticator_id), credential)
    return True


def webauthn_list_credentials(authenticator_id: str) -> list[dict[str, Any]]:
    """List the credentials a virtual authenticator holds (the page's registrations included)."""
    from je_web_runner.utils.webauthn.virtual_authenticator import list_credentials
    driver = selenium_driver("WR_webauthn_list_credentials")
    return list(to_plain(list_credentials(driver, _authenticator(authenticator_id))))


def webauthn_remove(authenticator_id: str) -> bool:
    """Remove a virtual authenticator from the running browser."""
    from je_web_runner.utils.webauthn.virtual_authenticator import remove_virtual_authenticator
    remove_virtual_authenticator(selenium_driver("WR_webauthn_remove"), _authenticator(authenticator_id))
    return True


# ---------- form_autofill ------------------------------------------------

def form_autofill_match(fields: list[dict[str, Any]], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Match form fields to the values of a fixture by their id, name, placeholder, label or type.

    :param fields: ``[{"id": str, "name": str, "type": str, "placeholder": str, "label": str,
        "data-testid": str}, ...]``
    :param fixture: ``{"email": "a@b.c", "password": "...", "first_name": "..."}``
    :return: ``[{"field": {...}, "fixture_key": str, "value": ..., "confidence": n, "reason": str}, ...]``
    """
    from je_web_runner.utils.form_autofill.autofill import match_fields
    return list(to_plain(match_fields(fields, fixture)))


def form_autofill_plan(
        fields: list[dict[str, Any]], fixture: dict[str, Any], submit_locator: dict[str, str] | None = None,
) -> list[list[Any]]:
    """
    Build the action list that fills the matched fields (arguments as ``WR_form_autofill_match``).

    :param submit_locator: ``{"strategy": "CSS_SELECTOR", "value": "button[type=submit]"}`` to click at the end
    """
    from je_web_runner.utils.form_autofill.autofill import plan_fill_actions
    return plan_fill_actions(fields, fixture, submit_locator)


def form_autofill_assert_all_matched(fields: list[dict[str, Any]], fixture: dict[str, Any]) -> int:
    """Fail when a form field gets no value from the fixture; returns the number of fields matched."""
    from je_web_runner.utils.form_autofill.autofill import FormAutoFillError, match_fields
    matched = [match.field for match in match_fields(fields, fixture)]
    missing = [field for field in fields if field not in matched]
    if missing:
        raise FormAutoFillError(f"{len(missing)} field(s) have no fixture value: {missing[:5]}")
    return len(matched)


# ---------- cross_browser ------------------------------------------------

def _parity_report(runs: list[dict[str, Any]], reference_browser: str | None) -> Any:
    from je_web_runner.utils.cross_browser import parity
    built = []
    for raw in runs:
        if not isinstance(raw, dict) or not raw.get("browser"):
            raise parity.CrossBrowserError("each run must be an object with a 'browser' name")
        shot = raw.get("screenshot_path")
        built.append(parity.BrowserRunResult(
            browser=str(raw["browser"]), title=raw.get("title"), dom_text=raw.get("dom_text"),
            console=list(raw.get("console") or []), network=list(raw.get("network") or []),
            screenshot=Path(shot).read_bytes() if shot else None,
        ))
    return parity.diff_runs(built, reference_browser)


def cross_browser_capture(browser: str) -> dict[str, Any]:
    """Record the current page as one browser's run: ``{"browser": str, "title": str, "dom_text": html}``."""
    driver = selenium_driver("WR_cross_browser_capture")
    return {"browser": browser, "title": str(driver.title), "dom_text": str(driver.page_source)}


def cross_browser_diff(runs: list[dict[str, Any]], reference_browser: str | None = None) -> dict[str, Any]:
    """
    Compare what several browsers produced for the same page against a reference run (default: the first).

    :param runs: ``[{"browser": str, "title": str, "dom_text": str, "console": [{"type", "text"}],
        "network": [{"url", "status"}], "screenshot_path": str}, ...]``; only ``browser`` is required
    :return: ``{"reference": str, "matches": bool, "major": n, "findings_by_browser": {browser: [{"field",
        "expected", "actual", "severity"}, ...]}}``
    """
    report = _parity_report(runs, reference_browser)
    return {"matches": report.matches, "major": len(report.major_findings()), **to_plain(report)}


def cross_browser_assert_parity(
        runs: list[dict[str, Any]], reference_browser: str | None = None,
        allow_fields: list[str] | None = None, only_major: bool = True,
) -> bool:
    """
    Fail when a browser's run differs from the reference (arguments as ``WR_cross_browser_diff``).

    :param allow_fields: finding fields to ignore: ``title``, ``dom_hash``, ``console``, ``network_status``,
        ``screenshot_hash``; ``only_major``: ignore minor findings (console, screenshot, non-5xx statuses)
    """
    from je_web_runner.utils.cross_browser.parity import assert_parity
    assert_parity(_parity_report(runs, reference_browser), allow_fields, only_major)
    return True


# ---------- extension_harness -------------------------------------------

def extension_harness_info(manifest: str | dict[str, Any]) -> dict[str, Any]:
    """
    Read a browser extension's manifest (a directory, a ``manifest.json`` path or the parsed object).

    :return: ``{"name", "version", "manifest_version", "popup", "background_script", "permissions",
        "extension_dir"}``; fails on a manifest without name / version or with a version other than 2 or 3
    """
    from je_web_runner.utils.extension_harness import harness
    if isinstance(manifest, str) and Path(manifest).is_dir():
        return dict(to_plain(harness.extension_info(manifest)))
    return dict(to_plain(harness.parse_manifest(manifest)))


def extension_harness_chrome_arguments(extensions: list[str]) -> list[str]:
    """Return the Chrome command-line arguments that load the unpacked extension directories."""
    from je_web_runner.utils.extension_harness.harness import apply_to_chrome_options
    arguments: list[str] = []
    apply_to_chrome_options(SimpleNamespace(add_argument=arguments.append), extensions)
    return arguments


def extension_harness_playwright_args(
        extensions: list[str], user_data_dir: str, headless: bool = False) -> dict[str, Any]:
    """Return the ``launch_persistent_context`` arguments that load the unpacked extension directories."""
    from je_web_runner.utils.extension_harness.harness import playwright_persistent_context_args
    return dict(to_plain(playwright_persistent_context_args(extensions, user_data_dir, headless)))


# ---------- pr_comment ---------------------------------------------------

def pr_comment_build_markdown(summary: dict[str, Any], run_url: str | None = None) -> str:
    """
    Render the Markdown of a test-summary comment for a pull request.

    :param summary: ``{"total": n, "passed": n, "failed": n, "skipped": n, "flaky": n, "duration_seconds": n,
        "sections": [{"title": str, "body": str}, ...]}``; the first three are required
    """
    from je_web_runner.utils.pr_comment.poster import PrCommentError, PrSummary, build_summary_markdown
    try:
        built = PrSummary(
            total=int(summary["total"]), passed=int(summary["passed"]), failed=int(summary["failed"]),
            skipped=int(summary.get("skipped") or 0), duration_seconds=summary.get("duration_seconds"),
            flaky=int(summary.get("flaky") or 0), sections=list(summary.get("sections") or []),
        )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise PrCommentError(f"summary needs numeric total / passed / failed: {error!r}") from error
    return build_summary_markdown(built, run_url)


def pr_comment_post(repo: str, pr_number: int, body: str) -> dict[str, Any]:
    """
    Create the WebRunner summary comment on a GitHub pull request, or update it when it already exists.

    The token is read from the ``GITHUB_TOKEN`` environment variable, never from the action file.

    :param repo: ``"owner/name"``; ``body``: Markdown, e.g. from ``WR_pr_comment_build_markdown``
    :return: GitHub's comment object (``id``, ``html_url``, ...)
    """
    from je_web_runner.utils.pr_comment.poster import post_or_update_comment
    return dict(to_plain(post_or_update_comment(repo, pr_number, body)))


FRONTEND_2_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_touch_gesture_tap": touch_gesture_tap,
    "WR_touch_gesture_swipe": touch_gesture_swipe,
    "WR_touch_gesture_pinch": touch_gesture_pinch,
    "WR_touch_gesture_dispatch": touch_gesture_dispatch,
    "WR_touch_gesture_assert_received": touch_gesture_assert_received,
    "WR_viewport_audit_check": viewport_audit_check,
    "WR_viewport_audit_check_page": viewport_audit_check_page,
    "WR_viewport_audit_assert_meta": viewport_audit_assert_meta,
    "WR_viewport_audit_safe_area_page": viewport_audit_safe_area_page,
    "WR_viewport_audit_assert_safe_area": viewport_audit_assert_safe_area,
    "WR_virtual_keyboard_snapshot_page": virtual_keyboard_snapshot_page,
    "WR_virtual_keyboard_assert_shrunk": virtual_keyboard_assert_shrunk,
    "WR_virtual_keyboard_assert_inset_set": virtual_keyboard_assert_inset_set,
    "WR_virtual_keyboard_assert_focused_visible": virtual_keyboard_assert_focused_visible,
    "WR_geo_locale_payloads": geo_locale_payloads,
    "WR_geo_locale_apply": geo_locale_apply,
    "WR_multi_tab_register": multi_tab_register,
    "WR_multi_tab_open": multi_tab_open,
    "WR_multi_tab_switch": multi_tab_switch,
    "WR_multi_tab_close": multi_tab_close,
    "WR_multi_tab_reset": multi_tab_reset,
    "WR_pom_codegen_render": pom_codegen_render,
    "WR_pom_codegen_render_page": pom_codegen_render_page,
    "WR_state_diff_capture": state_diff_capture,
    "WR_state_diff_compare": state_diff_compare,
    "WR_state_diff_assert_no_change": state_diff_assert_no_change,
    "WR_storybook_discover": storybook_discover,
    "WR_storybook_plan_actions": storybook_plan_actions,
    "WR_visual_review_list": visual_review_list,
    "WR_visual_review_accept": visual_review_accept,
    "WR_visual_review_assert_no_diffs": visual_review_assert_no_diffs,
    "WR_webauthn_enable": webauthn_enable,
    "WR_webauthn_add_credential": webauthn_add_credential,
    "WR_webauthn_list_credentials": webauthn_list_credentials,
    "WR_webauthn_remove": webauthn_remove,
    "WR_form_autofill_match": form_autofill_match,
    "WR_form_autofill_plan": form_autofill_plan,
    "WR_form_autofill_assert_all_matched": form_autofill_assert_all_matched,
    "WR_cross_browser_capture": cross_browser_capture,
    "WR_cross_browser_diff": cross_browser_diff,
    "WR_cross_browser_assert_parity": cross_browser_assert_parity,
    "WR_extension_harness_info": extension_harness_info,
    "WR_extension_harness_chrome_arguments": extension_harness_chrome_arguments,
    "WR_extension_harness_playwright_args": extension_harness_playwright_args,
    "WR_pr_comment_build_markdown": pr_comment_build_markdown,
    "WR_pr_comment_post": pr_comment_post,
}

PYTHON_ONLY: dict[str, str] = {}

# WR_pr_comment_post writes to api.github.com (a fixed host) for the repository its arguments name.
NETWORK_COMMANDS: frozenset[str] = frozenset({"WR_pr_comment_post"})
