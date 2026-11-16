"""
Resource hints (preload / prefetch / preconnect) actually-used auditor.

Pages routinely accumulate stale ``<link rel="preload">`` tags that point
at assets the page never actually loads — wasting bytes & confusing the
priority queue. This module:

* Parses ``<link rel="preload|prefetch|preconnect">`` declarations.
* Cross-references against a HAR (or fetched-URL list).
* Flags unused hints + missing hints (e.g. an LCP image with no preload).
* Detects ``preload`` without matching ``as=`` (browser will discard).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ResourceHintsAuditError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


class HintKind(str, Enum):
    """The ``<link rel>`` values that are resource hints."""
    PRELOAD = "preload"
    PREFETCH = "prefetch"
    PRECONNECT = "preconnect"
    DNS_PREFETCH = "dns-prefetch"
    MODULEPRELOAD = "modulepreload"


@dataclass
class Hint:
    """One resource hint: its kind, target, ``as`` value and whether it is crossorigin."""
    kind: HintKind
    href: str
    as_: str = ""        # only for preload
    crossorigin: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the hint as a dict with the kind as its string value."""
        return {**asdict(self), "kind": self.kind.value}


_LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))',
                      re.IGNORECASE)


def _parse_attrs(tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in _ATTR_RE.finditer(tag):
        key = match.group(1).lower()
        attrs[key] = match.group(2) or match.group(3) or match.group(4) or ""
    return attrs


def parse_hints(html: str) -> list[Hint]:
    """Return the resource hints declared by the ``<link>`` tags of ``html``.

    Raises ResourceHintsAuditError when ``html`` is not a string.
    """
    if not isinstance(html, str):
        raise ResourceHintsAuditError("html must be a string")
    out: list[Hint] = []
    for tag in _LINK_RE.findall(html):
        attrs = _parse_attrs(tag)
        rel = (attrs.get("rel") or "").lower()
        try:
            kind = HintKind(rel)
        except ValueError:
            continue
        out.append(Hint(
            kind=kind,
            href=attrs.get("href", ""),
            as_=attrs.get("as", ""),
            crossorigin="crossorigin" in tag.lower(),
        ))
    return out


def assert_preload_has_as(hints: Iterable[Hint]) -> None:
    """Raise ResourceHintsAuditError when a preload hint has no ``as`` attribute."""
    bad = [h for h in hints
           if h.kind == HintKind.PRELOAD and not h.as_]
    if bad:
        raise ResourceHintsAuditError(
            f"{len(bad)} preload(s) missing as= attribute → browser will "
            f"discard them: {[b.href for b in bad]}"
        )


def find_unused_hints(
    hints: Sequence[Hint], used_urls: Iterable[str],
) -> list[Hint]:
    """Return the preload, prefetch and modulepreload hints whose href matches none of ``used_urls``."""
    used = {u for u in used_urls if isinstance(u, str)}
    return [h for h in hints
            if h.kind in (HintKind.PRELOAD, HintKind.PREFETCH,
                          HintKind.MODULEPRELOAD)
            and h.href
            and h.href not in used
            and not any(u.endswith(h.href) or h.href.endswith(u)
                        for u in used)]


def assert_no_unused_hints(
    hints: Sequence[Hint], used_urls: Iterable[str],
) -> None:
    """Raise ResourceHintsAuditError when a hinted resource was never used."""
    unused = find_unused_hints(hints, used_urls)
    if unused:
        raise ResourceHintsAuditError(
            f"{len(unused)} unused resource hint(s): "
            f"{[u.href for u in unused]}"
        )


def assert_origin_preconnected(
    hints: Iterable[Hint], *, origin: str,
) -> None:
    """Raise ResourceHintsAuditError unless a preconnect hint targets ``origin``
    (a trailing slash is ignored).
    """
    if not origin:
        raise ResourceHintsAuditError("origin must be non-empty")
    for h in hints:
        if h.kind == HintKind.PRECONNECT and (h.href == origin
                                              or h.href.rstrip("/") == origin.rstrip("/")):
            return
    raise ResourceHintsAuditError(
        f"no <link rel='preconnect' href='{origin}'> found"
    )
