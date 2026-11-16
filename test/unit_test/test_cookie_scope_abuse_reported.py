"""Session cookies whose names carry no separator (``sessionid``, ``JSESSIONID``) are session-like."""
import pytest

from je_web_runner.utils.cookie_scope_abuse.scope import audit_cookie


@pytest.mark.parametrize("name", ["sessionid", "JSESSIONID", "PHPSESSID", "connect.sid", "ASP.NET_SessionId"])
def test_framework_session_names_are_audited_whatever_the_value(name):
    findings = audit_cookie({"name": name, "value": "short"}, page_host="app.example.com")
    assert "session-no-httponly" in {finding.rule for finding in findings}


@pytest.mark.parametrize("name", ["lang", "outside", "author", "consider"])
def test_names_that_only_contain_the_letters_are_not(name):
    assert audit_cookie({"name": name, "value": "en"}, page_host="app.example.com") == []
