"""
安全稽核類函式庫的命令轉接層（第二部分）
Command adapters for the security-audit libraries, part two: open redirects, PII in screenshots, SBOM
diffs, Subresource Integrity, TLS, token leaks, webhook signatures, the CSP violation listener, header
tampering, license scanning and PII scanning. Part one is ``_commands_audit``.

Every command takes and returns JSON values. Only the two ``WR_tls_cipher_audit`` commands that do a
handshake contact a host named by an argument; they are listed in :data:`NETWORK_COMMANDS`.
"""
# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import page_source, selenium_driver, to_plain


def _read_text(path: str) -> str:
    """The text of the file at ``path`` (UTF-8; undecodable bytes are replaced)."""
    return Path(path).read_text(encoding="utf-8", errors="replace")


# ---------- open_redirect_detector --------------------------------------

def open_redirect_detector_payloads(attacker_host: str = "evil.example") -> list[dict[str, Any]]:
    """
    List the values to try in a ``?redirect=`` / ``?next=`` parameter when testing for an open redirect.

    Each item has a ``label``, the ``value`` to send and the host a vulnerable server would redirect to.
    """
    from je_web_runner.utils.open_redirect_detector.detector import default_payloads
    return to_plain(default_payloads(attacker_host))


def _redirect_report(responses: list[dict[str, Any]], legitimate_host: str) -> Any:
    from je_web_runner.utils.open_redirect_detector.detector import (
        OpenRedirectError, ProbeReport, RedirectPayload, classify_response,
    )
    if not responses:
        raise OpenRedirectError("responses must be non-empty")
    report = ProbeReport(legitimate_host=legitimate_host)
    for index, item in enumerate(responses):
        payload = RedirectPayload(
            label=str(item.get("label", f"payload_{index}")), value=str(item.get("value", "")),
        )
        report.results.append(classify_response(
            payload, item.get("location"), item.get("status_code", 0), legitimate_host=legitimate_host,
        ))
    return report


def _redirect_result(report: Any) -> dict[str, Any]:
    return {
        "legitimate_host": report.legitimate_host,
        "passed": report.passed(),
        "results": to_plain(report.results),
    }


def open_redirect_detector_classify(responses: list[dict[str, Any]], legitimate_host: str) -> dict[str, Any]:
    """
    Decide from recorded answers whether a redirect parameter sends users off ``legitimate_host``.

    Each item is ``{label, value, status_code, location}``: the payload that was sent, the status that came
    back (redirects not followed) and its ``Location`` header. ``allowed`` in a result means vulnerable.
    This command sends nothing: make the requests with the HTTP commands and pass their answers.
    """
    return _redirect_result(_redirect_report(responses, legitimate_host))


def open_redirect_detector_assert_safe(responses: list[dict[str, Any]], legitimate_host: str) -> dict[str, Any]:
    """Fail when any recorded answer redirects to another host or to a ``javascript:`` / ``data:`` URL."""
    from je_web_runner.utils.open_redirect_detector.detector import assert_safe
    report = _redirect_report(responses, legitimate_host)
    assert_safe(report)
    return _redirect_result(report)


# ---------- pii_in_screenshot -------------------------------------------

def _screenshot_report(findings: list[Any] | None = None) -> Any:
    """A library ``ScanReport``, holding the findings of one scanned image when given."""
    from je_web_runner.utils.pii_in_screenshot.scanner import ScanReport
    report = ScanReport()
    if findings is not None:
        _add_scan(report, findings)
    return report


def _add_scan(report: Any, findings: list[Any]) -> None:
    report.scanned += 1
    for finding in findings:
        report.findings.append(finding)
        report.by_severity[finding.severity] = report.by_severity.get(finding.severity, 0) + 1


def _screenshot_result(report: Any) -> dict[str, Any]:
    return {**to_plain(report), "passed": report.passed()}


def _page_screenshot_findings(command: str) -> list[Any]:
    from je_web_runner.utils.pii_in_screenshot.scanner import scan_image
    return scan_image(selenium_driver(command).get_screenshot_as_png(), image_label="current_page")


