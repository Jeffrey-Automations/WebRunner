"""The audit action of a story plan must carry the axe source ``WR_a11y_run_audit`` cannot run without."""
import inspect

import pytest

from je_web_runner.utils.accessibility.axe_audit import selenium_run_audit
from je_web_runner.utils.storybook.discovery import StorybookError, StorybookStory, plan_actions_for_stories

STORIES = [StorybookStory(id="button--primary", title="Button", name="Primary")]
BASE = "http://localhost:6006"


def test_the_audit_action_has_every_required_argument():
    plan = plan_actions_for_stories(STORIES, BASE, axe_source="${axe}")
    audit = next(action for action in plan if action[0] == "WR_a11y_run_audit")
    required = [
        name for name, parameter in inspect.signature(selenium_run_audit).parameters.items()
        if parameter.default is inspect.Parameter.empty
    ]
    assert required == ["axe_source"]
    assert audit == ["WR_a11y_run_audit", {"axe_source": "${axe}"}]


def test_an_audit_without_the_axe_source_is_refused():
    with pytest.raises(StorybookError, match="axe_source"):
        plan_actions_for_stories(STORIES, BASE)


def test_a_plan_without_the_audit_needs_no_axe_source():
    assert plan_actions_for_stories(STORIES, BASE, run_a11y=False) == [
        ["WR_to_url", {"url": f"{BASE}/iframe.html?id=button--primary&viewMode=story"}],
        ["WR_get_screenshot_as_png"],
    ]
