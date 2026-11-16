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

from dataclasses import asdict, dataclass
from enum import Enum
from html.parser import HTMLParser
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


class _LinkCollector(HTMLParser):
    """Collects the attributes of every ``<link>`` start tag."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record a ``<link>``; as in a browser, the first of a repeated attribute wins."""
        if tag != "link":
            return
        found: dict[str, str] = {}
        for name, value in attrs:
            found.setdefault(name, value or "")
        self.links.append(found)


def link_tags(html: str) -> list[dict[str, str]]:
    """Return the attributes of each ``<link>`` tag of ``html``, by lower-case attribute name.

    An attribute without a value (``crossorigin``, ``disabled``) is present with the value ``""``;
    ``data-href`` is its own attribute, not ``href``.
    """
    collector = _LinkCollector()
    collector.feed(html)
    collector.close()
    return collector.links


def same_resource(first: str, second: str) -> bool:
    """True when two URLs name the same file: equal, or one is the other's path tail.

    ``/img/hero.jpg`` and ``img/hero.jpg`` match ``https://cdn.test/img/hero.jpg``;
    ``hero.jpg`` does not match ``not-hero.jpg``.
    """
    if first == second:
        return True
    for whole, tail in ((first, second), (second, first)):
        if tail.strip("/") and whole.endswith("/" + tail.lstrip("/")):
            return True
    return False


def parse_hints(html: str) -> list[Hint]:
    """Return the resource hints declared by the ``<link>`` tags of ``html``.

    Raises ResourceHintsAuditError when ``html`` is not a string.
    """
    if not isinstance(html, str):
        raise ResourceHintsAuditError("html must be a string")
    out: list[Hint] = []
    for attrs in link_tags(html):
        rel = (attrs.get("rel") or "").lower()
        try:
            kind = HintKind(rel)
        except ValueError:
            continue
        out.append(Hint(
            kind=kind,
            href=attrs.get("href", ""),
            as_=attrs.get("as", ""),
            crossorigin="crossorigin" in attrs,
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
    """Return the preload, prefetch and modulepreload hints whose href matches none of ``used_urls``
    (see ``same_resource`` for what matches).
    """
    used = {u for u in used_urls if isinstance(u, str)}
    return [h for h in hints
            if h.kind in (HintKind.PRELOAD, HintKind.PREFETCH,
                          HintKind.MODULEPRELOAD)
            and h.href
            and not any(same_resource(h.href, u) for u in used)]


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
