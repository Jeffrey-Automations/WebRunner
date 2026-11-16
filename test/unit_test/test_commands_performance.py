"""Tests for the performance command adapters (``_commands_performance`` and ``_commands_performance_2``)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.backend_log_correlator.correlator import BackendLogCorrelatorError
from je_web_runner.utils.bidi_backend.bridge import BidiBackendError
from je_web_runner.utils.bundle_budget.budget import BundleBudgetError
from je_web_runner.utils.bundle_diff_pr.diff import BundleDiffPrError
from je_web_runner.utils.cdp_tap.tap import CdpTapError
from je_web_runner.utils.console_error_budget.budget import ConsoleBudgetError
from je_web_runner.utils.critical_css_audit.audit import CriticalCssAuditError
from je_web_runner.utils.event_bus.bus import EventBusError
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException
from je_web_runner.utils.executor import _commands_performance as perf
from je_web_runner.utils.executor import _commands_performance_2 as perf2
from je_web_runner.utils.failure_bundle.bundle import FailureBundleError
from je_web_runner.utils.font_loading_strategy.strategy import FontLoadingStrategyError
from je_web_runner.utils.hydration_check.check import HydrationCheckError
from je_web_runner.utils.hydration_streaming.timing import HydrationStreamingError
from je_web_runner.utils.inp_tracker.tracker import InpTrackerError
from je_web_runner.utils.lcp_image_audit.audit import LcpImageAuditError
from je_web_runner.utils.lighthouse_regression.regression import LighthouseRegressionError
from je_web_runner.utils.long_animation_frame.frames import LongAnimationFrameError
from je_web_runner.utils.memory_leak.detector import MemoryLeakError
from je_web_runner.utils.memory_pressure_emulate.emulate import MemoryPressureError
from je_web_runner.utils.otel_bridge.trace_bridge import TraceBridgeError
from je_web_runner.utils.resource_hints_audit.hints import ResourceHintsAuditError
from je_web_runner.utils.third_party_block_test.block import ThirdPartyBlockError
from je_web_runner.utils.third_party_budget.budget import ThirdPartyBudgetError

PACKAGES = (
    "bundle_budget", "bundle_diff_pr", "critical_css_audit", "font_loading_strategy", "hydration_check",
    "hydration_streaming", "inp_tracker", "lcp_image_audit", "lighthouse_regression", "long_animation_frame",
    "memory_pressure_emulate", "resource_hints_audit", "third_party_block_test", "third_party_budget",
    "backend_log_correlator", "console_error_budget", "otel_bridge", "bidi_backend", "cdp_tap", "event_bus",
    "failure_bundle", "memory_leak", "trace_recorder",
)
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{TRACE_ID}-b7ad6b7169203331-01"
HEAD_HTML = (
    '<html><head><style>body{margin:0}</style>'
    '<link rel="preload" href="/app.css" as="style">'
    '<link rel="stylesheet" href="/app.css">'
    '<link rel="preload" href="/hero.jpg" as="image">'
    '<link rel="preconnect" href="https://cdn.example.com">'
    '</head><body><img src="/hero.jpg" fetchpriority="high"></body></html>'
)
FONT_CSS = (
    "@font-face{font-family:'Inter';src:url(inter.woff2);font-display:swap}"
    "@font-face{font-family:'Inter Fallback';src:local(Arial);font-display:swap;size-adjust:107%}"
)


def _har(*entries: tuple[str, str, int]) -> dict:
    return {"log": {"entries": [
        {
            "request": {"url": url},
            "_resourceType": kind,
            "response": {"_transferSize": size, "content": {"size": size}},
            "timings": {"wait": 120},
        }
        for url, kind, size in entries
    ]}}


BASE_HAR = _har(("https://shop.test/app.js", "script", 1000), ("https://shop.test/old.css", "stylesheet", 500))
HEAD_HAR = _har(
    ("https://shop.test/app.js", "script", 5000),
    ("https://www.google-analytics.com/ga.js", "script", 2000),
)


def _lighthouse(performance: float, lcp: float) -> dict:
    return {
        "categories": {"performance": {"score": performance}, "seo": {"score": 0.9}},
        "audits": {"largest-contentful-paint": {"numericValue": lcp}},
    }


@pytest.fixture(name="driver")
def _driver():
    """A stand-in browser for both adapter modules."""
    fake = MagicMock()
    fake.page_source = HEAD_HTML
    with patch.object(perf, "selenium_driver", return_value=fake), \
            patch.object(perf, "page_source", return_value=HEAD_HTML), \
            patch.object(perf2, "selenium_driver", return_value=fake), \
            patch.object(perf2, "selenium_only_driver", return_value=fake):
        yield fake


@pytest.fixture(autouse=True)
def _reset_state():
    """Forget the recorder state the stateful commands keep."""
    perf2.bidi_backend_reset()
    perf2._TAP.clear()  # pylint: disable=protected-access
    yield
    perf2.bidi_backend_reset()
    perf2._TAP.clear()  # pylint: disable=protected-access


# ---------- tables --------------------------------------------------------------------------------------

def test_tables_are_consistent():
    commands = {**perf.PERFORMANCE_COMMANDS, **perf2.PERFORMANCE_2_COMMANDS}
    python_only = {**perf.PYTHON_ONLY, **perf2.PYTHON_ONLY}
    assert len(commands) == len(perf.PERFORMANCE_COMMANDS) + len(perf2.PERFORMANCE_2_COMMANDS)
    for package in PACKAGES:
        has_command = any(name.startswith(f"WR_{package}_") for name in commands)
        assert has_command != (package in python_only), package
    assert set(python_only) <= set(PACKAGES)
    assert all(reason.strip() for reason in python_only.values())
    for name, function in commands.items():
        assert name == name.lower().replace("wr_", "WR_", 1)
        assert any(name.startswith(f"WR_{package}_") for package in PACKAGES), name
        assert callable(function) and (function.__doc__ or "").strip(), name
    assert perf.NETWORK_COMMANDS <= set(perf.PERFORMANCE_COMMANDS)
    assert perf2.NETWORK_COMMANDS <= set(perf2.PERFORMANCE_2_COMMANDS)
    assert perf2.NETWORK_COMMANDS == {
        "WR_backend_log_correlator_loki", "WR_backend_log_correlator_elasticsearch"}


def test_browser_command_without_a_browser_raises():
    with patch("je_web_runner.utils.executor._command_helpers.webdriver_wrapper_instance") as wrapper:
        wrapper.current_webdriver = None
        with pytest.raises(WebRunnerWebDriverIsNoneException):
            perf.critical_css_audit_page()
        with pytest.raises(WebRunnerWebDriverIsNoneException):
            perf2.memory_leak_sample()


# ---------- bundle_budget / bundle_diff_pr --------------------------------------------------------------

def test_bundle_budget_evaluate_and_markdown(tmp_path):
    result = perf.bundle_budget_evaluate(HEAD_HAR, budgets={"script": 6000}, biggest_n=1)
    assert result["passed"] is False
    assert result["totals"] == {"script": 7000}
    assert result["breaches"] == [{"kind": "script", "actual_bytes": 7000, "max_bytes": 6000, "over_bytes": 1000}]
    assert [asset["url"] for asset in result["biggest_assets"]] == ["https://shop.test/app.js"]
    json.dumps(result)
    har_file = tmp_path / "head.har"
    har_file.write_text(json.dumps(HEAD_HAR), encoding="utf-8")
    assert perf.bundle_budget_evaluate(str(har_file))["totals"] == {"script": 7000}
    assert perf.bundle_budget_evaluate(json.dumps(HEAD_HAR))["passed"] is True
    assert "| script | 7,000 |" in perf.bundle_budget_markdown(HEAD_HAR)


def test_bundle_budget_assert():
    assert perf.bundle_budget_assert(HEAD_HAR, budgets={"script": 8000})["passed"] is True
    with pytest.raises(BundleBudgetError, match="script: 7000>6000"):
        perf.bundle_budget_assert(HEAD_HAR, budgets={"script": 6000})
    with pytest.raises(BundleBudgetError, match="bad budgets"):
        perf.bundle_budget_assert(HEAD_HAR, budgets={"wasm": 1})


def test_bundle_diff_pr():
    result = perf.bundle_diff_pr_diff(BASE_HAR, HEAD_HAR)
    assert result["total_delta_bytes"] == 5500
    assert result["grew"] == [{
        "url": "https://shop.test/app.js", "kind": "script", "base_bytes": 1000, "head_bytes": 5000,
        "delta": 4000, "percent": 400.0,
    }]
    assert [row["url"] for row in result["added"]] == ["https://www.google-analytics.com/ga.js"]
    assert [row["delta"] for row in result["removed"]] == [-500]
    json.dumps(result)
    assert "Bundle delta: ▲ +5,500 bytes" in perf.bundle_diff_pr_markdown(BASE_HAR, HEAD_HAR, top_n=1)
    assert perf.bundle_diff_pr_assert_growth(BASE_HAR, HEAD_HAR, max_growth_bytes=6000)["unchanged"] == 0
    with pytest.raises(BundleDiffPrError, match="5,500B"):
        perf.bundle_diff_pr_assert_growth(BASE_HAR, HEAD_HAR, max_growth_bytes=100)


# ---------- critical_css_audit / font_loading_strategy --------------------------------------------------

def test_critical_css_audit(driver):
    expected = {"inline_blocks": 1, "inline_bytes": 14, "external_blocking": ["/app.css"], "preloaded": ["/app.css"]}
    assert perf.critical_css_audit_analyse(HEAD_HTML) == expected
    assert perf.critical_css_audit_page() == expected
    assert perf.critical_css_audit_assert() == expected
    assert driver.mock_calls == []
    json.dumps(expected)
    bare = '<head><link rel="stylesheet" href="/app.css"></head>'
    with pytest.raises(CriticalCssAuditError, match="no inline"):
        perf.critical_css_audit_assert(bare)
    with pytest.raises(CriticalCssAuditError, match="not preloaded"):
        perf.critical_css_audit_assert(bare, require_inline=False)
    with pytest.raises(CriticalCssAuditError, match="exceeds 5B"):
        perf.critical_css_audit_assert(HEAD_HTML, max_inline_bytes=5)


def test_font_loading_strategy(driver):
    faces = perf.font_loading_strategy_parse(FONT_CSS)
    assert [(face["family"], face["display"], face["size_adjust"]) for face in faces] == [
        ("Inter", "swap", ""), ("Inter Fallback", "swap", "107%")]
    json.dumps(faces)
    with patch.object(perf, "page_source", return_value=f"<style>{FONT_CSS}</style>"):
        assert perf.font_loading_strategy_page() == faces
        assert perf.font_loading_strategy_assert() == faces
    assert perf.font_loading_strategy_assert(FONT_CSS, strategy="swap", fallback_family="Inter Fallback") == faces
    with pytest.raises(FontLoadingStrategyError, match="expected optional"):
        perf.font_loading_strategy_assert(FONT_CSS, strategy="optional")
    with pytest.raises(FontLoadingStrategyError, match="unknown strategy"):
        perf.font_loading_strategy_assert(FONT_CSS, strategy="flash")
    with pytest.raises(FontLoadingStrategyError, match="missing font-display"):
        perf.font_loading_strategy_assert("@font-face{font-family:Inter;src:url(a.woff2)}")
    assert driver.mock_calls == []


# ---------- hydration_check / hydration_streaming -------------------------------------------------------

def test_hydration_check(driver):
    clean = perf.hydration_check_audit("<p>Hi</p>", "<p data-reactroot=\"\">Hi</p>", ["loaded"])
    assert clean == {"passed": True, "by_kind": {}, "findings": []}
    result = perf.hydration_check_audit("<p>1</p>", "<p>2</p>", ["Warning: Hydration failed because"])
    assert result["passed"] is False
    assert result["by_kind"] == {"dom_diff": 1, "console": 1}
    assert result["findings"][1]["source"] == "hydration failed"
    json.dumps(result)
    assert perf.hydration_check_page(HEAD_HTML)["passed"] is True
    assert perf.hydration_check_page("<p>other</p>")["by_kind"] == {"dom_diff": 1}
    assert perf.hydration_check_assert("<p>Hi</p>", "<p>Hi</p>")["passed"] is True
    with pytest.raises(HydrationCheckError, match="dom_diff"):
        perf.hydration_check_assert("<p>1</p>", "<p>2</p>")
    assert driver.mock_calls == []


def test_hydration_streaming(driver):
    log = {"boundaries": {"B:1": {"placeholder": 10, "arrived": 60, "interactive": 90}, "B:2": {"arrived": 40}}}
    result = perf.hydration_streaming_parse(log)
    assert result["boundaries"][0] == {
        "id": "B:1", "placeholder_ms": 10.0, "arrived_ms": 60.0, "interactive_ms": 90.0,
        "time_to_arrival": 50.0, "time_to_interactive": 30.0,
    }
    assert result["boundaries"][1]["time_to_arrival"] is None
    json.dumps(result)
    assert perf.hydration_streaming_install() is True
    assert "__wr_hs_installed__" in driver.execute_script.call_args.args[0]
    driver.execute_script.return_value = log
    assert perf.hydration_streaming_page() == result
    assert driver.execute_script.call_args.args[0].startswith("return window.__wr_hs__")
    assert perf.hydration_streaming_assert(
        boundary="B:1", max_arrival_ms=100, max_interactive_ms=100, expected_order=["B:2", "B:1"]) == result
    with pytest.raises(HydrationStreamingError, match="arrival took 50.0ms"):
        perf.hydration_streaming_assert(log, boundary="B:1", max_arrival_ms=20)
    with pytest.raises(HydrationStreamingError, match="needs the boundary"):
        perf.hydration_streaming_assert(log, max_interactive_ms=20)
    with pytest.raises(HydrationStreamingError, match="never arrived"):
        perf.hydration_streaming_assert({"boundaries": {"B:3": {"placeholder": 1}}})
    with pytest.raises(HydrationStreamingError, match="arrival order"):
        perf.hydration_streaming_assert(log, expected_order=["B:1", "B:2"])


# ---------- inp_tracker / long_animation_frame ----------------------------------------------------------

def test_inp_tracker(driver):
    log = [
        {"name": "click", "interactionId": 7, "duration_ms": 120, "targetTag": "BUTTON"},
        {"name": "keydown", "interactionId": 8, "duration_ms": 640},
        {"name": "mousemove", "interactionId": 0, "duration_ms": 900},
    ]
    result = perf.inp_tracker_report(log)
    assert (result["inp_ms"], result["rating"], result["interactions"]) == (640.0, "poor", 2)
    assert [event["rating"] for event in result["events"]] == ["good", "poor", "poor"]
    json.dumps(result)
    assert perf.inp_tracker_install() is True
    assert "__wr_inp_installed__" in driver.execute_script.call_args.args[0]
    driver.execute_script.return_value = log[:1]
    assert perf.inp_tracker_page()["inp_ms"] == pytest.approx(120.0)
    assert perf.inp_tracker_assert(forbid_poor=True)["rating"] == "good"
    assert perf.inp_tracker_assert(log, max_ms=700)["p75_ms"] == pytest.approx(640.0)
    with pytest.raises(InpTrackerError, match="INP 640.0ms exceeds budget"):
        perf.inp_tracker_assert(log)
    with pytest.raises(InpTrackerError, match="poor interactions: keydown"):
        perf.inp_tracker_assert(log, max_ms=700, forbid_poor=True)


def test_long_animation_frame(driver):
    script = {"name": "app", "source_url": "https://shop.test/app.js", "duration_ms": 80}
    log = [
        {"start_time_ms": 5, "duration_ms": 180, "blocking_duration_ms": 130, "scripts": [script]},
        {"start_time_ms": 400, "duration_ms": 60, "blocking_duration_ms": 10, "scripts": [script]},
    ]
    result = perf.long_animation_frame_report(log, top_n=1)
    assert (result["worst_frame_ms"], result["total_blocking_ms"]) == (180.0, 140.0)
    assert result["top_scripts"][0]["duration_ms"] == pytest.approx(160.0)
    assert len(result["frames"]) == 2
    json.dumps(result)
    assert perf.long_animation_frame_install() is True
    assert "__wr_loaf_installed__" in driver.execute_script.call_args.args[0]
    driver.execute_script.return_value = log[1:]
    assert perf.long_animation_frame_page()["worst_frame_ms"] == pytest.approx(60.0)
    assert perf.long_animation_frame_assert(max_frame_ms=100, max_total_blocking_ms=50)["frames"]
    with pytest.raises(LongAnimationFrameError, match="over 100ms: 180ms"):
        perf.long_animation_frame_assert(log, max_frame_ms=100)
    with pytest.raises(LongAnimationFrameError, match="total blocking 140.0ms"):
        perf.long_animation_frame_assert(log, max_total_blocking_ms=50)


# ---------- lcp_image_audit / lighthouse_regression -----------------------------------------------------

def test_lcp_image_audit(driver):
    result = perf.lcp_image_audit_check("/hero.jpg")
    assert result["candidate"]["url"] == "/hero.jpg"
    assert (result["preloaded"], result["not_lazy_loaded"], result["fetchpriority_high"]) == (True, True, True)
    assert result["problems"] == {}
    json.dumps(result)
    lazy = '<img src="/hero.jpg" loading="lazy">'
    bad = perf.lcp_image_audit_check({"src": "/hero.jpg", "size_px": 9000}, lazy, link_header_urls=["/hero.jpg"])
    assert (bad["preloaded"], bad["not_lazy_loaded"], bad["fetchpriority_high"]) == (True, False, False)
    assert sorted(bad["problems"]) == ["fetchpriority_high", "not_lazy_loaded"]
    assert perf.lcp_image_audit_assert("/hero.jpg") == result
    assert perf.lcp_image_audit_assert("/hero.jpg", lazy, ["/hero.jpg"], checks=["preloaded"])["preloaded"]
    with pytest.raises(LcpImageAuditError, match="loading=\"lazy\""):
        perf.lcp_image_audit_assert("/hero.jpg", lazy)
    with pytest.raises(LcpImageAuditError, match="unknown checks"):
        perf.lcp_image_audit_assert("/hero.jpg", lazy, checks=["cached"])
    assert driver.mock_calls == []


def test_lighthouse_regression(tmp_path):
    baseline, head = _lighthouse(0.95, 1800), _lighthouse(0.80, 3200)
    assert perf.lighthouse_regression_parse(head) == {
        "scores": {"performance": 80.0, "seo": 90.0}, "metrics": {"largest-contentful-paint": 3200.0}}
    report_file = tmp_path / "lh.json"
    report_file.write_text(json.dumps(baseline), encoding="utf-8")
    result = perf.lighthouse_regression_diff(str(report_file), json.dumps(head))
    assert result["score_changes"] == [{"category": "performance", "baseline": 95.0, "head": 80.0, "delta": -15.0}]
    assert result["metric_changes"][0]["delta"] == pytest.approx(1400.0)
    json.dumps(result)
    passed = perf.lighthouse_regression_assert(
        head, baseline, threshold_points=20, metric_budgets={"largest-contentful-paint": 4000})
    assert passed["snapshot"]["scores"]["performance"] == pytest.approx(80.0)
    assert len(passed["score_changes"]) == 1
    assert perf.lighthouse_regression_assert(head)["score_changes"] == []
    with pytest.raises(LighthouseRegressionError, match="regressed"):
        perf.lighthouse_regression_assert(head, baseline)
    with pytest.raises(LighthouseRegressionError, match="exceeds budget 2500"):
        perf.lighthouse_regression_assert(head, metric_budgets={"largest-contentful-paint": 2500})
    with pytest.raises(LighthouseRegressionError, match="not JSON"):
        perf.lighthouse_regression_parse("{broken")


# ---------- resource_hints_audit / third_party_budget ---------------------------------------------------

def test_resource_hints_audit(driver):
    hints = perf.resource_hints_audit_parse(HEAD_HTML)
    assert [(hint["kind"], hint["href"], hint["as_"]) for hint in hints] == [
        ("preload", "/app.css", "style"), ("preload", "/hero.jpg", "image"),
        ("preconnect", "https://cdn.example.com", ""),
    ]
    json.dumps(hints)
    assert perf.resource_hints_audit_page() == hints
    unused = perf.resource_hints_audit_unused(["https://shop.test/app.css"])
    assert [hint["href"] for hint in unused] == ["/hero.jpg"]
    used = ["https://shop.test/app.css", "https://shop.test/hero.jpg"]
    assert perf.resource_hints_audit_assert(used_urls=used, origins=["https://cdn.example.com/"]) == hints
    with pytest.raises(ResourceHintsAuditError, match="unused resource hint"):
        perf.resource_hints_audit_assert(HEAD_HTML, used_urls=[])
    with pytest.raises(ResourceHintsAuditError, match="preconnect"):
        perf.resource_hints_audit_assert(HEAD_HTML, origins=["https://fonts.example.com"])
    with pytest.raises(ResourceHintsAuditError, match="missing as="):
        perf.resource_hints_audit_assert('<link rel="preload" href="/x.js">')
    assert driver.mock_calls == []


def test_third_party_budget():
    requests = perf.third_party_budget_classify(HEAD_HAR, "shop.test")
    assert [(row["vendor"], row["bytes_transferred"], row["blocking"]) for row in requests] == [
        ("google_analytics", 2000, True)]
    custom = perf.third_party_budget_classify(
        _har(("https://t.acme.io/p.gif", "image", 40)), "shop.test", extra_vendors={"acme": ["acme.io"]})
    assert custom[0]["vendor"] == "acme"
    result = perf.third_party_budget_evaluate(HEAD_HAR, "shop.test", budget={"max_bytes": 1000})
    assert result["passed"] is False
    assert result["breaches"] == ["bytes 2000 > 1000"]
    assert result["by_vendor"] == {"google_analytics": {"requests": 1, "bytes": 2000, "blocking_ms": 120.0}}
    json.dumps(result)
    assert perf.third_party_budget_assert(HEAD_HAR, "shop.test", budget={"max_requests": 1})["passed"] is True
    with pytest.raises(ThirdPartyBudgetError, match="bytes 2000 > 1000"):
        perf.third_party_budget_assert(HEAD_HAR, "shop.test", budget={"max_bytes": 1000})
    with pytest.raises(ThirdPartyBudgetError, match="bad budget"):
        perf.third_party_budget_evaluate(HEAD_HAR, "shop.test", budget={"max_hosts": 1})


# ---------- backend_log_correlator ----------------------------------------------------------------------

def test_backend_log_correlator_file_and_attach(tmp_path):
    assert perf2.backend_log_correlator_trace_id(TRACEPARENT) == TRACE_ID
    assert perf2.backend_log_correlator_trace_id(TRACE_ID.upper()) == TRACE_ID
    with pytest.raises(BackendLogCorrelatorError):
        perf2.backend_log_correlator_trace_id("not-a-trace")
    log_file = tmp_path / "api.log"
    log_file.write_text(
        json.dumps({"trace_id": TRACE_ID, "level": "error", "msg": "db timeout", "app": "api", "pod": "a1"})
        + "\n" + json.dumps({"trace_id": "f" * 32, "msg": "other"})
        + f"\nplain line for {TRACE_ID}\n",
        encoding="utf-8",
    )
    logs = perf2.backend_log_correlator_file(TRACEPARENT, str(log_file))
    assert [(log["level"], log["message"], log["service"]) for log in logs] == [
        ("error", "db timeout", "api"), ("info", f"plain line for {TRACE_ID}", None)]
    assert logs[0]["extra"] == {"pod": "a1"}
    json.dumps(logs)
    assert len(perf2.backend_log_correlator_file(TRACE_ID, str(log_file), fallback_to_substring=False)) == 1
    written = perf2.backend_log_correlator_attach(str(tmp_path), logs)
    assert written == str(tmp_path / "backend_logs.json")
    assert json.loads((tmp_path / "backend_logs.json").read_text(encoding="utf-8")) == logs
    with pytest.raises(BackendLogCorrelatorError, match="bare file name"):
        perf2.backend_log_correlator_attach(str(tmp_path), logs, filename="../escape.json")
    with pytest.raises(BackendLogCorrelatorError, match="bad log entry"):
        perf2.backend_log_correlator_attach(str(tmp_path), [{"level": "info"}])
    with pytest.raises(BackendLogCorrelatorError, match="not found"):
        perf2.backend_log_correlator_attach(str(tmp_path / "missing"), logs)


def test_backend_log_correlator_network_fetchers():
    loki = MagicMock()
    loki.json.return_value = {"data": {"result": [
        {"stream": {"level": "warn", "app": "cart"}, "values": [["1700000000", "slow query"]]}]}}
    with patch("requests.get", return_value=loki) as get:
        logs = perf2.backend_log_correlator_loki(TRACE_ID, "http://loki.test/", limit=5)
    assert logs == [{
        "timestamp": "1700000000", "level": "warn", "message": "slow query", "service": "cart",
        "span_id": None, "extra": {},
    }]
    assert get.call_args.args == ("http://loki.test/loki/api/v1/query_range",)
    assert get.call_args.kwargs["params"] == {"query": f'{{trace_id="{TRACE_ID}"}}', "limit": 5}
    elastic = MagicMock()
    elastic.json.return_value = {"hits": {"hits": [{"_source": {"message": "boom", "severity": "error"}}]}}
    with patch("requests.post", return_value=elastic) as post:
        logs = perf2.backend_log_correlator_elasticsearch(TRACEPARENT, "http://es.test", "logs-*", size=3)
    assert [(log["level"], log["message"]) for log in logs] == [("error", "boom")]
    assert post.call_args.args == ("http://es.test/logs-*/_search",)
    assert post.call_args.kwargs["json"] == {"size": 3, "query": {"term": {"trace_id": TRACE_ID}}}


# ---------- console_error_budget ------------------------------------------------------------------------

def test_console_error_budget(driver):
    messages = [
        {"severity": "error", "text": "TypeError: x is undefined", "url": "https://shop.test/app.js", "line": 3},
        {"severity": "warn", "text": "deprecated API"},
        {"severity": "error", "text": "ResizeObserver loop limit exceeded"},
    ]
    result = perf2.console_error_budget_evaluate(messages, budget={"ignore_patterns": ["ResizeObserver"]})
    assert (result["passed"], result["error_count"], result["warning_count"], result["ignored_count"]) == (
        False, 1, 1, 1)
    assert result["breaches"] == ["errors 1 > max_errors 0"]
    assert result["sampled"][0]["line"] == 3
    json.dumps(result)
    cdp = [{"type": "error", "args": [{"value": "boom"}, {"description": "Error: x"}]}]
    assert perf2.console_error_budget_evaluate(cdp, source="cdp_console")["sampled"][0]["text"] == "boom Error: x"
    thrown = [{"exceptionDetails": {"text": "Uncaught", "lineNumber": 9}}]
    assert perf2.console_error_budget_evaluate(thrown, source="cdp_exception")["error_count"] == 1
    driver.get_log.return_value = [{"level": "SEVERE", "message": "404 /api", "timestamp": 1700000000000}]
    assert perf2.console_error_budget_page(budget={"max_errors": 1})["passed"] is True
    driver.get_log.assert_called_with("browser")
    with pytest.raises(ConsoleBudgetError, match="errors 1 > max_errors 0"):
        perf2.console_error_budget_assert()
    assert perf2.console_error_budget_assert(messages[1:2])["warning_count"] == 1
    with pytest.raises(ConsoleBudgetError, match="unknown source"):
        perf2.console_error_budget_evaluate(messages, source="playwright")
    with pytest.raises(ConsoleBudgetError, match="bad budget"):
        perf2.console_error_budget_evaluate(messages, budget={"max_infos": 1})


# ---------- otel_bridge ---------------------------------------------------------------------------------

def test_otel_bridge(driver):
    fresh = perf2.otel_bridge_new_context(sampled=False)
    assert fresh["traceparent"] == f"00-{fresh['trace_id']}-{fresh['span_id']}-00"
    parsed = perf2.otel_bridge_parse(TRACEPARENT)
    assert parsed == {
        "trace_id": TRACE_ID, "span_id": "b7ad6b7169203331", "sampled": True, "version": "00",
        "tracestate": None, "traceparent": TRACEPARENT,
    }
    json.dumps(parsed)
    injected = perf2.otel_bridge_inject(TRACEPARENT, tracestate="vendor=1")
    assert injected["tracestate"] == "vendor=1"
    driver.execute_cdp_cmd.assert_called_with(
        "Network.setExtraHTTPHeaders", {"headers": {"traceparent": TRACEPARENT, "tracestate": "vendor=1"}})
    with patch("je_web_runner.utils.otel_bridge.trace_bridge.current_otel_context", return_value=None):
        generated = perf2.otel_bridge_inject()
    assert len(generated["trace_id"]) == 32
    assert driver.execute_cdp_cmd.call_args.args[1] == {"headers": {"traceparent": generated["traceparent"]}}
    assert perf2.otel_bridge_clear() is True
    driver.execute_cdp_cmd.assert_called_with("Network.setExtraHTTPHeaders", {"headers": {}})
    assert perf2.otel_bridge_trace_link(TRACEPARENT, jaeger_base="http://jaeger.test/") == (
        f"http://jaeger.test/trace/{TRACE_ID}")
    assert perf2.otel_bridge_trace_link(TRACEPARENT) is None
    with pytest.raises(TraceBridgeError):
        perf2.otel_bridge_inject("00-zz-yy-01")


# ---------- bidi_backend / cdp_tap ----------------------------------------------------------------------

def test_bidi_backend(driver):
    subscription = perf2.bidi_backend_subscribe()
    assert subscription == {"subscription_id": subscription["subscription_id"], "event": "console",
                            "backend": "selenium"}
    handler = driver.script.add_console_message_handler.call_args.args[0]
    handler(MagicMock(type="error", text="boom"))
    expected = [{"name": "console", "payload": {"type": "error", "text": "boom"}}]
    assert perf2.bidi_backend_events() == expected
    json.dumps(expected)
    assert perf2.bidi_backend_events(clear=True) == expected
    assert perf2.bidi_backend_events() == []
    handler(MagicMock(type="log", text="again"))
    with pytest.raises(BidiBackendError, match="no translator"):
        perf2.bidi_backend_subscribe("response")
    assert perf2.bidi_backend_reset() == 1
    driver.script.remove_console_message_handler.assert_called_once()
    assert perf2.bidi_backend_events() == []
    assert perf2.bidi_backend_reset() == 0


def test_cdp_tap(driver, tmp_path):
    original = driver.execute_cdp_cmd
    original.side_effect = [{"frameId": "F1"}, RuntimeError("target closed")]
    output = tmp_path / "cdp" / "tap.ndjson"
    assert perf2.cdp_tap_records() == []
    assert perf2.cdp_tap_start(str(output)) is True
    with pytest.raises(CdpTapError, match="already running"):
        perf2.cdp_tap_start(str(output))
    assert driver.execute_cdp_cmd("Page.navigate", {"url": "https://shop.test"}) == {"frameId": "F1"}
    with pytest.raises(RuntimeError):
        driver.execute_cdp_cmd("Page.reload")
    assert [record["method"] for record in perf2.cdp_tap_records()] == ["Page.navigate", "Page.reload"]
    stopped = perf2.cdp_tap_stop()
    assert stopped["path"] == str(output)
    assert stopped["records"][0]["return_value"] == {"frameId": "F1"}
    assert "target closed" in stopped["records"][1]["error"]
    json.dumps(stopped)
    assert driver.execute_cdp_cmd is original
    assert perf2.cdp_tap_load(str(output)) == stopped["records"]
    with pytest.raises(CdpTapError, match="no CDP recording"):
        perf2.cdp_tap_stop()
    with pytest.raises(CdpTapError, match="not found"):
        perf2.cdp_tap_load(str(tmp_path / "missing.ndjson"))


# ---------- event_bus / failure_bundle ------------------------------------------------------------------

def test_event_bus(tmp_path):
    bus_file = str(tmp_path / "bus" / "events.ndjson")
    assert perf2.event_bus_poll(bus_file) == {"events": [], "offset": 0}
    first = perf2.event_bus_publish(bus_file, "setup.done", {"shard": 1}, sender="shard-1")
    assert (first["topic"], first["payload"], first["sender"]) == ("setup.done", {"shard": 1}, "shard-1")
    json.dumps(first)
    after_first = perf2.event_bus_poll(bus_file)
    assert after_first["events"] == [first]
    second = perf2.event_bus_publish(bus_file, "shard.started", {"shard": 2})
    later = perf2.event_bus_poll(bus_file, offset=after_first["offset"], topics=["shard.started"])
    assert later["events"] == [second]
    assert later["offset"] > after_first["offset"]
    assert perf2.event_bus_poll(bus_file, topics=["nothing"])["events"] == []
    assert perf2.event_bus_wait_for(bus_file, "shard.started", match={"shard": 2}, timeout=1) == second
    with pytest.raises(EventBusError, match="timed out"):
        perf2.event_bus_wait_for(bus_file, "shard.started", match={"shard": 9}, timeout=0.05)
    with pytest.raises(EventBusError, match="topic"):
        perf2.event_bus_publish(bus_file, "")


def test_failure_bundle(driver, tmp_path):
    extra = tmp_path / "server.log"
    extra.write_text("stack trace", encoding="utf-8")
    artifacts = {
        "dom": "<p>broken</p>", "console": [{"level": "error", "text": "boom"}],
        "network": [{"url": "/api", "status": 500}], "texts": {"notes.txt": "seen twice"}, "files": [str(extra)],
    }
    target = str(tmp_path / "out" / "login.zip")
    written = perf2.failure_bundle_write(target, "login", "AssertionError('x')", {"build": 7}, artifacts)
    assert written["path"] == target
    assert (written["manifest"]["test_name"], written["manifest"]["metadata"]) == ("login", {"build": 7})
    names = [artifact["name"] for artifact in written["manifest"]["artifacts"]]
    assert names == ["artifacts/console.json", "artifacts/dom.html", "artifacts/network.json",
                     "artifacts/notes.txt", "artifacts/server.log"]
    json.dumps(written)
    read = perf2.failure_bundle_read(target, include_text=True)
    assert read["files"] == names
    assert read["texts"]["artifacts/dom.html"] == "<p>broken</p>"
    assert json.loads(read["texts"]["artifacts/network.json"]) == [{"url": "/api", "status": 500}]
    assert perf2.failure_bundle_read(target)["texts"] == {}
    driver.get_screenshot_as_png.return_value = b"\x89PNG"
    captured = perf2.failure_bundle_capture(str(tmp_path / "page.zip"), "cart", "TimeoutError()")
    assert [artifact["name"] for artifact in captured["manifest"]["artifacts"]] == [
        "artifacts/dom.html", "artifacts/screenshot.png"]
    page = perf2.failure_bundle_read(captured["path"], include_text=True)
    assert page["texts"] == {"artifacts/dom.html": HEAD_HTML}
    with pytest.raises(FailureBundleError, match="unknown artifacts"):
        perf2.failure_bundle_write(target, "login", "x", artifacts={"video": "a.webm"})
    with pytest.raises(FailureBundleError, match="file not found"):
        perf2.failure_bundle_write(target, "login", "x", artifacts={"files": [str(tmp_path / "none.log")]})
    with pytest.raises(FailureBundleError, match="bundle not found"):
        perf2.failure_bundle_read(str(tmp_path / "none.zip"))


# ---------- memory_leak / memory_pressure_emulate -------------------------------------------------------

def test_memory_leak(driver):
    driver.execute_script.return_value = 4096
    assert perf2.memory_leak_sample() == 4096
    result = perf2.memory_leak_trend([1000, 1500, 2000])
    assert result == {
        "samples": [{"iteration": 0, "used_heap_bytes": 1000}, {"iteration": 1, "used_heap_bytes": 1500},
                    {"iteration": 2, "used_heap_bytes": 2000}],
        "slope_bytes_per_iter": 500.0, "delta_bytes": 1000,
    }
    json.dumps(result)
    assert perf2.memory_leak_trend([900, 900, 900], max_bytes_per_iter=10)["slope_bytes_per_iter"] == 0
    with pytest.raises(MemoryLeakError, match="heap grew 500.0 B/iter"):
        perf2.memory_leak_trend([1000, 1500, 2000], max_bytes_per_iter=100)
    with pytest.raises(MemoryLeakError, match="iterations must be >= 2"):
        perf2.memory_leak_trend([1000])
    driver.execute_script.return_value = -1
    with pytest.raises(MemoryLeakError):
        perf2.memory_leak_sample()


def test_memory_pressure_emulate(driver):
    profiles = perf2.memory_pressure_emulate_profiles()
    assert [profile["name"] for profile in profiles] == ["low_end_phone", "critical_pressure", "single_core"]
    assert profiles[1]["pressure_level"] == "critical"
    json.dumps(profiles)
    payloads = perf2.memory_pressure_emulate_payloads("single_core")
    assert payloads == [
        {"method": "Emulation.setHardwareConcurrencyOverride", "params": {"hardwareConcurrency": 1}},
        {"method": "Emulation.setCPUThrottlingRate", "params": {"rate": 2.0}},
        {"method": "Memory.simulatePressureNotification", "params": {"level": "fair"}},
    ]
    custom = {"name": "slow", "cpu_throttle_rate": 6, "pressure_level": "critical"}
    applied = perf2.memory_pressure_emulate_apply(custom)
    assert applied[1]["params"] == {"rate": 6}
    assert [call.args[0] for call in driver.execute_cdp_cmd.call_args_list] == [
        payload["method"] for payload in applied]
    driver.execute_cdp_cmd.reset_mock()
    assert perf2.memory_pressure_emulate_restore() is True
    assert driver.execute_cdp_cmd.call_args_list[1].args == ("Emulation.setCPUThrottlingRate", {"rate": 1.0})
    assert driver.execute_cdp_cmd.call_count == 3
    for bad in ("warp_speed", {"name": "x", "cpu_throttle_rate": 0.5}, {"name": "x", "pressure_level": "hot"},
                {"cores": 2}):
        with pytest.raises(MemoryPressureError):
            perf2.memory_pressure_emulate_payloads(bad)


# ---------- third_party_block_test ----------------------------------------------------------------------

def test_third_party_block_test(driver):
    vendors = perf2.third_party_block_test_vendors()
    assert {"name": "hotjar", "patterns": ["*://*.hotjar.com/*"], "critical_path": False} in vendors
    json.dumps(vendors)
    custom = {"name": "chat", "patterns": ["*://chat.example.com/*"]}
    blocked = perf2.third_party_block_test_block(["hotjar", custom])
    assert blocked == {"vendors": ["hotjar", "chat"], "patterns": ["*://*.hotjar.com/*", "*://chat.example.com/*"]}
    driver.execute_cdp_cmd.assert_called_with("Network.setBlockedURLs", {"urls": blocked["patterns"]})
    assert perf2.third_party_block_test_unblock() is True
    driver.execute_cdp_cmd.assert_called_with("Network.setBlockedURLs", {"urls": []})
    with pytest.raises(ThirdPartyBlockError, match="unknown vendor"):
        perf2.third_party_block_test_block(["myspace"])
    with pytest.raises(ThirdPartyBlockError, match="bad vendor"):
        perf2.third_party_block_test_block([{"name": "chat"}])
    outcomes = [
        {"vendor": "hotjar", "resilience": "resilient"},
        {"vendor": "stripe", "resilience": "broken", "error": "TimeoutError()", "notes": ["critical_path vendor"]},
    ]
    assert perf2.third_party_block_test_assert(outcomes, ["hotjar"]) == [
        {"vendor": "hotjar", "resilience": "resilient", "error": None, "notes": []},
        {"vendor": "stripe", "resilience": "broken", "error": "TimeoutError()", "notes": ["critical_path vendor"]},
    ]
    with pytest.raises(ThirdPartyBlockError, match=r"\['stripe', 'sentry'\]"):
        perf2.third_party_block_test_assert(outcomes, ["hotjar", "stripe", "sentry"])
    with pytest.raises(ThirdPartyBlockError, match="bad outcome"):
        perf2.third_party_block_test_assert([{"vendor": "hotjar", "resilience": "fine"}], ["hotjar"])
