"""
Suggest refactors to a WebRunner action JSON list.

Pure-Python rule engine that spots common test-code smells and emits
``Suggestion`` records pointing reviewers at fixes:

* Hard-coded waits (``time.sleep`` / numeric-only ``wait``).
* Brittle XPath (``//div[3]/span[2]``-style positional).
* Duplicated locator strings (extract into a TestObject).
* Repeated click → wait → click bursts (extract a helper).
* Magic-string assertions that look like English copy (use translation key).

An action is read in the shape the executor runs, ``["WR_name", {keyword arguments}]``
(``WR_``, a backend prefix and ``element_`` are dropped from the name; ``selector`` /
``test_object_name`` is the locator, ``by`` / ``object_type`` its strategy), the
actions inside blocks included. The list may also be an object document with
the actions under ``webdriver_wrapper``, or hold step objects
``{"action_name", "by", "by_value", "value", "expected"}``.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.flow.structure import keyword_arguments
from je_web_runner.utils.linter.flow_rules import every_action


class ActionRefactorSuggesterError(WebRunnerException):
    """Raised on malformed action input."""


# pylint: disable=duplicate-code  # each audit owns its severity scale; the ones that match today stay separate types
class Severity(str, Enum):
    """How serious a refactor suggestion is."""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
# pylint: enable=duplicate-code


@dataclass
class Suggestion:
    """One refactor suggestion: the rule that fired, its severity, a message and the steps concerned."""
    rule: str
    severity: Severity
    message: str
    step_indexes: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the suggestion as a dict, with the severity as its string value."""
        return {**asdict(self), "severity": self.severity.value}


_POSITIONAL_XPATH = re.compile(r"\[\d+\]")
_ENGLISH_SENTENCE = re.compile(r"^[A-Z][\w\s\.,!?:'-]{15,}$")
_ACTION_LIST_KEY = "webdriver_wrapper"
_NAME_PREFIX = re.compile(r"^WR_(?:a?pw_)?(?:element_)?")
_SLEEP_NAMES = frozenset({"sleep", "time_sleep", "wait_for_timeout"})
_LOCATOR_ARGUMENTS = ("selector", "test_object_name")

Step = tuple[int, dict[str, Any]]


def _text(value: Any) -> str:
    return value.lower() if isinstance(value, str) else ""


def _step_of(action: list[Any]) -> dict[str, Any]:
    """A ``["WR_name", {...}]`` action as the step object the rules read."""
    arguments = keyword_arguments(action)
    locator = next((arguments[key] for key in _LOCATOR_ARGUMENTS if isinstance(arguments.get(key), str)), None)
    return {
        "action_name": _NAME_PREFIX.sub("", action[0]),
        "by": arguments.get("by") or arguments.get("object_type"),
        "by_value": locator,
        "value": arguments.get("value"),
        "expected": arguments.get("expected"),
    }


def _steps(actions: Any) -> list[Step]:
    """
    ``(index, step)`` for every action of ``actions``. An action inside a block (``WR_if``, a loop …)
    carries the index of the top-level action that holds it.
    """
    if isinstance(actions, dict) and _ACTION_LIST_KEY in actions:
        actions = actions[_ACTION_LIST_KEY]
    if not isinstance(actions, (list, tuple)):
        raise ActionRefactorSuggesterError("actions must be a sequence")
    steps: list[Step] = []
    for index, action in enumerate(actions):
        if isinstance(action, dict):
            steps.append((index, action))
        elif isinstance(action, list) and action and isinstance(action[0], str):
            steps.extend((index, _step_of(nested)) for _, nested in every_action([action]))
        else:
            raise ActionRefactorSuggesterError(f"action #{index} is not an action list or a step object")
    return steps


def _indexes(hits: Iterable[int]) -> list[int]:
    return sorted(set(hits))


def _is_hard_sleep(step: dict[str, Any]) -> bool:
    name = _text(step.get("action_name"))
    # numeric-only `wait: 3` is a sleep in disguise
    return name in _SLEEP_NAMES or (name == "wait" and isinstance(step.get("value"), (int, float)))


def _hard_sleep_steps(steps: Sequence[Step]) -> list[int]:
    return _indexes(index for index, step in steps if _is_hard_sleep(step))


