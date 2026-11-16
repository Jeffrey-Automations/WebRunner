"""action_refactor_suggester reads real action lists (``["WR_name", {...}]``), not only step objects."""
from je_web_runner.utils.action_refactor_suggester.suggest import analyze

ACTIONS = [
    ["WR_to_url", {"url": "https://shop.example/"}],
    ["WR_find_element_by", {"selector": "//div[3]/span[2]", "by": "xpath"}],
    ["WR_element_click"],
    ["WR_sleep", {"seconds": 3}],
    ["WR_find_element_by", {"selector": "#buy"}],
    ["WR_element_click"],
    ["WR_wait_for_element", {"selector": "#buy"}],
    ["WR_find_element_by", {"selector": "#buy"}],
    ["WR_element_click"],
    ["WR_assert_var", {"name": "banner", "expected": "Thank you for your order, see you soon"}],
]


def _by_rule(actions):
    return {suggestion.rule: suggestion.step_indexes for suggestion in analyze(actions)}


def test_real_actions_get_every_rule():
    found = _by_rule(ACTIONS)
    assert found["no-hard-sleep"] == [3]
    assert found["no-positional-xpath"] == [1]
    assert found["prefer-translation-key"] == [9]
    assert found["extract-helper"] == [5]
    assert "extract-duplicated-locator" in found


def test_a_smell_inside_a_block_is_reported_at_the_block():
    actions = [
        ["WR_to_url", {"url": "https://shop.example/"}],
        ["WR_if", {"condition": {"var": "slow"}, "then": [["WR_sleep", {"seconds": 5}]]}],
    ]
    assert _by_rule(actions) == {"no-hard-sleep": [1]}


def test_an_object_document_is_read():
    document = {"meta": {}, "webdriver_wrapper": [["WR_pw_wait_for_timeout", {"timeout_ms": 500}]]}
    assert _by_rule(document) == {"no-hard-sleep": [0]}


def test_step_objects_still_work():
    steps = [{"action_name": "click"}, {"action_name": "wait", "value": 3}, {"action_name": "click"}]
    assert _by_rule(steps) == {"no-hard-sleep": [1], "extract-helper": [0]}
