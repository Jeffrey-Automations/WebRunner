"""
效能類函式庫的命令轉接層
Command adapters for the page-performance libraries: bundle and third-party budgets, critical CSS, fonts,
hydration, INP, LCP image, Lighthouse, long animation frames and resource hints.

Every command takes and returns JSON values. A HAR or a Lighthouse report is given as an object, as JSON
text, or as the path of a file holding it. The observability and CDP libraries are in
``_commands_performance_2``.
"""
# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import page_source, selenium_driver, to_plain


def _json_text(value: Any) -> Any:
    """``value`` itself, or the text of the file it names when it is a string that is not JSON text."""
    if not isinstance(value, str) or value.lstrip().startswith(("{", "[")):
        return value
    return Path(value).read_text(encoding="utf-8")


def _html(html: str | None, command: str) -> str:
    """``html``, or the current page's HTML when it is ``None``."""
    return page_source(command) if html is None else html


def _payload(payload: Any, command: str, script: str) -> Any:
    """``payload``, or what the library's fixed harvest ``script`` returns in the browser when ``None``."""
    return selenium_driver(command).execute_script(script) if payload is None else payload


def _with_properties(items: list[Any], names: tuple[str, ...]) -> list[dict[str, Any]]:
    """Each item as an object, with the values of its computed properties or methods ``names`` added."""
    rows = []
    for item in items:
        row = to_plain(item)
        for name in names:
            value = getattr(item, name)
            row[name] = value() if callable(value) else value
        rows.append(row)
    return rows


# ---------- bundle_budget -------------------------------------------------------------------------------

def _bundle_report(har: Any, budgets: dict[str, int] | None, biggest_n: int) -> Any:
    from je_web_runner.utils.bundle_budget import budget as lib
    chosen = lib.DEFAULT_BUDGETS
    if budgets is not None:
        try:
            chosen = [lib.Budget(kind=lib.AssetKind(kind), max_bytes=int(limit)) for kind, limit in budgets.items()]
        except ValueError as error:
            raise lib.BundleBudgetError(f"bad budgets: {error}") from error
    return lib.evaluate_budget(lib.assets_from_har(_json_text(har)), chosen, biggest_n=biggest_n)


def _bundle_report_plain(report: Any) -> dict[str, Any]:
    return {
        "passed": report.passed(),
        "totals": {kind.value: total for kind, total in report.totals.items()},
        "breaches": to_plain(report.breaches),
        "biggest_assets": to_plain(report.biggest_assets),
    }


def bundle_budget_evaluate(har: Any, budgets: dict[str, int] | None = None, biggest_n: int = 10) -> dict[str, Any]:
    """
    Add up a HAR's bytes per asset kind and compare them with size budgets.

    :param har: the HAR as an object, as JSON text, or the path of a ``.har`` file.
    :param budgets: ``{kind: max_bytes}`` for the kinds ``script``, ``stylesheet``, ``image``, ``font``,
        ``media``, ``document``, ``xhr``, ``other``; the library's defaults when omitted.
    :param biggest_n: how many of the biggest assets to list.
    :return: ``passed``, ``totals`` per kind, ``breaches`` and ``biggest_assets``.
    """
    return _bundle_report_plain(_bundle_report(har, budgets, biggest_n))


def bundle_budget_assert(har: Any, budgets: dict[str, int] | None = None, biggest_n: int = 10) -> dict[str, Any]:
    """Fail (``BundleBudgetError``) when a HAR passes a size budget; see ``WR_bundle_budget_evaluate``."""
    from je_web_runner.utils.bundle_budget.budget import assert_within_budget
    report = _bundle_report(har, budgets, biggest_n)
    assert_within_budget(report)
    return _bundle_report_plain(report)


def bundle_budget_markdown(har: Any, budgets: dict[str, int] | None = None, biggest_n: int = 10) -> str:
    """Render a HAR's bundle-budget result as a Markdown table; arguments as ``WR_bundle_budget_evaluate``."""
    from je_web_runner.utils.bundle_budget.budget import report_markdown
    return report_markdown(_bundle_report(har, budgets, biggest_n))


