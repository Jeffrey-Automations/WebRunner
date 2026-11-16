"""Tests for the security-audit command adapters (``_commands_audit`` and ``_commands_audit_2``)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest

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

ISOLATED_HEADERS = {
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
}

ENFORCED = {
    "csp-report": {
        "document-uri": PAGE,
        "violated-directive": "script-src",
        "blocked-uri": "https://evil.test/x.js",
        "line-number": 3,
    }
}

REPORT_ONLY = {"effectiveDirective": "img-src", "blockedURL": "https://img.test/a.png", "disposition": "report"}


def _mixed_har(*resources: tuple[str, str]) -> dict:
    return {"log": {"entries": [{"request": {"url": url}, "_resourceType": kind} for url, kind in resources]}}


def test_oauth_pkce_replay_verifier_and_challenge():
    from je_web_runner.utils.oauth_pkce_replay.replay import OauthPkceReplayError

    made = audit.oauth_pkce_replay_verifier(50)
    assert len(made["code_verifier"]) == 50 and made["code_challenge_method"] == "S256"
    assert made["code_challenge"] == audit.oauth_pkce_replay_challenge(made["code_verifier"])
    # The worked example of RFC 7636, appendix B.
    rfc_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert audit.oauth_pkce_replay_challenge(rfc_verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    with pytest.raises(OauthPkceReplayError):
        audit.oauth_pkce_replay_verifier(10)


def test_oauth_pkce_replay_classify_and_assert():
    from je_web_runner.utils.oauth_pkce_replay.replay import OauthPkceReplayError

    refused = {"name": "reuse_code", "status_code": 400, "body": {"error": "invalid_grant"}}
    issued = {"name": "reuse_verifier", "status_code": 200, "body": {"access_token": "issued"}}
    results = audit.oauth_pkce_replay_classify([refused, issued, {"status_code": 503}])
    assert [(item["case"], item["outcome"]) for item in results] == [
        ("reuse_code", "rejected"),
        ("reuse_verifier", "accepted"),
        ("case_2", "ambiguous"),
    ]
    assert results[1]["note"] == "expected rejected, got accepted"
    json.dumps(results)
    assert audit.oauth_pkce_replay_assert_all_rejected([refused])[0]["status_code"] == 400
    with pytest.raises(OauthPkceReplayError):
        audit.oauth_pkce_replay_assert_all_rejected([refused, issued])
    with pytest.raises(OauthPkceReplayError):
        audit.oauth_pkce_replay_assert_all_rejected([])
    with pytest.raises(OauthPkceReplayError):
        audit.oauth_pkce_replay_classify([{**refused, "expected": "maybe"}])


# ---------- open_redirect_detector --------------------------------------


def test_open_redirect_detector():
    from je_web_runner.utils.open_redirect_detector.detector import OpenRedirectError

    payloads = audit_2.open_redirect_detector_payloads("attacker.test")
    assert len(payloads) == 8
    assert payloads[1] == {
        "label": "absolute_https",
        "value": "https://attacker.test/",
        "expected_off_origin_host": "attacker.test",
    }
    json.dumps(payloads)
    off_site = {
        "label": "absolute_https",
        "value": "https://attacker.test/",
        "status_code": 302,
        "location": "https://attacker.test/",
    }
    stays = {"label": "scheme_relative", "value": "//attacker.test/", "status_code": 302, "location": "/home"}
    refused = {"value": "javascript:alert(1)", "status_code": 400, "location": None}
    report = audit_2.open_redirect_detector_classify([off_site, stays, refused], "app.example.com")
    assert report["passed"] is False
    assert [item["outcome"] for item in report["results"]] == ["allowed", "blocked", "blocked"]
    assert report["results"][2]["payload_label"] == "payload_2"
    json.dumps(report)
    assert audit_2.open_redirect_detector_assert_safe([stays, refused], "app.example.com")["passed"] is True
    with pytest.raises(OpenRedirectError):
        audit_2.open_redirect_detector_assert_safe([off_site], "app.example.com")
    with pytest.raises(OpenRedirectError):
        audit_2.open_redirect_detector_classify([], "app.example.com")


# ---------- pii_in_screenshot -------------------------------------------

OCR_TEXT = f"Customer alice@example.com paid with {CARD}"

EXTRACT = "je_web_runner.utils.pii_in_screenshot.scanner.extract_text"


def test_pii_in_screenshot_scan_text():
    result = audit_2.pii_in_screenshot_scan_text(OCR_TEXT, "invoice.png")
    assert result["passed"] is False and result["scanned"] == 1
    assert {item["rule"] for item in result["findings"]} == {"email", "credit_card"}
    assert result["by_severity"] == {"medium": 1, "critical": 1}
    assert all(item["image"] == "invoice.png" for item in result["findings"])
    assert CARD not in json.dumps(result)
    assert audit_2.pii_in_screenshot_scan_text("Quarterly revenue chart")["passed"] is True


def test_pii_in_screenshot_scan_images_and_page(driver):
    driver.get_screenshot_as_png.return_value = b"png-bytes"
    with patch(EXTRACT, return_value=OCR_TEXT) as extract:
        images = audit_2.pii_in_screenshot_scan_images(["a.png", "b.png"])
        page = audit_2.pii_in_screenshot_scan_page()
    assert images["scanned"] == 2 and len(images["findings"]) == 4
    assert {item["image"] for item in images["findings"]} == {"a.png", "b.png"}
    assert page["scanned"] == 1 and page["findings"][0]["image"] == "current_page"
    assert extract.call_args.args[0] == b"png-bytes"


def test_pii_in_screenshot_assert_clean(driver):
    from je_web_runner.utils.pii_in_screenshot.scanner import PiiInScreenshotError

    assert audit_2.pii_in_screenshot_assert_clean(text="nothing personal") == {
        "scanned": 1,
        "findings": [],
        "by_severity": {},
        "passed": True,
    }
    with pytest.raises(PiiInScreenshotError):
        audit_2.pii_in_screenshot_assert_clean(text=OCR_TEXT)
    driver.get_screenshot_as_png.return_value = b"png-bytes"
    with patch(EXTRACT, return_value="nothing personal"):
        assert audit_2.pii_in_screenshot_assert_clean()["scanned"] == 1
        assert audit_2.pii_in_screenshot_assert_clean(["a.png"], "still nothing")["scanned"] == 2
    with patch(EXTRACT, return_value=OCR_TEXT):
        with pytest.raises(PiiInScreenshotError):
            audit_2.pii_in_screenshot_assert_clean(["a.png"])
        with pytest.raises(PiiInScreenshotError):
            audit_2.pii_in_screenshot_assert_clean()


# ---------- sbom_diff ---------------------------------------------------


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


def test_sbom_diff_compare_and_markdown(tmp_path):
    report = audit_2.sbom_diff_compare(SBOM_BASE, SBOM_HEAD)
    assert [item["name"] for item in report["added"]] == ["ghost"]
    assert [item["name"] for item in report["removed"]] == ["left-pad"]
    assert report["upgraded"] == [{"name": "lodash", "base_version": "4.17.20", "head_version": "4.17.21"}]
    assert report["new_licenses"] == ["AGPL-3.0"]
    assert report["new_vulnerable"] == ["pkg:npm/ghost@2.0.0"]
    assert report["has_changes"] is True
    json.dumps(report)
    base_file = tmp_path / "base.json"
    head_file = tmp_path / "head.json"
    base_file.write_text(json.dumps(SBOM_BASE), encoding="utf-8")
    head_file.write_text(json.dumps(SBOM_HEAD), encoding="utf-8")
    assert audit_2.sbom_diff_compare(str(base_file), str(head_file)) == report
    markdown = audit_2.sbom_diff_markdown(SBOM_BASE, str(head_file))
    assert markdown.startswith("## SBOM diff") and "- `ghost@2.0.0`" in markdown
    assert audit_2.sbom_diff_markdown(SBOM_BASE, SBOM_BASE).endswith("_No changes._")


def test_sbom_diff_assert_acceptable(tmp_path):
    from je_web_runner.utils.sbom_diff.diff import SbomDiffError

    safe_head = {"components": SBOM_HEAD["components"]}
    assert audit_2.sbom_diff_assert_acceptable(SBOM_BASE, SBOM_BASE)["has_changes"] is False
    assert audit_2.sbom_diff_assert_acceptable(SBOM_BASE, safe_head, ["GPL-3.0"])["new_licenses"] == ["AGPL-3.0"]
    with pytest.raises(SbomDiffError):
        audit_2.sbom_diff_assert_acceptable(SBOM_BASE, SBOM_HEAD)
    with pytest.raises(SbomDiffError):
        audit_2.sbom_diff_assert_acceptable(SBOM_BASE, safe_head, ["agpl-3.0"])
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(SbomDiffError):
        audit_2.sbom_diff_compare(SBOM_BASE, str(broken))


# ---------- sri_verify --------------------------------------------------

CDN_SCRIPT = "https://cdn.test/lib.js"


def _sri_html(integrity: str) -> str:
    return (
        f'<html><head><script src="{CDN_SCRIPT}" integrity="{integrity}" crossorigin="anonymous"></script>'
        '<link rel="stylesheet" href="/site.css"></head></html>'
    )


def test_sri_verify_html_and_compute(tmp_path):
    resource = tmp_path / "lib.js"
    resource.write_bytes(b"console.log('lib');")
    digest = base64.b64encode(hashlib.sha384(b"console.log('lib');").digest()).decode("ascii")
    integrity = audit_2.sri_verify_compute(str(resource))
    assert integrity == f"sha384-{digest}"
    assert audit_2.sri_verify_compute(str(resource), "sha256").startswith("sha256-")
    findings = audit_2.sri_verify_html(_sri_html(integrity), resource_files={CDN_SCRIPT: str(resource)})
    assert [(item["url"], item["verdict"]) for item in findings] == [(CDN_SCRIPT, "ok"), ("/site.css", "missing")]
    json.dumps(findings)
    resource.write_bytes(b"console.log('tampered');")
    tampered = audit_2.sri_verify_html(_sri_html(integrity), resource_files={CDN_SCRIPT: str(resource)})
    assert tampered[0]["verdict"] == "hash_mismatch"
    assert audit_2.sri_verify_html(_sri_html("md5-abc"))[0]["verdict"] == "weak_alg"


def test_sri_verify_page_and_assert(driver):
    from je_web_runner.utils.sri_verify.verify import SriVerifyError

    protected = f'<script src="{CDN_SCRIPT}" integrity="sha384-abc" crossorigin="anonymous"></script>'
    driver.page_source = protected
    assert audit_2.sri_verify_page() == [{"tag": "script", "url": CDN_SCRIPT, "verdict": "ok", "detail": ""}]
    assert len(audit_2.sri_verify_assert_all_ok()) == 1
    bare = protected.replace(' crossorigin="anonymous"', "")
    assert audit_2.sri_verify_assert_all_ok(bare, require_crossorigin=False)[0]["verdict"] == "ok"
    with pytest.raises(SriVerifyError):
        audit_2.sri_verify_assert_all_ok(bare)
    driver.page_source = f'<script src="{CDN_SCRIPT}"></script>'
    with pytest.raises(SriVerifyError):
        audit_2.sri_verify_assert_all_ok()


# ---------- tls_cipher_audit --------------------------------------------

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


def test_tls_cipher_audit_live_commands_use_the_library_handshake():
    from je_web_runner.utils.tls_cipher_audit.audit import TlsCipherAuditError

    with patch(HANDSHAKE, return_value=_handshake_report()) as handshake:
        assert audit_2.tls_cipher_audit_handshake("example.com", 8443, 2.5) == MODERN
        handshake.assert_called_once_with("example.com", 8443, timeout=2.5)
        checked = audit_2.tls_cipher_audit_assert_host("example.com", subject_contains="commonName=example.com")
        assert checked == MODERN
        json.dumps(checked)
        with pytest.raises(TlsCipherAuditError):
            audit_2.tls_cipher_audit_assert_host("example.com", subject_contains="commonName=other.test")
    with patch(HANDSHAKE, return_value=_handshake_report(version="TLSv1.1")):
        with pytest.raises(TlsCipherAuditError):
            audit_2.tls_cipher_audit_assert_host("example.com")


def test_tls_cipher_audit_assert_report_is_offline():
    from je_web_runner.utils.tls_cipher_audit.audit import TlsCipherAuditError

    with patch(HANDSHAKE, side_effect=AssertionError("must not connect")):
        assert audit_2.tls_cipher_audit_assert_report(MODERN) == MODERN
        with pytest.raises(TlsCipherAuditError):
            audit_2.tls_cipher_audit_assert_report({**MODERN, "cipher_suite": "ECDHE-RSA-RC4-SHA"})
        assert (
            audit_2.tls_cipher_audit_assert_report(
                {**MODERN, "cipher_suite": "ECDHE-RSA-RC4-SHA"},
                banned_tokens=["NULL"],
            )["cipher_suite"]
            == "ECDHE-RSA-RC4-SHA"
        )
        with pytest.raises(TlsCipherAuditError):
            audit_2.tls_cipher_audit_assert_report({"host": "example.com", "version": "TLSv1.2"})


# ---------- token_leak_detector -----------------------------------------


def test_token_leak_detector_scan_text_and_page(driver):
    findings = audit_2.token_leak_detector_scan_text(f"Authorization: Bearer {_jwt()}", "response_body", PAGE)
    assert {item["pattern"] for item in findings} == {"jwt", "bearer_assignment"}
    assert all(item["source"] == "response_body" and item["location"] == PAGE for item in findings)
    assert _jwt() not in json.dumps(findings)
    critical = audit_2.token_leak_detector_scan_text(f"Bearer {_jwt()}", minimum_severity="critical")
    assert [item["pattern"] for item in critical] == ["jwt"]
    driver.page_source = f"<script>window.key = '{_aws_key()}';</script>"
    assert audit_2.token_leak_detector_scan_page() == [
        {
            "pattern": "aws_access_key_id",
            "severity": "critical",
            "token_suffix": "…KLMNOP",
            "source": "page_source",
            "location": PAGE,
        }
    ]


def test_token_leak_detector_scan_har_and_log(tmp_path):
    from je_web_runner.utils.token_leak_detector.detector import TokenLeakError

    har = {
        "log": {
            "entries": [
                {
                    "request": {"url": "https://api.test/config"},
                    "response": {"content": {"text": json.dumps({"key": _aws_key()})}},
                }
            ]
        }
    }
    from_har = audit_2.token_leak_detector_scan_har(har)
    assert [(item["pattern"], item["source"], item["location"]) for item in from_har] == [
        ("aws_access_key_id", "har.response", "https://api.test/config"),
    ]
    assert audit_2.token_leak_detector_scan_har(json.dumps(har), "critical") == from_har
    lines = ["started", f"debug key={_aws_key()}"]
    from_lines = audit_2.token_leak_detector_scan_log(lines)
    assert [item["location"] for item in from_lines] == ["line:2"]
    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join(lines), encoding="utf-8")
    assert audit_2.token_leak_detector_scan_log(path=str(log_file)) == from_lines
    with pytest.raises(TokenLeakError):
        audit_2.token_leak_detector_scan_log()


def test_token_leak_detector_assert_no_leaks(driver):
    from je_web_runner.utils.token_leak_detector.detector import TokenLeakError

    assert audit_2.token_leak_detector_assert_no_leaks("all quiet", lines=["nothing here"]) == []
    session = 'session_id="abcdefghijklmnopqrstuvwxyz"'
    allowed = audit_2.token_leak_detector_assert_no_leaks(session, minimum_severity="high")
    assert [item["severity"] for item in allowed] == ["medium"]
    with pytest.raises(TokenLeakError):
        audit_2.token_leak_detector_assert_no_leaks(session)
    with pytest.raises(TokenLeakError):
        audit_2.token_leak_detector_assert_no_leaks(lines=[_aws_key()], minimum_severity="critical")
    driver.page_source = "<p>hello</p>"
    assert audit_2.token_leak_detector_assert_no_leaks() == []
    driver.page_source = f"<p>{_aws_key()}</p>"
    with pytest.raises(TokenLeakError):
        audit_2.token_leak_detector_assert_no_leaks()


# ---------- webhook_signature_verify ------------------------------------

BODY = '{"event":"push","id":7}'

SHARED = "unit-test-shared-value"


@pytest.mark.parametrize(
    "scheme, header_names",
    [
        ("github", {"X-Hub-Signature-256"}),
        ("stripe", {"Stripe-Signature"}),
        ("slack", {"X-Slack-Signature", "X-Slack-Request-Timestamp"}),
    ],
)
def test_webhook_signature_sign_then_verify(scheme, header_names):
    from je_web_runner.utils.webhook_signature_verify.verify import (
        WebhookSignatureVerifyError,
    )

    headers = audit_2.webhook_signature_verify_sign(scheme, BODY, SHARED)
    assert set(headers) == header_names
    json.dumps(headers)
    assert audit_2.webhook_signature_verify_check(scheme, headers, BODY, SHARED) == {
        "ok": True,
        "scheme": scheme,
        "note": "",
    }
    assert audit_2.webhook_signature_verify_assert_valid(scheme.upper(), headers, BODY, SHARED)["ok"] is True
    assert audit_2.webhook_signature_verify_check(scheme, headers, BODY + " ", SHARED)["ok"] is False
    with pytest.raises(WebhookSignatureVerifyError):
        audit_2.webhook_signature_verify_assert_valid(scheme, headers, BODY, "another-value")


def test_webhook_signature_generic_stale_and_unknown():
    from je_web_runner.utils.webhook_signature_verify.verify import (
        WebhookSignatureVerifyError,
    )

    signature = hmac.new(SHARED.encode("utf-8"), BODY.encode("utf-8"), hashlib.sha256).hexdigest()
    assert audit_2.webhook_signature_verify_check("generic", {"X-Signature": signature}, BODY, SHARED)["ok"] is True
    stale = audit_2.webhook_signature_verify_sign("stripe", BODY, SHARED, int(time.time()) - 3600)
    with pytest.raises(WebhookSignatureVerifyError):
        audit_2.webhook_signature_verify_check("stripe", stale, BODY, SHARED)
    assert audit_2.webhook_signature_verify_check("stripe", stale, BODY, SHARED, 7200)["ok"] is True
    with pytest.raises(WebhookSignatureVerifyError):
        audit_2.webhook_signature_verify_sign("generic", BODY, SHARED)
    with pytest.raises(WebhookSignatureVerifyError):
        audit_2.webhook_signature_verify_check("paypal", {}, BODY, SHARED)
    with pytest.raises(WebhookSignatureVerifyError):
        audit_2.webhook_signature_verify_check("github", {}, BODY, SHARED)


# ---------- csp_reporter ------------------------------------------------


def test_csp_reporter(driver):
    from je_web_runner.utils.csp_reporter.reporter import CspReporterError

    assert audit_2.csp_reporter_install() is True
    assert "securitypolicyviolation" in driver.execute_script.call_args.args[0]
    driver.execute_script.return_value = json.dumps(
        [
            {
                "violatedDirective": "script-src",
                "blockedURI": "https://evil.test/x.js",
                "sourceFile": PAGE,
                "lineNumber": 12,
                "sample": "",
            }
        ]
    )
    collected = audit_2.csp_reporter_collect()
    assert collected == [
        {
            "violated_directive": "script-src",
            "blocked_uri": "https://evil.test/x.js",
            "source_file": PAGE,
            "line_number": 12,
            "sample": "",
        }
    ]
    json.dumps(collected)
    with pytest.raises(CspReporterError):
        audit_2.csp_reporter_assert_no_violations()
    assert audit_2.csp_reporter_assert_no_violations(["script-src"]) is True
    driver.execute_script.return_value = "[]"
    assert audit_2.csp_reporter_assert_no_violations() is True
    assert audit_2.csp_reporter_collect() == []


# ---------- header_tampering --------------------------------------------


def test_header_tampering_apply():
    from je_web_runner.utils.header_tampering.tamper import HeaderTamperingError

    original = {"Authorization": "Bearer abc", "Accept": "text/html"}
    rules = [
        {"header": "Authorization", "action": "remove"},
        {"header": "Origin", "action": "set", "value": "https://evil.test"},
        {"header": "Accept", "action": "append", "value": "application/json", "url_substring": "/api/"},
        {"header": "X-Skipped", "action": "set", "value": "1", "url_substring": "/admin/"},
    ]
    result = audit_2.header_tampering_apply(original, "https://app.test/api/users?id=1", rules)
    assert result == {"Accept": "text/html, application/json", "Origin": "https://evil.test"}
    assert original == {"Authorization": "Bearer abc", "Accept": "text/html"}
    json.dumps(result)
    assert audit_2.header_tampering_apply(original, "https://app.test/", []) == original
    with pytest.raises(HeaderTamperingError):
        audit_2.header_tampering_apply(original, "https://app.test/", [{"header": "Origin", "action": "swap"}])
    with pytest.raises(HeaderTamperingError):
        audit_2.header_tampering_apply(original, "https://app.test/", [{"header": "Origin", "action": "set"}])


# ---------- license_scanner ---------------------------------------------

BUNDLE = "/*! SPDX-License-Identifier: MIT */\nfunction a(){}\n/* Apache License, Version 2.0 */\n"


def test_license_scanner(tmp_path):
    from je_web_runner.utils.license_scanner.scanner import LicenseScannerError

    result = audit_2.license_scanner_scan_text(BUNDLE)
    assert result["summary"] == {"MIT": 1, "Apache-2.0": 1}
    assert [(item["license_id"], item["line_number"]) for item in result["findings"]] == [
        ("MIT", 1),
        ("Apache-2.0", 3),
    ]
    json.dumps(result)
    bundle_file = tmp_path / "bundle.js"
    bundle_file.write_text(BUNDLE, encoding="utf-8")
    assert audit_2.license_scanner_scan_file(str(bundle_file)) == result
    assert audit_2.license_scanner_assert_allowed(["MIT", "Apache-2.0"], BUNDLE) == result
    assert audit_2.license_scanner_assert_allowed(["MIT", "Apache-2.0"], path=str(bundle_file)) == result
    with pytest.raises(LicenseScannerError):
        audit_2.license_scanner_assert_allowed(["MIT"], BUNDLE)
    with pytest.raises(LicenseScannerError):
        audit_2.license_scanner_assert_allowed(["MIT", "Apache-2.0"], BUNDLE, deny=["Apache-2.0"])
    with pytest.raises(LicenseScannerError):
        audit_2.license_scanner_assert_allowed(["MIT"])


# ---------- pii_scanner -------------------------------------------------

PII_TEXT = "Reach bob@example.com from 10.0.0.1"


def test_pii_scanner_scan_and_redact(driver):
    result = audit_2.pii_scanner_scan_text(PII_TEXT)
    assert result["summary"] == {"email": 1, "ipv4": 1}
    assert result["findings"][0] == {"category": "email", "start": 6, "end": 21, "redacted": "bo***********om"}
    assert "bob@example.com" not in json.dumps(result)
    assert audit_2.pii_scanner_scan_text(PII_TEXT, ["ipv4"])["summary"] == {"ipv4": 1}
    assert audit_2.pii_scanner_redact_text(PII_TEXT) == "Reach [REDACTED] from [REDACTED]"
    assert audit_2.pii_scanner_redact_text(PII_TEXT, "<x>", ["email"]) == "Reach <x> from 10.0.0.1"
    driver.page_source = f"<td>{CARD}</td>"
    assert audit_2.pii_scanner_scan_page()["summary"] == {"credit_card": 1}
    assert audit_2.pii_scanner_scan_page(["email"])["findings"] == []


def test_pii_scanner_assert_no_pii(driver):
    from je_web_runner.utils.pii_scanner.scanner import PiiScannerError

    assert audit_2.pii_scanner_assert_no_pii("nothing personal") is True
    assert audit_2.pii_scanner_assert_no_pii(PII_TEXT, allow_categories=["email", "ipv4"]) is True
    assert audit_2.pii_scanner_assert_no_pii(PII_TEXT, categories=["credit_card"]) is True
    with pytest.raises(PiiScannerError):
        audit_2.pii_scanner_assert_no_pii(PII_TEXT)
    driver.page_source = "<p>clean</p>"
    assert audit_2.pii_scanner_assert_no_pii() is True
    driver.page_source = "<p>A123456789</p>"
    with pytest.raises(PiiScannerError):
        audit_2.pii_scanner_assert_no_pii()
