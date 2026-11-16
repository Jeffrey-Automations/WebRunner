"""web_locks: the log a real Chromium page produced must satisfy the library's own assertions."""
from je_web_runner.utils.web_locks.locks import (
    LockOutcome, assert_if_available_unavailable, assert_no_deadlock, parse_log,
)

# The log headless Chromium 148 produced for one holder of "cart" and an ifAvailable request that got
# null (times rounded; the second request's mode set to "shared" here to tell the two requests apart).
REAL_LOG = [
    {"id": "65645190", "name": "cart", "outcome": "requested", "mode": "exclusive", "if_available": False,
     "steal": False, "time": 35.7},
    {"id": "65645190", "name": "cart", "outcome": "acquired", "time": 6.3},
    {"id": "72377569", "name": "cart", "outcome": "requested", "mode": "shared", "if_available": True,
     "steal": False, "time": 89.7},
    {"id": "72377569", "name": "cart", "outcome": "unavailable", "time": 0.4},
    {"id": "65645190", "name": "cart", "outcome": "released", "time": 54.4},
]


def test_if_available_request_that_got_null_is_found_in_a_real_log():
    events = parse_log(REAL_LOG)
    event = assert_if_available_unavailable(events, name="cart")
    assert event.outcome is LockOutcome.UNAVAILABLE
    assert event.if_available is True
    assert event.mode == "shared"
    assert_no_deadlock(events)


def test_request_options_do_not_leak_to_another_request():
    events = parse_log(REAL_LOG)
    assert [e.if_available for e in events] == [False, True, False]
    assert [e.outcome.value for e in events] == ["acquired", "unavailable", "released"]