# ---------- bundle_diff_pr ------------------------------------------------------------------------------

def _bundle_diff(base_har: Any, head_har: Any) -> Any:
    from je_web_runner.utils.bundle_diff_pr.diff import diff_hars
    return diff_hars(_json_text(base_har), _json_text(head_har))


def _bundle_diff_plain(diff: Any) -> dict[str, Any]:
    plain: dict[str, Any] = {"unchanged": diff.unchanged, "total_delta_bytes": diff.total_delta_bytes}
    for group in ("added", "removed", "grew", "shrunk"):
        plain[group] = _with_properties(getattr(diff, group), ("delta", "percent"))
    return plain


def bundle_diff_pr_diff(base_har: Any, head_har: Any) -> dict[str, Any]:
    """
    Compare the asset sizes of two HARs (base branch and pull-request head).

    Each HAR is an object, JSON text, or the path of a ``.har`` file.

    :return: ``added``, ``removed``, ``grew``, ``shrunk`` (rows with ``delta`` and ``percent``),
        ``unchanged`` and ``total_delta_bytes``.
    """
    return _bundle_diff_plain(_bundle_diff(base_har, head_har))


def bundle_diff_pr_assert_growth(base_har: Any, head_har: Any, max_growth_bytes: int = 0) -> dict[str, Any]:
    """Fail (``BundleDiffPrError``) when the head HAR outgrows the base HAR by more than ``max_growth_bytes``."""
    from je_web_runner.utils.bundle_diff_pr.diff import assert_under_max_growth
    diff = _bundle_diff(base_har, head_har)
    assert_under_max_growth(diff, max_growth_bytes=max_growth_bytes)
    return _bundle_diff_plain(diff)


def bundle_diff_pr_markdown(base_har: Any, head_har: Any, top_n: int = 10, min_bytes: int = 1024) -> str:
    """Render the size difference of two HARs as Markdown for a pull-request comment."""
    from je_web_runner.utils.bundle_diff_pr.diff import report_markdown
    return report_markdown(_bundle_diff(base_har, head_har), top_n=top_n, min_bytes=min_bytes)


# ---------- critical_css_audit --------------------------------------------------------------------------

def critical_css_audit_analyse(html: str) -> dict[str, Any]:
    """Report an HTML document's critical CSS: inline blocks and bytes, blocking and preloaded stylesheets."""
    from je_web_runner.utils.critical_css_audit.audit import analyse
    return to_plain(analyse(html))


def critical_css_audit_page() -> dict[str, Any]:
    """Report the critical-CSS facts of the current page (see ``WR_critical_css_audit_analyse``)."""
    return critical_css_audit_analyse(page_source("WR_critical_css_audit_page"))


def critical_css_audit_assert(
    html: str | None = None, max_inline_bytes: int = 14 * 1024,
    require_inline: bool = True, require_preload: bool = True,
) -> dict[str, Any]:
    """
    Fail when a document breaks the critical-CSS rules; ``html`` omitted means the current page.

    :param max_inline_bytes: budget for the CSS inlined in ``<head>``.
    :param require_inline: an inline ``<style>`` block must exist.
    :param require_preload: every render-blocking stylesheet must also be preloaded.
    :raises CriticalCssAuditError: when a rule is broken.
    """
    from je_web_runner.utils.critical_css_audit import audit as lib
    report = lib.analyse(_html(html, "WR_critical_css_audit_assert"))
    if require_inline:
        lib.assert_has_inline_critical(report)
    lib.assert_inline_within_budget(report, max_bytes=max_inline_bytes)
    if require_preload:
        lib.assert_external_preloaded(report)
    return to_plain(report)


# ---------- font_loading_strategy -----------------------------------------------------------------------

