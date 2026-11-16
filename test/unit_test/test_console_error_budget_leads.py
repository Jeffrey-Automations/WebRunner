"""console_error_budget: the URL of a CDP console event is in its first call frame."""
from je_web_runner.utils.console_error_budget.budget import from_cdp_console_events

# A Runtime.consoleAPICalled event as Chromium 148 sent it (script URL filled in).
REAL_EVENT = {
    "type": "error",
    "args": [{"type": "string", "value": "boom"}, {"type": "number", "value": 42, "description": "42"}],
    "executionContextId": 3,
    "timestamp": 1794800597843.772,
    "stackTrace": {"callFrames": [
        {"functionName": "shout", "scriptId": "12", "url": "https://shop.test/app.js", "lineNumber": 7,
         "columnNumber": 27},
        {"functionName": "", "scriptId": "12", "url": "https://shop.test/boot.js", "lineNumber": 1,
         "columnNumber": 0},
    ]},
}


def test_url_and_line_come_from_the_top_call_frame():
    message = from_cdp_console_events([REAL_EVENT])[0]
    assert message.text == "boom 42"
    assert message.url == "https://shop.test/app.js"
    assert message.line == 7


def test_an_event_without_a_stack_has_no_url():
    message = from_cdp_console_events([{"type": "log", "args": []}])[0]
    assert message.url is None
    assert message.line is None
    for odd in ({"callFrames": []}, {"callFrames": "x"}, "nope"):
        assert from_cdp_console_events([{"type": "log", "stackTrace": odd}])[0].url is None
