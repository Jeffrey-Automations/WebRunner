"""
安全稽核類函式庫的命令轉接層（第一部分）
Command adapters for the security-audit libraries, part one: clickjacking, consent, CHIPS, cookie scope,
COOP/COEP, the CORS matrix, CSP violation reports, DOM XSS taint, HSTS preload, mixed content and
OAuth / PKCE replay. Part two is ``_commands_audit_2``.

Every command takes and returns JSON values. The CORS, OAuth and other "probe" libraries take a
caller-supplied transport in Python; here the action file passes the responses it already has and the
command classifies them, so nothing in this module sends a request.
"""
# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it
from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

from je_web_runner.utils.executor._command_helpers import selenium_driver, to_plain

_DRAIN_TAINT_SCRIPT = "return window.__wr_taint__ ? window.__wr_taint__.drain() : [];"


def _header_pairs(headers: Any) -> list[tuple[str, str]]:
    """Headers given as an object ``{name: value}`` or as a list of ``[name, value]`` pairs."""
    if isinstance(headers, dict):
        return [(str(name), str(value)) for name, value in headers.items()]
    return [(str(pair[0]), str(pair[1])) for pair in headers or [] if len(pair) == 2]


def _browser_cookies(command: str) -> list[dict[str, Any]]:
    """The cookies of the running browser, as Selenium returns them."""
    return list(selenium_driver(command).get_cookies())


# ---------- clickjacking_audit ------------------------------------------

def _clickjacking_report(target_url: str, headers: Any, probe_status: str | None) -> Any:
    from je_web_runner.utils.clickjacking_audit.audit import audit
    return audit(target_url, _header_pairs(headers), probe_status=probe_status)


def clickjacking_audit_headers(
    target_url: str, headers: Any, probe_status: str | None = None,
) -> dict[str, Any]:
    """
    Classify a response's X-Frame-Options / CSP frame-ancestors headers against clickjacking.

    ``headers`` is an object ``{name: value}`` or a list of ``[name, value]`` pairs; ``probe_status`` is the
    text an iframe probe page showed (``BLOCKED``, ``EMBEDDED``...), when one was run.
    Returns the verdict (``strict`` / ``sameorigin`` / ``allowed`` / ``missing``), the policy and ``passed``.
    """
    return to_plain(_clickjacking_report(target_url, headers, probe_status))


def clickjacking_audit_assert_protected(
    target_url: str, headers: Any, probe_status: str | None = None,
) -> dict[str, Any]:
    """Fail unless the headers forbid third-party framing (and the probe, when given, was blocked)."""
    from je_web_runner.utils.clickjacking_audit.audit import assert_protected
    report = _clickjacking_report(target_url, headers, probe_status)
    assert_protected(report)
    return to_plain(report)


def clickjacking_audit_probe_page(target_url: str) -> str:
    """Return the HTML of a probe page that tries to embed ``target_url`` in an iframe."""
    from je_web_runner.utils.clickjacking_audit.audit import build_probe_page
    return build_probe_page(target_url)


# ---------- consent_audit -----------------------------------------------

def _consent_rules(extra_rules: list[dict[str, Any]] | None) -> list[Any]:
    from je_web_runner.utils.consent_audit.audit import ConsentAuditError, CookieCategory, CookieRule
    rules = []
    for rule in extra_rules or []:
        try:
            category = CookieCategory(str(rule.get("category", "unknown")).lower())
        except ValueError as error:
            raise ConsentAuditError(f"unknown cookie category in rule: {rule!r}") from error
        rules.append(CookieRule(
            name_pattern=rule.get("name_pattern"),
            domain_suffix=rule.get("domain_suffix"),
            category=category,
            vendor=str(rule.get("vendor", "custom")),
        ))
    return rules


def _consent_report(
    before_consent: list[dict[str, Any]], after_consent: list[dict[str, Any]] | None,
    user_rejected: bool, extra_rules: list[dict[str, Any]] | None,
) -> Any:
    from je_web_runner.utils.consent_audit.audit import audit_consent, from_selenium_cookies
    return audit_consent(
        from_selenium_cookies(before_consent),
        from_selenium_cookies(after_consent or []),
        user_rejected=user_rejected,
        extra_rules=_consent_rules(extra_rules),
    )


