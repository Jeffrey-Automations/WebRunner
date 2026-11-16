"""Two different values that redact to the same text are two findings; a repeated value is one."""
from je_web_runner.utils.pii_in_screenshot.scanner import scan_text_only


def test_different_values_with_the_same_redaction_are_both_reported():
    findings = scan_text_only("contact alice@example.com or alan@other.com")
    emails = [finding for finding in findings if finding.rule == "email"]
    assert len(emails) == 2
    assert {finding.redacted_match for finding in emails} == {"al…om"}


def test_a_repeated_value_is_reported_once():
    findings = scan_text_only("alice@example.com wrote to alice@example.com")
    assert len([finding for finding in findings if finding.rule == "email"]) == 1
