"""Tests for the security-audit command adapters (``_commands_audit`` and ``_commands_audit_2``)."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException
from je_web_runner.utils.executor import _command_helpers
from je_web_runner.utils.executor import _commands_audit as audit
from je_web_runner.utils.executor import _commands_audit_2 as audit_2

FIRST_PACKAGES = (
    "clickjacking_audit",
    "consent_audit",
    "cookie_chips_audit",
    "cookie_scope_abuse",
    "coop_coep_audit",
    "cors_matrix",
    "csp_violation_parser",
    "dom_xss_taint",
    "hsts_preload_audit",
    "mixed_content_audit",
    "oauth_pkce_replay",
)

SECOND_PACKAGES = (
    "open_redirect_detector",
    "pii_in_screenshot",
    "sbom_diff",
    "sri_verify",
    "tls_cipher_audit",
    "token_leak_detector",
    "webhook_signature_verify",
    "csp_reporter",
    "header_tampering",
    "license_scanner",
    "pii_scanner",
)

CARD = "4111 1111 1111 1111"

PAGE = "https://app.example.com/account"


def _jwt() -> str:
    """A syntactically valid, meaningless JWT built at run time."""

    def part(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return ".".join((part(b'{"alg":"HS256","typ":"JWT"}'), part(b'{"sub":"1234567890"}'), part(b"0" * 24)))


def _aws_key() -> str:
    return "AKIA" + "ABCDEFGHIJKLMNOP"


@pytest.fixture(name="driver")
def driver_fixture():
    """A stand-in for the running Selenium browser."""
    mock = MagicMock()
    mock.current_url = PAGE
    with patch.object(_command_helpers.webdriver_wrapper_instance, "current_webdriver", mock):
        yield mock


# ---------- registries --------------------------------------------------


@pytest.mark.parametrize(
    "module, commands, packages",
    [
        (audit, audit.AUDIT_COMMANDS, FIRST_PACKAGES),
        (audit_2, audit_2.AUDIT_2_COMMANDS, SECOND_PACKAGES),
    ],
)
def test_registries_are_consistent(module, commands, packages):
    prefixes = tuple(f"WR_{package}_" for package in packages)
    for name, function in commands.items():
        assert name.startswith(prefixes), name
        assert name == name.lower().replace("wr_", "WR_", 1)
        assert callable(function)
        assert (function.__doc__ or "").strip(), name
    for package in packages:
        covered = any(name.startswith(f"WR_{package}_") for name in commands)
        assert covered or package in module.PYTHON_ONLY, package
    assert set(module.PYTHON_ONLY) <= set(packages)
    assert module.NETWORK_COMMANDS <= set(commands)
    assert isinstance(module.NETWORK_COMMANDS, frozenset)


def test_only_the_tls_handshakes_are_network_commands():
    assert audit.NETWORK_COMMANDS == frozenset()
    assert audit_2.NETWORK_COMMANDS == {"WR_tls_cipher_audit_handshake", "WR_tls_cipher_audit_assert_host"}
    assert not set(audit.AUDIT_COMMANDS) & set(audit_2.AUDIT_2_COMMANDS)


def test_browser_commands_need_a_browser():
    with patch.object(_command_helpers.webdriver_wrapper_instance, "current_webdriver", None):
        with pytest.raises(WebRunnerWebDriverIsNoneException):
            audit.consent_audit_classify_page()
        with pytest.raises(WebRunnerWebDriverIsNoneException):
            audit_2.sri_verify_page()


# ---------- clickjacking_audit ------------------------------------------


def test_clickjacking_headers():
    from je_web_runner.utils.clickjacking_audit.audit import ClickjackingAuditError

    strict = audit.clickjacking_audit_headers(PAGE, {"X-Frame-Options": "DENY"})
    assert strict["verdict"] == "strict" and strict["passed"] is True
    json.dumps(strict)
    pairs = [["Content-Security-Policy", "default-src 'self'; frame-ancestors 'self'"]]
    assert audit.clickjacking_audit_headers(PAGE, pairs)["verdict"] == "sameorigin"
    assert audit.clickjacking_audit_headers(PAGE, pairs, "EMBEDDED")["passed"] is False
    assert audit.clickjacking_audit_assert_protected(PAGE, pairs, "BLOCKED")["passed"] is True
    with pytest.raises(ClickjackingAuditError):
        audit.clickjacking_audit_assert_protected(PAGE, {})


def test_clickjacking_probe_page():
    from je_web_runner.utils.clickjacking_audit.audit import ClickjackingAuditError

    assert f'src="{PAGE}"' in audit.clickjacking_audit_probe_page(PAGE)
    with pytest.raises(ClickjackingAuditError):
        audit.clickjacking_audit_probe_page("file:///etc/hosts")


# ---------- consent_audit -----------------------------------------------


def test_consent_classify():
    from je_web_runner.utils.consent_audit.audit import ConsentAuditError

    cookies = [{"name": "_ga", "domain": ".example.com"}, {"name": "session"}, {"name": "acme_track"}]
    result = audit.consent_audit_classify(cookies)
    assert [item["category"] for item in result] == ["analytics", "necessary", "unknown"]
    json.dumps(result)
    rules = [{"name_pattern": "^acme_track$", "category": "marketing", "vendor": "acme"}]
    custom = audit.consent_audit_classify(cookies, rules)[2]
    assert (custom["category"], custom["vendor"]) == ("marketing", "acme")
    with pytest.raises(ConsentAuditError):
        audit.consent_audit_classify(cookies, [{"name_pattern": "x", "category": "tasty"}])


def test_consent_classify_page(driver):
    driver.get_cookies.return_value = [{"name": "_fbp", "domain": ".example.com"}]
    assert audit.consent_audit_classify_page() == [
        {"name": "_fbp", "domain": ".example.com", "category": "marketing", "vendor": "facebook_pixel"},
    ]


def test_consent_check_and_assert(driver):
    from je_web_runner.utils.consent_audit.audit import ConsentAuditError

    clean = [{"name": "session"}]
    tracked = [{"name": "session"}, {"name": "_ga"}]
    report = audit.consent_audit_check(tracked)
    assert report["passed"] is False
    assert [item["name"] for item in report["pre_consent_violations"]] == ["_ga"]
    rejected = audit.consent_audit_check(clean, tracked, user_rejected=True)
    assert [item["name"] for item in rejected["post_consent_reintroduced"]] == ["_ga"]
    assert audit.consent_audit_assert_passes(clean, tracked)["passed"] is True
    with pytest.raises(ConsentAuditError):
        audit.consent_audit_assert_passes(clean, tracked, user_rejected=True)
    driver.get_cookies.return_value = tracked
    with pytest.raises(ConsentAuditError):
        audit.consent_audit_assert_passes()
    driver.get_cookies.return_value = clean
    assert audit.consent_audit_assert_passes()["pre_consent_total"] == 1


# ---------- cookie_chips_audit ------------------------------------------

CHIPS_PAGE = "https://shop.example/"

CHIPS_THIRD_PARTY = "https://px.tracker.test/pixel"


def _chips_har(set_cookie: str) -> dict:
    return {
        "log": {
            "entries": [
                {
                    "request": {"url": CHIPS_THIRD_PARTY},
                    "response": {"headers": [{"name": "Set-Cookie", "value": set_cookie}]},
                }
            ]
        }
    }


def test_cookie_chips_headers_and_har():
    good = "id=1; Secure; SameSite=None; Partitioned"
    assert audit.cookie_chips_audit_headers([good], CHIPS_PAGE, CHIPS_THIRD_PARTY) == []
    findings = audit.cookie_chips_audit_headers(["id=1; Secure"], CHIPS_PAGE, CHIPS_THIRD_PARTY)
    assert [(item["rule"], item["severity"]) for item in findings] == [("third-party-missing-partitioned", "error")]
    json.dumps(findings)
    from_har = audit.cookie_chips_audit_har(_chips_har("id=1; Partitioned"), CHIPS_PAGE)
    assert sorted(item["rule"] for item in from_har) == [
        "partitioned-requires-samesite-none",
        "partitioned-requires-secure",
    ]


def test_cookie_chips_assert_no_errors():
    from je_web_runner.utils.cookie_chips_audit.audit import CookieChipsAuditError

    first_party = audit.cookie_chips_audit_assert_no_errors(
        CHIPS_PAGE,
        set_cookie_headers=["id=1; Secure; SameSite=None; Partitioned"],
        cookie_url=CHIPS_PAGE,
    )
    assert [item["severity"] for item in first_party] == ["warn"]
    with pytest.raises(CookieChipsAuditError):
        audit.cookie_chips_audit_assert_no_errors(CHIPS_PAGE, har=_chips_har("id=1"))
    with pytest.raises(CookieChipsAuditError):
        audit.cookie_chips_audit_assert_no_errors(CHIPS_PAGE)


# ---------- cookie_scope_abuse ------------------------------------------

SAFE_COOKIE = {
    "name": "session_id",
    "value": "abc",
    "domain": "app.example.com",
    "path": "/api",
    "httpOnly": True,
    "secure": True,
    "sameSite": "Lax",
}

LOOSE_COOKIE = {"name": "session_id", "value": "abc", "domain": ".example.com", "path": "/"}


def test_cookie_scope_abuse_audit():
    from je_web_runner.utils.cookie_scope_abuse.scope import CookieScopeAbuseError

    assert audit.cookie_scope_abuse_audit([SAFE_COOKIE], "app.example.com") == []
    findings = audit.cookie_scope_abuse_audit([LOOSE_COOKIE], "app.example.com")
    assert [item["rule"] for item in findings] == [
        "session-on-apex",
        "session-path-root",
        "session-no-httponly",
        "session-no-secure",
        "session-bad-samesite",
    ]
    json.dumps(findings)
    assert audit.cookie_scope_abuse_assert_no_errors([SAFE_COOKIE], "app.example.com") == []
    with pytest.raises(CookieScopeAbuseError):
        audit.cookie_scope_abuse_assert_no_errors([LOOSE_COOKIE], "app.example.com")


def test_cookie_scope_abuse_audit_page(driver):
    driver.get_cookies.return_value = [LOOSE_COOKIE]
    rules = [item["rule"] for item in audit.cookie_scope_abuse_audit_page()]
    assert "session-on-apex" in rules and "session-no-secure" in rules


# ---------- coop_coep_audit ---------------------------------------------

ISOLATED_HEADERS = {
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
}


def test_coop_coep_isolation():
    from je_web_runner.utils.coop_coep_audit.audit import CoopCoepAuditError

    report = audit.coop_coep_audit_isolation(PAGE, ISOLATED_HEADERS)
    assert report["isolated"] is True and report["passed"] is True
    json.dumps(report)
    har = {"log": {"entries": [{"request": {"url": "https://cdn.other.test/a.js"}, "response": {"headers": []}}]}}
    with_har = audit.coop_coep_audit_isolation(PAGE, ISOLATED_HEADERS, json.dumps(har))
    assert with_har["passed"] is False
    assert with_har["resource_findings"][0]["url"] == "https://cdn.other.test/a.js"
    assert audit.coop_coep_audit_assert_isolated(PAGE, list(ISOLATED_HEADERS.items()))["isolated"] is True
    with pytest.raises(CoopCoepAuditError):
        audit.coop_coep_audit_assert_isolated(PAGE, ISOLATED_HEADERS, har)
    with pytest.raises(CoopCoepAuditError):
        audit.coop_coep_audit_assert_isolated(PAGE, {})


# ---------- cors_matrix -------------------------------------------------


def test_cors_matrix_build():
    assert len(audit.cors_matrix_build()) == 6 * 3 * 2
    cases = audit.cors_matrix_build(["get", "delete"], ["https://a.test"], [True])
    assert cases == [
        {"verb": "GET", "origin": "https://a.test", "with_credentials": True, "needs_preflight": False},
        {"verb": "DELETE", "origin": "https://a.test", "with_credentials": True, "needs_preflight": True},
    ]
    json.dumps(cases)


def test_cors_matrix_classify_and_asserts():
    from je_web_runner.utils.cors_matrix.matrix import CorsMatrixError

    evil = "https://evil.test"
    wildcard = {"verb": "GET", "origin": evil, "status_code": 200, "allow_origin": "*"}
    pinned = {
        "verb": "DELETE",
        "origin": evil,
        "status_code": 204,
        "allow_origin": "https://app.test",
        "allow_methods": ["DELETE"],
    }
    results = audit.cors_matrix_classify([wildcard, pinned])
    assert [item["outcome"] for item in results] == ["allowed", "blocked"]
    json.dumps(results)
    assert audit.cors_matrix_assert_origin_blocked([pinned], evil)[0]["outcome"] == "blocked"
    with pytest.raises(CorsMatrixError):
        audit.cors_matrix_assert_origin_blocked([wildcard, pinned], evil)
    assert len(audit.cors_matrix_assert_credentials_origin([wildcard])) == 1
    with pytest.raises(CorsMatrixError):
        audit.cors_matrix_assert_credentials_origin([{**wildcard, "with_credentials": True}])
    with pytest.raises(CorsMatrixError):
        audit.cors_matrix_classify([])


# ---------- csp_violation_parser ----------------------------------------

ENFORCED = {
    "csp-report": {
        "document-uri": PAGE,
        "violated-directive": "script-src",
        "blocked-uri": "https://evil.test/x.js",
        "line-number": 3,
    }
}

REPORT_ONLY = {"effectiveDirective": "img-src", "blockedURL": "https://img.test/a.png", "disposition": "report"}


def test_csp_violation_parser():
    from je_web_runner.utils.csp_violation_parser.parser import CspViolationParserError

    parsed = audit.csp_violation_parser_parse([ENFORCED, REPORT_ONLY])
    assert parsed[0]["violated_directive"] == "script-src" and parsed[0]["line_number"] == 3
    assert parsed[1]["disposition"] == "report"
    json.dumps(parsed)
    summary = audit.csp_violation_parser_summary([ENFORCED, ENFORCED, REPORT_ONLY], top_n=1)
    assert summary["total"] == 3
    assert summary["by_directive"] == {"script-src": 2, "img-src": 1}
    assert summary["top_blocked_hosts"] == [{"host": "evil.test", "count": 2}]
    assert summary["recon_directives"] == []
    assert len(audit.csp_violation_parser_assert_no_enforced([REPORT_ONLY])) == 1
    with pytest.raises(CspViolationParserError):
        audit.csp_violation_parser_assert_no_enforced([ENFORCED, REPORT_ONLY])


def test_csp_violation_parser_recon():
    probes = [{"violated-directive": "connect-src", "blocked-uri": f"https://host{index}.test/"} for index in range(3)]
    summary = audit.csp_violation_parser_summary(probes, distinct_hosts_threshold=3)
    assert summary["recon_directives"] == ["connect-src"]


# ---------- dom_xss_taint -----------------------------------------------


def test_dom_xss_taint_canaries_and_install(driver):
    from je_web_runner.utils.dom_xss_taint.taint import INSTALL_SCRIPT, DomXssTaintError

    canaries = audit.dom_xss_taint_canaries("login")
    assert len(canaries) == 2 and all(item.startswith("WRXSS-login-") for item in canaries)
    assert audit.dom_xss_taint_install(canaries) == 2
    driver.execute_script.assert_called_once_with(INSTALL_SCRIPT, canaries)
    with pytest.raises(DomXssTaintError):
        audit.dom_xss_taint_install([])


def test_dom_xss_taint_drain_and_assert(driver):
    from je_web_runner.utils.dom_xss_taint.taint import DomXssTaintError

    seen = [{"sink": "innerHTML", "canary": "WRXSS-a", "snippet": "<b>WRXSS-a</b>"}]
    driver.execute_script.return_value = seen
    assert audit.dom_xss_taint_drain() == seen
    json.dumps(audit.dom_xss_taint_drain())
    with pytest.raises(DomXssTaintError):
        audit.dom_xss_taint_assert_no_taint()
    assert audit.dom_xss_taint_assert_no_taint(allowed_sinks=["innerHTML"]) == seen
    with pytest.raises(DomXssTaintError):
        audit.dom_xss_taint_assert_no_taint(seen, allowed_sinks=["eval"])
    driver.execute_script.return_value = None
    assert audit.dom_xss_taint_assert_no_taint() == []
    assert audit.dom_xss_taint_assert_no_taint([]) == []


# ---------- hsts_preload_audit ------------------------------------------


def test_hsts_preload_audit():
    from je_web_runner.utils.hsts_preload_audit.audit import HstsPreloadAuditError

    ready = "max-age=63072000; includeSubDomains; preload"
    parsed = audit.hsts_preload_audit_parse(ready)
    assert parsed == {"raw": ready, "max_age": 63072000, "include_subdomains": True, "preload": True}
    json.dumps(parsed)
    assert audit.hsts_preload_audit_assert_preload_ready(ready, "https")["preload"] is True
    with pytest.raises(HstsPreloadAuditError):
        audit.hsts_preload_audit_assert_preload_ready(ready, "http")
    with pytest.raises(HstsPreloadAuditError):
        audit.hsts_preload_audit_assert_preload_ready("max-age=3600; includeSubDomains")


# ---------- mixed_content_audit -----------------------------------------


def _mixed_har(*resources: tuple[str, str]) -> dict:
    return {"log": {"entries": [{"request": {"url": url}, "_resourceType": kind} for url, kind in resources]}}


def test_mixed_content_audit_scans():
    har = _mixed_har(
        ("http://cdn.test/a.js", "script"), ("http://img.test/a.png", "image"), ("https://ok.test/b.js", "script")
    )
    result = audit.mixed_content_audit_har(har, PAGE)
    assert result["summary"] == {"active": 1, "passive": 1}
    assert [item["url"] for item in result["findings"]] == ["http://cdn.test/a.js", "http://img.test/a.png"]
    json.dumps(result)
    assert audit.mixed_content_audit_har(har, "http://plain.test/")["findings"] == []
    line = (
        "Mixed Content: The page at 'https://app.example.com/' was loaded over HTTPS, but requested an "
        "insecure script 'http://cdn.test/a.js'. This request has been blocked."
    )
    console = audit.mixed_content_audit_console([line, "unrelated error"], PAGE)
    assert console["summary"] == {"active": 1}
    assert console["findings"][0]["url"] == "http://cdn.test/a.js"


def test_mixed_content_audit_assert_clean():
    from je_web_runner.utils.mixed_content_audit.audit import MixedContentAuditError

    passive = _mixed_har(("http://img.test/a.png", "image"))
    assert audit.mixed_content_audit_assert_clean(_mixed_har(), page_url=PAGE)["findings"] == []
    assert audit.mixed_content_audit_assert_clean(passive, page_url=PAGE, allow_passive=True)["summary"] == {
        "passive": 1,
    }
    with pytest.raises(MixedContentAuditError):
        audit.mixed_content_audit_assert_clean(passive, page_url=PAGE)
    with pytest.raises(MixedContentAuditError):
        audit.mixed_content_audit_assert_clean(
            _mixed_har(("http://cdn.test/a.js", "script")),
            page_url=PAGE,
            allow_passive=True,
        )
    with pytest.raises(MixedContentAuditError):
        audit.mixed_content_audit_assert_clean()


# ---------- oauth_pkce_replay -------------------------------------------

OCR_TEXT = f"Customer alice@example.com paid with {CARD}"

EXTRACT = "je_web_runner.utils.pii_in_screenshot.scanner.extract_text"


def _component(name: str, version: str, license_id: str) -> dict:
    return {
        "name": name,
        "version": version,
        "purl": f"pkg:npm/{name}@{version}",
        "licenses": [{"license": {"id": license_id}}],
    }


SBOM_BASE = {"components": [_component("left-pad", "1.0.0", "MIT"), _component("lodash", "4.17.20", "MIT")]}

SBOM_HEAD = {
    "components": [_component("lodash", "4.17.21", "MIT"), _component("ghost", "2.0.0", "AGPL-3.0")],
    "vulnerabilities": [{"id": "CVE-0000-0001", "affects": [{"ref": "pkg:npm/ghost@2.0.0"}]}],
}

CDN_SCRIPT = "https://cdn.test/lib.js"


def _sri_html(integrity: str) -> str:
    return (
        f'<html><head><script src="{CDN_SCRIPT}" integrity="{integrity}" crossorigin="anonymous"></script>'
        '<link rel="stylesheet" href="/site.css"></head></html>'
    )


HANDSHAKE = "je_web_runner.utils.tls_cipher_audit.audit.handshake"

MODERN = {
    "host": "example.com",
    "port": 443,
    "version": "TLSv1.3",
    "cipher_suite": "TLS_AES_256_GCM_SHA384",
    "ocsp_stapled": False,
    "cert_subject": "commonName=example.com",
}


def _handshake_report(**changes):
    from je_web_runner.utils.tls_cipher_audit.audit import TlsHandshakeReport

    return TlsHandshakeReport(**{**MODERN, **changes})


BODY = '{"event":"push","id":7}'

SHARED = "unit-test-shared-value"

BUNDLE = "/*! SPDX-License-Identifier: MIT */\nfunction a(){}\n/* Apache License, Version 2.0 */\n"

PII_TEXT = "Reach bob@example.com from 10.0.0.1"
