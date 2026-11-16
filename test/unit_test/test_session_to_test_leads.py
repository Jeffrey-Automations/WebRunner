"""session_to_test emits real actions: lists naming registered commands with arguments they accept."""
import inspect
import json

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.session_to_test.converter import (
    convert_generic_events,
    convert_rrweb_events,
    write_actions_json,
)

GENERIC_EVENTS = [
    {"kind": "navigate", "url": "https://shop.example/login"},
    {"kind": "input", "target": "#user", "value": "alice"},
    {"kind": "click", "target": {"by": "id", "value": "submit"}},
    {"kind": "submit", "target": "#form"},
    {"kind": "submit"},
    {"kind": "wait", "seconds": 1.5},
]
RRWEB_EVENTS = [
    {"type": 4, "timestamp": 0, "data": {"href": "https://shop.example/"}},
    {"type": 3, "timestamp": 1, "data": {"source": 2, "type": 2, "id": 7}},
    {"type": 3, "timestamp": 2, "data": {"source": 2, "type": 4, "id": 8}},
    {"type": 3, "timestamp": 3, "data": {"source": 5, "id": 9, "text": "hello"}},
    {"type": 3, "timestamp": 4, "data": {"source": 3, "x": 0, "y": 500}},
]


def _assert_runnable(actions):
    """Every action is ``[name]`` or ``[name, {kwargs}]``, the name is registered and the kwargs bind."""
    for action in actions:
        assert isinstance(action, list), action
        assert action[0] in executor.event_dict, action[0]
        kwargs = action[1] if len(action) > 1 else {}
        assert isinstance(kwargs, dict), action
        inspect.signature(executor.event_dict[action[0]]).bind(**kwargs)


def test_generic_events_become_registered_list_actions():
    result = convert_generic_events(GENERIC_EVENTS)
    _assert_runnable(result.actions)
    assert result.actions == [
        ["WR_to_url", {"url": "https://shop.example/login"}],
        ["WR_find_element_by", {"selector": "#user", "by": "css selector"}],
        ["WR_input_to_element", {"input_value": "alice"}],
        ["WR_find_element_by", {"selector": "submit", "by": "id"}],
        ["WR_element_click"],
        ["WR_find_element_by", {"selector": "#form", "by": "css selector"}],
        ["WR_element_submit"],
        ["WR_note", {"text": "submit form (no target)"}],
        ["WR_implicitly_wait", {"time_to_wait": 1.5}],
    ]


def test_rrweb_events_become_registered_list_actions():
    result = convert_rrweb_events(RRWEB_EVENTS)
    _assert_runnable(result.actions)
    assert result.actions == [
        ["WR_to_url", {"url": "https://shop.example/"}],
        ["WR_find_element_by", {"selector": '[data-rrweb-id="7"]', "by": "css selector"}],
        ["WR_element_click"],
        ["WR_note", {"text": 'double click [data-rrweb-id="8"]'}],
        ["WR_find_element_by", {"selector": '[data-rrweb-id="9"]', "by": "css selector"}],
        ["WR_input_to_element", {"input_value": "hello"}],
        ["WR_note", {"text": "scroll to 0,500"}],
    ]


def test_stats_count_the_actions_and_the_notes():
    generic = convert_generic_events(GENERIC_EVENTS).stats
    assert (generic.input_events, generic.actions_emitted, generic.comment_actions) == (6, 9, 1)
    rrweb = convert_rrweb_events(RRWEB_EVENTS).stats
    assert (rrweb.input_events, rrweb.actions_emitted, rrweb.comment_actions) == (5, 7, 2)


def test_written_file_is_an_action_list(tmp_path):
    result = convert_generic_events(GENERIC_EVENTS)
    written = json.loads(write_actions_json(result, tmp_path / "out.json").read_text(encoding="utf-8"))
    assert written == result.actions
    _assert_runnable(written)
