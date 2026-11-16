"""Mailpit messages without a recipient, and what IMAP cleanup logs."""
import logging

import pytest

from je_web_runner.utils.otp_interceptor.interceptor import ImapProvider, MailpitProvider


@pytest.mark.parametrize("to_field", [[], None, [{"Name": "no address"}], [{"Address": None}]])
def test_mailpit_message_without_recipient_has_an_empty_recipient(to_field):
    payload = {"messages": [{"ID": "m1", "To": to_field, "Subject": "code", "Text": "Token 224488"}]}
    provider = MailpitProvider("http://mailpit", http_fetcher=lambda _url: payload)  # noqa: S5332
    messages = provider.fetch_messages()
    assert messages[0].recipient == ""
    assert provider.fetch_messages(recipient="None") == []


def test_mailpit_recipient_is_still_read():
    payload = {"messages": [{"ID": "m1", "To": [{"Address": "b@x"}], "Text": "1234"}, {"ID": "m2", "To": ["c@x"]}]}
    provider = MailpitProvider("http://mailpit", http_fetcher=lambda _url: payload)  # noqa: S5332
    assert sorted(message.recipient for message in provider.fetch_messages()) == ["b@x", "c@x"]


class _FailedLogin:
    """An IMAP connection whose login fails: ``close`` is then illegal (no mailbox was selected)."""

    def __init__(self, logout_error=None):
        self.logout_error = logout_error
        self.calls = []

    def login(self, _user, _password):
        raise PermissionError("authentication failed")

    def close(self):
        self.calls.append("close")
        raise RuntimeError("command CLOSE illegal in state NONAUTH, only allowed in states SELECTED")

    def logout(self):
        self.calls.append("logout")
        if self.logout_error:
            raise self.logout_error


def _warnings(caplog):
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]


def test_failed_login_does_not_warn_about_the_close_that_cannot_work(caplog):
    connection = _FailedLogin()
    provider = ImapProvider("imap.test", username="u", password="p", connector=lambda _host, _port: connection)
    with caplog.at_level(logging.DEBUG, logger="WEBRunner"):
        with pytest.raises(PermissionError):
            provider.fetch_messages()
    assert connection.calls == ["close", "logout"]
    assert _warnings(caplog) == []
    assert any("close" in record.getMessage() for record in caplog.records)


def test_a_failing_logout_is_still_warned_about(caplog):
    connection = _FailedLogin(logout_error=OSError("connection reset"))
    provider = ImapProvider("imap.test", username="u", password="p", connector=lambda _host, _port: connection)
    with caplog.at_level(logging.DEBUG, logger="WEBRunner"):
        with pytest.raises(PermissionError):
            provider.fetch_messages()
    assert len(_warnings(caplog)) == 1
    assert "logout" in _warnings(caplog)[0]
