"""
Embedding-based action JSON 語意去重。
"我們有 50 個 test 都在測登入" — `test_dedup_ai` 抓出來。Two levels:

* **Structural dedupe** — exact-match canonicalised action sequences
  catch literal copy-paste; pure stdlib, no model required.
* **Semantic dedupe** — caller-supplied :class:`Embedder` provides
  embeddings; we cluster by cosine similarity. The embedder is a simple
  callable so tests can plug in a stub vector, and production code can
  use OpenAI / Voyage / a local model.

Both modes share the same clustering output, so downstream tooling treats
them uniformly.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.flow.structure import nested_actions


class TestDedupError(WebRunnerException):
    """Raised on malformed action files, bad embeddings, or bad config."""

    __test__ = False  # domain exception, not a pytest test class


# ---------- canonicalisation -------------------------------------------

def _split_action(action: Any, label: str) -> tuple[str, list[Any], dict[str, Any]]:
    """
    Command, positional and keyword arguments of one action.

    Reads the shape the executor runs (``["WR_x"]``, ``["WR_x", {kwargs}]``, ``["WR_x", [args]]``,
    ``["WR_x", [args], {kwargs}]``) and the older ``{"WR_x": [args]}`` object.
    """
    if isinstance(action, dict) and len(action) == 1:
        name, args = next(iter(action.items()))
        if not isinstance(args, list):
            raise TestDedupError(f"{label} ({name}) args must be a list")
        return str(name), args, {}
    if not isinstance(action, list) or not action or not isinstance(action[0], str) or len(action) > 3:
        raise TestDedupError(
            f"{label} must be [command, arguments] or a single-key dict, got {action!r}"
        )
    positional: list[Any] = []
    kwargs: dict[str, Any] = {}
    for part in action[1:]:
        if isinstance(part, dict):
            kwargs = part
        elif isinstance(part, list):
            positional = part
        else:
            raise TestDedupError(f"{label} ({action[0]}) arguments must be a list or an object")
    return action[0], positional, kwargs


def _canonicalise(actions: Sequence[Any]) -> str:
    """
    Reduce an action list to a structure-only fingerprint.
    Drops user-data (URL paths, typed text) so two tests that differ only
    in test-data end up with the same fingerprint. The actions a block command runs
    (``WR_if``, ``WR_for_each`` ...) are part of the fingerprint.
    """
    if not isinstance(actions, list):
        raise TestDedupError("actions must be a list")
    return " > ".join(_action_signature(action, f"action #{index}") for index, action in enumerate(actions))


def _action_signature(action: Any, label: str) -> str:
    """``command(argument kinds)`` for one action, followed by the signatures of the actions it holds."""
    name, positional, kwargs = _split_action(action, label)
    kinds = [_arg_kind(arg) for arg in positional]
    kinds.extend(f"{key}={_arg_kind(kwargs[key])}" for key in sorted(kwargs))
    signature = f"{name}({','.join(kinds)})"
    nested = [_action_signature(inner, f"{label} {where}") for where, inner in nested_actions(action, "")]
    return f"{signature}{{{' > '.join(nested)}}}" if nested else signature


def _arg_kind(arg: Any) -> str:
    """The kind of one argument value, without its data."""
    if isinstance(arg, bool):
        return "bool"
    if isinstance(arg, (int, float)):
        return "number"
    if isinstance(arg, str):
        return f"str[{_string_kind(arg)}]"
    if isinstance(arg, list):
        return "list"
    if isinstance(arg, dict):
        return "dict"
    return type(arg).__name__


def _string_kind(value: str) -> str:
    """Crude bucket: 'locator' / 'url' / 'short' / 'long' so canonical."""
    # S5332 ok: we are *classifying* a string, not making an HTTP request.
    if value.startswith(("http://", "https://")):  # NOSONAR S5332 — intentional plain HTTP
        return "url"
    if value in {"id", "name", "xpath", "link text", "partial link text",
                 "tag name", "class name", "css selector"}:
        return "by"
    if len(value) <= 12:
        return "short"
    return "long"


# ---------- file loading -----------------------------------------------

@dataclass
class ActionFile:
    """One on-disk action JSON file."""

    path: str
    actions: list[Any]
    fingerprint: str = ""

    @classmethod
    def load(cls, path: str | Path) -> ActionFile:
        """Read an action JSON file and compute its structural fingerprint.

        The file is a list of actions or an object with the list under ``webdriver_wrapper`` (its
        ``meta`` is not part of the fingerprint). Raises ``TestDedupError`` when the file is missing,
        is not JSON or holds neither.
        """
        p = Path(path)
        if not p.exists():
            raise TestDedupError(f"action file not found: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as error:
            raise TestDedupError(f"action file {p} is not JSON: {error}") from error
        if isinstance(data, dict):
            data = data.get("webdriver_wrapper")
        if not isinstance(data, list):
            raise TestDedupError(
                f"action file {p} must contain a JSON list, or an object with a 'webdriver_wrapper' list"
            )
        instance = cls(path=str(p), actions=data)
        instance.fingerprint = _canonicalise(data)
        return instance


def load_dir(directory: str | Path) -> list[ActionFile]:
    """Load every ``*.json`` file in ``directory`` (non-recursive)."""
    d = Path(directory)
    if not d.is_dir():
        raise TestDedupError(f"not a directory: {d}")
    return [ActionFile.load(child) for child in sorted(d.glob("*.json"))]


# ---------- cluster model ----------------------------------------------

@dataclass
class DuplicateCluster:
    """A set of files judged equivalent under the chosen mode."""

    mode: str  # 'structural' | 'semantic'
    members: list[str] = field(default_factory=list)
    representative: str = ""
    similarity_threshold: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Return the fields as a plain dict for JSON output."""
        return asdict(self)


