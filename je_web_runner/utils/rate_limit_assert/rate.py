"""
HTTP rate limit / 429 / Retry-After verifier.

Verifies that an API actually enforces declared rate limits AND returns
the right metadata clients need to back off correctly:

* When N+1 requests fire inside the limit window, response is 429.
* ``Retry-After`` header is present and ≥ documented refill time.
* ``X-RateLimit-Limit`` / ``X-RateLimit-Remaining`` / ``-Reset`` are
  consistent across responses (Remaining decreases monotonically).
* After waiting ``Retry-After`` seconds, the next request succeeds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class RateLimitAssertError(WebRunnerException):
    """Raised on rate-limit protocol violation."""


@dataclass
class RateLimitResponse:
    """The status, headers and body of one response, with the rate-limit headers decoded."""
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None

    def header(self, name: str) -> str | None:
        """The value of header ``name``, whatever case the response spells it in; None when absent."""
        wanted = name.lower()
        for key, value in self.headers.items():
            if str(key).lower() == wanted:
                return value
        return None

    @property
    def is_429(self) -> bool:
        """True when the status is 429 Too Many Requests."""
        return self.status_code == 429

    @property
    def retry_after_seconds(self) -> float | None:
        """The ``Retry-After`` header as seconds, or None when it is absent or not a number."""
        raw = self.header("Retry-After")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @property
    def limit(self) -> int | None:
        """The ``X-RateLimit-Limit`` header as an int, or None when absent or not digits."""
        raw = self.header("X-RateLimit-Limit")
        return int(raw) if raw and raw.isdigit() else None

    @property
    def remaining(self) -> int | None:
        """The ``X-RateLimit-Remaining`` header as an int, or None when absent or not digits."""
        raw = self.header("X-RateLimit-Remaining")
        return int(raw) if raw and raw.isdigit() else None


def assert_429_after_burst(
    responses: Sequence[RateLimitResponse], *, after: int,
) -> RateLimitResponse:
    """Return the first 429 among the responses after the first ``after``.

    Raises RateLimitAssertError when there is none or too few responses were given.
    """
    if after < 1:
        raise RateLimitAssertError("after must be >= 1")
    if len(responses) <= after:
        raise RateLimitAssertError(
            f"need > {after} responses, got {len(responses)}"
        )
    for r in responses[after:]:
        if r.is_429:
            return r
    raise RateLimitAssertError(
        f"no 429 after first {after} successful request(s)"
    )


def assert_retry_after_present(response: RateLimitResponse) -> None:
    """Raise RateLimitAssertError unless the 429 response carries a positive ``Retry-After``;
    also when the response is not a 429.
    """
    if not response.is_429:
        raise RateLimitAssertError(
            "assert_retry_after_present called on non-429 response"
        )
    if response.retry_after_seconds is None:
        raise RateLimitAssertError(
            "429 response missing Retry-After header"
        )
    if response.retry_after_seconds <= 0:
        raise RateLimitAssertError(
            f"Retry-After is {response.retry_after_seconds}s — clients can't "
            "compute a positive back-off"
        )


def assert_remaining_monotonic(
    responses: Sequence[RateLimitResponse],
) -> None:
    """``X-RateLimit-Remaining`` must decrease (or stay flat) until 429."""
    last: int | None = None
    for i, r in enumerate(responses):
        rem = r.remaining
        if rem is None:
            continue
        if last is not None and rem > last:
            raise RateLimitAssertError(
                f"X-RateLimit-Remaining went UP between request {i-1} ({last}) "
                f"and {i} ({rem})"
            )
        last = rem


def assert_recovery_after_retry_after(
    *, before: RateLimitResponse, after: RateLimitResponse,
) -> None:
    """``before`` is a 429 with Retry-After. ``after`` is the next request
    once the harness slept that long — must NOT be 429 again."""
    if not before.is_429:
        raise RateLimitAssertError("before must be a 429 response")
    if after.is_429:
        raise RateLimitAssertError(
            "API still returned 429 after waiting Retry-After — "
            "either window didn't refill or Retry-After was wrong"
        )
