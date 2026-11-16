"""Hostile and real-world inputs of the webhook verifier: non-ASCII signatures, header case, epoch 0."""
import time

import pytest

from je_web_runner.utils.webhook_signature_verify.verify import (
    Scheme,
    WebhookSignatureVerifyError,
    sign_github,
    sign_slack,
    sign_stripe,
    verify,
)

BODY = b'{"event": "ping"}'
SECRET = "s3cret"


@pytest.mark.parametrize("scheme, headers", [
    (Scheme.GITHUB, {"X-Hub-Signature-256": "sha256=éé"}),
    (Scheme.GENERIC, {"X-Signature": "簽名"}),
    (Scheme.STRIPE, {"Stripe-Signature": f"t={int(time.time())},v1=é"}),
    (Scheme.SLACK, {"X-Slack-Signature": "v0=é", "X-Slack-Request-Timestamp": str(int(time.time()))}),
])
def test_a_non_ascii_signature_is_rejected_not_a_crash(scheme, headers):
    assert verify(scheme, headers, BODY, SECRET).ok is False


def test_header_names_are_matched_without_case():
    now = int(time.time())
    assert verify(Scheme.GITHUB, {"x-hub-signature-256": sign_github(BODY, SECRET)}, BODY, SECRET).ok
    assert verify(Scheme.STRIPE, {"stripe-signature": sign_stripe(BODY, SECRET, now)}, BODY, SECRET).ok
    assert verify(Scheme.GENERIC, {"X-SIGNATURE": sign_github(BODY, SECRET)[len("sha256="):]}, BODY, SECRET).ok
    slack = {"x-slack-signature": sign_slack(BODY, SECRET, now), "x-slack-request-timestamp": str(now)}
    assert verify(Scheme.SLACK, slack, BODY, SECRET).ok


def test_a_missing_header_is_still_reported():
    with pytest.raises(WebhookSignatureVerifyError, match="missing X-Hub-Signature-256"):
        verify(Scheme.GITHUB, {"X-Other": "1"}, BODY, SECRET)


def test_timestamp_zero_is_signed_as_zero():
    assert sign_stripe(BODY, SECRET, ts=0).startswith("t=0,")
    assert sign_slack(BODY, SECRET, ts=0) != sign_slack(BODY, SECRET, ts=int(time.time()))
    with pytest.raises(WebhookSignatureVerifyError, match="outside tolerance"):
        verify(Scheme.STRIPE, {"Stripe-Signature": sign_stripe(BODY, SECRET, ts=0)}, BODY, SECRET)