def font_loading_strategy_parse(css: str) -> list[dict[str, Any]]:
    """List the ``@font-face`` blocks of a stylesheet's text, each with its ``display`` and ``size_adjust``."""
    from je_web_runner.utils.font_loading_strategy.strategy import parse_font_faces
    return to_plain(parse_font_faces(css))


def font_loading_strategy_page() -> list[dict[str, Any]]:
    """List the ``@font-face`` blocks inlined in the current page's HTML (linked stylesheets are not read)."""
    return font_loading_strategy_parse(page_source("WR_font_loading_strategy_page"))


def font_loading_strategy_assert(
    css: str | None = None, strategy: str | None = None, fallback_family: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fail when ``@font-face`` blocks have no ``font-display``; ``css`` omitted means the current page's HTML.

    :param strategy: when given (``swap``, ``fallback``, ``optional`` or ``block``), every block must use it.
    :param fallback_family: when given, that family must declare ``size-adjust``.
    :raises FontLoadingStrategyError: when a check fails.
    """
    from je_web_runner.utils.font_loading_strategy import strategy as lib
    faces = lib.parse_font_faces(_html(css, "WR_font_loading_strategy_assert"))
    lib.assert_no_missing_display(faces)
    if strategy is not None:
        try:
            wanted = lib.Display(strategy)
        except ValueError as error:
            raise lib.FontLoadingStrategyError(f"unknown strategy {strategy!r}") from error
        lib.assert_display_strategy(faces, strategy=wanted)
    if fallback_family is not None:
        lib.assert_size_adjust_for_fallback(fallback_family, faces)
    return to_plain(faces)


# ---------- hydration_check -----------------------------------------------------------------------------

def _hydration_plain(report: Any) -> dict[str, Any]:
    return {"passed": report.passed(), "by_kind": report.by_kind(), "findings": to_plain(report.findings)}


def hydration_check_audit(
    server_html: str | None = None, client_html: str | None = None, console_messages: list[str] | None = None,
) -> dict[str, Any]:
    """
    Look for SSR hydration mismatches in a server/client HTML pair and in console lines.

    :param server_html: the HTML the server sent; compared only when ``client_html`` is given too.
    :param client_html: the HTML after hydration.
    :param console_messages: console lines to scan for the frameworks' hydration warnings.
    :return: ``passed``, ``by_kind`` and the ``findings``.
    """
    from je_web_runner.utils.hydration_check.check import audit
    return _hydration_plain(audit(
        server_html=server_html, client_html=client_html, console_messages=console_messages))


def hydration_check_page(server_html: str, console_messages: list[str] | None = None) -> dict[str, Any]:
    """Compare the server's HTML with the current page's HTML (see ``WR_hydration_check_audit``)."""
    return hydration_check_audit(server_html, page_source("WR_hydration_check_page"), console_messages)


def hydration_check_assert(
    server_html: str | None = None, client_html: str | None = None, console_messages: list[str] | None = None,
) -> dict[str, Any]:
    """Fail (``HydrationCheckError``) on a hydration mismatch; arguments as ``WR_hydration_check_audit``."""
    from je_web_runner.utils.hydration_check import check as lib
    report = lib.audit(server_html=server_html, client_html=client_html, console_messages=console_messages)
    lib.assert_no_mismatch(report)
    return _hydration_plain(report)


# ---------- hydration_streaming -------------------------------------------------------------------------

def _streaming_plain(report: Any) -> dict[str, Any]:
    return {"boundaries": _with_properties(report.boundaries, ("time_to_arrival", "time_to_interactive"))}


def hydration_streaming_install() -> bool:
    """Start recording streaming-SSR boundary arrivals in the current page (run right after navigating)."""
    from je_web_runner.utils.hydration_streaming.timing import INSTALL_SCRIPT
    selenium_driver("WR_hydration_streaming_install").execute_script(INSTALL_SCRIPT)
    return True


def hydration_streaming_parse(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Turn a harvested boundary log ``{"boundaries": {id: {placeholder, arrived, interactive}}}`` into timings.

    :return: ``boundaries``: per id the three times plus ``time_to_arrival`` and ``time_to_interactive``.
    """
    from je_web_runner.utils.hydration_streaming.timing import parse_log
    return _streaming_plain(parse_log(payload))


def hydration_streaming_page() -> dict[str, Any]:
    """Read the boundary timings recorded in the current page since ``WR_hydration_streaming_install``."""
    from je_web_runner.utils.hydration_streaming.timing import HARVEST_SCRIPT
    return hydration_streaming_parse(_payload(None, "WR_hydration_streaming_page", HARVEST_SCRIPT))


def hydration_streaming_assert(
    payload: dict[str, Any] | None = None, boundary: str | None = None,
    max_arrival_ms: float | None = None, max_interactive_ms: float | None = None,
    expected_order: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fail when a streaming boundary never arrived; ``payload`` omitted means the current page's log.

    :param boundary: the boundary id the two time limits apply to.
    :param max_arrival_ms: limit for placeholder-to-arrival of ``boundary``.
    :param max_interactive_ms: limit for arrival-to-interactive of ``boundary``; the page reports a
        boundary interactive with ``__wr_hs_done__(id)``.
    :param expected_order: boundary ids in the order they must arrive.
    :raises HydrationStreamingError: when a check fails.
    """
    from je_web_runner.utils.hydration_streaming import timing as lib
    report = lib.parse_log(_payload(payload, "WR_hydration_streaming_assert", lib.HARVEST_SCRIPT))
    lib.assert_all_arrived(report)
    if (max_arrival_ms is not None or max_interactive_ms is not None) and boundary is None:
        raise lib.HydrationStreamingError("a time limit needs the boundary it applies to")
    if max_arrival_ms is not None:
        lib.assert_arrival_under(report, id_=str(boundary), max_ms=max_arrival_ms)
    if max_interactive_ms is not None:
        lib.assert_interactive_under(report, id_=str(boundary), max_ms=max_interactive_ms)
    if expected_order is not None:
        lib.assert_order(report, expected_order=expected_order)
    return _streaming_plain(report)


# ---------- inp_tracker ---------------------------------------------------------------------------------

def _inp_report(payload: Any, command: str) -> Any:
    from je_web_runner.utils.inp_tracker import tracker as lib
    return lib.InpReport(events=lib.parse_log(_payload(payload, command, lib.HARVEST_SCRIPT)))


def _inp_plain(report: Any) -> dict[str, Any]:
    return {
        "inp_ms": report.inp(),
        "rating": report.rating().value,
        "p75_ms": report.percentile(75),
        "interactions": len(report.filtered()),
        "events": to_plain(report.events),
    }


def inp_tracker_install() -> bool:
    """Start recording interaction timings (Interaction to Next Paint) in the current page."""
    from je_web_runner.utils.inp_tracker.tracker import build_install_script
    selenium_driver("WR_inp_tracker_install").execute_script(build_install_script())
    return True


def inp_tracker_report(payload: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Summarise a harvested interaction log (objects with ``name``, ``interactionId``, ``duration_ms``).

    :return: ``inp_ms``, ``rating``, ``p75_ms``, the number of ``interactions`` and the rated ``events``.
    """
    return _inp_plain(_inp_report(payload, "WR_inp_tracker_report"))


def inp_tracker_page() -> dict[str, Any]:
    """Summarise the interactions recorded in the current page since ``WR_inp_tracker_install``."""
    return _inp_plain(_inp_report(None, "WR_inp_tracker_page"))


def inp_tracker_assert(
    payload: list[dict[str, Any]] | None = None, max_ms: float = 200.0, forbid_poor: bool = False,
) -> dict[str, Any]:
    """
    Fail when the INP passes ``max_ms``; ``payload`` omitted means the current page's log.

    :param forbid_poor: also fail when any single interaction took more than 500 ms.
    :raises InpTrackerError: when a check fails.
    """
    from je_web_runner.utils.inp_tracker import tracker as lib
    report = _inp_report(payload, "WR_inp_tracker_assert")
    lib.assert_inp_under(report, max_ms=max_ms)
    if forbid_poor:
        lib.assert_no_poor_interactions(report)
    return _inp_plain(report)


# ---------- lcp_image_audit -----------------------------------------------------------------------------

_LCP_CHECKS = ("preloaded", "not_lazy_loaded", "fetchpriority_high")


def _lcp_check(candidate: Any, html: str, link_header_urls: list[str] | None) -> dict[str, Any]:
    from je_web_runner.utils.lcp_image_audit import audit as lib
    parsed = lib.parse_candidate({"url": candidate} if isinstance(candidate, str) else candidate)
    checks: dict[str, Callable[[], None]] = {
        "preloaded": lambda: lib.assert_lcp_preloaded(parsed, html, link_header_urls=link_header_urls or ()),
        "not_lazy_loaded": lambda: lib.assert_lcp_not_lazy_loaded(parsed, html),
        "fetchpriority_high": lambda: lib.assert_fetchpriority_high(parsed, html),
    }
    result: dict[str, Any] = {"candidate": to_plain(parsed), "problems": {}}
    for name, check in checks.items():
        try:
            check()
            result[name] = True
        except lib.LcpImageAuditError as error:
            result[name] = False
            result["problems"][name] = str(error)
    return result


def lcp_image_audit_check(
    candidate: Any, html: str | None = None, link_header_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Check how the Largest Contentful Paint image is loaded; ``html`` omitted means the current page.

    :param candidate: the image URL, or an object with ``url`` (or ``src``), ``element_tag``,
        ``render_time_ms``, ``size_px``.
    :param link_header_urls: image URLs preloaded by a ``Link:`` response header.
    :return: ``candidate``, the booleans ``preloaded``, ``not_lazy_loaded``, ``fetchpriority_high``, and
        ``problems`` (check name to message).
    """
    return _lcp_check(candidate, _html(html, "WR_lcp_image_audit_check"), link_header_urls)


def lcp_image_audit_assert(
    candidate: Any, html: str | None = None, link_header_urls: list[str] | None = None,
    checks: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fail when the LCP image is not preloaded, is lazy-loaded or lacks ``fetchpriority="high"``.

    :param checks: the checks that must pass, of ``preloaded``, ``not_lazy_loaded``, ``fetchpriority_high``;
        all three when omitted. Other arguments as ``WR_lcp_image_audit_check``.
    :raises LcpImageAuditError: when a required check fails or a check name is unknown.
    """
    from je_web_runner.utils.lcp_image_audit.audit import LcpImageAuditError
    required = _LCP_CHECKS if checks is None else tuple(checks)
    unknown = [name for name in required if name not in _LCP_CHECKS]
    if unknown:
        raise LcpImageAuditError(f"unknown checks {unknown}; choose from {list(_LCP_CHECKS)}")
    result = _lcp_check(candidate, _html(html, "WR_lcp_image_audit_assert"), link_header_urls)
    failed = [result["problems"][name] for name in required if name in result["problems"]]
    if failed:
        raise LcpImageAuditError("; ".join(failed))
    return result


# ---------- lighthouse_regression -----------------------------------------------------------------------

def _lighthouse_snapshot(report: Any) -> Any:
    from je_web_runner.utils.lighthouse_regression import regression as lib
    source = _json_text(report)
    if isinstance(source, str):
        try:
            source = json.loads(source)
        except ValueError as error:
            raise lib.LighthouseRegressionError(f"report is not JSON: {error}") from error
    return lib.parse_report(source)


def _lighthouse_diff_plain(report: Any) -> dict[str, Any]:
    return {
        "score_changes": _with_properties(report.score_changes, ("delta",)),
        "metric_changes": _with_properties(report.metric_changes, ("delta",)),
    }


def lighthouse_regression_parse(report: Any) -> dict[str, Any]:
    """
    Extract the category scores (0-100) and Core Web Vitals metrics of a Lighthouse JSON result.

    :param report: the result as an object, as JSON text, or the path of the ``lighthouse --output=json`` file.
    :return: ``scores`` and ``metrics``.
    """
    return to_plain(_lighthouse_snapshot(report))


def lighthouse_regression_diff(baseline: Any, head: Any) -> dict[str, Any]:
    """
    Compare two Lighthouse results (each as in ``WR_lighthouse_regression_parse``).

    :return: ``score_changes`` and ``metric_changes``: rows of ``category``, ``baseline``, ``head``, ``delta``.
    """
    from je_web_runner.utils.lighthouse_regression.regression import diff
    return _lighthouse_diff_plain(diff(_lighthouse_snapshot(baseline), _lighthouse_snapshot(head)))


def lighthouse_regression_assert(
    head: Any, baseline: Any = None, threshold_points: float = 5,
    metric_budgets: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Fail when a Lighthouse score dropped against a baseline or a metric passes its budget.

    :param head: the result under test (as in ``WR_lighthouse_regression_parse``).
    :param baseline: the result to compare with; omitted means only ``metric_budgets`` are checked.
    :param threshold_points: the biggest allowed drop of a category score.
    :param metric_budgets: ``{metric: max_value}``, e.g. ``{"largest-contentful-paint": 2500}``.
    :raises LighthouseRegressionError: when a check fails.
    :return: the head ``snapshot`` plus ``score_changes`` and ``metric_changes``.
    """
    from je_web_runner.utils.lighthouse_regression import regression as lib
    snapshot = _lighthouse_snapshot(head)
    changes = lib.RegressionReport()
    if baseline is not None:
        changes = lib.diff(_lighthouse_snapshot(baseline), snapshot)
        lib.assert_no_score_regression(changes, threshold_points=threshold_points)
    for metric, max_value in (metric_budgets or {}).items():
        lib.assert_metric_within(snapshot, metric=metric, max_value=float(max_value))
    return {"snapshot": to_plain(snapshot), **_lighthouse_diff_plain(changes)}


# ---------- long_animation_frame ------------------------------------------------------------------------

def _loaf_report(payload: Any, command: str) -> Any:
    from je_web_runner.utils.long_animation_frame import frames as lib
    return lib.LoafReport(frames=lib.parse_log(_payload(payload, command, lib.HARVEST_SCRIPT)))


def _loaf_plain(report: Any, top_n: int = 5) -> dict[str, Any]:
    return {
        "worst_frame_ms": report.worst_frame_ms(),
        "total_blocking_ms": report.total_blocking_ms(),
        "top_scripts": to_plain(report.top_scripts(n=top_n)),
        "frames": to_plain(report.frames),
    }


def long_animation_frame_install() -> bool:
    """Start recording long animation frames (Chromium's LoAF API) in the current page."""
    from je_web_runner.utils.long_animation_frame.frames import build_install_script
    selenium_driver("WR_long_animation_frame_install").execute_script(build_install_script())
    return True


def long_animation_frame_report(payload: list[dict[str, Any]], top_n: int = 5) -> dict[str, Any]:
    """
    Summarise a harvested long-animation-frame log (objects with ``duration_ms``, ``scripts`` ...).

    :return: ``worst_frame_ms``, ``total_blocking_ms``, the ``top_n`` slowest ``top_scripts`` and the ``frames``.
    """
    return _loaf_plain(_loaf_report(payload, "WR_long_animation_frame_report"), top_n)


def long_animation_frame_page(top_n: int = 5) -> dict[str, Any]:
    """Summarise the long frames recorded in the current page since ``WR_long_animation_frame_install``."""
    return _loaf_plain(_loaf_report(None, "WR_long_animation_frame_page"), top_n)


def long_animation_frame_assert(
    payload: list[dict[str, Any]] | None = None, max_frame_ms: float | None = None,
    max_total_blocking_ms: float | None = None,
) -> dict[str, Any]:
    """
    Fail when a long animation frame or the total blocking time passes a limit.

    ``payload`` omitted means the current page's log; a limit left out is not checked.

    :raises LongAnimationFrameError: when a limit is passed.
    """
    from je_web_runner.utils.long_animation_frame import frames as lib
    report = _loaf_report(payload, "WR_long_animation_frame_assert")
    if max_frame_ms is not None:
        lib.assert_no_frame_over(report, max_ms=max_frame_ms)
    if max_total_blocking_ms is not None:
        lib.assert_total_blocking_under(report, max_ms=max_total_blocking_ms)
    return _loaf_plain(report)


# ---------- resource_hints_audit ------------------------------------------------------------------------

def resource_hints_audit_parse(html: str) -> list[dict[str, Any]]:
    """List a document's resource hints (preload, prefetch, preconnect ...) with ``kind``, ``href``, ``as_``."""
    from je_web_runner.utils.resource_hints_audit.hints import parse_hints
    return to_plain(parse_hints(html))


def resource_hints_audit_page() -> list[dict[str, Any]]:
    """List the resource hints of the current page (see ``WR_resource_hints_audit_parse``)."""
    return resource_hints_audit_parse(page_source("WR_resource_hints_audit_page"))


def resource_hints_audit_unused(used_urls: list[str], html: str | None = None) -> list[dict[str, Any]]:
    """
    List the preload / prefetch hints whose URL is not among the URLs the page fetched.

    :param used_urls: the fetched URLs, e.g. the request URLs of a HAR.
    :param html: the document; omitted means the current page.
    """
    from je_web_runner.utils.resource_hints_audit import hints as lib
    return to_plain(lib.find_unused_hints(
        lib.parse_hints(_html(html, "WR_resource_hints_audit_unused")), used_urls))


def resource_hints_audit_assert(
    html: str | None = None, used_urls: list[str] | None = None, origins: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fail when a ``preload`` has no ``as=``; ``html`` omitted means the current page.

    :param used_urls: when given, every preload / prefetch hint must be among these fetched URLs.
    :param origins: origins that must have a ``preconnect`` hint.
    :raises ResourceHintsAuditError: when a check fails.
    """
    from je_web_runner.utils.resource_hints_audit import hints as lib
    found = lib.parse_hints(_html(html, "WR_resource_hints_audit_assert"))
    lib.assert_preload_has_as(found)
    if used_urls is not None:
        lib.assert_no_unused_hints(found, used_urls)
    for origin in origins or []:
        lib.assert_origin_preconnected(found, origin=origin)
    return to_plain(found)


# ---------- third_party_budget --------------------------------------------------------------------------

def _third_party_report(
    har: Any, first_party_hostname: str, budget: dict[str, Any] | None,
    extra_vendors: dict[str, Any] | None,
) -> Any:
    from je_web_runner.utils.third_party_budget import budget as lib
    try:
        limits = lib.ThirdPartyBudget(**(budget or {}))
    except TypeError as error:
        raise lib.ThirdPartyBudgetError(f"bad budget: {error}") from error
    requests = lib.classify_har(
        _json_text(har), first_party_hostname=first_party_hostname, extra_vendors=extra_vendors)
    return lib.evaluate(requests, limits)


def _third_party_plain(report: Any) -> dict[str, Any]:
    return {"passed": report.passed(), **to_plain(report)}


def third_party_budget_classify(
    har: Any, first_party_hostname: str, extra_vendors: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    List a HAR's requests to hosts other than the site's own, each with its vendor.

    :param har: the HAR as an object, as JSON text, or the path of a ``.har`` file.
    :param first_party_hostname: the site's host; it and its subdomains are first party.
    :param extra_vendors: ``{vendor: [hosts]}`` added to the built-in vendor catalogue.
    """
    from je_web_runner.utils.third_party_budget.budget import classify_har
    return to_plain(classify_har(
        _json_text(har), first_party_hostname=first_party_hostname, extra_vendors=extra_vendors))


def third_party_budget_evaluate(
    har: Any, first_party_hostname: str, budget: dict[str, Any] | None = None,
    extra_vendors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Add up a HAR's third-party requests and compare them with a budget.

    :param budget: any of ``max_requests``, ``max_bytes``, ``max_blocking_ms``, ``max_vendors``.
        Other arguments as ``WR_third_party_budget_classify``.
    :return: ``passed``, ``total_requests``, ``total_bytes``, ``blocking_ms``, ``by_vendor``, ``breaches``.
    """
    return _third_party_plain(_third_party_report(har, first_party_hostname, budget, extra_vendors))


def third_party_budget_assert(
    har: Any, first_party_hostname: str, budget: dict[str, Any] | None = None,
    extra_vendors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail (``ThirdPartyBudgetError``) over budget; arguments as ``WR_third_party_budget_evaluate``."""
    from je_web_runner.utils.third_party_budget.budget import assert_within_budget
    report = _third_party_report(har, first_party_hostname, budget, extra_vendors)
    assert_within_budget(report)
    return _third_party_plain(report)


PERFORMANCE_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_bundle_budget_evaluate": bundle_budget_evaluate,
    "WR_bundle_budget_assert": bundle_budget_assert,
    "WR_bundle_budget_markdown": bundle_budget_markdown,
    "WR_bundle_diff_pr_diff": bundle_diff_pr_diff,
    "WR_bundle_diff_pr_assert_growth": bundle_diff_pr_assert_growth,
    "WR_bundle_diff_pr_markdown": bundle_diff_pr_markdown,
    "WR_critical_css_audit_analyse": critical_css_audit_analyse,
    "WR_critical_css_audit_page": critical_css_audit_page,
    "WR_critical_css_audit_assert": critical_css_audit_assert,
    "WR_font_loading_strategy_parse": font_loading_strategy_parse,
    "WR_font_loading_strategy_page": font_loading_strategy_page,
    "WR_font_loading_strategy_assert": font_loading_strategy_assert,
    "WR_hydration_check_audit": hydration_check_audit,
    "WR_hydration_check_page": hydration_check_page,
    "WR_hydration_check_assert": hydration_check_assert,
    "WR_hydration_streaming_install": hydration_streaming_install,
    "WR_hydration_streaming_parse": hydration_streaming_parse,
    "WR_hydration_streaming_page": hydration_streaming_page,
    "WR_hydration_streaming_assert": hydration_streaming_assert,
    "WR_inp_tracker_install": inp_tracker_install,
    "WR_inp_tracker_report": inp_tracker_report,
    "WR_inp_tracker_page": inp_tracker_page,
    "WR_inp_tracker_assert": inp_tracker_assert,
    "WR_lcp_image_audit_check": lcp_image_audit_check,
    "WR_lcp_image_audit_assert": lcp_image_audit_assert,
    "WR_lighthouse_regression_parse": lighthouse_regression_parse,
    "WR_lighthouse_regression_diff": lighthouse_regression_diff,
    "WR_lighthouse_regression_assert": lighthouse_regression_assert,
    "WR_long_animation_frame_install": long_animation_frame_install,
    "WR_long_animation_frame_report": long_animation_frame_report,
    "WR_long_animation_frame_page": long_animation_frame_page,
    "WR_long_animation_frame_assert": long_animation_frame_assert,
    "WR_resource_hints_audit_parse": resource_hints_audit_parse,
    "WR_resource_hints_audit_page": resource_hints_audit_page,
    "WR_resource_hints_audit_unused": resource_hints_audit_unused,
    "WR_resource_hints_audit_assert": resource_hints_audit_assert,
    "WR_third_party_budget_classify": third_party_budget_classify,
    "WR_third_party_budget_evaluate": third_party_budget_evaluate,
    "WR_third_party_budget_assert": third_party_budget_assert,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset()
