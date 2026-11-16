"""webauthn_mock: a credential built twice for the same user is the same credential."""
import base64

from je_web_runner.utils.webauthn_mock.mock import build_credential


def test_build_credential_is_deterministic_signature_included():
    first = build_credential("alice", "example.test")
    second = build_credential("alice", "example.test")
    assert first == second
    assert first.signature_b64 == second.signature_b64


def test_signature_is_64_bytes_and_differs_per_user():
    alice = build_credential("alice", "example.test")
    bob = build_credential("bob", "example.test")
    assert alice.signature_b64 != bob.signature_b64
    padded = alice.signature_b64 + "=" * (-len(alice.signature_b64) % 4)
    assert len(base64.urlsafe_b64decode(padded)) == 64