# ---------- structural dedupe -------------------------------------------

def structural_clusters(files: Sequence[ActionFile]) -> list[DuplicateCluster]:
    """Group by canonical fingerprint. Singletons are dropped."""
    if not files:
        raise TestDedupError("files must be a non-empty sequence")
    buckets: dict[str, list[str]] = {}
    for f in files:
        buckets.setdefault(f.fingerprint, []).append(f.path)
    clusters: list[DuplicateCluster] = []
    for paths in buckets.values():
        if len(paths) <= 1:
            continue
        sorted_paths = sorted(paths)
        clusters.append(DuplicateCluster(
            mode="structural",
            members=sorted_paths,
            representative=min(paths),
            similarity_threshold=1.0,
        ))
    clusters.sort(key=lambda c: -len(c.members))
    return clusters


# ---------- semantic dedupe --------------------------------------------

Embedder = Callable[[str], Sequence[float]]
"""Callable: text → embedding vector."""


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        raise TestDedupError("embeddings must be non-empty and equal-length")
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _summary_for(file: ActionFile) -> str:
    """Compact text representation an embedder will encode."""
    parts: list[str] = []
    for index, action in enumerate(file.actions[:25]):  # cap to keep embeddings stable
        try:
            name, positional, kwargs = _split_action(action, f"action #{index}")
        except TestDedupError:
            continue  # an entry that is not an action adds nothing to the summary
        args = [*positional, *(kwargs[key] for key in sorted(kwargs))]
        textual = [a for a in args if isinstance(a, str)][:3]
        if textual:
            parts.append(f"{name}: {' '.join(textual)}")
        else:
            parts.append(name)
    return " | ".join(parts)


def _embed_one(embedder: Embedder, file: ActionFile) -> list[float]:
    """Call ``embedder`` for one file and validate the returned vector."""
    try:
        vector = embedder(_summary_for(file))
    except Exception as error:
        raise TestDedupError(
            f"embedder failed for {file.path}: {error!r}"
        ) from error
    if not isinstance(vector, (list, tuple)) or not vector:
        raise TestDedupError(
            f"embedder returned bad vector for {file.path}: {vector!r}"
        )
    return list(vector)


class _UnionFind:
    """Tiny union-find for the agglomerative cluster step."""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, i: int) -> int:
        """Return the representative of ``i``'s set, shortening the path on the way."""
        while self._parent[i] != i:
            self._parent[i] = self._parent[self._parent[i]]
            i = self._parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        """Merge the sets that contain ``i`` and ``j``."""
        a, b = self.find(i), self.find(j)
        if a != b:
            self._parent[a] = b


def semantic_clusters(
    files: Sequence[ActionFile],
    embedder: Embedder,
    *,
    similarity_threshold: float = 0.92,
) -> list[DuplicateCluster]:
    """
    Group files whose summary embeddings are pairwise above
    ``similarity_threshold``. Uses simple agglomerative union-find; fine
    for the test-suite scale (hundreds, not millions).
    """
    if not files:
        raise TestDedupError("files must be a non-empty sequence")
    if not 0.0 < similarity_threshold <= 1.0:
        raise TestDedupError("similarity_threshold must be in (0, 1]")
    embeddings = [_embed_one(embedder, f) for f in files]
    uf = _UnionFind(len(files))
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            if _cosine(embeddings[i], embeddings[j]) >= similarity_threshold:
                uf.union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(files)):
        groups.setdefault(uf.find(i), []).append(i)

    clusters: list[DuplicateCluster] = []
    for indices in groups.values():
        if len(indices) <= 1:
            continue
        paths = sorted(files[i].path for i in indices)
        clusters.append(DuplicateCluster(
            mode="semantic",
            members=paths,
            representative=paths[0],
            similarity_threshold=similarity_threshold,
        ))
    clusters.sort(key=lambda c: -len(c.members))
    return clusters


# ---------- reporting --------------------------------------------------

def clusters_markdown(clusters: Sequence[DuplicateCluster]) -> str:
    """Render a small markdown table of duplicate clusters."""
    if not clusters:
        return "_No duplicate test clusters found._\n"
    lines = [
        "| Mode | Members | Representative | Threshold |",
        "|------|---------|----------------|-----------|",
    ]
    for c in clusters:
        members = ", ".join(f"`{m}`" for m in c.members[:6])
        if len(c.members) > 6:
            members += f" (+{len(c.members) - 6} more)"
        lines.append(
            f"| {c.mode} | {members} | `{c.representative}` | {c.similarity_threshold:.2f} |"
        )
    return "\n".join(lines) + "\n"


def stable_fingerprint(actions: Sequence[Any]) -> str:
    """SHA-256 of the canonical fingerprint. Stable across processes."""
    raw = _canonicalise(actions)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
