"""
API 測試類函式庫的命令轉接層（二）
Command adapters for the API-testing libraries, part two: local mock servers (route mocks, HAR replay,
OAuth / SMTP mocks, webhook receiver) and outbound messages (e-mail, OTP, push, message queues, chat
digests). Each ``WR_*`` command takes JSON values and returns JSON values. Part one is ``_commands_api.py``.

The servers these commands start listen on 127.0.0.1 only.
"""
# pylint: disable=import-outside-toplevel,too-many-arguments,too-many-positional-arguments
# Each library is imported inside its adapter so that importing je_web_runner stays fast. The project's
# parameter limit is 7 (S107), and an action file passes a command's arguments by name.
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor._command_helpers import page_source, selenium_driver, to_plain

_STATE: dict[str, Any] = {}


def _refuse_running(name: str) -> None:
    if name in _STATE:
        raise WebRunnerException(f"{name} is already running; stop it first")


def _running(name: str) -> Any:
    if name not in _STATE:
        raise WebRunnerException(f"{name} is not running; start it first")
    return _STATE[name]


def _error_text(check: Callable[[], Any], error_type: type[Exception]) -> str:
    """Run ``check``; the message of the ``error_type`` it raised, or an empty string when it passed."""
    try:
        check()
    except error_type as error:
        return str(error)
    return ""


# ---------- api_mock -----------------------------------------------------------
def api_mock_register(
        method: str, url_pattern: str, body: Any = "", status: int = 200, times: int | None = None,
        headers: dict[str, str] | None = None, content_type: str | None = None,
) -> dict[str, Any]:
    """
    Register a mocked HTTP route for the Playwright page.

    ``url_pattern`` is an exact URL, a ``*`` wildcard pattern or ``re:<regex>``; ``method`` may be ``*``.
    ``times`` limits how often the route answers; ``headers`` and ``content_type`` are sent with the
    answer. Routes take effect after ``WR_api_mock_attach``.
    """
    from je_web_runner.utils.api_mock.router import register_route
    # Only what was given: the router has its own default content type for a body.
    given = (("headers", headers), ("content_type", content_type))
    extra: dict[str, Any] = {name: value for name, value in given if value is not None}
    return to_plain(register_route(method, url_pattern, body=body, status=status, times=times, **extra))


def api_mock_attach() -> bool:
    """Serve the registered mock routes (also ones registered later) on the current Playwright page."""
    from je_web_runner.utils.api_mock.router import global_router
    from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
    global_router().attach_to_page(playwright_wrapper_instance.page)
    return True


def api_mock_match(method: str, url: str) -> dict[str, Any] | None:
    """
    Ask the mock router what it answers to ``method`` ``url``: ``{"status", "headers", "body"}`` or ``null``
    when no route matches. Counts as a call and uses up one of the route's ``times``.
    """
    from je_web_runner.utils.api_mock.router import global_router
    route = global_router().match(method, url)
    return None if route is None else to_plain(route.response.to_payload())


def api_mock_calls() -> list[list[str]]:
    """List the ``[method, url]`` pairs the mock router was asked for, in order."""
    from je_web_runner.utils.api_mock.router import global_router
    return to_plain(global_router().calls())


def api_mock_reset() -> bool:
    """Remove every registered mock route and forget the recorded calls."""
    from je_web_runner.utils.api_mock.router import reset_global_router
    reset_global_router()
    return True


# ---------- har_replay ---------------------------------------------------------
def har_replay_load(har_path: str) -> list[dict[str, Any]]:
    """Read a HAR file and list the responses it can replay (method, path, status, headers, body)."""
    from je_web_runner.utils.har_replay.server import load_har
    return to_plain(load_har(har_path))


def har_replay_start(har_path: str, port: int = 0, not_found_status: int = 404) -> dict[str, Any]:
    """
    Start a local server on 127.0.0.1 that answers requests with the responses recorded in a HAR file.

    ``port`` 0 picks a free port. Returns ``{"base_url", "port", "entries"}``.
    """
    from je_web_runner.utils.har_replay.server import HarReplayServer, load_har
    _refuse_running("har_replay")
    server = HarReplayServer(load_har(har_path), port=port, not_found_status=not_found_status)
    base_url = server.start()
    _STATE["har_replay"] = server
    return {"base_url": base_url, "port": server.port, "entries": len(server.entries)}


