"""
把 rrweb / 通用 session event 串流轉成 WR action JSON。
Production session replays (rrweb, Pendo, Hotjar) carry rich event
streams. This converter normalises them into the WebRunner action JSON
that ``executor`` already understands, so a real user flow becomes a
reproducible test.

Supports two input shapes:

* **rrweb events** — the public ``[{type, data, timestamp}]`` shape from
  ``rrweb.record``. We handle ``IncrementalSnapshot`` mouse / input / scroll
  events plus the top-level page-load metadata.
* **Generic events** — provider-agnostic ``{kind, target, value?, url?,
  timestamp}`` dicts. This is the format you'd produce when scraping
  Pendo/Hotjar/custom telemetry.

The output is an action list as the executor runs it: ``["WR_name", {kwargs}]``
entries naming registered commands. An event on an element becomes two
actions, ``WR_find_element_by`` and the command that acts on the element found.

The converter is deliberately conservative: events it cannot map cleanly
(a scroll, a double click, a submit without a target) become ``WR_note``
action lines instead of being silently dropped, so the engineer reviewing
the output sees what was skipped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

_CSS_SELECTOR_BY = "css selector"

Action = list[Any]


class SessionToTestError(WebRunnerException):
    """Raised on unreadable input, malformed events, or empty conversions."""


# rrweb event type ids
_RRWEB_FULL_SNAPSHOT = 2
_RRWEB_INCREMENTAL = 3
_RRWEB_META = 4

# rrweb incremental-source ids
_RRWEB_SRC_MOUSE_INTERACTION = 2
_RRWEB_SRC_SCROLL = 3
_RRWEB_SRC_INPUT = 5

# rrweb mouse-interaction kinds
_RRWEB_MI_CLICK = 2
_RRWEB_MI_DOUBLE_CLICK = 4

# pragmatic threshold: drop micro-mouse-moves rarer than this many ms apart
_MIN_INTER_EVENT_MS = 50


# ---------- public model ------------------------------------------------

@dataclass
class ConversionStats:
    """Roll-up returned by :func:`convert_events`."""

    input_events: int = 0
    actions_emitted: int = 0
    skipped_events: int = 0
    comment_actions: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def note_skip(self, reason: str) -> None:
        """Count one skipped event and tally it under ``reason``."""
        self.skipped_events += 1
        self.reasons[reason] = self.reasons.get(reason, 0) + 1

    def note_actions(self, actions: Sequence[Action]) -> None:
        """Count the actions one event produced; the ``WR_note`` ones also count as comments."""
        self.actions_emitted += len(actions)
        self.comment_actions += sum(1 for action in actions if action[0] == "WR_note")


@dataclass
class ConversionResult:
    """Output of :func:`convert_events`: actions plus stats."""

    actions: list[Action]
    stats: ConversionStats


# ---------- action builders ---------------------------------------------

def _navigate(url: str) -> list[Action]:
    return [["WR_to_url", {"url": url}]]


def _note(text: str) -> list[Action]:
    return [["WR_note", {"text": text}]]


def _on_element(locator: tuple[str, str], *then: Action) -> list[Action]:
    """Find the element of ``locator`` (it becomes the current element), then run ``then`` on it."""
    by, selector = locator
    return [["WR_find_element_by", {"selector": selector, "by": by}], *then]


# ---------- entry points ------------------------------------------------

def _convert_rrweb_event(event: Any, stats: ConversionStats) -> list[Action]:
    """The actions of one rrweb event; an event that maps to nothing is counted as skipped."""
    if not isinstance(event, dict):
        stats.note_skip("non-dict event")
        return []
    kind = event.get("type")
    if kind == _RRWEB_META and isinstance(event.get("data"), dict):
        url = event["data"].get("href")
        if isinstance(url, str) and url:
            return _navigate(url)
        stats.note_skip("meta without href")
        return []
    if kind == _RRWEB_FULL_SNAPSHOT:
        stats.note_skip("full snapshot (no action)")
        return []
    if kind != _RRWEB_INCREMENTAL:
        stats.note_skip(f"unknown rrweb type {kind!r}")
        return []
    return _convert_rrweb_incremental(event, stats)


def convert_rrweb_events(events: Sequence[dict[str, Any]]) -> ConversionResult:
    """Convert an rrweb event list into WR action JSON."""
    if not isinstance(events, list):
        raise SessionToTestError("rrweb events must be a list")
    stats = ConversionStats(input_events=len(events))
    actions: list[Action] = []
    for event in events:
        emitted = _convert_rrweb_event(event, stats)
        actions.extend(emitted)
        stats.note_actions(emitted)
    if not actions:
        raise SessionToTestError(
            f"no actions produced from {len(events)} rrweb events; "
            "input may be unsupported or empty"
        )
    return ConversionResult(actions=actions, stats=stats)


def convert_generic_events(events: Sequence[dict[str, Any]]) -> ConversionResult:
    """Convert a provider-agnostic event list into WR action JSON."""
    if not isinstance(events, list):
        raise SessionToTestError("generic events must be a list")
    stats = ConversionStats(input_events=len(events))
    actions: list[Action] = []
    for event in events:
        if not isinstance(event, dict):
            stats.note_skip("non-dict event")
            continue
        emitted = _convert_generic_event(event, stats)
        actions.extend(emitted)
        stats.note_actions(emitted)
    if not actions:
        raise SessionToTestError(
            f"no actions produced from {len(events)} generic events"
        )
    return ConversionResult(actions=actions, stats=stats)


def convert_events(payload: str | Path | Sequence[dict[str, Any]]) -> ConversionResult:
    """
    Sniff the input: file → list / list → list. rrweb vs generic is
    detected by the presence of an integer ``type`` field on the events.
    """
    events = _load_events(payload)
    if not events:
        raise SessionToTestError("event list is empty")
    if isinstance(events[0], dict) and isinstance(events[0].get("type"), int):
        return convert_rrweb_events(events)
    return convert_generic_events(events)


def _load_events(payload: str | Path | Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, (list, tuple)):
        return list(payload)
    if isinstance(payload, (str, Path)):
        path = Path(payload)
        if not path.exists():
            raise SessionToTestError(f"events file not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise SessionToTestError(f"events file is not JSON: {error}") from error
        if isinstance(data, dict) and "events" in data:
            data = data["events"]
        if not isinstance(data, list):
            raise SessionToTestError("events file did not contain a list")
        return data
    raise SessionToTestError(
        f"convert_events expects path or list, got {type(payload).__name__}"
    )


# ---------- rrweb mappings ----------------------------------------------

def _convert_rrweb_mouse(data: dict[str, Any], stats: ConversionStats) -> list[Action]:
    """Map an rrweb mouse interaction: a click is found and clicked, a double click is noted, others skipped."""
    kind = data.get("type")
    selector = _selector_for_node(data.get("id"))
    if selector is None:
        stats.note_skip("mouse without node id")
        return []
    if kind == _RRWEB_MI_CLICK:
        return _on_element((_CSS_SELECTOR_BY, selector), ["WR_element_click"])
    if kind == _RRWEB_MI_DOUBLE_CLICK:
        # No registered command double-clicks the element a raw selector found.
        return _note(f"double click {selector}")
    stats.note_skip(f"mouse type {kind!r}")
    return []


def _convert_rrweb_input(data: dict[str, Any], stats: ConversionStats) -> list[Action]:
    """Map an rrweb input event to a find and an input action; skipped when it names no node."""
    selector = _selector_for_node(data.get("id"))
    value = data.get("text", "")
    if selector is None:
        stats.note_skip("input without node id")
        return []
    return _on_element((_CSS_SELECTOR_BY, selector), ["WR_input_to_element", {"input_value": str(value)}])


def _convert_rrweb_incremental(
    event: dict[str, Any],
    stats: ConversionStats,
) -> list[Action]:
    data = event.get("data") if isinstance(event.get("data"), dict) else None
    if not data:
        stats.note_skip("incremental without data")
        return []
    source = data.get("source")
    if source == _RRWEB_SRC_MOUSE_INTERACTION:
        return _convert_rrweb_mouse(data, stats)
    if source == _RRWEB_SRC_INPUT:
        return _convert_rrweb_input(data, stats)
    if source == _RRWEB_SRC_SCROLL:
        x = data.get("x", 0)
        y = data.get("y", 0)
        return _note(f"scroll to {x},{y}")
    stats.note_skip(f"incremental source {source!r}")
    return []


def _selector_for_node(node_id: Any) -> str | None:
    """
    rrweb identifies nodes by integer id from its DOM mirror. Without the
    full snapshot we can't recover a stable CSS path, so we emit a custom
    attribute selector that the test harness can rewrite later.
    """
    if not isinstance(node_id, int) or node_id < 0:
        return None
    return f'[data-rrweb-id="{node_id}"]'


# ---------- generic mappings --------------------------------------------

def _generic_navigate(event: dict[str, Any], stats: ConversionStats) -> list[Action]:
    url = event.get("url")
    if isinstance(url, str) and url:
        return _navigate(url)
    stats.note_skip("navigate without url")
    return []


def _generic_click(locator: tuple[str, str] | None, stats: ConversionStats) -> list[Action]:
    if locator is None:
        stats.note_skip("click without target")
        return []
    return _on_element(locator, ["WR_element_click"])


def _generic_input(
    event: dict[str, Any], locator: tuple[str, str] | None, stats: ConversionStats,
) -> list[Action]:
    if locator is None:
        stats.note_skip("input without target")
        return []
    value = event.get("value", "")
    return _on_element(locator, ["WR_input_to_element", {"input_value": str(value)}])


def _generic_submit(locator: tuple[str, str] | None) -> list[Action]:
    if locator is None:
        return _note("submit form (no target)")
    return _on_element(locator, ["WR_element_submit"])


def _generic_wait(event: dict[str, Any], stats: ConversionStats) -> list[Action]:
    try:
        seconds = float(event.get("seconds", 0))
    except (TypeError, ValueError):
        stats.note_skip("wait with non-numeric seconds")
        return []
    return [["WR_implicitly_wait", {"time_to_wait": seconds}]]


_GENERIC_DISPATCH = {
    "navigate": lambda event, locator, stats: _generic_navigate(event, stats),
    "click": lambda event, locator, stats: _generic_click(locator, stats),
    "input": _generic_input,
    "submit": lambda event, locator, stats: _generic_submit(locator),
    "wait": lambda event, locator, stats: _generic_wait(event, stats),
}


def _convert_generic_event(
    event: dict[str, Any],
    stats: ConversionStats,
) -> list[Action]:
    kind = str(event.get("kind") or "").lower()
    handler = _GENERIC_DISPATCH.get(kind)
    if handler is None:
        stats.note_skip(f"unknown generic kind {kind!r}")
        return []
    return handler(event, _coerce_locator(event.get("target")), stats)


def _coerce_locator(target: Any) -> tuple[str, str] | None:
    if isinstance(target, dict):
        by = target.get("by") or _CSS_SELECTOR_BY
        value = target.get("value")
        if isinstance(value, str) and value:
            return str(by), value
        return None
    if isinstance(target, str) and target:
        return _CSS_SELECTOR_BY, target
    return None


# ---------- output helpers ----------------------------------------------

def write_actions_json(
    result: ConversionResult,
    output_path: str | Path,
) -> Path:
    """Persist the converted actions list to disk in WR action format."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(result.actions, fp, ensure_ascii=False, indent=2)
    web_runner_logger.info(
        f"session_to_test: wrote {result.stats.actions_emitted} actions to {path} "
        f"(skipped {result.stats.skipped_events})"
    )
    return path
