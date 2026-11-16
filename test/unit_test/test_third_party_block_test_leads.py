"""third_party_block_test: a vendor that was never run is reported as not run, not as having broken the flow."""
import pytest

from je_web_runner.utils.third_party_block_test.block import (
    ThirdPartyBlockError, Vendor, assert_resilient_to, run_block_matrix,
)


def test_a_vendor_missing_from_the_report_is_named_as_not_run():
    report = run_block_matrix([Vendor(name="hotjar", patterns=("*://*.hotjar.com/*",))], lambda patterns: None,
                              lambda: None)
    with pytest.raises(ThirdPartyBlockError, match="not in the report") as caught:
        assert_resilient_to(report, vendors=["hotjar", "sentry"])
    assert "sentry" in str(caught.value)
    assert "broke" not in str(caught.value)


def test_a_broken_vendor_is_still_reported_as_broken():
    def flow():
        raise RuntimeError("checkout failed")

    report = run_block_matrix([Vendor(name="hotjar", patterns=("*://*.hotjar.com/*",))], lambda patterns: None, flow)
    with pytest.raises(ThirdPartyBlockError, match="flow broke when these vendors were blocked"):
        assert_resilient_to(report, vendors=["hotjar"])