def pii_in_screenshot_scan_text(text: str, image_label: str = "") -> dict[str, Any]:
    """
    Scan text already read from an image (OCR output) for e-mail, phone, card, SSN, ID, IBAN and IPv4.

    Returns ``findings`` (rule, severity, redacted match), ``by_severity`` counts and ``passed``.
    """
    from je_web_runner.utils.pii_in_screenshot.scanner import scan_text_only
    return _screenshot_result(_screenshot_report(scan_text_only(text, image_label=image_label)))


def pii_in_screenshot_scan_images(paths: list[str]) -> dict[str, Any]:
    """OCR the image files at ``paths`` and scan their text for PII (needs pytesseract and Pillow)."""
    from je_web_runner.utils.pii_in_screenshot.scanner import scan_screenshots
    return _screenshot_result(scan_screenshots([str(path) for path in paths or []]))


def pii_in_screenshot_scan_page() -> dict[str, Any]:
    """Screenshot the current page, OCR it and scan the text for PII (needs pytesseract and Pillow)."""
    return _screenshot_result(_screenshot_report(_page_screenshot_findings("WR_pii_in_screenshot_scan_page")))


def pii_in_screenshot_assert_clean(paths: list[str] | None = None, text: str | None = None) -> dict[str, Any]:
    """
    Fail when image files, or text already read from an image, show PII.

    Give ``paths``, ``text`` or both; with neither, a screenshot of the current page is checked.
    """
    from je_web_runner.utils.pii_in_screenshot.scanner import assert_clean, scan_screenshots, scan_text_only
    if paths is None and text is None:
        report = _screenshot_report(_page_screenshot_findings("WR_pii_in_screenshot_assert_clean"))
    else:
        report = _screenshot_report() if paths is None else scan_screenshots([str(path) for path in paths])
        if text is not None:
            _add_scan(report, scan_text_only(text, image_label="text"))
    assert_clean(report)
    return _screenshot_result(report)


# ---------- sbom_diff ---------------------------------------------------

def _sbom_report(base: dict[str, Any] | str, head: dict[str, Any] | str) -> Any:
    from je_web_runner.utils.sbom_diff.diff import SbomDiffError, diff_sboms
    loaded = []
    for sbom in (base, head):
        if isinstance(sbom, str):
            try:
                sbom = json.loads(_read_text(sbom))
            except ValueError as error:
                raise SbomDiffError(f"SBOM file is not JSON: {error}") from error
        loaded.append(sbom)
    return diff_sboms(loaded[0], loaded[1])


def _sbom_result(report: Any) -> dict[str, Any]:
    return {**to_plain(report), "has_changes": report.has_changes}


def sbom_diff_compare(base: dict[str, Any] | str, head: dict[str, Any] | str) -> dict[str, Any]:
    """
    Compare two CycloneDX SBOMs: components added, removed, upgraded, downgraded, new licenses.

    ``base`` and ``head`` are each the SBOM object or the path of its JSON file. ``new_vulnerable`` lists
    the component references that ``head``'s ``vulnerabilities`` section names and ``base``'s did not.
    """
    return _sbom_result(_sbom_report(base, head))


def sbom_diff_markdown(base: dict[str, Any] | str, head: dict[str, Any] | str) -> str:
    """Return the difference of two CycloneDX SBOMs as Markdown, ready for a PR comment."""
    from je_web_runner.utils.sbom_diff.diff import report_markdown
    return report_markdown(_sbom_report(base, head))


