"""trend_dashboard: a ledger whose root is not an object is a TrendDashboardError."""
import json

import pytest

from je_web_runner.utils.trend_dashboard.trend import TrendDashboardError, compute_trend


@pytest.mark.parametrize("root", [[{"time": "2026-11-16T10:00:00", "passed": True}], "runs", 3, None])
def test_ledger_root_that_is_not_an_object(tmp_path, root):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(root), encoding="utf-8")
    with pytest.raises(TrendDashboardError, match="runs"):
        compute_trend(str(path))
