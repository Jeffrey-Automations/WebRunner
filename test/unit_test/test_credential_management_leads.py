"""credential_management: the shim's real log passes the checks a correct page should pass."""
import pytest

from je_web_runner.utils.credential_management.credentials import (
    INSTALL_SCRIPT, CmLog, CredentialManagementError, assert_get_requested_mediation, assert_no_password_in_clear,
    assert_stored, parse_log,
)

# What the shim returns in Chromium 148 after the page stored {id: 'alice', type: 'password', password: ...}.
REAL_LOG = {
    "stored": [{"id": "alice", "type": "password", "hasPassword": True, "provider": ""}],
    "gets": [],
    "preventCount": 0,
}


def test_a_legitimate_password_store_is_not_a_leak():
    log = parse_log(REAL_LOG)
    stored = assert_stored(log, credential_id="alice")
    assert stored.has_password is True
    assert stored.password == ""
    assert_no_password_in_clear(log)


def test_a_log_that_does_carry_a_plaintext_password_is_still_refused():
    log = parse_log({"stored": [{"id": "alice", "password": "hunter2"}]})
    assert log.stored[0].has_password is True
    with pytest.raises(CredentialManagementError, match="plaintext password"):
        assert_no_password_in_clear(log)


def test_the_shim_does_not_copy_the_password_into_its_log():
    assert "password: cred.password" not in INSTALL_SCRIPT
    assert "hasPassword" in INSTALL_SCRIPT


def test_mediation_check_needs_a_get_call():
    with pytest.raises(CredentialManagementError, match="never called"):
        assert_get_requested_mediation(CmLog(), mediation="required")
    with pytest.raises(CredentialManagementError, match="never called"):
        assert_get_requested_mediation(parse_log(REAL_LOG), mediation="required")
    assert_get_requested_mediation(CmLog(gets=[{"mediation": "required"}]), mediation="required")
