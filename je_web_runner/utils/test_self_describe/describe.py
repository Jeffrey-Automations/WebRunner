"""
Reverse-engineer a human description of what a JSON action script does.

Given a list of WebRunner action steps, emit a Gherkin-ish ``Given / When /
Then`` paragraph. Useful for:

* PR reviewers without selenium knowledge.
* JIRA / Confluence "what this test covers" sections.
* Sanity-check that a freshly recorded test is actually doing what its
  filename claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.flow.structure import nested_actions


class SelfDescribeError(WebRunnerException):
    """Raised on malformed action input."""


# action verb → category. The verb is the command name without its ``WR_`` (and ``pw_``) prefix.
_NAVIGATION = {"to_url", "open", "navigate", "back", "forward", "refresh"}
_INPUT = {"input_to_element", "element_input", "send_keys", "type", "set_value"}
_CLICK = {"click_element", "element_click", "click", "double_click", "right_click",
          "left_click", "left_double_click"}
_WAIT = {"wait", "implicit_wait", "implicitly_wait", "explicit_wait", "explict_wait", "wait_visible",
         "wait_clickable", "wait_for_element", "sleep"}
_ASSERT = {"assert_text", "assert_visible", "assert_value", "assert_url", "assert_title", "assert_var",
           "element_assert", "element_check_current_web_element"}
_SCROLL = {"scroll_to_element", "scroll_to", "scroll"}
_FIND = {"find_element_by", "find_element"}

# Commands that act on the element the last find made current.
_ON_CURRENT_ELEMENT = {"click_element", "input_to_element"}
_LOCATOR_KEYS = ("element_name", "test_object", "locator", "by_value", "selector", "var")
_WAIT_KEYS = ("timeout", "value", "seconds", "time_to_wait", "wait_time")

# Parameter names of the positional form ``["WR_x", [arguments]]``.
_POSITIONAL = {
    "to_url": ("url",),
    "find_element_by": ("selector", "by"),
    "find_element": ("element_name",),
    "wait_for_element": ("selector", "by", "timeout"),
    "input_to_element": ("input_value",),
    "element_input": ("input_value",),
    "implicitly_wait": ("time_to_wait",),
    "explicit_wait": ("wait_time",),
    "sleep": ("seconds",),
    "assert_title": ("value",),
    "element_assert": ("check_dict",),
    "left_click": ("element_name",),
    "left_double_click": ("element_name",),
    "right_click": ("element_name",),
}


@dataclass
class StepSummary:
    """One action rendered as a sentence, with the Gherkin phase it belongs to."""
    phase: str          # "Given" | "When" | "Then"
    sentence: str       # natural-language sentence


_STEP_KINDS = (
    ("navigation", _NAVIGATION),
    ("input", _INPUT),
    ("click", _CLICK),
    ("wait", _WAIT),
    ("assert", _ASSERT),
    ("scroll", _SCROLL),
    ("find", _FIND),
)


def _step_name(action: dict[str, Any]) -> str:
    return str(action.get("action_name") or action.get("function") or "").lower()


def _step_kind(action: dict[str, Any]) -> str:
    name = _step_name(action)
    for kind, names in _STEP_KINDS:
        if name in names:
            return kind
    return "other"


def _locator(action: dict[str, Any]) -> str:
    for key in _LOCATOR_KEYS:
        if action.get(key):
            return str(action[key])
    return ""


def _locator_phrase(action: dict[str, Any]) -> str:
    target = _locator(action)
    if not target:
        return "an element"
    return f'"{target}"'


def _navigation_sentence(name: str, action: dict[str, Any]) -> StepSummary:
    url = action.get("url") or action.get("value") or ""
    if url:
        return StepSummary("Given", f"the user opens {url}")
    if name in ("back", "forward", "refresh"):
        return StepSummary("When", f"the user presses {name} in the browser")
    return StepSummary("Given", "the user opens the application")


def _wait_sentence(action: dict[str, Any]) -> StepSummary:
    seconds = next((action[key] for key in _WAIT_KEYS if action.get(key)), "")
    target = f" for {_locator_phrase(action)}" if _locator(action) else ""
    return StepSummary(
        "When",
        f"the user waits{target}" + (f" up to {seconds}s" if seconds else ""),
    )


def _assert_sentence(action: dict[str, Any]) -> StepSummary:
    subject = "the page title" if _step_name(action) == "assert_title" else _locator_phrase(action)
    expected = action.get("expected") or action.get("value") or ""
    checks = action.get("check_dict")
    if not expected and isinstance(checks, dict):
        expected = ", ".join(f"{key}={value}" for key, value in checks.items())
    return StepSummary("Then", f'{subject} should be / contain "{expected}"')


_SIMPLE_TEMPLATES = {
    "input": lambda a: StepSummary(
        "When",
        f'the user types "{a.get("input_value") or a.get("value") or ""}"'
        f' into {_locator_phrase(a)}',
    ),
    "click": lambda a: StepSummary(
        "When", f"the user clicks {_locator_phrase(a)}",
    ),
    "wait": _wait_sentence,
    "assert": _assert_sentence,
    "scroll": lambda a: StepSummary(
        "When", f"the user scrolls to {_locator_phrase(a)}",
    ),
    "find": lambda a: StepSummary(
        "When", f"the user locates {_locator_phrase(a)}",
    ),
}


def _sentence_for(action: dict[str, Any]) -> StepSummary:
    kind = _step_kind(action)
    name = _step_name(action)
    if kind == "navigation":
        return _navigation_sentence(name, action)
    template = _SIMPLE_TEMPLATES.get(kind)
    if template:
        return template(action)
    return StepSummary("When", f"the user performs {name or 'a step'}")


def _step_from_list(action: list[Any], label: str) -> dict[str, Any]:
    """An ``["WR_x", ...]`` action as ``{"action_name": "x", argument: value, ...}``."""
    if not action or not isinstance(action[0], str) or len(action) > 3:
        raise SelfDescribeError(f"{label} must be [command, arguments], got {action!r}")
    name = action[0].removeprefix("WR_").removeprefix("pw_")
    step: dict[str, Any] = {}
    for part in action[1:]:
        if isinstance(part, dict):
            step.update(part)
        elif isinstance(part, list):
            step.update(zip(_POSITIONAL.get(name, ()), part))
        else:
            raise SelfDescribeError(f"{label} ({action[0]}) arguments must be a list or an object")
    step["action_name"] = name
    return step


def _steps(actions: list[Any] | tuple[Any, ...], prefix: str = "action") -> Iterator[dict[str, Any]]:
    """Every action as a step dict, each block command followed by the actions it holds."""
    for index, action in enumerate(actions):
        label = f"{prefix} #{index}"
        if isinstance(action, dict):
            yield action
        elif isinstance(action, list):
            yield _step_from_list(action, label)
            yield from _steps([inner for _where, inner in nested_actions(action, "")], f"{label} nested")
        else:
            raise SelfDescribeError(f"{label} is not an action")


def _acts_on_current_element(step: dict[str, Any]) -> bool:
    name = _step_name(step)
    return name.startswith("element_") or name in _ON_CURRENT_ELEMENT


def summarise(actions: Any) -> list[StepSummary]:
    """Turn each action into a ``StepSummary``, in order.

    ``actions`` is a list of ``["WR_command", {arguments}]`` actions as the executor runs them, or
    the object form of an action file (the list under ``webdriver_wrapper``). The actions inside a
    block command (``WR_if``, ``WR_for_each`` ...) follow the block. A command that acts on the
    current element is described with the element the last find located.
    ``{"action_name": ..., ...}`` dicts are read as well.

    Raises ``SelfDescribeError`` when the list is empty, is not a sequence or holds something that
    is not an action.
    """
    if isinstance(actions, dict):
        actions = actions.get("webdriver_wrapper")
    if not isinstance(actions, (list, tuple)):
        raise SelfDescribeError("actions must be a sequence")
    if not actions:
        raise SelfDescribeError("actions must be non-empty")
    out: list[StepSummary] = []
    current = ""
    for step in _steps(actions):
        if _step_kind(step) == "find":
            current = _locator(step)
        elif current and not _locator(step) and _acts_on_current_element(step):
            step = {**step, "element_name": current}
        out.append(_sentence_for(step))
    return out


def describe(actions: Any, title: str = "") -> str:
    """Render Gherkin-style paragraph with optional title heading."""
    summaries = summarise(actions)
    lines: list[str] = []
    if title:
        if not isinstance(title, str):
            raise SelfDescribeError("title must be string")
        lines.append(f"# {title}")
    last_phase = None
    for s in summaries:
        if s.phase == last_phase:
            lines.append(f"  And {s.sentence}")
        else:
            lines.append(f"  {s.phase} {s.sentence}")
            last_phase = s.phase
    return "\n".join(lines)


def assert_mentions(description: str, *needles: str) -> None:
    """Raise ``SelfDescribeError`` listing the ``needles`` that ``description`` does not contain."""
    if not isinstance(description, str):
        raise SelfDescribeError("description must be string")
    if not needles:
        raise SelfDescribeError("must pass at least one needle")
    missing = [n for n in needles if n not in description]
    if missing:
        raise SelfDescribeError(
            f"description missing expected phrases: {missing}"
        )
