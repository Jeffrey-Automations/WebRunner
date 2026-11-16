"""Tests for the front-end command adapters (``_commands_frontend.py`` and ``_commands_frontend_2.py``)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from je_web_runner.utils.cross_browser.parity import CrossBrowserError
from je_web_runner.utils.dst_boundary_test.boundary import DstBoundaryError
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException
from je_web_runner.utils.executor import _command_helpers
from je_web_runner.utils.executor import _commands_frontend as part_one
from je_web_runner.utils.executor import _commands_frontend_2 as part_two
from je_web_runner.utils.extension_harness.harness import ExtensionHarnessError
from je_web_runner.utils.forced_colors_mode.modes import ForcedColorsModeError
from je_web_runner.utils.form_autofill.autofill import FormAutoFillError
from je_web_runner.utils.geo_locale.geo_locale import GeoLocaleError
from je_web_runner.utils.multi_tab.choreographer import MultiTabError
from je_web_runner.utils.number_currency_locale.locale import NumberCurrencyLocaleError
from je_web_runner.utils.ocr_assert.ocr import OcrAssertError
from je_web_runner.utils.pom_codegen.codegen import PomCodegenError
from je_web_runner.utils.pr_comment.poster import PrCommentError
from je_web_runner.utils.pseudo_localization.pseudo import PseudoLocalizationError
from je_web_runner.utils.pull_to_refresh.refresh import PullToRefreshError
from je_web_runner.utils.rtl_layout_verify.verify import RtlLayoutVerifyError
from je_web_runner.utils.screen_reader_runner.reader import ScreenReaderError
from je_web_runner.utils.state_diff.diff import StateDiffError
from je_web_runner.utils.storybook.discovery import StorybookError
from je_web_runner.utils.touch_gesture.gesture import TouchGestureError
from je_web_runner.utils.viewport_audit.audit import ViewportAuditError
from je_web_runner.utils.virtual_keyboard.keyboard import VirtualKeyboardError
from je_web_runner.utils.visual_ai.perceptual import VisualAIError
from je_web_runner.utils.visual_review.review_server import VisualReviewError
from je_web_runner.utils.wcag22_touch_target.touch import Wcag22TouchTargetError
from je_web_runner.utils.webauthn.virtual_authenticator import WebAuthnError

PACKAGES = (
    "dst_boundary_test", "forced_colors_mode", "number_currency_locale", "ocr_assert", "pseudo_localization",
    "rtl_layout_verify", "screen_reader_runner", "visual_ai", "wcag22_touch_target", "pull_to_refresh",
    "touch_gesture", "viewport_audit", "virtual_keyboard", "geo_locale", "multi_tab", "pom_codegen",
    "state_diff", "storybook", "visual_review", "webauthn", "form_autofill", "cross_browser",
    "extension_harness", "pr_comment",
)
OCR_BACKEND = "je_web_runner.utils.ocr_assert.ocr.tesseract_backend"
VIEWPORT_OK = '<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head></html>'


def _json(result: Any) -> Any:
    """Return ``result`` after proving it can be written as JSON."""
    json.dumps(result)
    return result


@pytest.fixture(name="driver")
def _driver(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr(_command_helpers.webdriver_wrapper_instance, "current_webdriver", mock)
    return mock


@pytest.fixture(autouse=True)
def _forget_tabs() -> None:
    part_two.multi_tab_reset()


# ---------- the three tables --------------------------------------------

def test_tables_are_consistent() -> None:
    commands = {**part_one.FRONTEND_COMMANDS, **part_two.FRONTEND_2_COMMANDS}
    assert len(commands) == len(part_one.FRONTEND_COMMANDS) + len(part_two.FRONTEND_2_COMMANDS)
    python_only = {**part_one.PYTHON_ONLY, **part_two.PYTHON_ONLY}
    for package in PACKAGES:
        covered = any(name.startswith(f"WR_{package}_") for name in commands)
        assert covered or package in python_only, package
    for name, function in commands.items():
        assert name == name.lower().replace("wr_", "WR_", 1)
        assert any(name.startswith(f"WR_{package}_") for package in PACKAGES), name
        assert callable(function) and (function.__doc__ or "").strip(), name
    assert set(python_only) <= set(PACKAGES)
    assert part_one.NETWORK_COMMANDS <= set(part_one.FRONTEND_COMMANDS)
    assert part_two.NETWORK_COMMANDS <= set(part_two.FRONTEND_2_COMMANDS)


def test_page_command_without_browser_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_command_helpers.webdriver_wrapper_instance, "current_webdriver", None)
    with pytest.raises(WebRunnerWebDriverIsNoneException):
        part_two.viewport_audit_check_page()


# ---------- dst_boundary_test -------------------------------------------

def test_dst_find_and_classify() -> None:
    boundaries = _json(part_one.dst_boundary_test_find("America/New_York", 2026, 2026))
    assert [item["transition"] for item in boundaries] == ["spring_forward", "fall_back"]
    assert boundaries[0]["shift_seconds"] == 3600
    gap = part_one.dst_boundary_test_classify("America/New_York", "2026-03-08T02:30:00")
    assert gap == {"nonexistent": True, "ambiguous": False}
    overlap = part_one.dst_boundary_test_classify("America/New_York", "2026-11-01T01:30:00")
    assert overlap == {"nonexistent": False, "ambiguous": True}
    plain = part_one.dst_boundary_test_classify("America/New_York", "2026-06-01T12:00:00")
    assert plain == {"nonexistent": False, "ambiguous": False}
    with pytest.raises(DstBoundaryError):
        part_one.dst_boundary_test_classify("Nowhere/Nothing", "2026-03-08T02:30:00")
    with pytest.raises(DstBoundaryError):
        part_one.dst_boundary_test_classify("America/New_York", "half past two")


def test_dst_fire_assertions() -> None:
    fires = ["2026-11-01T05:30:00+00:00", "2026-11-01T06:30:00+00:00"]
    assert part_one.dst_boundary_test_assert_no_duplicate_fires(fires) == 2
    with pytest.raises(DstBoundaryError):
        part_one.dst_boundary_test_assert_no_duplicate_fires(fires + ["2026-11-01T01:30:00-05:00"])
    assert part_one.dst_boundary_test_assert_fired_around(fires, "2026-11-01T06:30:20+00:00") is True
    with pytest.raises(DstBoundaryError):
        part_one.dst_boundary_test_assert_fired_around(fires, "2026-11-01T08:00:00+00:00", 30)


# ---------- forced_colors_mode ------------------------------------------

def test_forced_colors_profiles_and_apply(driver: MagicMock) -> None:
    profiles = _json(part_one.forced_colors_mode_profiles())
    assert [item["name"] for item in profiles][:2] == ["baseline", "dark"]
    applied = part_one.forced_colors_mode_apply(profile="dark")
    assert applied["color_scheme"] == "dark"
    method, params = driver.execute_cdp_cmd.call_args.args
    assert method == "Emulation.setEmulatedMedia"
    assert {"name": "prefers-color-scheme", "value": "dark"} in params["features"]
    custom = part_one.forced_colors_mode_apply(forced_colors="active", contrast="more")
    assert custom["name"] == "custom" and custom["forced_colors"] == "active"
    with pytest.raises(ForcedColorsModeError):
        part_one.forced_colors_mode_apply(profile="sepia")
    with pytest.raises(ForcedColorsModeError):
        part_one.forced_colors_mode_apply(color_scheme="purple")


def test_forced_colors_audit_and_assert() -> None:
    baseline = {".btn": {"background_color": "#fff", "color": "#000"}}
    broken = {"baseline": baseline, "dark": {".btn": {"background_color": "#000", "color": "#000"}}}
    report = _json(part_one.forced_colors_mode_audit(broken))
    assert report["passed"] is False and report["invisible_in_modes"] == {"dark": [".btn"]}
    with pytest.raises(ForcedColorsModeError):
        part_one.forced_colors_mode_assert_no_invisible(broken)
    fine = {"baseline": baseline, "dark": {".btn": {"background_color": "#000", "color": "#fff"}}}
    assert part_one.forced_colors_mode_assert_no_invisible(fine) == 1
    with pytest.raises(ForcedColorsModeError):
        part_one.forced_colors_mode_audit(fine, baseline_mode="light")


# ---------- number_currency_locale --------------------------------------

def test_number_currency_locale() -> None:
    assert _json(part_one.number_currency_locale_check("1.234,56 €", "de-DE", currency=True))["passed"] is True
    wrong = part_one.number_currency_locale_check("1,234.56", "de-DE", currency=True)
    assert wrong["passed"] is False and len(wrong["problems"]) == 2
    assert part_one.number_currency_locale_assert_number("1,234.56", "en-US") is True
    with pytest.raises(NumberCurrencyLocaleError):
        part_one.number_currency_locale_assert_number("1,234.56", "de-DE")
    assert part_one.number_currency_locale_assert_currency("$1,234.56", "en-US") is True
    with pytest.raises(NumberCurrencyLocaleError):
        part_one.number_currency_locale_assert_currency("1,234.56", "en-US")
    assert part_one.number_currency_locale_assert_date("2026-05-24") is True
    with pytest.raises(NumberCurrencyLocaleError):
        part_one.number_currency_locale_assert_date("05/24/2026", "iso")


# ---------- ocr_assert ---------------------------------------------------

def test_ocr_commands_on_a_file() -> None:
    reader = MagicMock(return_value="Q4  2025\nRevenue")
    with patch(OCR_BACKEND, return_value=reader) as backend:
        assert part_one.ocr_assert_extract_text("chart.png", lang="deu") == "Q4  2025\nRevenue"
        backend.assert_called_with(lang="deu")
        found = _json(part_one.ocr_assert_contains("chart.png", "q4 2025"))
        assert found["matched"] is True and found["mode"] == "contains"
        assert part_one.ocr_assert_fuzzy("chart.png", "Q4 2025 Revenue")["score"] == pytest.approx(1.0)
        assert part_one.ocr_assert_any("chart.png", ["Costs", "Revenue"])["needle"] == "Revenue"
        with pytest.raises(OcrAssertError):
            part_one.ocr_assert_contains("chart.png", "Q1 2024")
        with pytest.raises(OcrAssertError):
            part_one.ocr_assert_fuzzy("chart.png", "an entirely different caption", min_ratio=0.9)
        with pytest.raises(OcrAssertError):
            part_one.ocr_assert_any("chart.png", ["Costs"])
    reader.assert_called_with("chart.png")


def test_ocr_page_contains(driver: MagicMock) -> None:
    driver.get_screenshot_as_png.return_value = b"png-bytes"
    reader = MagicMock(return_value="Total: 42")
    with patch(OCR_BACKEND, return_value=reader):
        assert part_one.ocr_assert_page_contains("total: 42")["matched"] is True
        with pytest.raises(OcrAssertError):
            part_one.ocr_assert_page_contains("Total: 43")
    reader.assert_called_with(b"png-bytes")


# ---------- pseudo_localization -----------------------------------------

def test_pseudo_localization(driver: MagicMock) -> None:
    assert part_one.pseudo_localization_text("Save", expansion_ratio=0, bracket=False) == "Šäṽé"
    assert "{name}" in part_one.pseudo_localization_text("Hi {name}")
    catalogue = {"save": "Save changes", "ok": "OK"}
    pseudo = _json(part_one.pseudo_localization_catalogue(catalogue, bracket=False))
    assert set(pseudo) == {"save", "ok"} and "Save" not in pseudo["save"]
    leaked = "<button>Save changes</button><button>Save changes</button>"
    report = _json(part_one.pseudo_localization_scan(leaked, catalogue))
    assert report["passed"] is False and report["hits"] == [{"string": "Save changes", "occurrences": 2}]
    driver.page_source = "<button>⟦Šäṽé⟧</button>"
    assert part_one.pseudo_localization_scan_page(catalogue)["passed"] is True
    assert part_one.pseudo_localization_assert_no_hardcoded("⟦Šäṽé⟧", catalogue) == 6
    with pytest.raises(PseudoLocalizationError):
        part_one.pseudo_localization_assert_no_hardcoded(leaked, catalogue)


# ---------- rtl_layout_verify -------------------------------------------

def _rtl_payload(document_dir: str = "rtl", margin_left: str = "0px") -> dict[str, Any]:
    first = {"tag": "li", "text": "بيت", "left": 300, "right": 400, "direction": "rtl",
             "marginLeft": margin_left, "marginRight": "0px"}
    second = {"tag": "li", "text": "حول", "left": 100, "right": 200, "direction": "rtl"}
    return {"documentDir": document_dir, "items": [{"selector": "nav li", "boxes": [first, second]}]}


def test_rtl_layout_verify() -> None:
    good = _json(part_one.rtl_layout_verify_check(_rtl_payload(), ["nav li"], ["nav li"]))
    assert good == {"document_dir": "rtl", "passed": True, "problems": []}
    assert part_one.rtl_layout_verify_assert(_rtl_payload(), ["nav li"], ["nav li"]) == 4
    bad = part_one.rtl_layout_verify_check(_rtl_payload("ltr", "12px"), ["nav li"])
    assert bad["passed"] is False and len(bad["problems"]) == 2
    with pytest.raises(RtlLayoutVerifyError):
        part_one.rtl_layout_verify_assert(_rtl_payload("ltr"))


# ---------- screen_reader_runner ----------------------------------------

def test_screen_reader_runner() -> None:
    tree = {"role": "main", "children": [
        {"role": "heading", "level": 1, "name": "Orders"},
        {"role": "button", "name": "Save"},
    ]}
    walked = _json(part_one.screen_reader_runner_walk(tree))
    assert walked["speech"] == "heading level 1: Orders button: Save" and walked["passed"] is True
    assert part_one.screen_reader_runner_assert_no_violations(tree) == 2
    assert part_one.screen_reader_runner_assert_reads(tree, "save")["role"] == "button"
    with pytest.raises(ScreenReaderError):
        part_one.screen_reader_runner_assert_reads(tree, "Delete")
    broken = {"role": "main", "children": [{"role": "button", "name": ""}]}
    kinds = [item["kind"] for item in part_one.screen_reader_runner_walk(broken)["violations"]]
    assert kinds == ["unnamed_interactive", "empty_button"]
    with pytest.raises(ScreenReaderError):
        part_one.screen_reader_runner_assert_no_violations(broken)


# ---------- visual_ai ----------------------------------------------------

def _images(folder: Path) -> tuple[str, str]:
    """A left-to-right gradient and a checkerboard, as PNG files."""
    gradient = Image.new("L", (64, 64))
    gradient.putdata([column * 4 for _row in range(64) for column in range(64)])
    checker = Image.new("L", (64, 64))
    checker.putdata([255 * ((row // 8 + column // 8) % 2) for row in range(64) for column in range(64)])
    paths = (folder / "gradient.png", folder / "checker.png")
    gradient.save(paths[0])
    checker.save(paths[1])
    return str(paths[0]), str(paths[1])


def test_visual_ai_files(tmp_path: Path) -> None:
    gradient, checker = _images(tmp_path)
    hashed = _json(part_one.visual_ai_hash(gradient))
    assert hashed["kind"] == "dHash" and hashed["bits"] == "1" * 64 and hashed["hex"] == "f" * 16
    assert len(part_one.visual_ai_hash(gradient, kind="phash", crop_box=[0, 0, 32, 32])["bits"]) == 63
    with pytest.raises(VisualAIError):
        part_one.visual_ai_hash(gradient, kind="md5")
    same = _json(part_one.visual_ai_compare(gradient, gradient))
    assert same["composite"] == pytest.approx(1.0) and same["passed"] is True
    assert part_one.visual_ai_compare(gradient, checker)["passed"] is False
    assert part_one.visual_ai_assert_similar(gradient, gradient, mask_boxes=[[0, 0, 8, 8]])["passed"] is True
    with pytest.raises(VisualAIError):
        part_one.visual_ai_assert_similar(gradient, checker)


def test_visual_ai_page(tmp_path: Path, driver: MagicMock) -> None:
    gradient, checker = _images(tmp_path)
    driver.get_screenshot_as_png.return_value = Path(gradient).read_bytes()
    assert part_one.visual_ai_assert_page_similar(gradient, threshold=0.95)["passed"] is True
    driver.get_screenshot_as_png.return_value = Path(checker).read_bytes()
    with pytest.raises(VisualAIError):
        part_one.visual_ai_assert_page_similar(gradient)


# ---------- wcag22_touch_target -----------------------------------------

def test_wcag22_touch_target(driver: MagicMock) -> None:
    crowded = [
        {"tag": "button", "label": "x", "width": 10, "height": 10, "x": 0, "y": 0},
        {"tag": "button", "label": "y", "width": 10, "height": 10, "x": 5, "y": 0},
    ]
    roomy = [{"tag": "button", "label": "Save", "width": 44, "height": 44, "x": 0, "y": 0}]
    assert [item["label"] for item in _json(part_one.wcag22_touch_target_audit(crowded))] == ["x", "y"]
    assert part_one.wcag22_touch_target_assert(roomy) == 1
    with pytest.raises(Wcag22TouchTargetError):
        part_one.wcag22_touch_target_assert(crowded)
    driver.execute_script.return_value = crowded
    assert len(part_one.wcag22_touch_target_audit_page()) == 2
    # The library's script returns its own value; the adapter's ``return`` in front is harmless.
    assert driver.execute_script.call_args.args[0].startswith("return arguments.harvested = (function")


# ---------- pull_to_refresh ---------------------------------------------

def test_pull_to_refresh(driver: MagicMock) -> None:
    payload = {"overscroll_y": "contain", "scroller_height": 800, "pull_threshold_attr": "80"}
    driver.execute_script.return_value = payload
    assert _json(part_one.pull_to_refresh_snapshot_page("#feed")) == payload
    assert driver.execute_script.call_args.args[1] == "#feed"
    driver.execute_script.return_value = None
    with pytest.raises(PullToRefreshError):
        part_one.pull_to_refresh_snapshot_page()
    assert part_one.pull_to_refresh_assert_contained(payload) == "contain"
    with pytest.raises(PullToRefreshError):
        part_one.pull_to_refresh_assert_contained({**payload, "overscroll_y": "auto"})
    assert part_one.pull_to_refresh_assert_threshold(payload) == pytest.approx(80.0)
    with pytest.raises(PullToRefreshError):
        part_one.pull_to_refresh_assert_threshold({**payload, "pull_threshold_attr": "10"})
    assert part_one.pull_to_refresh_assert_triggered(True, True) is True
    with pytest.raises(PullToRefreshError):
        part_one.pull_to_refresh_assert_triggered(True, False)


# ---------- touch_gesture -----------------------------------------------

def test_touch_gesture_builders() -> None:
    tap = _json(part_two.touch_gesture_tap(10, 20))
    assert [frame["type"] for frame in tap] == ["touchStart", "touchEnd"]
    assert tap[0]["touchPoints"][0]["x"] == 10
    assert len(part_two.touch_gesture_tap(10, 20, hold_ms=800)) == 3
    with pytest.raises(TouchGestureError):
        part_two.touch_gesture_tap(10, 20, hold_ms=100)
    swipe = part_two.touch_gesture_swipe(0, 0, 100, 0)
    assert len(swipe["frames"]) == 9 and swipe["distance_px"] == pytest.approx(87.5)
    pinch = part_two.touch_gesture_pinch(50, 50, start_radius=10, end_radius=40)
    assert len(pinch[0]["touchPoints"]) == 2 and pinch[-1]["type"] == "touchEnd"
    with pytest.raises(TouchGestureError):
        part_two.touch_gesture_pinch(50, 50, start_radius=0, end_radius=40)


def test_touch_gesture_dispatch_and_assert(driver: MagicMock) -> None:
    frames = part_two.touch_gesture_tap(10, 20)
    assert part_two.touch_gesture_dispatch(frames) == 2
    assert driver.execute_cdp_cmd.call_args_list[0].args == ("Input.dispatchTouchEvent", frames[0])
    with pytest.raises(TouchGestureError):
        part_two.touch_gesture_dispatch([{"type": "click"}])
    events = [{"type": "touchstart", "touchCount": 2}, {"type": "touchend", "touchCount": 0}]
    assert part_two.touch_gesture_assert_received(events, "touchend", two_finger=True) == 2
    with pytest.raises(TouchGestureError):
        part_two.touch_gesture_assert_received(events, "touchmove")
    with pytest.raises(TouchGestureError):
        part_two.touch_gesture_assert_received(events[1:], "touchend", two_finger=True)


# ---------- viewport_audit ----------------------------------------------

def test_viewport_audit(driver: MagicMock) -> None:
    good = _json(part_two.viewport_audit_check(VIEWPORT_OK))
    assert good["passed"] is True and good["parsed"]["width"] == "device-width"
    locked = '<meta name="viewport" content="width=device-width, user-scalable=no">'
    assert len(part_two.viewport_audit_check(locked, notch_aware=True)["problems"]) == 2
    missing = part_two.viewport_audit_check("<html></html>")
    assert missing["present"] is False and len(missing["problems"]) == 1
    driver.page_source = VIEWPORT_OK
    assert part_two.viewport_audit_check_page()["passed"] is True
    assert part_two.viewport_audit_assert_meta(VIEWPORT_OK) == "width=device-width, initial-scale=1"
    with pytest.raises(ViewportAuditError):
        part_two.viewport_audit_assert_meta(locked)
    with pytest.raises(ViewportAuditError):
        part_two.viewport_audit_assert_meta(VIEWPORT_OK, notch_aware=True)


def test_viewport_safe_area(driver: MagicMock) -> None:
    driver.execute_script.return_value = {"padding_top": "47px", "padding_bottom": "34px"}
    padding = part_two.viewport_audit_safe_area_page()
    assert padding["padding_top"] == "47px" and padding["padding_left"] == "0px"
    assert part_two.viewport_audit_assert_safe_area(padding) is True
    with pytest.raises(ViewportAuditError):
        part_two.viewport_audit_assert_safe_area({"padding_top": "0px"})


# ---------- virtual_keyboard --------------------------------------------

def test_virtual_keyboard(driver: MagicMock) -> None:
    driver.execute_script.return_value = {"viewport_width": 390, "viewport_height": 800, "scale": 1}
    before = _json(part_two.virtual_keyboard_snapshot_page())
    assert before["viewport_height"] == 800 and before["keyboard_inset"] == ""
    after = {**before, "viewport_height": 500, "keyboard_inset": " 300px"}
    assert part_two.virtual_keyboard_assert_shrunk(before, after) == pytest.approx(300.0)
    with pytest.raises(VirtualKeyboardError):
        part_two.virtual_keyboard_assert_shrunk(before, before)
    assert part_two.virtual_keyboard_assert_inset_set(after) == "300px"
    with pytest.raises(VirtualKeyboardError):
        part_two.virtual_keyboard_assert_inset_set(before)
    assert part_two.virtual_keyboard_assert_focused_visible(after, {"selector": "#q", "bottom": 400}) is True
    with pytest.raises(VirtualKeyboardError):
        part_two.virtual_keyboard_assert_focused_visible(after, {"selector": "#q", "bottom": 700})


# ---------- geo_locale ---------------------------------------------------

def test_geo_locale(driver: MagicMock) -> None:
    payloads = _json(part_two.geo_locale_payloads(25.03, 121.56, "Asia/Taipei", "zh-TW"))
    assert [item["method"] for item in payloads["cdp"]] == [
        "Emulation.setGeolocationOverride", "Emulation.setTimezoneOverride", "Emulation.setLocaleOverride",
    ]
    assert payloads["playwright"]["timezone_id"] == "Asia/Taipei"
    assert part_two.geo_locale_apply(timezone="Europe/Berlin") == ["Emulation.setTimezoneOverride"]
    driver.execute_cdp_cmd.assert_called_once_with(
        "Emulation.setTimezoneOverride", {"timezoneId": "Europe/Berlin"})
    with pytest.raises(GeoLocaleError):
        part_two.geo_locale_payloads(latitude=25.03)


# ---------- multi_tab ----------------------------------------------------

def test_multi_tab(driver: MagicMock) -> None:
    driver.current_window_handle = "h1"
    driver.window_handles = ["h1"]
    driver.switch_to.new_window.side_effect = lambda _kind: driver.window_handles.append("h2")
    assert _json(part_two.multi_tab_register("main")) == {"alias": "main", "handle": "h1"}
    assert part_two.multi_tab_open("side") == {"alias": "side", "handle": "h2"}
    assert part_two.multi_tab_switch("main")["handle"] == "h1"
    driver.switch_to.window.assert_called_with("h1")
    with pytest.raises(MultiTabError):
        part_two.multi_tab_switch("unknown")
    assert part_two.multi_tab_close("side") == ["main"]
    driver.close.assert_called_once()
    assert part_two.multi_tab_reset() == ["main"]
    with pytest.raises(MultiTabError):
        part_two.multi_tab_switch("main")


# ---------- pom_codegen --------------------------------------------------

def test_pom_codegen(driver: MagicMock) -> None:
    html = '<form><input id="email"><button data-testid="submit-btn">Go</button></form>'
    rendered = _json(part_two.pom_codegen_render(html, "LoginPage"))
    assert "class LoginPage:" in rendered["source"] and "def submit_btn(self)" in rendered["source"]
    assert [item["strategy"] for item in rendered["elements"]] == ["ID", "CSS_SELECTOR"]
    with pytest.raises(PomCodegenError):
        part_two.pom_codegen_render(html, "not a class")
    driver.page_source = html
    assert "def email(self)" in part_two.pom_codegen_render_page()["source"]


# ---------- state_diff ---------------------------------------------------

def test_state_diff(driver: MagicMock) -> None:
    driver.get_cookies.return_value = [{"name": "sid", "value": "1"}]
    driver.execute_script.side_effect = [{"cart": "2"}, {}]
    before = _json(part_two.state_diff_capture())
    assert before == {"cookies": {"sid": {"name": "sid", "value": "1"}},
                      "local_storage": {"cart": "2"}, "session_storage": {}}
    after = {"cookies": before["cookies"], "local_storage": {"cart": "3", "seen": "1"}}
    diff = _json(part_two.state_diff_compare(before, after))
    assert diff["has_changes"] is True and diff["cookies"]["changed"] == {}
    assert diff["local_storage"] == {"added": {"seen": "1"}, "removed": {}, "changed": {"cart": ["2", "3"]}}
    assert part_two.state_diff_assert_no_change(before, before) is True
    assert part_two.state_diff_assert_no_change(before, after, allow_keys=["cart", "seen"]) is True
    with pytest.raises(StateDiffError):
        part_two.state_diff_assert_no_change(before, after, allow_keys=["cart"])


# ---------- storybook ----------------------------------------------------

def test_storybook(tmp_path: Path) -> None:
    index = {"v": 4, "entries": {
        "components-button--primary": {"title": "Components/Button", "name": "Primary", "type": "story"},
        "components-button--docs": {"title": "Components/Button", "name": "Docs", "type": "docs"},
        "example-page--intro": {"title": "Example/Page", "name": "Intro", "type": "story"},
    }}
    stories = _json(part_two.storybook_discover(index))
    assert [story["id"] for story in stories] == ["components-button--primary"]
    assert stories[0]["iframe_path"] == "iframe.html?id=components-button--primary&viewMode=story"
    index_file = tmp_path / "index.json"
    index_file.write_text(json.dumps(index), encoding="utf-8")
    assert len(part_two.storybook_discover(str(index_file), skip_examples=False)) == 2
    assert part_two.storybook_discover(index, title_prefix="Forms/") == []
    plan = _json(part_two.storybook_plan_actions(
        index, "http://localhost:6006/", capture_screenshot=False, axe_source="${axe}"))
    assert plan == [
        ["WR_to_url", {"url": f"http://localhost:6006/{stories[0]['iframe_path']}"}],
        ["WR_a11y_run_audit", {"axe_source": "${axe}"}],
    ]
    # An audit without the axe source could not run, so the plan is refused instead of emitted.
    with pytest.raises(StorybookError):
        part_two.storybook_plan_actions(index, "http://localhost:6006/")
    assert _json(part_two.storybook_plan_actions(
        index, "http://localhost:6006/", run_a11y=False, capture_screenshot=False)) == [
        ["WR_to_url", {"url": f"http://localhost:6006/{stories[0]['iframe_path']}"}]]
    with pytest.raises(StorybookError):
        part_two.storybook_discover({"v": 4})


# ---------- visual_review ------------------------------------------------

def test_visual_review(tmp_path: Path) -> None:
    baseline, current = tmp_path / "baseline", tmp_path / "current"
    baseline.mkdir()
    current.mkdir()
    for name, old, new in (("same.png", b"1", b"1"), ("changed.png", b"1", b"2")):
        (baseline / name).write_bytes(old)
        (current / name).write_bytes(new)
    (current / "new.png").write_bytes(b"3")
    listed = _json(part_two.visual_review_list(str(baseline), str(current)))
    assert {pair["name"]: pair["status"] for pair in listed} == {
        "changed.png": "diff", "new.png": "missing-baseline", "same.png": "match"}
    with pytest.raises(VisualReviewError):
        part_two.visual_review_assert_no_diffs(str(baseline), str(current))
    with pytest.raises(VisualReviewError):
        part_two.visual_review_accept(str(baseline), str(current), "../escape.png")
    for name in ("changed.png", "new.png"):
        assert Path(part_two.visual_review_accept(str(baseline), str(current), name)) == baseline / name
    assert (baseline / "changed.png").read_bytes() == b"2"
    assert part_two.visual_review_assert_no_diffs(str(baseline), str(current)) == 3


# ---------- webauthn -----------------------------------------------------

def test_webauthn(driver: MagicMock) -> None:
    driver.execute_cdp_cmd.return_value = {"authenticatorId": "auth-1"}
    enabled = _json(part_two.webauthn_enable(transport="usb"))
    assert enabled["authenticator_id"] == "auth-1" and enabled["transport"] == "usb"
    credential = {"credentialId": "YWJj", "rpId": "example.test", "isResidentCredential": True}
    assert part_two.webauthn_add_credential("auth-1", credential) is True
    driver.execute_cdp_cmd.assert_called_with(
        "WebAuthn.addCredential", {"authenticatorId": "auth-1", "credential": credential})
    driver.execute_cdp_cmd.return_value = {"credentials": [credential]}
    assert part_two.webauthn_list_credentials("auth-1") == [credential]
    assert part_two.webauthn_remove("auth-1") is True
    driver.execute_cdp_cmd.assert_called_with(
        "WebAuthn.removeVirtualAuthenticator", {"authenticatorId": "auth-1"})
    with pytest.raises(WebAuthnError):
        part_two.webauthn_remove("")
    driver.execute_cdp_cmd.return_value = {}
    with pytest.raises(WebAuthnError):
        part_two.webauthn_enable()


# ---------- form_autofill ------------------------------------------------

def test_form_autofill() -> None:
    fields = [{"id": "email", "type": "email"}, {"name": "pwd", "type": "password"}, {"id": "nickname"}]
    fixture = {"email": "user@example.test", "password": "not-a-real-secret"}
    matches = _json(part_two.form_autofill_match(fields, fixture))
    assert [match["fixture_key"] for match in matches] == ["email", "password"]
    plan = part_two.form_autofill_plan(fields, fixture, {"strategy": "ID", "value": "go"})
    assert len(plan) == 9 and plan[2] == ["WR_element_input", {"input_value": "user@example.test"}]
    assert plan[-1] == ["WR_element_click"]
    assert part_two.form_autofill_assert_all_matched(fields[:2], fixture) == 2
    with pytest.raises(FormAutoFillError):
        part_two.form_autofill_assert_all_matched(fields, fixture)


# ---------- cross_browser ------------------------------------------------

def test_cross_browser(tmp_path: Path, driver: MagicMock) -> None:
    driver.title = "Home"
    driver.page_source = "<html>home</html>"
    chrome = part_two.cross_browser_capture("chrome")
    assert chrome == {"browser": "chrome", "title": "Home", "dom_text": "<html>home</html>"}
    firefox = {**chrome, "browser": "firefox", "title": "Home - Firefox"}
    report = _json(part_two.cross_browser_diff([chrome, firefox]))
    assert report["reference"] == "chrome" and report["matches"] is False and report["major"] == 1
    assert report["findings_by_browser"]["firefox"][0]["field"] == "title"
    with pytest.raises(CrossBrowserError):
        part_two.cross_browser_assert_parity([chrome, firefox])
    assert part_two.cross_browser_assert_parity([chrome, firefox], allow_fields=["title"]) is True
    for name, content in (("chrome.png", b"1"), ("webkit.png", b"2")):
        (tmp_path / name).write_bytes(content)
    webkit = {**chrome, "browser": "webkit", "screenshot_path": str(tmp_path / "webkit.png")}
    shot = {**chrome, "screenshot_path": str(tmp_path / "chrome.png")}
    minor = part_two.cross_browser_diff([shot, webkit], reference_browser="chrome")
    assert minor["major"] == 0 and minor["findings_by_browser"]["webkit"][0]["field"] == "screenshot_hash"
    assert part_two.cross_browser_assert_parity([shot, webkit]) is True
    with pytest.raises(CrossBrowserError):
        part_two.cross_browser_assert_parity([shot, webkit], only_major=False)
    with pytest.raises(CrossBrowserError):
        part_two.cross_browser_diff([{"title": "no browser"}])


# ---------- extension_harness -------------------------------------------

def test_extension_harness(tmp_path: Path) -> None:
    manifest = {"name": "Helper", "version": "1.2.0", "manifest_version": 3,
                "action": {"default_popup": "popup.html"}, "permissions": ["storage"]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    info = _json(part_two.extension_harness_info(str(tmp_path)))
    assert info["popup"] == "popup.html" and info["extension_dir"] == str(tmp_path.resolve())
    assert part_two.extension_harness_info(manifest)["extension_dir"] is None
    with pytest.raises(ExtensionHarnessError):
        part_two.extension_harness_info({**manifest, "manifest_version": 1})
    arguments = part_two.extension_harness_chrome_arguments([str(tmp_path)])
    assert arguments == [f"--load-extension={tmp_path.resolve()}",
                         f"--disable-extensions-except={tmp_path.resolve()}"]
    with pytest.raises(ExtensionHarnessError):
        part_two.extension_harness_chrome_arguments([str(tmp_path / "missing")])
    launch = part_two.extension_harness_playwright_args([str(tmp_path)], "profile-dir")
    assert launch["user_data_dir"] == "profile-dir" and launch["headless"] is False and len(launch["args"]) == 2


# ---------- pr_comment ---------------------------------------------------

def test_pr_comment_build_markdown() -> None:
    summary = {"total": 10, "passed": 8, "failed": 2, "sections": [{"title": "Failures", "body": "- login"}]}
    markdown = part_two.pr_comment_build_markdown(summary, "https://ci.example.test/run/1")
    assert "- **Passed:** 8 (80.0%)" in markdown and "### Failures" in markdown
    assert "[https://ci.example.test/run/1]" in markdown
    with pytest.raises(PrCommentError):
        part_two.pr_comment_build_markdown({"total": 10})


def test_pr_comment_post(monkeypatch: pytest.MonkeyPatch) -> None:
    created = {"id": 5, "html_url": "https://github.com/owner/name/pull/7#issuecomment-5"}
    monkeypatch.setenv("GITHUB_TOKEN", "placeholder")
    with patch("je_web_runner.utils.pr_comment.poster._request", side_effect=[[], created]) as request:
        assert _json(part_two.pr_comment_post("owner/name", 7, "All green")) == created
    assert request.call_args_list[1].args[0] == "POST"
    assert request.call_args_list[1].kwargs["payload"]["body"].endswith("All green")
    monkeypatch.delenv("GITHUB_TOKEN")
    with pytest.raises(PrCommentError):
        part_two.pr_comment_post("owner/name", 7, "All green")
    assert "WR_pr_comment_post" in part_two.NETWORK_COMMANDS
