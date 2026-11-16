"""Rate-limit headers are found whatever case the server or client library gives them."""
import pytest

from je_web_runner.utils.rate_limit_assert.rate import (
    RateLimitAssertError,
    RateLimitResponse,
    assert_remaining_monotonic,
    assert_retry_after_present,
)


@pytest.mark.parametrize("headers", [
    {"X-Ratelimit-Limit": "10", "X-Ratelimit-Remaining": "3", "RETRY-AFTER": "2"},   # Go canonical form
    {"X-RATELIMIT-LIMIT": "10", "x-RateLimit-remaining": "3", "Retry-after": "2"},
    {"X-RateLimit-Limit": "10", "X-RateLimit-Remaining": "3", "Retry-After": "2"},
    {"x-ratelimit-limit": "10", "x-ratelimit-remaining": "3", "retry-after": "2"},
])
def test_headers_are_read_in_any_case(headers):
    response = RateLimitResponse(status_code=429, headers=headers)
    assert (response.limit, response.remaining, response.retry_after_seconds) == (10, 3, 2.0)
    assert_retry_after_present(response)


def test_remaining_that_goes_up_is_seen_in_any_case():
    responses = [
        RateLimitResponse(200, {"X-Ratelimit-Remaining": "2"}),
        RateLimitResponse(200, {"X-Ratelimit-Remaining": "5"}),
    ]
    with pytest.raises(RateLimitAssertError):
        assert_remaining_monotonic(responses)


def test_absent_headers_are_none():
    response = RateLimitResponse(status_code=200, headers={"Content-Type": "text/plain"})
    assert (response.limit, response.remaining, response.retry_after_seconds) == (None, None, None)
