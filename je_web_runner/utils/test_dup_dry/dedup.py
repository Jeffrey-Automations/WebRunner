"""
Test code DRY-checker.

Detects duplicated test logic across two axes:

* **Action-JSON duplicates** — two WebRunner action JSON files that walk
  the same sequence of action_name + (locator or value) tokens. Shows
  the diff so reviewers know whether to merge or parameterize.
* **Action-prefix overlap** — two files share a long common prefix
  (login → navigate → ...), suggesting an opportunity to extract a
  fixture helper.

The duplicate detection is structural — it ignores formatting and
absolute coordinates so it stays robust across small edits.

An action is read in the shape the executor runs, ``["WR_name", {...}]`` or
``["WR_name", [...]]`` (its target is the ``element_name`` / ``by_value`` /
``url`` / ``selector`` / ``test_object_name`` argument, else the first
positional one), the actions inside blocks included; step objects
``{"action_name", "element_name" | "by_value" | "url"}`` are still read.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.flow.structure import keyword_arguments
from je_web_runner.utils.linter.flow_rules import every_action

_TARGET_ARGUMENTS = ("element_name", "by_value", "url", "selector", "test_object_name")


class DupDryError(WebRunnerException):
    """Raised on malformed input."""


@dataclass
class DupSpec:
    """A named test and its action list; an empty name or a non-list raises ``DupDryError``."""
    name: str
    actions: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            raise DupDryError("DupSpec.name required")
        if not isinstance(self.actions, list):
            raise DupDryError("DupSpec.actions must be a list")


def _signature_token(action: dict[str, Any]) -> str:
    name = (action.get("action_name") or "").lower()
    target = (action.get("element_name") or action.get("by_value")
              or action.get("url") or "")
    return f"{name}:{target}"


def _list_action_token(action: list[Any]) -> str:
    """The token of a ``["WR_name", ...]`` action: its name and the element, locator or URL it works on."""
    arguments = keyword_arguments(action)
    target = next((arguments[key] for key in _TARGET_ARGUMENTS if arguments.get(key)), None)
    if target is None:
        positional = action[1] if len(action) > 1 and isinstance(action[1], list) else []
        target = positional[0] if positional and isinstance(positional[0], str) else ""
    return f"{action[0].lower()}:{target}"


def _tokens(actions: Sequence[Any]) -> list[str]:
    """One token per action, the actions inside blocks included; entries that are no action are left out."""
    tokens: list[str] = []
    for action in actions:
        if isinstance(action, dict):
            tokens.append(_signature_token(action))
        else:
            tokens.extend(_list_action_token(nested) for _, nested in every_action([action]))
    return tokens


def _signature(actions: Sequence[Any]) -> str:
    joined = "|".join(_tokens(actions))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


@dataclass
class DuplicateGroup:
    """Tests whose action lists share one signature."""
    signature: str
    test_names: list[str]


def find_duplicates(specs: Iterable[DupSpec]) -> list[DuplicateGroup]:
    """Group the specs by action signature and return the groups of two or more tests.
    Raises ``DupDryError`` when an item is not a ``DupSpec``.
    """
    buckets: dict[str, list[str]] = defaultdict(list)
    for spec in specs:
        if not isinstance(spec, DupSpec):
            raise DupDryError("each spec must be DupSpec")
        sig = _signature(spec.actions)
        buckets[sig].append(spec.name)
    return [DuplicateGroup(signature=sig, test_names=sorted(names))
            for sig, names in buckets.items() if len(names) >= 2]


@dataclass
class PrefixOverlap:
    """Two tests and the number of leading actions they have in common."""
    a: str
    b: str
    common_prefix_len: int


def _common_prefix(la: list[str], lb: list[str]) -> int:
    n = 0
    for x, y in zip(la, lb, strict=False):
        if x != y:
            break
        n += 1
    return n


def find_prefix_overlap(
    specs: Sequence[DupSpec], *, min_prefix: int = 5,
) -> list[PrefixOverlap]:
    """Return the pairs of tests that share at least ``min_prefix`` leading actions
    without one being a full prefix of the other.
    """
    if min_prefix < 1:
        raise DupDryError("min_prefix must be >= 1")
    tokens = {s.name: _tokens(s.actions) for s in specs}
    out: list[PrefixOverlap] = []
    names = sorted(tokens)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            la, lb = tokens[a], tokens[b]
            common = _common_prefix(la, lb)
            if min_prefix <= common < min(len(la), len(lb)):
                out.append(PrefixOverlap(a=a, b=b, common_prefix_len=common))
    return sorted(out, key=lambda o: -o.common_prefix_len)


def assert_no_duplicates(groups: Iterable[DuplicateGroup]) -> None:
    """Raise ``DupDryError`` listing the test names of every duplicate group."""
    items = list(groups)
    if items:
        names = [g.test_names for g in items]
        raise DupDryError(
            f"{len(items)} duplicate-action group(s) found: {names}"
        )
