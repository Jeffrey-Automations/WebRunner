"""bundle_diff_pr: bad input raises the module's own error."""
import pytest

from je_web_runner.utils.bundle_diff_pr.diff import BundleDiffPrError, assert_under_max_growth, diff_hars

GOOD = {"log": {"entries": []}}


@pytest.mark.parametrize("bad", ["{not json", {"log": {"entries": "nope"}}, 12])
def test_diff_hars_reports_bad_har_as_its_own_error(bad):
    with pytest.raises(BundleDiffPrError):
        diff_hars(bad, GOOD)
    with pytest.raises(BundleDiffPrError):
        diff_hars(GOOD, bad)


def test_assert_under_max_growth_checks_what_it_is_given():
    with pytest.raises(BundleDiffPrError, match="expects BundleDiff"):
        assert_under_max_growth({"total_delta_bytes": 5}, max_growth_bytes=10)
    assert_under_max_growth(diff_hars(GOOD, GOOD), max_growth_bytes=0)
