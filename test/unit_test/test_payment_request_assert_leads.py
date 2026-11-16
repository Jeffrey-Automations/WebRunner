"""payment_request_assert: an assertion about PaymentRequests does not pass when there is nothing to check."""
import pytest

from je_web_runner.utils.payment_request_assert.payment import (
    PaymentLog, PaymentRequestAssertError, assert_shipping_required, assert_total_currency, parse_log,
)

# Harvested from the shim in Chromium 148 (``options`` was not passed, so it came back null).
REAL_LOG = {
    "constructed": [{
        "methodData": [{"supportedMethods": "basic-card"}],
        "details": {"total": {"label": "t", "amount": {"currency": "USD", "value": "1.00"}}},
        "options": None,
    }],
    "completed": [{"status": "success"}],
}


def test_shipping_required_fails_when_no_request_was_constructed():
    with pytest.raises(PaymentRequestAssertError, match="never constructed"):
        assert_shipping_required(PaymentLog())


def test_shipping_required_on_real_data():
    with pytest.raises(PaymentRequestAssertError, match="requestShipping"):
        assert_shipping_required(parse_log(REAL_LOG))
    with_shipping = {**REAL_LOG, "constructed": [{**REAL_LOG["constructed"][0], "options": {"requestShipping": True}}]}
    assert_shipping_required(parse_log(with_shipping))


@pytest.mark.parametrize("total", [
    {"label": "t", "amount": "1.00 USD"}, {"label": "t", "amount": ["USD"]}, "USD 1.00", {"label": "t"}, None,
])
def test_total_currency_fails_when_the_total_has_no_readable_amount(total):
    log = parse_log({"constructed": [{"methodData": [], "details": {"total": total}}]})
    with pytest.raises(PaymentRequestAssertError):
        assert_total_currency(log, currency="USD")


def test_total_currency_on_real_data():
    assert_total_currency(parse_log(REAL_LOG), currency="USD")
    with pytest.raises(PaymentRequestAssertError, match="!= 'EUR'"):
        assert_total_currency(parse_log(REAL_LOG), currency="EUR")