def _positional_xpath_steps(steps: Sequence[Step]) -> list[int]:
    return _indexes(
        index for index, step in steps
        if _text(step.get("by")) == "xpath"
        and isinstance(step.get("by_value"), str)
        and _POSITIONAL_XPATH.search(step["by_value"])
    )


def _duplicated_locators(steps: Sequence[Step]) -> list[str]:
    locators = [value for value in (step.get("by_value") for _, step in steps)
                if isinstance(value, str) and value]
    counts = Counter(locators)
    return [k for k, v in counts.items() if v >= 3]


def _is_assertion(name: str) -> bool:
    return name.startswith("assert") or "_assert" in name


def _english_string_assertions(steps: Sequence[Step]) -> list[int]:
    out = []
    for index, step in steps:
        if _is_assertion(_text(step.get("action_name"))):
            expected = step.get("expected") or step.get("value")
            if isinstance(expected, str) and _ENGLISH_SENTENCE.match(expected):
                out.append(index)
    return _indexes(out)


def _click_wait_click_bursts(steps: Sequence[Step]) -> list[int]:
    """Where a click, a wait and a click follow each other; the finds between them do not break the run."""
    acting = [(index, name) for index, name in ((index, _text(step.get("action_name"))) for index, step in steps)
              if not name.startswith("find")]
    out = []
    for position in range(len(acting) - 2):
        names = [acting[position + k][1] for k in range(3)]
        if (names[0].startswith("click")
                and names[1].startswith("wait")
                and names[2].startswith("click")):
            out.append(acting[position][0])
    return _indexes(out)


def analyze(actions: Sequence[Any] | dict[str, Any]) -> list[Suggestion]:
    """Run all rules and return suggestions sorted by severity."""
    steps = _steps(actions)
    out: list[Suggestion] = []
    sleeps = _hard_sleep_steps(steps)
    if sleeps:
        out.append(Suggestion(
            rule="no-hard-sleep", severity=Severity.WARN,
            message="Replace hard sleeps with explicit waits on a condition.",
            step_indexes=sleeps,
        ))
    xpaths = _positional_xpath_steps(steps)
    if xpaths:
        out.append(Suggestion(
            rule="no-positional-xpath", severity=Severity.WARN,
            message="Replace positional XPath with role/text/data-* selector.",
            step_indexes=xpaths,
        ))
    dups = _duplicated_locators(steps)
    if dups:
        out.append(Suggestion(
            rule="extract-duplicated-locator", severity=Severity.INFO,
            message=f"Locator(s) repeated 3+ times: {dups}. Extract a TestObject.",
        ))
    english = _english_string_assertions(steps)
    if english:
        out.append(Suggestion(
            rule="prefer-translation-key", severity=Severity.INFO,
            message="Assertion contains English copy — prefer i18n key for locale safety.",
            step_indexes=english,
        ))
    bursts = _click_wait_click_bursts(steps)
    if bursts:
        out.append(Suggestion(
            rule="extract-helper", severity=Severity.INFO,
            message="Repeated click→wait→click pattern — extract a helper action.",
            step_indexes=bursts,
        ))
    severity_rank = {Severity.ERROR: 0, Severity.WARN: 1, Severity.INFO: 2}
    return sorted(out, key=lambda s: severity_rank[s.severity])


def report_markdown(suggestions: Iterable[Suggestion]) -> str:
    """Render the suggestions as a Markdown bullet list, or a "looks clean" note when there are none."""
    suggestions = list(suggestions)
    if not suggestions:
        return "## Action refactor suggestions\n_No suggestions — looks clean._"
    lines = ["## Action refactor suggestions"]
    for s in suggestions:
        marker = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}.get(s.severity.value, "•")
        lines.append(f"- {marker} **{s.rule}** — {s.message}")
        if s.step_indexes:
            lines.append(f"  at steps: {s.step_indexes}")
    return "\n".join(lines)


def assert_no_warns_or_errors(suggestions: Iterable[Suggestion]) -> None:
    """Raise ``ActionRefactorSuggesterError`` naming the rules of every WARN or ERROR suggestion."""
    bad = [s for s in suggestions
           if s.severity in (Severity.WARN, Severity.ERROR)]
    if bad:
        rules = [s.rule for s in bad]
        raise ActionRefactorSuggesterError(
            f"action script has warnings/errors: {rules}"
        )
