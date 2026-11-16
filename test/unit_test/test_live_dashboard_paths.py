"""A dashboard path set as text after the configuration was built is read like one given at construction."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.live_dashboard._config import DashboardConfig
from je_web_runner.utils.live_dashboard._data import build_summary


class TestPathsAssignedLater(unittest.TestCase):

    def test_a_text_path_assigned_after_construction_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Path(folder) / "ledger.json"
            runs = [{"path": "a.json", "passed": True, "time": "2026-11-16T00:00:00Z"}]
            ledger.write_text(json.dumps({"runs": runs}),
                              encoding="utf-8")
            given_at_construction = build_summary(DashboardConfig(ledger_path=str(ledger)))
            config = DashboardConfig()
            config.ledger_path = str(ledger)
            assigned_later = build_summary(config)
        self.assertEqual(assigned_later, given_at_construction)

    def test_no_path_is_still_an_empty_summary(self):
        self.assertEqual(build_summary(DashboardConfig()), build_summary(DashboardConfig(ledger_path=None)))


if __name__ == "__main__":
    unittest.main()
