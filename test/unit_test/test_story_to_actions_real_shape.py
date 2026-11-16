"""story_to_actions validates and returns actions the executor can run."""
import inspect
import json
from pathlib import Path

import pytest

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.json.json_validator import validate_action_json
from je_web_runner.utils.linter.action_linter import lint_action
from je_web_runner.utils.story_to_actions import generator
from je_web_runner.utils.story_to_actions.generator import (
    ALLOWED_ACTIONS,
    StoryPrompt,
    StoryToActionsError,
    build_prompt_text,
    generate_actions,
    validate_actions,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

LOGIN = [
    ["WR_to_url", {"url": "https://shop.test/login"}],
    ["WR_find_element_by", {"selector": "#user", "by": "css selector"}],
    ["WR_element_clear"],
    ["WR_element_input", {"input_value": "alice"}],
    ["WR_find_element_by", {"selector": "submit", "by": "id"}],
    ["WR_element_click"],
    ["WR_wait_for_element", {"selector": "#welcome", "timeout": 5, "state": "visible"}],
    ["WR_element_assert", {"check_dict": {"text": "Welcome alice"}}],
    ["WR_assert_title", {"value": "Shop"}],
    ["WR_implicitly_wait", {"time_to_wait": 2}],
    ["WR_note", {"text": "logged in"}],
]


class _Client:
    def __init__(self, reply):
        self.reply = reply

    def generate(self, _prompt_text):
        return self.reply


def test_every_allowed_command_is_registered_with_those_arguments():
    for name, arguments in generator._COMMANDS.items():  # pylint: disable=protected-access
        assert name in executor.event_dict, name
        signature = inspect.signature(executor.event_dict[name])
        signature.bind(**{argument.name: None for argument in arguments if argument.required})
        signature.bind(**{argument.name: None for argument in arguments})
        assert [argument.name for argument in arguments] == list(signature.parameters)[:len(arguments)]


def test_the_repository_smoke_file_is_a_valid_story_result():
    smoke = json.loads((EXAMPLES / "ci" / "smoke" / "smoke.json").read_text(encoding="utf-8"))
    validate_actions(smoke["webdriver_wrapper"])


def test_generated_actions_are_what_the_executor_runs():
    reply = "```json\n" + json.dumps(LOGIN[1:]) + "\n```"
    actions = generate_actions(StoryPrompt(story="log in", start_url="https://shop.test/login"), _Client(reply))
    assert actions == LOGIN
    assert validate_action_json(actions) is True
    assert {finding["rule"] for finding in lint_action(actions)} <= {"hardcoded_url"}


def test_start_url_is_not_repeated_in_either_argument_form():
    for first in (["WR_to_url", {"url": "https://x.test"}], ["WR_to_url", ["https://x.test"]]):
        actions = generate_actions(
            StoryPrompt(story="open", start_url="https://x.test"), _Client(json.dumps([first])))
        assert actions == [first]


def test_the_object_shape_the_executor_cannot_run_is_rejected():
    with pytest.raises(StoryToActionsError, match="WR_command"):
        validate_actions([{"WR_to_url": ["https://x.test"]}])


@pytest.mark.parametrize("action", [
    ["WR_click_element", ["id", "submit"]],          # registered, but takes no locator: not a story command
    ["WR_assert_element_text", ["id", "status", "OK"]],  # not registered
    ["WR_execute_script", {"script": "alert(1)"}],
    ["WR_to_url"],
    ["WR_to_url", {"url": ""}],
    ["WR_to_url", {"url": "https://x.test", "extra": 1}],
    ["WR_to_url", ["https://x.test", "extra"]],
    ["WR_to_url", "https://x.test"],
    ["WR_find_element_by", {"selector": "#x", "by": "jquery"}],
    ["WR_wait_for_element", {"selector": "#x", "state": "gone"}],
    ["WR_wait_for_element", {"selector": "#x", "timeout": True}],
    ["WR_implicitly_wait", {"time_to_wait": -1}],
    ["WR_element_input", {"input_value": 5}],
    ["WR_element_assert", {"check_dict": {}}],
    ["WR_element_click", {"selector": "#x"}],
    [],
    "WR_element_click",
])
def test_invalid_actions_are_rejected(action):
    with pytest.raises(StoryToActionsError):
        validate_actions([action])


def test_the_prompt_asks_for_the_executor_shape():
    text = build_prompt_text(StoryPrompt(story="log in"))
    assert '["WR_command", {"argument": value}]' in text
    assert "WR_find_element_by(selector, by?)" in text
    assert "WR_element_click()" in text
    assert all(name in text for name in ALLOWED_ACTIONS)
