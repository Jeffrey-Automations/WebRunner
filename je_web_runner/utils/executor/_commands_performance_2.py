"""
觀測與 CDP 類函式庫的命令轉接層
Command adapters for the observability and CDP libraries: backend log correlation, console error budget,
trace-context injection, BiDi events, CDP recording, the file event bus, failure bundles, heap growth,
memory-pressure emulation and third-party blocking. The page-performance audits are in
``_commands_performance``.

Every command takes and returns JSON values.
"""
# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import selenium_driver, to_plain

# What the stateful commands keep between actions: the BiDi bridge with the events it received, and the
# CDP recording in progress.
_BIDI: dict[str, Any] = {"bridge": None, "events": []}
_TAP: dict[str, Any] = {}


# ---------- backend_log_correlator ----------------------------------------------------------------------

def _correlated(trace: str, fetcher: Any) -> list[dict[str, Any]]:
    from je_web_runner.utils.backend_log_correlator.correlator import correlate
    return to_plain(correlate(trace, [fetcher]))


def backend_log_correlator_trace_id(trace: str) -> str:
    """
    Return the 32-hex trace id of a W3C ``traceparent`` header value (or check a bare trace id).

    :raises BackendLogCorrelatorError: when the value is malformed.
    """
    from je_web_runner.utils.backend_log_correlator import correlator as lib
    value = trace.strip() if isinstance(trace, str) else ""
    return lib.parse_traceparent(value) if "-" in value else lib.validate_trace_id(value)


def backend_log_correlator_file(
    trace: str, log_path: str, trace_field: str = "trace_id", fallback_to_substring: bool = True,
) -> list[dict[str, Any]]:
    """
    List the lines of a backend log file that belong to a trace.

    :param trace: a trace id or a full ``traceparent`` value.
    :param log_path: a JSON-lines or plain-text log file.
    :param trace_field: the JSON field holding the trace id.
    :param fallback_to_substring: match plain-text lines that contain the trace id.
    :return: objects with ``timestamp``, ``level``, ``message``, ``service``, ``span_id``, ``extra``.
    """
    from je_web_runner.utils.backend_log_correlator.correlator import fetch_file_log
    return _correlated(trace, fetch_file_log(
        log_path, trace_field=trace_field, fallback_to_substring=fallback_to_substring))


def backend_log_correlator_loki(
    trace: str, base_url: str, label: str = "trace_id", limit: int = 1000, timeout: float = 15.0,
) -> list[dict[str, Any]]:
    """
    Fetch the log lines of a trace from Grafana Loki at ``base_url`` (sends an HTTP request).

    :param label: the Loki label holding the trace id.
    :raises BackendLogCorrelatorError: when the request fails.
    """
    from je_web_runner.utils.backend_log_correlator.correlator import fetch_loki
    return _correlated(trace, fetch_loki(base_url, label=label, timeout=timeout, limit=limit))


def backend_log_correlator_elasticsearch(
    trace: str, base_url: str, index: str, trace_field: str = "trace_id", size: int = 500,
) -> list[dict[str, Any]]:
    """
    Fetch the log lines of a trace from an Elasticsearch ``index`` at ``base_url`` (sends an HTTP request).

    :raises BackendLogCorrelatorError: when the request fails.
    """
    from je_web_runner.utils.backend_log_correlator.correlator import fetch_elasticsearch
    return _correlated(trace, fetch_elasticsearch(base_url, index, trace_field=trace_field, size=size))


def backend_log_correlator_attach(
    bundle_dir: str, logs: list[dict[str, Any]], filename: str = "backend_logs.json",
) -> str:
    """
    Write correlated log lines (as the fetch commands return them) into a failure-bundle directory.

    :param filename: a file name inside ``bundle_dir``, without directories.
    :return: the path of the written file.
    :raises BackendLogCorrelatorError: when the directory is missing or ``filename`` holds a directory.
    """
    from je_web_runner.utils.backend_log_correlator import correlator as lib
    if Path(filename).name != filename:
        raise lib.BackendLogCorrelatorError(f"filename must be a bare file name, got {filename!r}")
    names = {field.name for field in dataclasses.fields(lib.CorrelatedLog)}
    try:
        entries = [lib.CorrelatedLog(**{key: log[key] for key in log if key in names}) for log in logs]
    except TypeError as error:
        raise lib.BackendLogCorrelatorError(f"bad log entry: {error}") from error
    return str(lib.attach_to_failure_bundle(bundle_dir, entries, filename=filename))


