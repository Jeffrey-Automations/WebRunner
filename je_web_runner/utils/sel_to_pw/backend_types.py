"""
翻譯表的共用型別與數值轉換
What the modules of the translation table share: the shape of an entry and the value conversions.

An entry of the table is a :class:`Rule` (one command becomes one command) or a builder function (it gets
the action's arguments by the Selenium parameter names and returns the Playwright actions, or raises
:class:`Untranslatable`). :mod:`~je_web_runner.utils.sel_to_pw.backend_rules` explains how they are read.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

Action = list[Any]
Builder = Callable[[dict[str, Any]], list[Action]]


class Untranslatable(Exception):
    """One action cannot be translated; the message is the reason."""


@dataclass(frozen=True)
class Conversion:
    """How an argument value changes: ``forward`` to Playwright, ``backward`` to Selenium."""

    forward: Callable[[Any], Any]
    backward: Callable[[Any], Any] | None = None


@dataclass(frozen=True)
class Rule:
    """One Selenium command that becomes one Playwright command (see ``backend_rules``)."""

    target: str
    rename: Mapping[str, str] = field(default_factory=dict)
    convert: Mapping[str, Conversion] = field(default_factory=dict)
    add: Mapping[str, Any] = field(default_factory=dict)
    defaults: Mapping[str, Any] = field(default_factory=dict)
    # Selenium arguments filled when a Playwright action leaves them out (the other direction of ``defaults``).
    inverse_defaults: Mapping[str, Any] = field(default_factory=dict)
    inverse: bool = True


def number(value: Any, what: str) -> float:
    """``value`` when it is a literal number; a ``${placeholder}`` or anything else cannot be converted."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Untranslatable(f"{what} must be a literal number to be converted, got {value!r}")
    return value


def text(value: Any, what: str) -> str:
    """``value`` when it is text."""
    if not isinstance(value, str):
        raise Untranslatable(f"{what} must be text, got {value!r}")
    return value


def _tidy(value: float) -> float:
    rounded = round(value, 6)
    return int(rounded) if float(rounded).is_integer() else rounded


def seconds_to_ms(value: Any) -> float:
    """Selenium waits in seconds, Playwright in milliseconds."""
    return _tidy(number(value, "a time in seconds") * 1000)


def ms_to_seconds(value: Any) -> float:
    """The other direction of :func:`seconds_to_ms`."""
    return _tidy(number(value, "a time in milliseconds") / 1000)


SECONDS = Conversion(seconds_to_ms, ms_to_seconds)
