"""FCM needs exactly one target; a long number is not PII unless it is shaped like it."""
import pytest

from je_web_runner.utils.push_delivery.delivery import PushDeliveryError, assert_apns_payload, assert_fcm_payload


def _fcm(body="Your order is ready", **targets):
    return {"message": {**(targets or {"token": "abc"}), "notification": {"title": "Shop", "body": body}}}


@pytest.mark.parametrize("targets", [
    {"token": "abc", "topic": "news"},
    {"topic": "news", "condition": "'a' in topics"},
    {"token": "abc", "topic": "news", "condition": "'a' in topics"},
])
def test_two_targets_are_rejected(targets):
    with pytest.raises(PushDeliveryError, match="exactly one"):
        assert_fcm_payload(_fcm(**targets))


@pytest.mark.parametrize("targets", [{"token": "abc"}, {"topic": "news"}, {"condition": "'a' in topics"}])
def test_one_target_passes(targets):
    assert_fcm_payload(_fcm(**targets))


@pytest.mark.parametrize("body", [
    "Order 123456789 has shipped",               # nine digits, not written as an SSN
    "Tracking 1Z9999999999999999 is on its way",
    "Reference 1700000000000 received",          # thirteen digits that fail the card checksum
    "Call 0800 123 4567 8901 for help",          # sixteen digits that fail the card checksum
])
def test_a_long_number_is_not_pii(body):
    assert_fcm_payload(_fcm(body=body))
    assert_apns_payload({"aps": {"alert": {"title": "Shop", "body": body}}})


@pytest.mark.parametrize("body", [
    "SSN 123-45-6789 on file",
    "Your card 4111 1111 1111 1111 expired",
    "Card 4111-1111-1111-1111",
    "Card 5500005555555559 declined",
    "Write to user@example.com",
])
def test_pii_shaped_values_are_still_rejected(body):
    with pytest.raises(PushDeliveryError, match="PII"):
        assert_fcm_payload(_fcm(body=body))
    with pytest.raises(PushDeliveryError, match="PII"):
        assert_apns_payload({"aps": {"alert": {"title": "Shop", "body": body}}})
