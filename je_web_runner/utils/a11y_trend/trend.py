"""
A11y violations trend：把多次跑的 axe 結果依日期 / impact 統計，畫時間序列。
Aggregate axe-core run history into per-day per-impact counts and render
a self-contained HTML dashboard with an SVG line chart.
"""
from __future__ import annotations

import html as _html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.trend_dashboard.trend import bucket_label, render_page


class A11yTrendError(WebRunnerException):
    """Raised when the history JSON has the wrong shape."""


@dataclass
class A11yTrendPoint:
    """One point of the trend: a date label and the violation count per axe impact level."""
    label: str  # YYYY-MM-DD
    impacts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Sum of the violation counts over every impact level."""
        return sum(self.impacts.values())


def aggregate_history(history: Iterable[dict[str, Any]]) -> list[A11yTrendPoint]:
    """
    把 ``[{timestamp, violations:[{impact,...}]}, …]`` 按天彙總每個 impact 的計數。
    Bucket history entries by day and count each violation's ``impact``
    (``critical`` / ``serious`` / ``moderate`` / ``minor`` / ``unknown``).
    """
    if history is None:
        raise A11yTrendError("history must be iterable")
    buckets: dict[str, A11yTrendPoint] = {}
    for index, entry in enumerate(history):
        _absorb_entry(buckets, index, entry)
    return sorted(buckets.values(), key=lambda p: p.label)


def _absorb_entry(buckets: dict[str, A11yTrendPoint], index: int, entry: Any) -> None:
    if not isinstance(entry, dict):
        raise A11yTrendError(f"history[{index}] must be an object")
    label = bucket_label(entry.get("timestamp"))
    violations = entry.get("violations") or []
    if not isinstance(violations, list):
        raise A11yTrendError(f"history[{index}].violations must be a list")
    point = buckets.setdefault(label, A11yTrendPoint(label=label))
    for violation in violations:
        _count_violation(point, violation)


def _count_violation(point: A11yTrendPoint, violation: Any) -> None:
    if not isinstance(violation, dict):
        return
    impact = str(violation.get("impact") or "unknown")
    nodes = violation.get("nodes")
    count = len(nodes) if isinstance(nodes, list) and nodes else 1
    point.impacts[impact] = point.impacts.get(impact, 0) + count


def render_html(points: list[A11yTrendPoint], title: str = "A11y trend") -> str:
    """Render a self-contained HTML page with table + SVG line chart."""
    rows = []
    impact_keys = sorted({impact for point in points for impact in point.impacts})
    for point in points:
        cells = "".join(
            f"<td>{point.impacts.get(key, 0)}</td>" for key in impact_keys
        )
        rows.append(f"<tr><td>{_html.escape(point.label)}</td>{cells}<td>{point.total}</td></tr>")
    headers = "".join(f"<th>{_html.escape(key)}</th>" for key in impact_keys)
    return render_page(
        title,
        _render_svg(points),
        f"<tr><th>Date</th>{headers}<th>Total</th></tr>",
        "".join(rows) or '<tr><td colspan="999"><em>No data</em></td></tr>',
    )


def _render_svg(points: list[A11yTrendPoint]) -> str:
    if not points:
        return "<p><em>No history yet.</em></p>"
    width, height, margin = 720, 200, 30
    plot_w = width - 2 * margin
    plot_h = height - 2 * margin
    x_step = plot_w / (len(points) - 1) if len(points) > 1 else 0.0
    max_total = max(p.total for p in points) or 1
    coords = []
    for i, point in enumerate(points):
        x = margin + i * x_step
        y = margin + (1 - point.total / max_total) * plot_h
        coords.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(coords)
    axis = (
        f"<line x1='{margin}' y1='{margin + plot_h}' x2='{margin + plot_w}' "
        f"y2='{margin + plot_h}' stroke='#888'/>"
        f"<line x1='{margin}' y1='{margin}' x2='{margin}' y2='{margin + plot_h}' stroke='#888'/>"
    )
    return (
        f"<svg width='{width}' height='{height}' xmlns='http://www.w3.org/2000/svg'>"
        f"{axis}<polyline points='{polyline}' fill='none' stroke='#dc2626' stroke-width='2'/>"
        f"</svg>"
    )


def write_dashboard(history: Iterable[dict[str, Any]], output_path: str | Path,
                    title: str = "A11y trend") -> Path:
    """Aggregate ``history`` and write the HTML dashboard to ``output_path``."""
    points = aggregate_history(history)
    text = render_html(points, title=title)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def load_history(path: str | Path) -> list[dict[str, Any]]:
    """Read an ``a11y-history.json`` file (``[{timestamp, violations}, …]``)."""
    fp = Path(path)
    if not fp.is_file():
        raise A11yTrendError(f"history file not found: {path!r}")
    try:
        document = json.loads(fp.read_text(encoding="utf-8"))
    except ValueError as error:
        raise A11yTrendError(f"history file invalid JSON: {error}") from error
    if not isinstance(document, list):
        raise A11yTrendError("history file root must be a list")
    return document