# ---------- console_error_budget ------------------------------------------------------------------------

def _console_messages(messages: list[dict[str, Any]], source: str) -> list[Any]:
    from je_web_runner.utils.console_error_budget import budget as lib
    converters: dict[str, Callable[[Any], list[Any]]] = {
        "selenium": lib.from_selenium_log,
        "cdp_console": lib.from_cdp_console_events,
        "cdp_exception": lib.from_cdp_exception_events,
    }
    if source in converters:
        return converters[source](messages)
    if source != "plain":
        raise lib.ConsoleBudgetError(f"unknown source {source!r}; choose from plain, {', '.join(converters)}")
    return [
        lib.ConsoleMessage(
            severity=str(message.get("severity") or "info"), text=str(message.get("text") or ""),
            url=message.get("url"), line=message.get("line"), source=message.get("source"),
        )
        for message in messages
    ]


def _console_report(
    messages: list[dict[str, Any]] | None, budget: dict[str, Any] | None, source: str, command: str,
) -> Any:
    from je_web_runner.utils.console_error_budget import budget as lib
    if messages is None:
        messages = selenium_driver(command).get_log("browser")
        source = "selenium"
    try:
        limits = lib.ErrorBudget(**(budget or {}))
    except TypeError as error:
        raise lib.ConsoleBudgetError(f"bad budget: {error}") from error
    return lib.evaluate(_console_messages(messages, source), limits)


def console_error_budget_evaluate(
    messages: list[dict[str, Any]], budget: dict[str, Any] | None = None, source: str = "plain",
) -> dict[str, Any]:
    """
    Count console errors and warnings against a budget.

    :param messages: the console entries, in the shape ``source`` names.
    :param budget: any of ``max_errors`` (0), ``max_warnings`` (5), ``count_warnings`` (true),
        ``ignore_patterns`` (regular expressions matched on text and URL), ``sample_size`` (10).
    :param source: ``plain`` (objects with ``severity``, ``text``, ``url``, ``line``), ``selenium``
        (browser-log entries), ``cdp_console`` or ``cdp_exception`` (CDP ``Runtime`` event payloads).
    :return: ``passed``, ``error_count``, ``warning_count``, ``ignored_count``, ``breaches``, ``sampled``.
    """
    return to_plain(_console_report(messages, budget, source, "WR_console_error_budget_evaluate"))


