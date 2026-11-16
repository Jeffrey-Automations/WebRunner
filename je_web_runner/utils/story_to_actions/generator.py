"""
從使用者故事 / Figma frame metadata 產生 WR action JSON。
The "smart" bit (LLM call) is abstracted behind a :class:`StoryClient`
protocol so this module stays unit-testable without network. Real usage
plugs in a Claude / GPT / local model client; tests inject a stub that
returns canned responses.

The output goes through a strict validator before being returned, so a
hallucinated action name or malformed args is caught here — not by the
executor at runtime.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class StoryToActionsError(WebRunnerException):
    """Raised on bad inputs, client failures, or invalid generated actions."""


# Commands we trust the LLM to emit, each with its arguments in call order. Anything else is
# rejected so we don't silently let in hallucinations. Every name is registered in the executor;
# ``WR_find_element_by`` makes an element current and the ``WR_element_*`` commands act on it.
_LOCATOR_BY = frozenset({
    "id", "name", "xpath", "link text", "partial link text",
    "tag name", "class name", "css selector",
})
_WAIT_STATES = frozenset({"present", "visible", "clickable", "hidden"})


@dataclass(frozen=True)
class _Argument:
    """One argument of an allowed command: its name, the test a value must pass, and what to say when it fails."""

    name: str
    accepts: Callable[[Any], bool]
    wants: str
    required: bool = True


def _is_text(value: Any) -> bool:
    return isinstance(value, str)


def _is_filled_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _is_seconds(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _is_checks(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


_SELECTOR = _Argument("selector", _is_filled_text, "a non-empty string")
_BY = _Argument("by", _LOCATOR_BY.__contains__, f"one of {sorted(_LOCATOR_BY)}", required=False)

_COMMANDS: dict[str, tuple[_Argument, ...]] = {
    "WR_to_url": (_Argument("url", _is_filled_text, "a non-empty string"),),
    "WR_find_element_by": (_SELECTOR, _BY),
    "WR_wait_for_element": (
        _SELECTOR, _BY,
        _Argument("timeout", _is_seconds, "a number of seconds >= 0", required=False),
        _Argument("state", _WAIT_STATES.__contains__, f"one of {sorted(_WAIT_STATES)}", required=False),
    ),
    "WR_element_click": (),
    "WR_element_clear": (),
    "WR_element_submit": (),
    "WR_element_input": (_Argument("input_value", _is_text, "a string"),),
    "WR_element_assert": (_Argument("check_dict", _is_checks, "a non-empty object of attribute to value"),),
    "WR_assert_title": (_Argument("value", _is_text, "a string"),),
    "WR_implicitly_wait": (_Argument("time_to_wait", _is_seconds, "a number of seconds >= 0"),),
    "WR_note": (_Argument("text", _is_text, "a string"),),
}

ALLOWED_ACTIONS = frozenset(_COMMANDS)


def _command_signatures() -> list[str]:
    """``WR_command(argument, optional?)`` for every allowed command, sorted."""
    return [
        f"{name}({', '.join(a.name if a.required else a.name + '?' for a in _COMMANDS[name])})"
        for name in sorted(_COMMANDS)
    ]


# ---------- input model -------------------------------------------------

@dataclass
class FigmaHint:
    """One element extracted from a Figma frame (optional context for the LLM)."""

    name: str
    type: str  # 'button' | 'input' | 'text' | ...
    selector_hint: str | None = None  # e.g. data-test-id from layer metadata
    text: str | None = None


@dataclass
class StoryPrompt:
    """The user story + optional structured context."""

    story: str
    start_url: str | None = None
    figma_hints: list[FigmaHint] = field(default_factory=list)
    style_notes: list[str] = field(default_factory=list)  # extra constraints

    def __post_init__(self) -> None:
        if not isinstance(self.story, str) or not self.story.strip():
            raise StoryToActionsError("story must be a non-empty string")


# ---------- client protocol --------------------------------------------

class StoryClient(Protocol):
    """LLM client interface. ``generate`` returns a JSON-string action list."""

    def generate(self, prompt_text: str) -> str:
        """Send ``prompt_text`` to the model and return its raw text reply."""


# ---------- prompt construction ----------------------------------------

def build_prompt_text(prompt: StoryPrompt) -> str:
    """Render a deterministic prompt the LLM client will see verbatim."""
    parts: list[str] = []
    parts.append("# Task")
    parts.append(
        "Translate the user story below into a WebRunner action JSON list. "
        'Each action is ["WR_command", {"argument": value}], or ["WR_command"] for a command '
        "without arguments. Allowed commands (a ? marks an optional argument): "
        f"{_command_signatures()}. "
        "WR_find_element_by makes an element the current one; the WR_element_* commands act on it. "
        f"Locator strategies for 'by': {sorted(_LOCATOR_BY)}. "
        "Return ONLY the JSON array of actions, no commentary."
    )
    parts.append("\n# Story\n" + prompt.story.strip())
    if prompt.start_url:
        parts.append("\n# Start URL\n" + prompt.start_url)
    if prompt.figma_hints:
        parts.append("\n# Figma element hints")
        for hint in prompt.figma_hints:
            line = f"- {hint.name} ({hint.type})"
            if hint.selector_hint:
                line += f" selector: {hint.selector_hint}"
            if hint.text:
                line += f" text: {hint.text!r}"
            parts.append(line)
    if prompt.style_notes:
        parts.append("\n# Style notes")
        for note in prompt.style_notes:
            parts.append(f"- {note}")
    return "\n".join(parts)


# ---------- generation --------------------------------------------------


def generate_actions(
    prompt: StoryPrompt,
    client: StoryClient,
) -> list[Any]:
    """
    Build prompt → ask client → parse → validate. Returns the action list.

    The actions are in the shape the executor runs: ``["WR_command", {arguments}]``.
    """
    prompt_text = build_prompt_text(prompt)
    try:
        raw = client.generate(prompt_text)
    except Exception as error:
        raise StoryToActionsError(f"story client failed: {error!r}") from error
    if not isinstance(raw, str):
        raise StoryToActionsError(
            f"story client returned {type(raw).__name__}, want JSON string"
        )
    actions = _parse_json_response(raw)
    validate_actions(actions)
    # Apply the start_url policy: if user supplied one and the LLM didn't
    # open with WR_to_url, prepend it. Saves a round of corrections.
    if prompt.start_url and not _starts_with_navigate(actions, prompt.start_url):
        actions.insert(0, ["WR_to_url", {"url": prompt.start_url}])
        web_runner_logger.info(
            f"story_to_actions: prepended WR_to_url with start_url {prompt.start_url!r}"
        )
    return actions


def _fenced_block(text: str) -> str:
    """Return the body of the first ``` fence (dropping a ``json`` tag), or ``text`` if there is none.

    Found with ``str.find`` rather than a lazy ``.+?`` regex, which rescanned the rest of the reply
    from every position when a fence was never closed.
    """
    start = text.find("```")
    if start == -1:
        return text
    end = text.find("```", start + 3)
    if end == -1:
        return text
    body = text[start + 3:end]
    if body.startswith("json"):
        body = body[len("json"):]
    body = body.strip()
    return body if body else text