def har_replay_calls() -> list[list[str]]:
    """List the ``[method, path]`` pairs the HAR replay server was asked for, in order."""
    return to_plain(_running("har_replay").calls)


def har_replay_stop() -> list[list[str]]:
    """Stop the HAR replay server; returns the ``[method, path]`` pairs it was asked for."""
    server = _STATE.pop("har_replay", None)
    if server is None:
        return []
    server.stop()
    return to_plain(server.calls)


# ---------- mock_services ------------------------------------------------------
def _mock_services_state() -> dict[str, Any]:
    oauth = _STATE.get("mock_oauth")
    smtp = _STATE.get("mock_smtp")
    return {
        "oauth_tokens": [] if oauth is None else list(oauth.issued),
        "smtp_messages": [] if smtp is None else list(smtp.captured),
    }


def mock_services_start_oauth(port: int = 0) -> dict[str, Any]:
    """
    Start a mock OAuth server on 127.0.0.1 whose ``POST /token`` issues a fake bearer token.

    ``port`` 0 picks a free port. Returns ``{"base_url", "token_url", "port"}``.
    """
    from je_web_runner.utils.mock_services.servers import MockOAuthServer
    _refuse_running("mock_oauth")
    server = MockOAuthServer(port=port)
    base_url = server.start()
    _STATE["mock_oauth"] = server
    return {"base_url": base_url, "token_url": f"{base_url}/token", "port": server.port}


def mock_services_start_smtp(port: int = 0) -> dict[str, Any]:
    """
    Start a capture-only SMTP server on 127.0.0.1 for the application under test to send mail to.

    ``port`` 0 picks a free port. Returns ``{"host", "port"}``.
    """
    from je_web_runner.utils.mock_services.servers import MockSmtpServer
    _refuse_running("mock_smtp")
    server = MockSmtpServer(port=port)
    server.start()
    _STATE["mock_smtp"] = server
    return {"host": server.host, "port": server.port}


def mock_services_captured() -> dict[str, Any]:
    """Return what the mock services saw so far: ``oauth_tokens`` issued and ``smtp_messages`` captured."""
    return _mock_services_state()


def mock_services_stop() -> dict[str, Any]:
    """Stop the mock OAuth and SMTP servers; returns what they saw."""
    seen = _mock_services_state()
    for name in ("mock_oauth", "mock_smtp"):
        server = _STATE.pop(name, None)
        if server is not None:
            server.stop()
    return seen


# ---------- email_deliverability -----------------------------------------------
def _deliverability_checks(raw: str, expected_policy: str) -> dict[str, Callable[[], None]]:
    from je_web_runner.utils.email_deliverability import headers as library
    parsed = library.parse_headers(raw)
    return {
        "spf": lambda: library.assert_spf_pass(parsed),
        "dkim": lambda: library.assert_dkim_pass(parsed),
        "dmarc": lambda: library.assert_dmarc_pass(parsed, expected_policy=expected_policy),
        "list_unsubscribe": lambda: library.assert_list_unsubscribe(parsed),
        "no_bcc_leak": lambda: library.assert_no_bcc_leak(parsed),
    }


def email_deliverability_parse(raw: str) -> dict[str, list[str]]:
    """Parse the headers of a raw e-mail message into ``{lower-case name: [values]}``."""
    from je_web_runner.utils.email_deliverability.headers import parse_headers
    return to_plain(parse_headers(raw).headers)


def email_deliverability_audit(raw: str, expected_policy: str = "") -> dict[str, dict[str, Any]]:
    """
    Check a raw delivered e-mail for SPF, DKIM, DMARC, one-click List-Unsubscribe and a leaked Bcc header.

    Returns ``{check: {"passed", "error"}}`` for spf, dkim, dmarc, list_unsubscribe and no_bcc_leak.
    ``expected_policy`` is the DMARC policy (reject, quarantine) the message must report.
    """
    from je_web_runner.utils.email_deliverability.headers import EmailDeliverabilityError
    results: dict[str, dict[str, Any]] = {}
    for name, check in _deliverability_checks(raw, expected_policy).items():
        error = _error_text(check, EmailDeliverabilityError)
        results[name] = {"passed": not error, "error": error}
    return results