def consent_audit_classify(
    cookies: list[dict[str, Any]], extra_rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Classify cookies as necessary / preferences / analytics / marketing / social / unknown.

    ``cookies`` are objects with ``name`` and optionally ``domain`` (the shape Selenium returns);
    ``extra_rules`` are objects ``{name_pattern, domain_suffix, category, vendor}`` tried before the
    built-in vendor catalogue.
    """
    from je_web_runner.utils.consent_audit.audit import classify_all, from_selenium_cookies
    return to_plain(classify_all(from_selenium_cookies(cookies), extra_rules=_consent_rules(extra_rules)))


def consent_audit_classify_page(extra_rules: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Classify the cookies the running browser holds right now."""
    return consent_audit_classify(_browser_cookies("WR_consent_audit_classify_page"), extra_rules)


def consent_audit_check(
    before_consent: list[dict[str, Any]], after_consent: list[dict[str, Any]] | None = None,
    user_rejected: bool = False, extra_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Report non-essential cookies set before consent and, with ``user_rejected``, those set after a reject.

    Returns the totals, ``pre_consent_violations``, ``post_consent_reintroduced``, ``unknown_cookies``
    and ``passed``.
    """
    return to_plain(_consent_report(before_consent, after_consent, user_rejected, extra_rules))


def consent_audit_assert_passes(
    before_consent: list[dict[str, Any]] | None = None, after_consent: list[dict[str, Any]] | None = None,
    user_rejected: bool = False, extra_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Fail when a non-essential cookie exists before consent or comes back after a reject.

    Without ``before_consent`` the cookies of the running browser are checked.
    """
    from je_web_runner.utils.consent_audit.audit import assert_passes
    if before_consent is None:
        before_consent = _browser_cookies("WR_consent_audit_assert_passes")
    report = _consent_report(before_consent, after_consent, user_rejected, extra_rules)
    assert_passes(report)
    return to_plain(report)


# ---------- cookie_chips_audit ------------------------------------------

def cookie_chips_audit_headers(
    set_cookie_headers: list[str], page_url: str, cookie_url: str,
) -> list[dict[str, Any]]:
    """
    Audit ``Set-Cookie`` header values for CHIPS (``Partitioned``) compliance.

    ``page_url`` is the top-level page, ``cookie_url`` the URL whose response set the cookies.
    """
    from je_web_runner.utils.cookie_chips_audit.audit import audit_headers
    return to_plain(audit_headers(set_cookie_headers, page_url, cookie_url))


def cookie_chips_audit_har(har: dict[str, Any], page_url: str) -> list[dict[str, Any]]:
    """Audit every ``Set-Cookie`` response header of a HAR object for CHIPS compliance."""
    from je_web_runner.utils.cookie_chips_audit.audit import audit_har
    return to_plain(audit_har(har, page_url))


def cookie_chips_audit_assert_no_errors(
    page_url: str, har: dict[str, Any] | None = None,
    set_cookie_headers: list[str] | None = None, cookie_url: str = "",
) -> list[dict[str, Any]]:
    """
    Fail when a HAR and / or a list of ``Set-Cookie`` values holds an error-level CHIPS finding.

    ``cookie_url`` is the URL that sent ``set_cookie_headers``. Returns all findings when none is an error.
    """
    from je_web_runner.utils.cookie_chips_audit.audit import (
        CookieChipsAuditError, assert_no_errors, audit_har, audit_headers,
    )
    if har is None and set_cookie_headers is None:
        raise CookieChipsAuditError("give har, set_cookie_headers or both")
    findings = [] if har is None else audit_har(har, page_url)
    if set_cookie_headers is not None:
        findings.extend(audit_headers(set_cookie_headers, page_url, cookie_url))
    assert_no_errors(findings)
    return to_plain(findings)


# ---------- cookie_scope_abuse ------------------------------------------

def cookie_scope_abuse_audit(cookies: list[dict[str, Any]], page_host: str) -> list[dict[str, Any]]:
    """
    Find session-like cookies that are scoped too widely or lack HttpOnly / Secure / SameSite.

    ``cookies`` are objects with ``name``, ``value``, ``domain``, ``path``, ``httpOnly``, ``secure`` and
    ``sameSite``; ``page_host`` is the host of the page that owns them.
    """
    from je_web_runner.utils.cookie_scope_abuse.scope import audit_many
    return to_plain(audit_many(cookies, page_host=page_host))


def cookie_scope_abuse_audit_page() -> list[dict[str, Any]]:
    """Audit the cookies of the running browser against the host of the current page."""
    driver = selenium_driver("WR_cookie_scope_abuse_audit_page")
    return cookie_scope_abuse_audit(list(driver.get_cookies()), urlparse(str(driver.current_url)).hostname or "")


def cookie_scope_abuse_assert_no_errors(
    cookies: list[dict[str, Any]], page_host: str,
) -> list[dict[str, Any]]:
    """Fail when a session-like cookie misses HttpOnly, Secure or a Strict / Lax SameSite."""
    from je_web_runner.utils.cookie_scope_abuse.scope import assert_no_errors, audit_many
    findings = audit_many(cookies, page_host=page_host)
    assert_no_errors(findings)
    return to_plain(findings)


# ---------- coop_coep_audit ---------------------------------------------

def _isolation_report(page_url: str, page_headers: Any, har: Any) -> Any:
    from je_web_runner.utils.coop_coep_audit.audit import audit_isolation
    return audit_isolation(page_url, _header_pairs(page_headers), har=har)


def coop_coep_audit_isolation(
    page_url: str, page_headers: Any, har: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """
    Report whether a page's COOP / COEP headers make it cross-origin isolated.

    ``page_headers`` is an object or a list of ``[name, value]`` pairs; ``har`` (object or JSON text) adds a
    check that every cross-origin resource satisfies the page's COEP.
    """
    return to_plain(_isolation_report(page_url, page_headers, har))


def coop_coep_audit_assert_isolated(
    page_url: str, page_headers: Any, har: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Fail unless the page is cross-origin isolated and no resource in ``har`` violates COEP."""
    from je_web_runner.utils.coop_coep_audit.audit import assert_isolated
    report = _isolation_report(page_url, page_headers, har)
    assert_isolated(report)
    return to_plain(report)


# ---------- cors_matrix -------------------------------------------------

def cors_matrix_build(
    verbs: list[str] | None = None, origins: list[str] | None = None,
    credentials_modes: list[bool] | None = None,
) -> list[dict[str, Any]]:
    """
    List the ``verb`` x ``origin`` x ``with_credentials`` cases of a CORS test matrix.

    An omitted axis takes the library default; each case also says whether it ``needs_preflight``.
    """
    from je_web_runner.utils.cors_matrix.matrix import build_matrix
    axes: dict[str, Any] = {"verbs": verbs, "origins": origins, "credentials_modes": credentials_modes}
    cases = build_matrix(**{name: values for name, values in axes.items() if values is not None})
    return [{**to_plain(case), "needs_preflight": case.needs_preflight()} for case in cases]


def _cors_results(responses: list[dict[str, Any]]) -> list[Any]:
    from je_web_runner.utils.cors_matrix.matrix import CorsCase, CorsMatrixError, CorsResponse, classify
    if not responses:
        raise CorsMatrixError("responses must be non-empty")
    results = []
    for item in responses:
        case = CorsCase(
            verb=str(item.get("verb", "GET")).upper(),
            origin=str(item.get("origin", "")),
            with_credentials=bool(item.get("with_credentials", False)),
        )
        response = CorsResponse(
            status_code=int(item.get("status_code", 0)),
            allow_origin=item.get("allow_origin"),
            allow_credentials=bool(item.get("allow_credentials", False)),
            allow_methods=list(item.get("allow_methods") or []),
            allow_headers=list(item.get("allow_headers") or []),
        )
        results.append(classify(case, response))
    return results


def cors_matrix_classify(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Decide for recorded CORS responses whether the browser would allow each request.

    Each item holds the case (``verb``, ``origin``, ``with_credentials``) and what the server answered
    (``status_code``, ``allow_origin``, ``allow_credentials``, ``allow_methods``, ``allow_headers``).
    Returns one ``{case, outcome, response, note}`` per item; ``outcome`` is ``allowed`` / ``blocked`` /
    ``ambiguous``. This command sends nothing.
    """
    return to_plain(_cors_results(responses))


def cors_matrix_assert_origin_blocked(responses: list[dict[str, Any]], origin: str) -> list[dict[str, Any]]:
    """Fail when any recorded response lets ``origin`` through."""
    from je_web_runner.utils.cors_matrix.matrix import assert_origin_blocked
    results = _cors_results(responses)
    assert_origin_blocked(results, origin=origin)
    return to_plain(results)


def cors_matrix_assert_credentials_origin(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fail when a credentialed request was answered with ``Access-Control-Allow-Origin: *``."""
    from je_web_runner.utils.cors_matrix.matrix import assert_credentials_require_explicit_origin
    results = _cors_results(responses)
    assert_credentials_require_explicit_origin(results)
    return to_plain(results)


# ---------- csp_violation_parser ----------------------------------------

def csp_violation_parser_parse(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise CSP ``report-uri`` / ``report-to`` payloads into one violation record each."""
    from je_web_runner.utils.csp_violation_parser.parser import parse_many
    return to_plain(parse_many(reports))


def csp_violation_parser_summary(
    reports: list[dict[str, Any]], top_n: int = 5, distinct_hosts_threshold: int = 5,
) -> dict[str, Any]:
    """
    Summarise CSP violation reports: count per directive, most blocked hosts, probable reconnaissance.

    ``recon_directives`` lists the directives whose reports name at least ``distinct_hosts_threshold``
    different blocked hosts.
    """
    from je_web_runner.utils.csp_violation_parser.parser import (
        group_by_directive, looks_like_recon, parse_many, top_blocked_hosts,
    )
    violations = parse_many(reports)
    return {
        "total": len(violations),
        "by_directive": {name: len(items) for name, items in group_by_directive(violations).items()},
        "top_blocked_hosts": top_blocked_hosts(violations, top_n=top_n),
        "recon_directives": looks_like_recon(violations, distinct_hosts_threshold=distinct_hosts_threshold),
    }


def csp_violation_parser_assert_no_enforced(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fail when a report is an enforced violation (report-only ones are returned, not failed)."""
    from je_web_runner.utils.csp_violation_parser.parser import assert_no_enforced_violations, parse_many
    violations = parse_many(reports)
    assert_no_enforced_violations(violations)
    return to_plain(violations)


# ---------- dom_xss_taint -----------------------------------------------

def dom_xss_taint_canaries(test_name: str) -> list[str]:
    """
    Return two sentinel strings to inject as untrusted input (URL hash, query, postMessage payload).

    The strings differ between Python processes; use them within the run that made them.
    """
    from je_web_runner.utils.dom_xss_taint.taint import make_canaries
    return make_canaries(test_name)


def dom_xss_taint_install(canaries: list[str]) -> int:
    """
    Watch the current page's DOM sinks (innerHTML, document.write, eval...) for the given canaries.

    Run it after the page loads and before the code under test writes; returns how many canaries it watches.
    """
    from je_web_runner.utils.dom_xss_taint.taint import INSTALL_SCRIPT, DomXssTaintError
    if not canaries or not all(isinstance(canary, str) and canary for canary in canaries):
        raise DomXssTaintError("canaries must be a non-empty list of non-empty strings")
    selenium_driver("WR_dom_xss_taint_install").execute_script(INSTALL_SCRIPT, list(canaries))
    return len(canaries)


def _taint_findings(command: str, findings: list[dict[str, Any]] | None) -> list[Any]:
    from je_web_runner.utils.dom_xss_taint.taint import parse_findings
    if findings is None:
        findings = selenium_driver(command).execute_script(_DRAIN_TAINT_SCRIPT) or []
    return parse_findings(findings)


def dom_xss_taint_drain() -> list[dict[str, Any]]:
    """Return, and clear, the canary writes the page's watched sinks saw since the last drain."""
    return to_plain(_taint_findings("WR_dom_xss_taint_drain", None))


def dom_xss_taint_assert_no_taint(
    findings: list[dict[str, Any]] | None = None, allowed_sinks: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fail when a canary reached a DOM sink; with ``allowed_sinks``, only when it reached another sink.

    ``findings`` are ``{sink, canary, snippet}`` objects; without them the current page is drained.
    """
    from je_web_runner.utils.dom_xss_taint.taint import assert_no_taint, assert_only_safe_sinks
    parsed = _taint_findings("WR_dom_xss_taint_assert_no_taint", findings)
    if allowed_sinks is None:
        assert_no_taint(parsed)
    else:
        assert_only_safe_sinks(parsed, allowed_sinks=allowed_sinks)
    return to_plain(parsed)


# ---------- hsts_preload_audit ------------------------------------------

def hsts_preload_audit_parse(header: str) -> dict[str, Any]:
    """Parse a ``Strict-Transport-Security`` value into ``max_age``, ``include_subdomains``, ``preload``."""
    from je_web_runner.utils.hsts_preload_audit.audit import parse_header
    return to_plain(parse_header(header))


def hsts_preload_audit_assert_preload_ready(header: str, scheme: str | None = None) -> dict[str, Any]:
    """
    Fail unless an HSTS header qualifies for the browser preload list.

    It needs ``max-age`` of a year or more, ``includeSubDomains`` and ``preload``; with ``scheme`` given,
    the response must also have been served over ``https``.
    """
    from je_web_runner.utils.hsts_preload_audit.audit import (
        assert_preload_ready, assert_served_over_https, parse_header,
    )
    parsed = parse_header(header)
    assert_preload_ready(parsed)
    if scheme is not None:
        assert_served_over_https(scheme)
    return to_plain(parsed)


# ---------- mixed_content_audit -----------------------------------------

def _mixed_result(findings: list[Any]) -> dict[str, Any]:
    from je_web_runner.utils.mixed_content_audit.audit import summary
    return {"findings": to_plain(findings), "summary": summary(findings)}


def _mixed_findings(har: Any, messages: list[str] | None, page_url: str | None) -> list[Any]:
    from je_web_runner.utils.mixed_content_audit.audit import (
        MixedContentAuditError, scan_console_errors, scan_har,
    )
    if har is None and messages is None:
        raise MixedContentAuditError("give har, messages or both")
    findings = [] if har is None else scan_har(har, page_url=page_url)
    if messages is not None:
        findings.extend(scan_console_errors(messages, page_url=page_url or ""))
    return findings


def mixed_content_audit_har(har: dict[str, Any] | str, page_url: str | None = None) -> dict[str, Any]:
    """
    Find ``http://`` requests made by an ``https://`` page in a HAR (object or JSON text).

    Returns ``findings`` (``active`` = blocked by the browser, ``passive``, ``upgrade``) and a ``summary``
    count per severity. Without ``page_url`` the HAR's first page is taken as the document.
    """
    return _mixed_result(_mixed_findings(har, None, page_url))


def mixed_content_audit_console(messages: list[str], page_url: str = "") -> dict[str, Any]:
    """Find mixed-content warnings in a list of browser console messages."""
    return _mixed_result(_mixed_findings(None, messages, page_url))


def mixed_content_audit_assert_clean(
    har: dict[str, Any] | str | None = None, messages: list[str] | None = None,
    page_url: str | None = None, allow_passive: bool = False,
) -> dict[str, Any]:
    """
    Fail when a HAR and / or console messages show mixed content.

    With ``allow_passive`` only active mixed content (scripts, styles, frames, XHR) fails.
    """
    from je_web_runner.utils.mixed_content_audit.audit import assert_clean, assert_no_active
    findings = _mixed_findings(har, messages, page_url)
    check: Callable[[list[Any]], None] = assert_no_active if allow_passive else assert_clean
    check(findings)
    return _mixed_result(findings)


# ---------- oauth_pkce_replay -------------------------------------------

def oauth_pkce_replay_verifier(length: int = 64) -> dict[str, str]:
    """Make a fresh PKCE ``code_verifier`` (43 to 128 characters) and its S256 ``code_challenge``."""
    from je_web_runner.utils.oauth_pkce_replay.replay import challenge_for, generate_verifier
    verifier = generate_verifier(length)
    return {
        "code_verifier": verifier,
        "code_challenge": challenge_for(verifier),
        "code_challenge_method": "S256",
    }


def oauth_pkce_replay_challenge(verifier: str) -> str:
    """Return the S256 ``code_challenge`` of a PKCE ``code_verifier``."""
    from je_web_runner.utils.oauth_pkce_replay.replay import challenge_for
    return challenge_for(verifier)


def _recorded_probe(answer: Any) -> Callable[[dict[str, Any]], Any]:
    """A probe that sends nothing and hands back the answer the action file recorded."""
    def probe(_payload: dict[str, Any]) -> Any:
        return answer
    return probe


def _replay_results(responses: list[dict[str, Any]]) -> list[Any]:
    from je_web_runner.utils.oauth_pkce_replay.replay import (
        OauthPkceReplayError, ReplayCase, ReplayOutcome, TokenExchangeResponse, replay,
    )
    results = []
    for index, item in enumerate(responses or []):
        try:
            expected = ReplayOutcome(str(item.get("expected", "rejected")).lower())
        except ValueError as error:
            raise OauthPkceReplayError(f"unknown expected outcome in {item!r}") from error
        recorded = TokenExchangeResponse(
            status_code=int(item.get("status_code", 0)), body=item.get("body") or {},
        )
        case = ReplayCase(name=str(item.get("name", f"case_{index}")), payload={}, expected=expected)
        results.append(replay(case, _recorded_probe(recorded)))
    return results


def oauth_pkce_replay_classify(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Classify recorded token-endpoint answers to replayed OAuth values as rejected / accepted / ambiguous.

    Each item is ``{name, status_code, body}`` (``body`` the parsed JSON answer) and optionally
    ``expected``. ``accepted`` means the server issued a token for a replayed code, state or verifier.
    This command sends nothing: make the replay requests with the HTTP commands and pass their answers.
    """
    return to_plain(_replay_results(responses))


def oauth_pkce_replay_assert_all_rejected(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fail when any recorded replay answer carries an ``access_token`` (or when no answer is given)."""
    from je_web_runner.utils.oauth_pkce_replay.replay import assert_all_rejected
    results = _replay_results(responses)
    assert_all_rejected(results)
    return to_plain(results)


AUDIT_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_clickjacking_audit_headers": clickjacking_audit_headers,
    "WR_clickjacking_audit_assert_protected": clickjacking_audit_assert_protected,
    "WR_clickjacking_audit_probe_page": clickjacking_audit_probe_page,
    "WR_consent_audit_classify": consent_audit_classify,
    "WR_consent_audit_classify_page": consent_audit_classify_page,
    "WR_consent_audit_check": consent_audit_check,
    "WR_consent_audit_assert_passes": consent_audit_assert_passes,
    "WR_cookie_chips_audit_headers": cookie_chips_audit_headers,
    "WR_cookie_chips_audit_har": cookie_chips_audit_har,
    "WR_cookie_chips_audit_assert_no_errors": cookie_chips_audit_assert_no_errors,
    "WR_cookie_scope_abuse_audit": cookie_scope_abuse_audit,
    "WR_cookie_scope_abuse_audit_page": cookie_scope_abuse_audit_page,
    "WR_cookie_scope_abuse_assert_no_errors": cookie_scope_abuse_assert_no_errors,
    "WR_coop_coep_audit_isolation": coop_coep_audit_isolation,
    "WR_coop_coep_audit_assert_isolated": coop_coep_audit_assert_isolated,
    "WR_cors_matrix_build": cors_matrix_build,
    "WR_cors_matrix_classify": cors_matrix_classify,
    "WR_cors_matrix_assert_origin_blocked": cors_matrix_assert_origin_blocked,
    "WR_cors_matrix_assert_credentials_origin": cors_matrix_assert_credentials_origin,
    "WR_csp_violation_parser_parse": csp_violation_parser_parse,
    "WR_csp_violation_parser_summary": csp_violation_parser_summary,
    "WR_csp_violation_parser_assert_no_enforced": csp_violation_parser_assert_no_enforced,
    "WR_dom_xss_taint_canaries": dom_xss_taint_canaries,
    "WR_dom_xss_taint_install": dom_xss_taint_install,
    "WR_dom_xss_taint_drain": dom_xss_taint_drain,
    "WR_dom_xss_taint_assert_no_taint": dom_xss_taint_assert_no_taint,
    "WR_hsts_preload_audit_parse": hsts_preload_audit_parse,
    "WR_hsts_preload_audit_assert_preload_ready": hsts_preload_audit_assert_preload_ready,
    "WR_mixed_content_audit_har": mixed_content_audit_har,
    "WR_mixed_content_audit_console": mixed_content_audit_console,
    "WR_mixed_content_audit_assert_clean": mixed_content_audit_assert_clean,
    "WR_oauth_pkce_replay_verifier": oauth_pkce_replay_verifier,
    "WR_oauth_pkce_replay_challenge": oauth_pkce_replay_challenge,
    "WR_oauth_pkce_replay_classify": oauth_pkce_replay_classify,
    "WR_oauth_pkce_replay_assert_all_rejected": oauth_pkce_replay_assert_all_rejected,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset()
