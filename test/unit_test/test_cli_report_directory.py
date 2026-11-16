"""``--report BASE``: a missing directory is created, and a report that was not written fails the run."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.cli import cli_main
from je_web_runner.utils.cli.cli_main import _generate_reports
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.test_record.test_record_class import test_record_instance

_RECORD = {"function_name": "probe", "local_param": {}, "time": "now", "program_exception": "None"}


class TestReportDirectory(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        saved = list(test_record_instance.test_record_list)
        self.addCleanup(setattr, test_record_instance, "test_record_list", saved)
        test_record_instance.test_record_list = [dict(_RECORD)]
        clean_environment = patch.dict("os.environ", {}, clear=False)
        clean_environment.start()
        self.addCleanup(clean_environment.stop)
        import os
        os.environ.pop("TEST_PIONEER_ARTIFACT_DIR", None)

    def test_a_directory_that_does_not_exist_is_created(self):
        base = self.folder / "not" / "there" / "yet" / "run"
        _generate_reports(str(base))
        written = sorted(path.name for path in base.parent.iterdir())
        self.assertEqual(written, ["run.html", "run_failure.json", "run_failure.xml", "run_junit.xml",
                                   "run_success.json", "run_success.xml"])

    def test_only_the_chosen_formats_are_required(self):
        base = self.folder / "reports" / "run"
        _generate_reports(str(base), ("junit",))
        self.assertEqual([path.name for path in base.parent.iterdir()], ["run_junit.xml"])

    def test_a_report_that_cannot_be_written_fails_the_run(self):
        blocker = self.folder / "is_a_file"
        blocker.write_text("x", encoding="utf-8")
        with self.assertRaises(WebRunnerExecuteException) as caught:
            _generate_reports(str(blocker / "run"), ("json", "junit"))
        self.assertIn("run_success.json", str(caught.exception))

    def test_a_writer_that_writes_nothing_fails_the_run(self):
        base = self.folder / "reports" / "run"
        with patch("je_web_runner.utils.generate_report.generate_junit_xml_report.generate_junit_xml_report"):
            with self.assertRaises(WebRunnerExecuteException) as caught:
                _generate_reports(str(base), ("junit",))
        self.assertIn("run_junit.xml", str(caught.exception))

    def test_main_exits_with_an_error_when_the_report_is_not_written(self):
        blocker = self.folder / "is_a_file"
        blocker.write_text("x", encoding="utf-8")
        with self.assertRaises(WebRunnerExecuteException):
            cli_main.main(["--execute_str", '[["WR_set_var", {"name": "report_probe", "value": 1}]]',
                           "--report", str(blocker / "run"), "--no-config"])


if __name__ == "__main__":
    unittest.main()
