"""The ``us`` (month first) and ``fr`` (day first) date patterns must tell an impossible order apart."""
import pytest

from je_web_runner.utils.number_currency_locale.locale import NumberCurrencyLocaleError, assert_date_format


def test_day_first_is_not_a_us_date():
    assert_date_format("12/31/2024", "us")
    with pytest.raises(NumberCurrencyLocaleError):
        assert_date_format("31/12/2024", "us")


def test_month_first_is_not_a_french_date():
    assert_date_format("31/12/2024", "fr")
    with pytest.raises(NumberCurrencyLocaleError):
        assert_date_format("12/31/2024", "fr")


def test_a_date_that_reads_both_ways_passes_both():
    assert_date_format("1/2/24", "us")
    assert_date_format("01/02/2024", "fr")