def _parse_json_response(raw: str) -> list[Any]:
    text = _fenced_block(raw.strip())
    try:
        loaded = json.loads(text)
    except ValueError as error:
        raise StoryToActionsError(
            f"client response was not valid JSON: {error}; first 120 chars: {raw[:120]!r}"
        ) from error
    if not isinstance(loaded, list):
        raise StoryToActionsError(
            f"client response must be a JSON list, got {type(loaded).__name__}"
        )
    return loaded


def _starts_with_navigate(actions: Sequence[Any], url: str) -> bool:
    if not actions:
        return False
    name, arguments = _bound_arguments(0, actions[0])
    return name == "WR_to_url" and arguments.get("url") == url


# ---------- validation --------------------------------------------------

def validate_actions(actions: Sequence[Any]) -> None:
    """
    Raise :class:`StoryToActionsError` on the first invalid entry.

    An entry is an action as the executor runs it: ``["WR_command"]``, ``["WR_command", {arguments}]``
    or ``["WR_command", [arguments]]``, with a command of ``ALLOWED_ACTIONS`` and its arguments.
    """
    if not isinstance(actions, list):
        raise StoryToActionsError(
            f"actions must be a list, got {type(actions).__name__}"
        )
    if not actions:
        raise StoryToActionsError("actions list is empty")
    for index, action in enumerate(actions):
        _validate_one(index, action)


def _bound_arguments(index: int, action: Any) -> tuple[str, dict[str, Any]]:
    """The command of ``action`` and its arguments by name; positional ones take the names in call order."""
    if not isinstance(action, list) or not action or not isinstance(action[0], str) or len(action) > 3:
        raise StoryToActionsError(
            f'action #{index} must be ["WR_command", {{arguments}}], got {action!r}'
        )
    name = action[0]
    if name not in _COMMANDS:
        raise StoryToActionsError(
            f"action #{index} uses disallowed name {name!r}; allowed: {sorted(ALLOWED_ACTIONS)}"
        )
    names = [argument.name for argument in _COMMANDS[name]]
    bound: dict[str, Any] = {}
    for part in action[1:]:
        if isinstance(part, dict):
            bound.update(part)
        elif isinstance(part, list) and len(part) <= len(names):
            bound.update(zip(names, part))
        else:
            raise StoryToActionsError(
                f"action #{index} ({name}) takes an object of {names} or at most {len(names)} listed values"
            )
    return name, bound


def _validate_one(index: int, action: Any) -> None:
    name, bound = _bound_arguments(index, action)
    arguments = _COMMANDS[name]
    unknown = sorted(set(bound) - {argument.name for argument in arguments})
    if unknown:
        raise StoryToActionsError(f"action #{index} ({name}) has unknown argument(s) {unknown}")
    for argument in arguments:
        if argument.name not in bound:
            if argument.required:
                raise StoryToActionsError(f"action #{index} ({name}) needs {argument.name!r}")
        elif not argument.accepts(bound[argument.name]):
            raise StoryToActionsError(
                f"action #{index} ({name}) {argument.name!r} must be {argument.wants}, "
                f"got {bound[argument.name]!r}"
            )


# ---------- output helpers ----------------------------------------------

def write_actions_json(
    actions: Sequence[Any],
    output_path: str | Path,
) -> Path:
    """Persist validated actions to disk in WebRunner action JSON format."""
    validate_actions(actions)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(list(actions), fp, ensure_ascii=False, indent=2)
    return path