def sbom_diff_assert_acceptable(
    base: dict[str, Any] | str, head: dict[str, Any] | str, disallowed_licenses: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fail when ``head`` adds a vulnerable component or, with ``disallowed_licenses``, one of those licenses.

    License names are compared without regard to case, against the licenses new in ``head``.
    """
    from je_web_runner.utils.sbom_diff.diff import assert_no_disallowed_licenses, assert_no_new_vulnerable
    report = _sbom_report(base, head)
    assert_no_new_vulnerable(report)
    if disallowed_licenses is not None:
        assert_no_disallowed_licenses(report, disallowed_licenses)
    return _sbom_result(report)


# ---------- sri_verify --------------------------------------------------

def _sri_findings(html: str, require_crossorigin: bool, resource_files: dict[str, str] | None) -> list[Any]:
    from je_web_runner.utils.sri_verify.verify import verify_html
    files = resource_files or {}

    def provider(url: str) -> bytes | None:
        return Path(files[url]).read_bytes() if url in files else None

    return verify_html(
        html, payload_provider=provider if files else None, require_crossorigin=require_crossorigin,
    )


def sri_verify_html(
    html: str, require_crossorigin: bool = True, resource_files: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Check every ``<script src>`` and stylesheet ``<link>`` in ``html`` for Subresource Integrity.

    Verdicts: ``ok``, ``missing``, ``weak_alg``, ``no_crossorigin``, ``unknown_format``, and
    ``hash_mismatch`` for a URL listed in ``resource_files`` (URL as written in the tag -> local copy of
    the resource) whose bytes do not match the ``integrity`` value.
    """
    return to_plain(_sri_findings(html, require_crossorigin, resource_files))


def sri_verify_page(require_crossorigin: bool = True) -> list[dict[str, Any]]:
    """Check the scripts and stylesheets of the current page for Subresource Integrity."""
    return to_plain(_sri_findings(page_source("WR_sri_verify_page"), require_crossorigin, None))


def sri_verify_compute(path: str, algorithm: str = "sha384") -> str:
    """Return the ``integrity`` value (``sha384-...``) for the file at ``path``."""
    from je_web_runner.utils.sri_verify.verify import compute_integrity
    return compute_integrity(Path(path).read_bytes(), algorithm)


def sri_verify_assert_all_ok(
    html: str | None = None, require_crossorigin: bool = True, resource_files: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fail when a script or stylesheet lacks a valid, strong ``integrity`` attribute.

    Without ``html`` the current page is checked. Same-origin resources are checked too.
    """
    from je_web_runner.utils.sri_verify.verify import assert_all_ok
    if html is None:
        html = page_source("WR_sri_verify_assert_all_ok")
    findings = _sri_findings(html, require_crossorigin, resource_files)
    assert_all_ok(findings)
    return to_plain(findings)


# ---------- tls_cipher_audit --------------------------------------------

def _tls_check(report: Any, banned_tokens: list[str] | None, subject_contains: str | None) -> dict[str, Any]:
    from je_web_runner.utils.tls_cipher_audit.audit import (
        assert_cipher_safe, assert_modern_tls, assert_subject_matches,
    )
    assert_modern_tls(report)
    if banned_tokens is None:
        assert_cipher_safe(report)
    else:
        assert_cipher_safe(report, banned_tokens=banned_tokens)
    if subject_contains is not None:
        assert_subject_matches(report, contains=subject_contains)
    return to_plain(report)


def tls_cipher_audit_handshake(host: str, port: int = 443, timeout: float = 10.0) -> dict[str, Any]:
    """
    Connect to ``host``:``port`` over TLS and return the negotiated version, cipher and certificate subject.

    The certificate must be trusted by the system store and match ``host``, or the command fails.
    """
    from je_web_runner.utils.tls_cipher_audit.audit import handshake
    return to_plain(handshake(host, port, timeout=timeout))


def tls_cipher_audit_assert_host(
    host: str, port: int = 443, timeout: float = 10.0,
    banned_tokens: list[str] | None = None, subject_contains: str | None = None,
) -> dict[str, Any]:
    """
    Connect to ``host`` and fail unless it negotiates TLS 1.2 or 1.3 with a cipher that is not weak.

    ``banned_tokens`` replaces the default weak-cipher markers (RC4, 3DES, NULL, EXPORT, MD5...);
    ``subject_contains`` must appear in the certificate subject, e.g. ``commonName=example.com``.
    """
    from je_web_runner.utils.tls_cipher_audit.audit import handshake
    return _tls_check(handshake(host, port, timeout=timeout), banned_tokens, subject_contains)


def tls_cipher_audit_assert_report(
    report: dict[str, Any], banned_tokens: list[str] | None = None, subject_contains: str | None = None,
) -> dict[str, Any]:
    """
    Fail unless a recorded handshake report shows TLS 1.2 or 1.3 and a cipher that is not weak.

    ``report`` is ``{host, port, version, cipher_suite, cert_subject}``, as ``WR_tls_cipher_audit_handshake``
    returns it. This command connects to nothing.
    """
    from je_web_runner.utils.tls_cipher_audit.audit import TlsHandshakeReport
    recorded = TlsHandshakeReport(
        host=str(report.get("host", "")),
        port=int(report.get("port", 443)),
        version=report.get("version"),
        cipher_suite=report.get("cipher_suite"),
        ocsp_stapled=bool(report.get("ocsp_stapled", False)),
        cert_subject=str(report.get("cert_subject", "")),
    )
    return _tls_check(recorded, banned_tokens, subject_contains)


# ---------- token_leak_detector -----------------------------------------

def _leaks_at(findings: list[Any], minimum_severity: str | None) -> list[Any]:
    from je_web_runner.utils.token_leak_detector.detector import filter_by_severity
    if minimum_severity is None:
        return findings
    return filter_by_severity(findings, minimum=minimum_severity)


def token_leak_detector_scan_text(
    text: str, source: str = "text", location: str = "", minimum_severity: str | None = None,
) -> list[dict[str, Any]]:
    """
    Scan text for leaked JWTs, cloud and API keys, bearer and session tokens.

    Findings carry the pattern name, a severity and only the last characters of the token.
    ``minimum_severity`` (``low`` / ``medium`` / ``high`` / ``critical``) drops the lesser ones.
    """
    from je_web_runner.utils.token_leak_detector.detector import scan_text
    return to_plain(_leaks_at(scan_text(text, source=source, location=location), minimum_severity))


def token_leak_detector_scan_page(minimum_severity: str | None = None) -> list[dict[str, Any]]:
    """Scan the HTML of the current page for leaked tokens and keys."""
    driver = selenium_driver("WR_token_leak_detector_scan_page")
    return token_leak_detector_scan_text(
        str(driver.page_source), "page_source", str(driver.current_url), minimum_severity,
    )


def token_leak_detector_scan_har(
    har: dict[str, Any] | str, minimum_severity: str | None = None,
) -> list[dict[str, Any]]:
    """Scan the request and response bodies of a HAR (object or JSON text) for leaked tokens and keys."""
    from je_web_runner.utils.token_leak_detector.detector import scan_har
    return to_plain(_leaks_at(scan_har(har), minimum_severity))


def token_leak_detector_scan_log(
    lines: list[str] | None = None, path: str | None = None, minimum_severity: str | None = None,
) -> list[dict[str, Any]]:
    """Scan log lines, given as a list or as the path of a log file, for leaked tokens and keys."""
    from je_web_runner.utils.token_leak_detector.detector import TokenLeakError, scan_log_lines
    if lines is None and path is None:
        raise TokenLeakError("give lines or path")
    if lines is None:
        lines = _read_text(str(path)).splitlines()
    return to_plain(_leaks_at(scan_log_lines(lines), minimum_severity))


def token_leak_detector_assert_no_leaks(
    text: str | None = None, har: dict[str, Any] | str | None = None,
    lines: list[str] | None = None, minimum_severity: str = "low",
) -> list[dict[str, Any]]:
    """
    Fail when text, a HAR or log lines hold a token or key at or above ``minimum_severity``.

    Give any of ``text``, ``har`` and ``lines``; with none of them the HTML of the current page is checked.
    """
    from je_web_runner.utils.token_leak_detector.detector import (
        assert_no_leaks, filter_by_severity, scan_har, scan_log_lines, scan_text,
    )
    if text is None and har is None and lines is None:
        text = page_source("WR_token_leak_detector_assert_no_leaks")
    findings = [] if text is None else scan_text(text)
    if har is not None:
        findings.extend(scan_har(har))
    if lines is not None:
        findings.extend(scan_log_lines(lines))
    assert_no_leaks(filter_by_severity(findings, minimum=minimum_severity))
    return to_plain(findings)


# ---------- webhook_signature_verify ------------------------------------

def _webhook_scheme(scheme: str) -> Any:
    from je_web_runner.utils.webhook_signature_verify.verify import Scheme, WebhookSignatureVerifyError
    try:
        return Scheme(str(scheme).lower())
    except ValueError as error:
        raise WebhookSignatureVerifyError(
            f"unknown scheme {scheme!r}; pick from {[item.value for item in Scheme]}"
        ) from error


def _webhook_result(scheme: str, headers: dict[str, str], body: str, secret: str, tolerance_seconds: int) -> Any:
    from je_web_runner.utils.webhook_signature_verify.verify import verify
    return verify(_webhook_scheme(scheme), headers, body.encode("utf-8"), secret, tolerance_seconds)


def webhook_signature_verify_sign(
    scheme: str, body: str, secret: str, timestamp: int | None = None,
) -> dict[str, str]:
    """
    Return the signature headers a ``github``, ``stripe`` or ``slack`` webhook with this body would carry.

    Use them to send a test webhook to your own receiver. ``timestamp`` (Unix seconds) defaults to now.
    """
    from je_web_runner.utils.webhook_signature_verify.verify import (
        Scheme, WebhookSignatureVerifyError, sign_github, sign_slack, sign_stripe,
    )
    kind = _webhook_scheme(scheme)
    raw = body.encode("utf-8")
    moment = int(time.time()) if timestamp is None else int(timestamp)
    if kind == Scheme.GITHUB:
        return {"X-Hub-Signature-256": sign_github(raw, secret)}
    if kind == Scheme.STRIPE:
        return {"Stripe-Signature": sign_stripe(raw, secret, moment)}
    if kind == Scheme.SLACK:
        return {
            "X-Slack-Signature": sign_slack(raw, secret, moment),
            "X-Slack-Request-Timestamp": str(moment),
        }
    raise WebhookSignatureVerifyError("no signer for the generic scheme; sign github, stripe or slack")


def webhook_signature_verify_check(
    scheme: str, headers: dict[str, str], body: str, secret: str, tolerance_seconds: int = 300,
) -> dict[str, Any]:
    """
    Say whether a captured webhook's signature matches its body and the shared secret.

    ``scheme`` is ``github``, ``stripe``, ``slack`` or ``generic``; ``headers`` uses the provider's exact
    header names (``X-Hub-Signature-256``, ``Stripe-Signature``, ``X-Slack-Signature`` with
    ``X-Slack-Request-Timestamp``, ``X-Signature``). A missing header or a stale timestamp fails the command.
    """
    return to_plain(_webhook_result(scheme, headers, body, secret, tolerance_seconds))


def webhook_signature_verify_assert_valid(
    scheme: str, headers: dict[str, str], body: str, secret: str, tolerance_seconds: int = 300,
) -> dict[str, Any]:
    """Fail unless a captured webhook's signature matches its body and the shared secret."""
    from je_web_runner.utils.webhook_signature_verify.verify import assert_valid
    result = _webhook_result(scheme, headers, body, secret, tolerance_seconds)
    assert_valid(result)
    return to_plain(result)


# ---------- csp_reporter ------------------------------------------------

def csp_reporter_install() -> bool:
    """
    Start recording the Content-Security-Policy violations the current page fires.

    Run it after each page load; a navigation discards the listener.
    """
    from je_web_runner.utils.csp_reporter.reporter import install_listener
    install_listener(selenium_driver("WR_csp_reporter_install"))
    return True


def csp_reporter_collect() -> list[dict[str, Any]]:
    """Return the CSP violations recorded on the current page since ``WR_csp_reporter_install``."""
    from je_web_runner.utils.csp_reporter.reporter import collect_violations
    return to_plain(collect_violations(selenium_driver("WR_csp_reporter_collect")))


def csp_reporter_assert_no_violations(allow_directives: list[str] | None = None) -> bool:
    """Fail when the current page recorded a CSP violation of a directive not in ``allow_directives``."""
    from je_web_runner.utils.csp_reporter.reporter import assert_no_violations
    assert_no_violations(selenium_driver("WR_csp_reporter_assert_no_violations"), allow_directives)
    return True


# ---------- header_tampering --------------------------------------------

def header_tampering_apply(headers: dict[str, str], url: str, rules: list[dict[str, Any]]) -> dict[str, str]:
    """
    Return request headers with tampering rules applied, to send with an HTTP command.

    Each rule is ``{header, action, value, url_substring}``: ``action`` is ``set``, ``remove`` or
    ``append``; a rule with ``url_substring`` only applies when ``url`` contains it. Header names are
    matched exactly as written.
    """
    from je_web_runner.utils.header_tampering.tamper import HeaderRule, apply_to_request_headers
    built = []
    for rule in rules or []:
        action = str(rule.get("action", "set"))
        header = str(rule.get("header", ""))
        substring = rule.get("url_substring")
        built.append(HeaderRule(
            name=str(rule.get("name", f"{action}:{header}")),
            header=header,
            action=action,
            value=rule.get("value"),
            url_match=re.compile(re.escape(str(substring))) if substring else None,
        ))
    return apply_to_request_headers(dict(headers or {}), url, built)


# ---------- license_scanner ---------------------------------------------

def _license_findings(text: str | None, path: str | None) -> list[Any]:
    from je_web_runner.utils.license_scanner.scanner import LicenseScannerError, scan_text
    if text is None and path is None:
        raise LicenseScannerError("give text or path")
    return scan_text(_read_text(str(path)) if text is None else text)


def _license_result(findings: list[Any]) -> dict[str, Any]:
    from je_web_runner.utils.license_scanner.scanner import summarise
    return {"findings": to_plain(findings), "summary": dict(summarise(findings))}


def license_scanner_scan_text(text: str) -> dict[str, Any]:
    """
    Find SPDX identifiers and well-known license texts (MIT, Apache, GPL, AGPL...) in bundle text.

    Returns ``findings`` (license id, line number, snippet) and a ``summary`` count per license id.
    """
    return _license_result(_license_findings(text, None))


def license_scanner_scan_file(path: str) -> dict[str, Any]:
    """Find SPDX identifiers and well-known license texts in the JS / CSS bundle file at ``path``."""
    return _license_result(_license_findings(None, path))


def license_scanner_assert_allowed(
    allow: list[str], text: str | None = None, path: str | None = None, deny: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fail when bundle text (``text`` or the file at ``path``) names a license outside ``allow`` or in ``deny``.

    License ids are compared exactly, e.g. ``MIT``, ``Apache-2.0``, ``GPL-3.0``.
    """
    from je_web_runner.utils.license_scanner.scanner import assert_allowed_licenses
    findings = _license_findings(text, path)
    assert_allowed_licenses(findings, allow, deny)
    return _license_result(findings)


# ---------- pii_scanner -------------------------------------------------

def pii_scanner_scan_text(text: str, categories: list[str] | None = None) -> dict[str, Any]:
    """
    Find personal data in text: ``email``, ``phone_e164``, ``credit_card``, ``ssn_us``, ``taiwan_id``, ``ipv4``.

    Returns ``findings`` (category, position, redacted preview) and a ``summary`` count per category;
    ``categories`` limits the scan to the named ones.
    """
    from je_web_runner.utils.pii_scanner.scanner import scan_text, summarise
    findings = scan_text(text, categories=categories)
    return {"findings": to_plain(findings), "summary": dict(summarise(findings))}


def pii_scanner_scan_page(categories: list[str] | None = None) -> dict[str, Any]:
    """Find personal data in the HTML of the current page."""
    return pii_scanner_scan_text(page_source("WR_pii_scanner_scan_page"), categories)


def pii_scanner_redact_text(
    text: str, replacement: str = "[REDACTED]", categories: list[str] | None = None,
) -> str:
    """Return ``text`` with every piece of personal data replaced by ``replacement``."""
    from je_web_runner.utils.pii_scanner.scanner import redact_text
    return redact_text(text, replacement, categories)


def pii_scanner_assert_no_pii(
    text: str | None = None, categories: list[str] | None = None, allow_categories: list[str] | None = None,
) -> bool:
    """
    Fail when text holds personal data of a category not in ``allow_categories``.

    Without ``text`` the HTML of the current page is checked.
    """
    from je_web_runner.utils.pii_scanner.scanner import assert_no_pii
    if text is None:
        text = page_source("WR_pii_scanner_assert_no_pii")
    assert_no_pii(text, categories, allow_categories)
    return True


AUDIT_2_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_open_redirect_detector_payloads": open_redirect_detector_payloads,
    "WR_open_redirect_detector_classify": open_redirect_detector_classify,
    "WR_open_redirect_detector_assert_safe": open_redirect_detector_assert_safe,
    "WR_pii_in_screenshot_scan_text": pii_in_screenshot_scan_text,
    "WR_pii_in_screenshot_scan_images": pii_in_screenshot_scan_images,
    "WR_pii_in_screenshot_scan_page": pii_in_screenshot_scan_page,
    "WR_pii_in_screenshot_assert_clean": pii_in_screenshot_assert_clean,
    "WR_sbom_diff_compare": sbom_diff_compare,
    "WR_sbom_diff_markdown": sbom_diff_markdown,
    "WR_sbom_diff_assert_acceptable": sbom_diff_assert_acceptable,
    "WR_sri_verify_html": sri_verify_html,
    "WR_sri_verify_page": sri_verify_page,
    "WR_sri_verify_compute": sri_verify_compute,
    "WR_sri_verify_assert_all_ok": sri_verify_assert_all_ok,
    "WR_tls_cipher_audit_handshake": tls_cipher_audit_handshake,
    "WR_tls_cipher_audit_assert_host": tls_cipher_audit_assert_host,
    "WR_tls_cipher_audit_assert_report": tls_cipher_audit_assert_report,
    "WR_token_leak_detector_scan_text": token_leak_detector_scan_text,
    "WR_token_leak_detector_scan_page": token_leak_detector_scan_page,
    "WR_token_leak_detector_scan_har": token_leak_detector_scan_har,
    "WR_token_leak_detector_scan_log": token_leak_detector_scan_log,
    "WR_token_leak_detector_assert_no_leaks": token_leak_detector_assert_no_leaks,
    "WR_webhook_signature_verify_sign": webhook_signature_verify_sign,
    "WR_webhook_signature_verify_check": webhook_signature_verify_check,
    "WR_webhook_signature_verify_assert_valid": webhook_signature_verify_assert_valid,
    "WR_csp_reporter_install": csp_reporter_install,
    "WR_csp_reporter_collect": csp_reporter_collect,
    "WR_csp_reporter_assert_no_violations": csp_reporter_assert_no_violations,
    "WR_header_tampering_apply": header_tampering_apply,
    "WR_license_scanner_scan_text": license_scanner_scan_text,
    "WR_license_scanner_scan_file": license_scanner_scan_file,
    "WR_license_scanner_assert_allowed": license_scanner_assert_allowed,
    "WR_pii_scanner_scan_text": pii_scanner_scan_text,
    "WR_pii_scanner_scan_page": pii_scanner_scan_page,
    "WR_pii_scanner_redact_text": pii_scanner_redact_text,
    "WR_pii_scanner_assert_no_pii": pii_scanner_assert_no_pii,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset({
    "WR_tls_cipher_audit_handshake",
    "WR_tls_cipher_audit_assert_host",
})
