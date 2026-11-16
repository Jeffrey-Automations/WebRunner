"""Unknown cookies are listed from both snapshots, each once."""
from je_web_runner.utils.consent_audit.audit import Cookie, audit_consent


def test_an_unknown_cookie_set_after_consent_is_listed():
    before = [Cookie(name="mystery_a", domain="app.example")]
    after = [Cookie(name="mystery_a", domain="app.example"), Cookie(name="mystery_b", domain="app.example")]
    report = audit_consent(before, after)
    assert [c.cookie.name for c in report.unknown_cookies] == ["mystery_a", "mystery_b"]
    assert report.passed() is True