def console_error_budget_page(budget: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Count the current browser's console errors against a budget (see ``WR_console_error_budget_evaluate``).

    Reading the browser log empties it, so each call sees the entries since the previous one.
    """
    return to_plain(_console_report(None, budget, "selenium", "WR_console_error_budget_page"))


def console_error_budget_assert(
    messages: list[dict[str, Any]] | None = None, budget: dict[str, Any] | None = None, source: str = "plain",
) -> dict[str, Any]:
    """
    Fail when console errors or warnings pass the budget; ``messages`` omitted means the browser's log.

    Arguments as ``WR_console_error_budget_evaluate``.

    :raises ConsoleBudgetError: when the budget is exceeded.
    """
    report = _console_report(messages, budget, source, "WR_console_error_budget_assert")
    report.raise_if_failed()
    return to_plain(report)


# ---------- otel_bridge ---------------------------------------------------------------------------------

def _context_plain(context: Any) -> dict[str, Any]:
    return {**to_plain(context), "traceparent": context.to_traceparent()}


def otel_bridge_new_context(sampled: bool = True) -> dict[str, Any]:
    """
    Make a fresh W3C trace context.

    :return: ``trace_id``, ``span_id``, ``sampled``, ``version``, ``tracestate`` and the ``traceparent`` value.
    """
    from je_web_runner.utils.otel_bridge.trace_bridge import random_trace_context
    return _context_plain(random_trace_context(sampled))


def otel_bridge_parse(traceparent: str) -> dict[str, Any]:
    """
    Split a ``traceparent`` header value into its fields (as ``WR_otel_bridge_new_context`` returns).

    :raises TraceBridgeError: when the value is malformed.
    """
    from je_web_runner.utils.otel_bridge.trace_bridge import parse_traceparent
    return _context_plain(parse_traceparent(traceparent))


def otel_bridge_inject(traceparent: str | None = None, tracestate: str | None = None) -> dict[str, Any]:
    """
    Send a ``traceparent`` header with every request of the current Chromium browser.

    :param traceparent: the header value; omitted means the active OpenTelemetry span, or a fresh context.
    :param tracestate: an optional ``tracestate`` header value.
    :return: the injected context, so its ``trace_id`` can be looked up in the backend.
    :raises TraceBridgeError: when the value is malformed or the browser has no CDP.
    """
    from je_web_runner.utils.otel_bridge import trace_bridge as lib
    if traceparent is not None:
        context = lib.parse_traceparent(traceparent)
    else:
        context = lib.current_otel_context() or lib.random_trace_context()
    if tracestate:
        context = dataclasses.replace(context, tracestate=tracestate)
    lib.inject_headers_selenium(selenium_driver("WR_otel_bridge_inject"), context)
    return _context_plain(context)


def otel_bridge_clear() -> bool:
    """Stop sending the trace headers ``WR_otel_bridge_inject`` added."""
    from je_web_runner.utils.otel_bridge.trace_bridge import clear_headers_selenium
    clear_headers_selenium(selenium_driver("WR_otel_bridge_clear"))
    return True


def otel_bridge_trace_link(
    traceparent: str, jaeger_base: str | None = None, tempo_base: str | None = None,
) -> str | None:
    """Build the Jaeger or Grafana Tempo URL of a trace; ``None`` when neither base URL is given."""
    from je_web_runner.utils.otel_bridge import trace_bridge as lib
    return lib.trace_link(lib.parse_traceparent(traceparent), jaeger_base=jaeger_base, tempo_base=tempo_base)


# ---------- bidi_backend --------------------------------------------------------------------------------

def _bidi_bridge() -> Any:
    if _BIDI["bridge"] is None:
        from je_web_runner.utils.bidi_backend.bridge import BidiBridge
        _BIDI["bridge"] = BidiBridge()
    return _BIDI["bridge"]


def bidi_backend_subscribe(event: str = "console") -> dict[str, Any]:
    """
    Start collecting a BiDi event of the current browser; read them with ``WR_bidi_backend_events``.

    :param event: the event name; a Selenium browser offers ``console``.
    :return: ``subscription_id``, ``event`` and ``backend``.
    :raises BidiBackendError: when the browser does not offer the event.
    """
    subscription = _bidi_bridge().subscribe(
        selenium_driver("WR_bidi_backend_subscribe"), event,
        lambda received: _BIDI["events"].append(to_plain(received)),
    )
    return {
        "subscription_id": subscription.subscription_id,
        "event": subscription.event,
        "backend": subscription.backend,
    }


def bidi_backend_events(clear: bool = False) -> list[dict[str, Any]]:
    """
    List the BiDi events collected so far, each as ``{"name": ..., "payload": {...}}``.

    :param clear: forget the returned events.
    """
    events = list(_BIDI["events"])
    if clear:
        _BIDI["events"].clear()
    return events


def bidi_backend_reset() -> int:
    """Stop every BiDi subscription and forget the collected events; return how many were stopped."""
    bridge = _bidi_bridge()
    stopped = len(bridge.active_subscriptions())
    bridge.unsubscribe_all()
    _BIDI["events"].clear()
    return stopped


# ---------- cdp_tap -------------------------------------------------------------------------------------

def cdp_tap_start(output_path: str) -> bool:
    """
    Start recording every CDP command the current browser is sent, with its result.

    :param output_path: the ndjson file ``WR_cdp_tap_stop`` writes.
    :raises CdpTapError: when a recording is already running or the browser has no CDP.
    """
    from je_web_runner.utils.cdp_tap.tap import CdpRecorder, CdpTapError
    if _TAP:
        raise CdpTapError("a CDP recording is already running; call WR_cdp_tap_stop first")
    driver = selenium_driver("WR_cdp_tap_start")
    recorder = CdpRecorder(output_path)
    _TAP.update(recorder=recorder, driver=driver, original=recorder.attach(driver))
    return True


def cdp_tap_records() -> list[dict[str, Any]]:
    """List the CDP calls recorded so far (``timestamp``, ``method``, ``params``, ``return_value``, ``error``)."""
    return to_plain(_TAP["recorder"].records()) if _TAP else []


def cdp_tap_stop() -> dict[str, Any]:
    """
    Stop the CDP recording and write it to the file given to ``WR_cdp_tap_start``.

    :return: the ``path`` written and the ``records``.
    :raises CdpTapError: when no recording is running.
    """
    from je_web_runner.utils.cdp_tap.tap import CdpTapError
    if not _TAP:
        raise CdpTapError("no CDP recording is running")
    recorder = _TAP["recorder"]
    recorder.detach(_TAP["driver"], _TAP["original"])
    _TAP.clear()
    return {"path": str(recorder.output_path), "records": to_plain(recorder.records())}


def cdp_tap_load(path: str) -> list[dict[str, Any]]:
    """
    Read a CDP recording file written by ``WR_cdp_tap_stop``.

    :raises CdpTapError: when the file is missing or a line is not JSON.
    """
    from je_web_runner.utils.cdp_tap.tap import load_recording
    return to_plain(load_recording(path))


# ---------- event_bus -----------------------------------------------------------------------------------

def event_bus_publish(
    log_path: str, topic: str, payload: dict[str, Any] | None = None, sender: str | None = None,
) -> dict[str, Any]:
    """
    Append an event to a file event bus, for other shards or processes to read.

    :param log_path: the bus file; created when missing.
    :return: the event: ``event_id``, ``topic``, ``payload``, ``timestamp_ms``, ``sender``.
    """
    from je_web_runner.utils.event_bus.bus import EventBus
    return to_plain(EventBus(log_path, sender=sender).publish(topic, payload))


def event_bus_poll(log_path: str, offset: int = 0, topics: list[str] | None = None) -> dict[str, Any]:
    """
    Read the events of a file event bus from a byte offset on.

    :param topics: only events of these topics.
    :return: the ``events`` and the ``offset`` to pass to the next poll.
    """
    from je_web_runner.utils.event_bus.bus import EventBus
    bus = EventBus(log_path)
    return {"events": to_plain(bus.poll(offset=offset, topics=topics)), "offset": bus.current_offset()}


def event_bus_wait_for(
    log_path: str, topic: str, offset: int = 0, timeout: float = 30.0, match: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Wait until an event of ``topic`` is on a file event bus and return it.

    :param match: payload keys and values the event must have.
    :raises EventBusError: when no such event arrives within ``timeout`` seconds.
    """
    from je_web_runner.utils.event_bus.bus import EventBus
    wanted = match or {}
    return to_plain(EventBus(log_path).wait_for(
        topic, offset=offset, timeout=timeout,
        predicate=lambda envelope: all(envelope.payload.get(key) == value for key, value in wanted.items()),
    ))


# ---------- failure_bundle ------------------------------------------------------------------------------

_BUNDLE_TEXT_SUFFIXES = (".json", ".html", ".txt", ".log")


def _new_bundle(test_name: str, error_repr: str, metadata: dict[str, Any] | None, artifacts: dict[str, Any]) -> Any:
    from je_web_runner.utils.failure_bundle.bundle import FailureBundle, FailureBundleError
    bundle = FailureBundle(test_name=test_name, error_repr=error_repr, metadata=dict(metadata or {}))
    single: dict[str, Callable[[Any], None]] = {
        "dom": bundle.add_dom,
        "console": bundle.add_console,
        "network": bundle.add_network,
        "trace": bundle.add_trace,
    }
    unknown = sorted(set(artifacts) - set(single) - {"texts", "files"})
    if unknown:
        raise FailureBundleError(f"unknown artifacts {unknown}; choose from dom, console, network, trace, texts, files")
    for key, add in single.items():
        if key in artifacts:
            add(artifacts[key])
    for name, text in (artifacts.get("texts") or {}).items():
        bundle.add_text(name, text)
    for source in artifacts.get("files") or []:
        bundle.add_file(source)
    return bundle


def _written_bundle(bundle: Any, output_path: str) -> dict[str, Any]:
    from je_web_runner.utils.failure_bundle.bundle import extract_bundle
    path = bundle.write(output_path)
    return {"path": str(path), "manifest": extract_bundle(path)["manifest"]}


def failure_bundle_write(
    output_path: str, test_name: str, error_repr: str,
    metadata: dict[str, Any] | None = None, artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Zip the material of a failed test into one failure bundle with a manifest.

    :param output_path: the ``.zip`` to write.
    :param error_repr: the failure, as text.
    :param metadata: free-form values stored in the manifest.
    :param artifacts: any of ``dom`` (HTML text), ``console`` and ``network`` (lists of objects), ``trace``
        (a file path), ``texts`` (``{name: text}``) and ``files`` (file paths).
    :return: the ``path`` written and the ``manifest``.
    :raises FailureBundleError: when an artifact key is unknown or a file is missing.
    """
    return _written_bundle(_new_bundle(test_name, error_repr, metadata, artifacts or {}), output_path)


def failure_bundle_capture(
    output_path: str, test_name: str, error_repr: str,
    metadata: dict[str, Any] | None = None, artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Write a failure bundle holding the current page's screenshot and HTML; see ``WR_failure_bundle_write``.

    An ``artifacts`` ``dom`` entry replaces the page's HTML.
    """
    driver = selenium_driver("WR_failure_bundle_capture")
    bundle = _new_bundle(test_name, error_repr, metadata, {"dom": str(driver.page_source), **(artifacts or {})})
    bundle.add_screenshot(driver.get_screenshot_as_png())
    return _written_bundle(bundle, output_path)


def failure_bundle_read(zip_path: str, include_text: bool = False) -> dict[str, Any]:
    """
    Read a failure bundle's manifest and file names.

    :param include_text: also return the content of the ``.json`` / ``.html`` / ``.txt`` / ``.log`` files.
    :return: ``manifest``, ``files`` (names) and ``texts`` (name to content; empty unless asked for).
    :raises FailureBundleError: when the file is missing or has no manifest.
    """
    from je_web_runner.utils.failure_bundle.bundle import extract_bundle
    content = extract_bundle(zip_path)
    texts = {
        name: data.decode("utf-8", errors="replace")
        for name, data in content["files"].items()
        if include_text and name.endswith(_BUNDLE_TEXT_SUFFIXES)
    }
    return {"manifest": content["manifest"], "files": sorted(content["files"]), "texts": texts}


# ---------- memory_leak ---------------------------------------------------------------------------------

def memory_leak_sample() -> int:
    """
    Return the current page's used JavaScript heap in bytes (Chromium only).

    :raises MemoryLeakError: when the browser does not report ``performance.memory``.
    """
    from je_web_runner.utils.memory_leak.detector import sample_used_heap
    return sample_used_heap(selenium_driver("WR_memory_leak_sample"))


def memory_leak_trend(samples: list[int], max_bytes_per_iter: int | None = None) -> dict[str, Any]:
    """
    Fit a line through heap sizes sampled after each round of a repeated action.

    :param samples: at least two heap sizes in bytes, e.g. from ``WR_memory_leak_sample``, in order.
    :param max_bytes_per_iter: when given, fail if the heap grows faster than this per round.
    :return: the ``samples``, ``slope_bytes_per_iter`` and ``delta_bytes``.
    :raises MemoryLeakError: when there are fewer than two samples or the growth passes the limit.
    """
    from je_web_runner.utils.memory_leak.detector import detect_growth
    remaining = iter(samples)
    return to_plain(detect_growth(
        None, lambda: None, iterations=len(samples), warmup=0,
        growth_bytes_per_iter_budget=max_bytes_per_iter, sampler=lambda _driver: int(next(remaining)),
    ))


# ---------- memory_pressure_emulate ---------------------------------------------------------------------

# What the library's own runner sends to undo a profile.
_PRESSURE_RESTORE: tuple[tuple[str, dict[str, Any]], ...] = (
    ("Emulation.setHardwareConcurrencyOverride", {"hardwareConcurrency": 0}),
    ("Emulation.setCPUThrottlingRate", {"rate": 1.0}),
    ("Memory.simulatePressureNotification", {"level": "nominal"}),
)


def _pressure_profile(profile: Any) -> Any:
    from je_web_runner.utils.memory_pressure_emulate import emulate as lib
    if isinstance(profile, str):
        known = {default.name: default for default in lib.DEFAULT_PROFILES}
        if profile not in known:
            raise lib.MemoryPressureError(f"unknown profile {profile!r}; choose from {sorted(known)}")
        return known[profile]
    try:
        fields = dict(profile)
        if "pressure_level" in fields:
            fields["pressure_level"] = lib.PressureLevel(fields["pressure_level"])
        return lib.EmulationProfile(**fields)
    except (TypeError, ValueError) as error:
        raise lib.MemoryPressureError(f"bad profile: {error}") from error


def memory_pressure_emulate_profiles() -> list[dict[str, Any]]:
    """List the built-in low-resource profiles (``low_end_phone``, ``critical_pressure``, ``single_core``)."""
    from je_web_runner.utils.memory_pressure_emulate.emulate import DEFAULT_PROFILES
    return to_plain(DEFAULT_PROFILES)


def memory_pressure_emulate_payloads(profile: Any) -> list[dict[str, Any]]:
    """
    List the CDP commands that put a browser under a low-resource profile.

    :param profile: a built-in profile's name, or an object with ``name`` and any of
        ``hardware_concurrency``, ``pressure_level`` (``nominal``, ``fair``, ``serious``, ``critical``),
        ``cpu_throttle_rate``, ``js_heap_limit_bytes``.
    :return: objects with ``method`` and ``params``.
    :raises MemoryPressureError: when the profile is unknown or invalid.
    """
    from je_web_runner.utils.memory_pressure_emulate.emulate import cdp_payloads
    return to_plain(cdp_payloads(_pressure_profile(profile)))


def memory_pressure_emulate_apply(profile: Any) -> list[dict[str, Any]]:
    """
    Put the current Chromium browser under a low-resource profile (see ``WR_memory_pressure_emulate_payloads``).

    Undo it with ``WR_memory_pressure_emulate_restore``.

    :return: the CDP commands that were sent.
    """
    payloads = memory_pressure_emulate_payloads(profile)
    driver = selenium_driver("WR_memory_pressure_emulate_apply")
    for payload in payloads:
        driver.execute_cdp_cmd(payload["method"], payload["params"])
    return payloads


def memory_pressure_emulate_restore() -> bool:
    """Take the current Chromium browser back to normal CPU, core count and memory pressure."""
    driver = selenium_driver("WR_memory_pressure_emulate_restore")
    for method, params in _PRESSURE_RESTORE:
        driver.execute_cdp_cmd(method, dict(params))
    return True


# ---------- third_party_block_test ----------------------------------------------------------------------

def _block_vendors(vendors: list[Any]) -> list[Any]:
    from je_web_runner.utils.third_party_block_test import block as lib
    known = {vendor.name: vendor for vendor in lib.builtin_vendors()}
    chosen = []
    for vendor in vendors:
        if isinstance(vendor, str):
            if vendor not in known:
                raise lib.ThirdPartyBlockError(f"unknown vendor {vendor!r}; choose from {sorted(known)}")
            chosen.append(known[vendor])
            continue
        try:
            chosen.append(lib.Vendor(
                name=str(vendor["name"]), patterns=tuple(vendor["patterns"]),
                critical_path=bool(vendor.get("critical_path", False)),
            ))
        except (KeyError, TypeError, AttributeError) as error:
            raise lib.ThirdPartyBlockError(f"bad vendor {vendor!r}: {error!r}") from error
    return chosen


def _set_blocked_urls(command: str, patterns: list[str]) -> None:
    driver = selenium_driver(command)
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": patterns})


def third_party_block_test_vendors() -> list[dict[str, Any]]:
    """List the built-in third-party vendors with the URL patterns that block them."""
    from je_web_runner.utils.third_party_block_test.block import builtin_vendors
    return to_plain(builtin_vendors())


def third_party_block_test_block(vendors: list[Any]) -> dict[str, Any]:
    """
    Block third-party vendors in the current Chromium browser, to see whether the flow survives without them.

    :param vendors: built-in vendor names, or objects with ``name``, ``patterns`` and ``critical_path``.
    :return: the ``vendors`` blocked and the URL ``patterns`` sent to the browser.
    :raises ThirdPartyBlockError: when a vendor is unknown or malformed.
    """
    chosen = _block_vendors(vendors)
    patterns = [pattern for vendor in chosen for pattern in vendor.patterns]
    _set_blocked_urls("WR_third_party_block_test_block", patterns)
    return {"vendors": [vendor.name for vendor in chosen], "patterns": patterns}


def third_party_block_test_unblock() -> bool:
    """Stop blocking the vendors ``WR_third_party_block_test_block`` blocked."""
    _set_blocked_urls("WR_third_party_block_test_unblock", [])
    return True


def third_party_block_test_assert(outcomes: list[dict[str, Any]], vendors: list[str]) -> list[dict[str, Any]]:
    """
    Fail when the flow broke while one of ``vendors`` was blocked.

    :param outcomes: what happened per blocked vendor: objects with ``vendor`` and ``resilience``
        (``resilient``, ``degraded`` or ``broken``), optionally ``error`` and ``notes``.
    :param vendors: the vendors that must not be ``broken``; one without an outcome counts as broken.
    :raises ThirdPartyBlockError: when a listed vendor broke the flow or an outcome is malformed.
    """
    from je_web_runner.utils.third_party_block_test import block as lib
    try:
        report = lib.BlockReport(outcomes=[
            lib.BlockOutcome(
                vendor=str(outcome["vendor"]), resilience=lib.Resilience(outcome["resilience"]),
                error=outcome.get("error"), notes=list(outcome.get("notes") or []),
            )
            for outcome in outcomes
        ])
    except (KeyError, TypeError, ValueError) as error:
        raise lib.ThirdPartyBlockError(f"bad outcome: {error!r}") from error
    lib.assert_resilient_to(report, vendors=vendors)
    return to_plain(report.outcomes)


PERFORMANCE_2_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_backend_log_correlator_trace_id": backend_log_correlator_trace_id,
    "WR_backend_log_correlator_file": backend_log_correlator_file,
    "WR_backend_log_correlator_loki": backend_log_correlator_loki,
    "WR_backend_log_correlator_elasticsearch": backend_log_correlator_elasticsearch,
    "WR_backend_log_correlator_attach": backend_log_correlator_attach,
    "WR_console_error_budget_evaluate": console_error_budget_evaluate,
    "WR_console_error_budget_page": console_error_budget_page,
    "WR_console_error_budget_assert": console_error_budget_assert,
    "WR_otel_bridge_new_context": otel_bridge_new_context,
    "WR_otel_bridge_parse": otel_bridge_parse,
    "WR_otel_bridge_inject": otel_bridge_inject,
    "WR_otel_bridge_clear": otel_bridge_clear,
    "WR_otel_bridge_trace_link": otel_bridge_trace_link,
    "WR_bidi_backend_subscribe": bidi_backend_subscribe,
    "WR_bidi_backend_events": bidi_backend_events,
    "WR_bidi_backend_reset": bidi_backend_reset,
    "WR_cdp_tap_start": cdp_tap_start,
    "WR_cdp_tap_records": cdp_tap_records,
    "WR_cdp_tap_stop": cdp_tap_stop,
    "WR_cdp_tap_load": cdp_tap_load,
    "WR_event_bus_publish": event_bus_publish,
    "WR_event_bus_poll": event_bus_poll,
    "WR_event_bus_wait_for": event_bus_wait_for,
    "WR_failure_bundle_write": failure_bundle_write,
    "WR_failure_bundle_capture": failure_bundle_capture,
    "WR_failure_bundle_read": failure_bundle_read,
    "WR_memory_leak_sample": memory_leak_sample,
    "WR_memory_leak_trend": memory_leak_trend,
    "WR_memory_pressure_emulate_profiles": memory_pressure_emulate_profiles,
    "WR_memory_pressure_emulate_payloads": memory_pressure_emulate_payloads,
    "WR_memory_pressure_emulate_apply": memory_pressure_emulate_apply,
    "WR_memory_pressure_emulate_restore": memory_pressure_emulate_restore,
    "WR_third_party_block_test_vendors": third_party_block_test_vendors,
    "WR_third_party_block_test_block": third_party_block_test_block,
    "WR_third_party_block_test_unblock": third_party_block_test_unblock,
    "WR_third_party_block_test_assert": third_party_block_test_assert,
}

PYTHON_ONLY: dict[str, str] = {
    "trace_recorder": (
        "TraceRecorder drives the tracing of a live Playwright BrowserContext, which the Playwright wrapper "
        "already owns and exposes as WR_pw_tracing_start / WR_pw_tracing_stop."
    ),
}

NETWORK_COMMANDS: frozenset[str] = frozenset({
    "WR_backend_log_correlator_loki",
    "WR_backend_log_correlator_elasticsearch",
})