def email_deliverability_assert(
        raw: str, checks: list[str] | None = None, expected_policy: str = "",
) -> list[str]:
    """
    Fail when a raw delivered e-mail does not pass the named ``checks`` (default spf, dkim, dmarc; also
    list_unsubscribe and no_bcc_leak); returns the checks that ran.
    """
    from je_web_runner.utils.email_deliverability.headers import EmailDeliverabilityError
    available = _deliverability_checks(raw, expected_policy)
    wanted = list(checks) if checks else ["spf", "dkim", "dmarc"]
    for name in wanted:
        if name not in available:
            raise EmailDeliverabilityError(f"unknown check {name!r}; use {sorted(available)}")
        available[name]()
    return wanted


# ---------- email_render -------------------------------------------------------
def _captured_email(email: dict[str, Any]) -> Any:
    from je_web_runner.utils.email_render.render import CapturedEmail
    return CapturedEmail(
        message_id=str(email.get("message_id", "")),
        subject=str(email.get("subject", "")),
        from_addr=str(email.get("from_addr", "")),
        to=[str(address) for address in email.get("to") or []],
        html_body=email.get("html_body"),
        text_body=email.get("text_body"),
        headers=dict(email.get("headers") or {}),
        raw=email.get("raw"),
    )


def _viewports(viewports: list[dict[str, Any]] | None) -> Any:
    from je_web_runner.utils.email_render.render import DEFAULT_VIEWPORTS, ViewportProfile
    if not viewports:
        return DEFAULT_VIEWPORTS
    return [
        ViewportProfile(
            name=str(item.get("name", "")),
            width=int(item.get("width", 800)),
            height=int(item.get("height", 1200)),
            dark_mode=bool(item.get("dark_mode", False)),
        )
        for item in viewports
    ]


def _selenium_render(html: str, viewport: Any, target: Path) -> Path:
    """Show ``html`` in the running browser at the viewport's size and save a screenshot to ``target``."""
    driver = selenium_driver("WR_email_render_screenshots")
    driver.set_window_size(viewport.width, viewport.height)
    if hasattr(driver, "execute_cdp_cmd"):
        scheme = "dark" if viewport.dark_mode else "light"
        driver.execute_cdp_cmd(
            "Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]},
        )
    driver.get("data:text/html;charset=utf-8;base64," + base64.b64encode(html.encode("utf-8")).decode("ascii"))
    driver.save_screenshot(str(target))
    return target


def email_render_load_eml(path: str) -> list[dict[str, Any]]:
    """
    Read captured mail from an ``.eml`` file, or from every ``.eml`` file of a directory.

    Each message has ``message_id``, ``subject``, ``from_addr``, ``to``, ``html_body``, ``text_body``,
    ``headers`` and ``raw``.
    """
    from je_web_runner.utils.email_render.render import load_eml_dir, load_eml_file
    if Path(path).is_dir():
        return to_plain(load_eml_dir(path))
    return to_plain([load_eml_file(path)])


def email_render_fetch(
        base_url: str, provider: str = "mailhog", timeout: float = 10.0, limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch the captured mail of a MailHog or Mailpit server (``provider``) at ``base_url``."""
    from je_web_runner.utils.email_render.render import EmailRenderError, fetch_mailhog, fetch_mailpit
    if provider == "mailhog":
        return to_plain(fetch_mailhog(base_url, timeout=timeout))
    if provider == "mailpit":
        return to_plain(fetch_mailpit(base_url, timeout=timeout, limit=limit))
    raise EmailRenderError(f"unknown provider {provider!r}; use mailhog or mailpit")


def email_render_assert_subject(email: dict[str, Any], needle: str) -> bool:
    """Fail when the subject of a captured ``email`` (as the load / fetch commands return it) lacks ``needle``."""
    from je_web_runner.utils.email_render.render import assert_subject_contains
    assert_subject_contains(_captured_email(email), needle)
    return True


def email_render_screenshots(
        email: dict[str, Any], output_dir: str, viewports: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Open a captured e-mail's HTML body in the running browser at several sizes and save a screenshot of each.

    ``viewports`` is a list of ``{"name", "width", "height", "dark_mode"}`` (default: desktop light and
    dark, mobile light); dark mode is emulated on Chromium browsers only. The browser is left on the
    e-mail. Returns ``{"viewport", "screenshot_path", "width", "height"}`` per screenshot.
    """
    from je_web_runner.utils.email_render.render import render_email_in_viewports
    artifacts = render_email_in_viewports(
        _captured_email(email), _selenium_render, output_dir, viewports=_viewports(viewports),
    )
    return to_plain(artifacts)


# ---------- inbox_render_outlook -----------------------------------------------
def _render_findings(html: str, clients: list[str] | None) -> list[Any]:
    from je_web_runner.utils.inbox_render_outlook import render as library
    audits = {
        "outlook": library.audit_outlook,
        "gmail": library.audit_gmail,
        "apple_mail": library.audit_apple_mail,
    }
    findings: list[Any] = []
    for client in clients or list(audits):
        if client not in audits:
            raise library.InboxRenderOutlookError(f"unknown client {client!r}; use {sorted(audits)}")
        findings.extend(audits[client](html))
    return findings


def inbox_render_outlook_audit(html: str, clients: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Audit an HTML e-mail body for things mail clients render badly.

    ``clients`` picks from outlook, gmail and apple_mail (default all). Each finding has ``rule``,
    ``severity`` (info, warn, error), ``message`` and ``snippet``.
    """
    return to_plain(_render_findings(html, clients))


def inbox_render_outlook_audit_page(clients: list[str] | None = None) -> list[dict[str, Any]]:
    """Audit the current page's HTML as an e-mail body (for a page that previews the e-mail)."""
    return to_plain(_render_findings(page_source("WR_inbox_render_outlook_audit_page"), clients))


def inbox_render_outlook_assert(html: str, clients: list[str] | None = None) -> list[dict[str, Any]]:
    """Fail when the HTML e-mail body has an error-level finding; returns the findings otherwise."""
    from je_web_runner.utils.inbox_render_outlook.render import assert_no_errors
    findings = _render_findings(html, clients)
    assert_no_errors(findings)
    return to_plain(findings)


# ---------- mq_assert ----------------------------------------------------------
def _mq_messages(messages: list[dict[str, Any]]) -> list[Any]:
    from je_web_runner.utils.mq_assert.assertions import Message
    return [
        Message(
            topic=str(item.get("topic", "")),
            body=item.get("body"),
            key=item.get("key"),
            headers=dict(item.get("headers") or {}),
        )
        for item in messages
    ]


def mq_assert_published(
        messages: list[dict[str, Any]],
        body_contains: dict[str, Any] | None = None,
        key_matches: str | None = None,
        header_equals: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Fail when none of the consumed queue ``messages`` (``{"topic", "body", "key", "headers"}`` each) has the
    given key, headers and body fields; returns the first message that does.
    """
    from je_web_runner.utils.mq_assert.assertions import assert_message_published
    found = assert_message_published(
        _mq_messages(messages), body_contains=body_contains, key_matches=key_matches, header_equals=header_equals,
    )
    return to_plain(found)


def mq_assert_no_message(
        messages: list[dict[str, Any]], topic: str | None = None, body_contains: dict[str, Any] | None = None,
) -> bool:
    """Fail when a consumed queue message on ``topic`` (any topic when ``null``) has the given body fields."""
    from je_web_runner.utils.mq_assert.assertions import assert_no_message
    assert_no_message(_mq_messages(messages), topic=topic, body_contains=body_contains)
    return True


def mq_assert_idempotent(messages: list[dict[str, Any]], key: str) -> bool:
    """Fail when more than one consumed queue message carries the idempotency ``key``."""
    from je_web_runner.utils.mq_assert.assertions import assert_idempotent
    assert_idempotent(_mq_messages(messages), key=key)
    return True


def mq_assert_ordered(messages: list[dict[str, Any]], key: str, expected_order: list[str]) -> bool:
    """Fail when the body ``type`` of the messages with ``key`` did not arrive in ``expected_order``."""
    from je_web_runner.utils.mq_assert.assertions import assert_ordered
    assert_ordered(_mq_messages(messages), key=key, expected_order=expected_order)
    return True


# ---------- otp_interceptor ----------------------------------------------------
def _otp_provider(provider: str, base_url: str) -> Any:
    from je_web_runner.utils.otp_interceptor import interceptor as library
    providers = {
        "mailhog": library.MailHogProvider,
        "mailpit": library.MailpitProvider,
        "sms_webhook": library.WebhookSmsProvider,
    }
    if provider not in providers:
        raise library.OtpInterceptError(f"unknown provider {provider!r}; use {sorted(providers)}")
    return providers[provider](base_url)


def otp_interceptor_extract(text: str, pattern: str | None = None) -> str | None:
    """
    Pull a one-time code out of ``text``: the first 4-8 digit number, or the first match (first group) of
    the regular expression ``pattern``. Returns ``null`` when there is none.
    """
    from je_web_runner.utils.otp_interceptor.interceptor import extract_otp_from_text
    return extract_otp_from_text(text, pattern)


def otp_interceptor_messages(
        base_url: str, provider: str = "mailhog", recipient: str | None = None, limit: int = 25,
) -> list[dict[str, Any]]:
    """
    List the newest messages of a test inbox at ``base_url``, optionally only those to ``recipient``.

    ``provider`` is mailhog, mailpit or sms_webhook (a ``GET /messages`` endpoint that lists SMS).
    """
    return to_plain(_otp_provider(provider, base_url).fetch_messages(recipient=recipient, limit=limit))


def otp_interceptor_wait(
        base_url: str,
        recipient: str,
        provider: str = "mailhog",
        pattern: str | None = None,
        timeout: float = 30.0,
        subject_contains: str | None = None,
        lookback_seconds: float = 0.0,
) -> str:
    """
    Wait for a one-time code sent to ``recipient`` to reach the test inbox at ``base_url`` and return it.

    Only messages that arrive after the command starts count; ``lookback_seconds`` also accepts messages
    that arrived that long before it (the step that triggered the message usually ran just before).
    Fails after ``timeout`` seconds. ``provider`` is mailhog, mailpit or sms_webhook.
    """
    from je_web_runner.utils.otp_interceptor.interceptor import wait_for_otp
    since = time.time() - lookback_seconds if lookback_seconds > 0 else None
    return wait_for_otp(
        _otp_provider(provider, base_url), recipient,
        pattern=pattern, timeout=timeout, since=since, subject_contains=subject_contains,
    )


# ---------- push_delivery ------------------------------------------------------
def _push_validate(payload: dict[str, Any], provider: str | None, collapse: bool) -> str:
    from je_web_runner.utils.push_delivery import delivery as library
    name = provider or ("apns" if isinstance(payload, dict) and "aps" in payload else "fcm")
    try:
        chosen = library.Provider(name)
    except ValueError as error:
        raise library.PushDeliveryError(f"unknown provider {name!r}; use fcm or apns") from error
    if chosen == library.Provider.APNS:
        library.assert_apns_payload(payload)
    else:
        library.assert_fcm_payload(payload)
    if collapse:
        library.assert_collapse_intent(payload)
    return str(chosen.value)


def push_delivery_check(
        payload: dict[str, Any], provider: str | None = None, collapse: bool = False,
) -> dict[str, Any]:
    """
    Validate a server-side push payload (FCM v1 ``{"message": ...}`` or APNs ``{"aps": ...}``) without
    failing the run: required fields, size limit, TTL, no PII in title / body.

    ``provider`` is fcm or apns (default: detected from the payload); ``collapse`` also requires a collapse
    key. Returns ``{"passed", "error", "size_bytes"}``.
    """
    from je_web_runner.utils.push_delivery.delivery import PushDeliveryError
    error = _error_text(lambda: _push_validate(payload, provider, collapse), PushDeliveryError)
    size = len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return {"passed": not error, "error": error, "size_bytes": size}


def push_delivery_assert(payload: dict[str, Any], provider: str | None = None, collapse: bool = False) -> str:
    """Fail when a server-side push payload is invalid for FCM / APNs; returns the provider it was checked as."""
    return _push_validate(payload, provider, collapse)


# ---------- slack_digest -------------------------------------------------------
def _digest_inputs(digest: dict[str, Any]) -> Any:
    from je_web_runner.utils.slack_digest import digest as library
    cost = digest.get("cost")
    return library.DigestInputs(
        period_label=str(digest.get("period_label", "last 7 days")),
        flake_changes=[
            library.FlakeStat(
                test_id=str(item.get("test_id", "")),
                action=str(item.get("action", "")),
                flake_score=float(item.get("flake_score") or 0),
            )
            for item in digest.get("flake_changes") or []
        ],
        risky_prs=[
            library.RiskyPr(
                number=int(item.get("number", 0)),
                title=str(item.get("title", "")),
                score=float(item.get("score") or 0),
                url=str(item.get("url", "")),
            )
            for item in digest.get("risky_prs") or []
        ],
        cost=None if not cost else library.CostTrend(
            current_usd=float(cost.get("current_usd") or 0), previous_usd=float(cost.get("previous_usd") or 0),
        ),
        suite_pass_rate=digest.get("suite_pass_rate"),
        suite_pass_rate_previous=digest.get("suite_pass_rate_previous"),
        extra_lines=[str(line) for line in digest.get("extra_lines") or []],
    )


def slack_digest_payload(digest: dict[str, Any], channel: str | None = None) -> dict[str, Any]:
    """
    Render a test digest as a Slack ``chat.postMessage`` payload (Block Kit); nothing is sent.

    ``digest`` may hold ``period_label``, ``suite_pass_rate`` and ``suite_pass_rate_previous`` (0..1),
    ``flake_changes`` (``test_id``, ``action`` added / released / still_in, ``flake_score``), ``risky_prs``
    (``number``, ``title``, ``score``, ``url``), ``cost`` (``current_usd``, ``previous_usd``), ``extra_lines``.
    """
    from je_web_runner.utils.slack_digest.digest import build_slack_payload
    return to_plain(build_slack_payload(_digest_inputs(digest), channel=channel))


def slack_digest_teams_card(digest: dict[str, Any]) -> dict[str, Any]:
    """Render a test digest (same ``digest`` as ``WR_slack_digest_payload``) as a Microsoft Teams Adaptive Card."""
    from je_web_runner.utils.slack_digest.digest import build_teams_card
    return to_plain(build_teams_card(_digest_inputs(digest)))


def slack_digest_text(digest: dict[str, Any]) -> str:
    """Render a test digest (same ``digest`` as ``WR_slack_digest_payload``) as plain text."""
    from je_web_runner.utils.slack_digest.digest import render_plain_text
    return render_plain_text(_digest_inputs(digest))


# ---------- webhook_receiver ---------------------------------------------------
def _is_request(request: Any, path: str | None, method: str | None) -> bool:
    return (path is None or request.path == path) and (method is None or request.method == method.upper())


def webhook_receiver_start(port: int | None = None) -> dict[str, Any]:
    """
    Start a local server on 127.0.0.1 that records the webhooks the application under test sends.

    ``port`` ``null`` picks a free port. Returns ``{"base_url"}``: point the application's webhook URL at it.
    """
    from je_web_runner.utils.webhook_receiver.receiver import WebhookServer
    _refuse_running("webhook_receiver")
    server = WebhookServer(port=port).start()
    _STATE["webhook_receiver"] = server
    return {"base_url": server.base_url}


def webhook_receiver_received(path: str | None = None, method: str | None = None) -> list[dict[str, Any]]:
    """
    List the webhook requests received so far, optionally only those to ``path`` with ``method``.

    Each has ``method``, ``path``, ``query``, ``headers``, ``body`` (text) and ``timestamp``.
    """
    received = _running("webhook_receiver").received()
    return to_plain([request for request in received if _is_request(request, path, method)])


def webhook_receiver_wait(path: str, method: str | None = None, timeout: float = 5.0) -> dict[str, Any]:
    """Wait up to ``timeout`` seconds for a webhook request to ``path`` and return it; fail when none arrives."""
    server = _running("webhook_receiver")
    return to_plain(server.wait_for(lambda request: _is_request(request, path, method), timeout=timeout))


def webhook_receiver_assert_path(path: str, method: str | None = None, minimum: int = 1) -> int:
    """Fail when fewer than ``minimum`` webhook requests hit ``path``; returns how many did."""
    from je_web_runner.utils.webhook_receiver.receiver import assert_received_path
    wanted = None if method is None else method.upper()
    return assert_received_path(_running("webhook_receiver"), path, method=wanted, minimum=minimum)


def webhook_receiver_assert_header(header: str, value: str) -> dict[str, Any]:
    """Fail when no received webhook request has ``header`` equal to ``value``; returns the first that does."""
    from je_web_runner.utils.webhook_receiver.receiver import assert_received_with_header
    return to_plain(assert_received_with_header(_running("webhook_receiver"), header, value))


def webhook_receiver_assert_json(contains: dict[str, Any]) -> dict[str, Any]:
    """
    Fail when no received webhook request has a JSON object body with every field of ``contains``; returns
    the first that does.
    """
    from je_web_runner.utils.webhook_receiver.receiver import assert_received_json_matching

    def has_fields(payload: Any) -> bool:
        return isinstance(payload, dict) and all(payload.get(name) == value for name, value in contains.items())

    found = assert_received_json_matching(
        _running("webhook_receiver"), has_fields, description=f"body contains {contains!r}",
    )
    return to_plain(found)


def webhook_receiver_clear() -> int:
    """Forget the webhook requests received so far; returns how many were dropped."""
    server = _running("webhook_receiver")
    dropped = len(server.received())
    server.clear()
    return dropped


def webhook_receiver_stop() -> list[dict[str, Any]]:
    """Stop the webhook receiver; returns the requests it received."""
    server = _STATE.pop("webhook_receiver", None)
    if server is None:
        return []
    server.stop()
    return to_plain(server.received())


API_2_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_api_mock_register": api_mock_register,
    "WR_api_mock_attach": api_mock_attach,
    "WR_api_mock_match": api_mock_match,
    "WR_api_mock_calls": api_mock_calls,
    "WR_api_mock_reset": api_mock_reset,
    "WR_har_replay_load": har_replay_load,
    "WR_har_replay_start": har_replay_start,
    "WR_har_replay_calls": har_replay_calls,
    "WR_har_replay_stop": har_replay_stop,
    "WR_mock_services_start_oauth": mock_services_start_oauth,
    "WR_mock_services_start_smtp": mock_services_start_smtp,
    "WR_mock_services_captured": mock_services_captured,
    "WR_mock_services_stop": mock_services_stop,
    "WR_email_deliverability_parse": email_deliverability_parse,
    "WR_email_deliverability_audit": email_deliverability_audit,
    "WR_email_deliverability_assert": email_deliverability_assert,
    "WR_email_render_load_eml": email_render_load_eml,
    "WR_email_render_fetch": email_render_fetch,
    "WR_email_render_assert_subject": email_render_assert_subject,
    "WR_email_render_screenshots": email_render_screenshots,
    "WR_inbox_render_outlook_audit": inbox_render_outlook_audit,
    "WR_inbox_render_outlook_audit_page": inbox_render_outlook_audit_page,
    "WR_inbox_render_outlook_assert": inbox_render_outlook_assert,
    "WR_mq_assert_published": mq_assert_published,
    "WR_mq_assert_no_message": mq_assert_no_message,
    "WR_mq_assert_idempotent": mq_assert_idempotent,
    "WR_mq_assert_ordered": mq_assert_ordered,
    "WR_otp_interceptor_extract": otp_interceptor_extract,
    "WR_otp_interceptor_messages": otp_interceptor_messages,
    "WR_otp_interceptor_wait": otp_interceptor_wait,
    "WR_push_delivery_check": push_delivery_check,
    "WR_push_delivery_assert": push_delivery_assert,
    "WR_slack_digest_payload": slack_digest_payload,
    "WR_slack_digest_teams_card": slack_digest_teams_card,
    "WR_slack_digest_text": slack_digest_text,
    "WR_webhook_receiver_start": webhook_receiver_start,
    "WR_webhook_receiver_received": webhook_receiver_received,
    "WR_webhook_receiver_wait": webhook_receiver_wait,
    "WR_webhook_receiver_assert_path": webhook_receiver_assert_path,
    "WR_webhook_receiver_assert_header": webhook_receiver_assert_header,
    "WR_webhook_receiver_assert_json": webhook_receiver_assert_json,
    "WR_webhook_receiver_clear": webhook_receiver_clear,
    "WR_webhook_receiver_stop": webhook_receiver_stop,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset({
    "WR_email_render_fetch",
    "WR_otp_interceptor_messages",
    "WR_otp_interceptor_wait",
})
