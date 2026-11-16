"""Records know their action file; JUnit groups by file; --report-format; --merge-reports."""
import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from defusedxml.ElementTree import fromstring, parse

from je_web_runner.utils.cli.cli_main import _report_formats, main
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.flow.subflow import FileStack
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml
from je_web_runner.utils.generate_report.report_merge import ReportMergeError, merge_reports
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    record_file,
    test_record_instance,
)


class _Recording(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self.addCleanup(test_record_instance.set_record_enable, test_record_instance.init_record)
        self.addCleanup(setattr, test_record_instance, "test_record_list", test_record_instance.test_record_list)
        test_record_instance.test_record_list = []
        test_record_instance.set_record_enable(True)

    @staticmethod
    def _add(name, time, error=None):
        record_action_to_list(name, None, error)
        test_record_instance.test_record_list[-1]["time"] = time


class TestRecordFile(_Recording):

    def test_records_carry_the_running_file(self):
        record_action_to_list("before", None)
        with record_file("suite/a.json"):
            record_action_to_list("inside", None)
            with record_file("suite/called.json"):
                record_action_to_list("called", None)
        record_action_to_list("after", None)
        files = [record.get("file") for record in test_record_instance.test_record_list]
        self.assertEqual(files, [None, "suite/a.json", "suite/a.json", None])
        self.assertNotIn("file", test_record_instance.test_record_list[0])

    def test_file_stack_marks_records(self):
        stack = FileStack()
        with stack.scope(self.root / "login.json"):
            record_action_to_list("step", None)
        self.assertEqual(test_record_instance.test_record_list[0]["file"], str(self.root / "login.json"))

    def test_other_threads_have_no_file(self):
        with record_file("suite/a.json"):
            worker = threading.Thread(target=record_action_to_list, args=("elsewhere", None))
            worker.start()
            worker.join()
        self.assertNotIn("file", test_record_instance.test_record_list[0])


class TestJunitPerFile(_Recording):

    def test_one_suite_per_file_with_times(self):
        with record_file(str(self.root / "suite" / "a.json")):
            self._add("open", "2026-11-16 10:00:00.000000")
            self._add("click", "2026-11-16 10:00:01.500000")
            self._add("check", "2026-11-16 10:00:04.000000", RuntimeError("boom"))
        with record_file(str(self.root / "b.json")):
            self._add("open", "2026-11-16 10:00:10.000000")
        root = fromstring(generate_junit_xml())
        suites = root.findall("testsuite")
        self.assertEqual([suite.get("name") for suite in suites], ["suite/a.json", "b.json"])
        self.assertEqual([(suite.get("tests"), suite.get("failures"), suite.get("time")) for suite in suites],
                         [("3", "1", "4.000"), ("1", "0", "0.000")])
        self.assertEqual([case.get("time") for case in suites[0].findall("testcase")], ["0", "1.500", "2.500"])
        self.assertEqual((root.get("tests"), root.get("failures"), root.get("time")), ("4", "1", "4.000"))
        self.assertEqual(suites[0].get("file"), str(self.root / "suite" / "a.json"))

    def test_records_outside_a_file_keep_their_own_suite(self):
        self._add("loose", "2026-11-16 10:00:00.000000")
        with record_file(str(self.root / "a.json")):
            self._add("open", "2026-11-16 10:00:01.000000")
        suites = fromstring(generate_junit_xml()).findall("testsuite")
        self.assertEqual([suite.get("name") for suite in suites], ["webrunner", "a.json"])

    def test_without_files_the_report_is_one_suite_as_before(self):
        self._add("one", "2026-11-16 10:00:00.000000")
        self._add("two", "2026-11-16 10:00:05.000000")
        root = fromstring(generate_junit_xml())
        suites = root.findall("testsuite")
        self.assertEqual([(suite.get("name"), suite.get("time")) for suite in suites], [("webrunner", "0")])
        self.assertEqual([case.get("time") for case in suites[0].findall("testcase")], ["0", "0"])

    def test_unreadable_timestamps_give_zero(self):
        with record_file(str(self.root / "a.json")):
            self._add("one", "not a time")
            self._add("two", "2026-11-16 10:00:05.000000")
        suite = fromstring(generate_junit_xml()).find("testsuite")
        self.assertEqual(suite.get("time"), "0")
        self.assertEqual([case.get("time") for case in suite.findall("testcase")], ["0", "0"])


class TestReportFormats(_Recording):

    def test_default_and_chosen_formats(self):
        self.assertEqual(list(_report_formats(None)), ["json", "html", "xml", "junit"])
        self.assertEqual(list(_report_formats("junit, json")), ["json", "junit"])
        self.assertEqual(list(_report_formats("interactive,allure")), ["allure", "interactive"])

    def test_unknown_format(self):
        with self.assertRaises(WebRunnerExecuteException) as raised:
            _report_formats("junit,pdf")
        self.assertIn("pdf", str(raised.exception))

    def test_cli_writes_only_the_chosen_reports(self):
        executor.event_dict["WR_recorded_probe"] = lambda: record_action_to_list("probe", None)
        self.addCleanup(executor.event_dict.pop, "WR_recorded_probe", None)
        action_file = self.root / "a.json"
        action_file.write_text(json.dumps([["WR_recorded_probe"]]), encoding="utf-8")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main(["-e", str(action_file), "--report", "out", "--report-format", "junit,interactive",
                         "--no-config"])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(path.name for path in self.root.glob("out*")),
                         ["out_interactive.html", "out_junit.xml"])
        suite = parse(str(self.root / "out_junit.xml")).getroot().find("testsuite")
        self.assertEqual(suite.get("name"), "a.json")


class TestMergeReports(_Recording):

    def _shard(self, base, steps):
        test_record_instance.test_record_list = []
        with record_file(str(self.root / f"{base}.json")):
            for name, error in steps:
                record_action_to_list(name, None, error)
        from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
        from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
        generate_json_report(base)
        generate_junit_xml_report(base)

    def test_merges_json_and_junit(self):
        self._shard("shard1", [("open", None), ("check", RuntimeError("boom"))])
        self._shard("shard2", [("open", None), ("click", None)])
        written = merge_reports("all", ["shard1", "shard2"])
        self.assertEqual(sorted(Path(path).name for path in written),
                         ["all_failure.json", "all_junit.xml", "all_success.json"])
        success = json.loads((self.root / "all_success.json").read_text(encoding="utf-8"))
        failure = json.loads((self.root / "all_failure.json").read_text(encoding="utf-8"))
        self.assertEqual(list(success), ["Success_Test1", "Success_Test2", "Success_Test3"])
        self.assertEqual(list(failure), ["Failure_Test1"])
        root = parse(str(self.root / "all_junit.xml")).getroot()
        self.assertEqual((root.get("tests"), root.get("failures")), ("4", "1"))
        self.assertEqual([suite.get("name") for suite in root.findall("testsuite")], ["shard1.json", "shard2.json"])

    def test_repeated_suite_names_are_told_apart(self):
        for base in ("one", "two"):
            test_record_instance.test_record_list = []
            record_action_to_list("loose", None)
            from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
            generate_junit_xml_report(base)
        merge_reports("all", ["one", "two"])
        root = parse(str(self.root / "all_junit.xml")).getroot()
        self.assertEqual([suite.get("name") for suite in root.findall("testsuite")], ["webrunner", "webrunner [two]"])

    def test_nothing_to_merge(self):
        with self.assertRaises(ReportMergeError):
            merge_reports("all", [])
        with self.assertRaises(ReportMergeError):
            merge_reports("all", ["no_such_base"])

    def test_broken_input(self):
        (self.root / "bad_success.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(ReportMergeError):
            merge_reports("all", ["bad"])
        (self.root / "worse_junit.xml").write_text("<testsuites>", encoding="utf-8")
        with self.assertRaises(ReportMergeError):
            merge_reports("all", ["worse"])

    def test_cli_flag(self):
        self._shard("shard1", [("open", None)])
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--merge-reports", "all", "shard1", "--no-config"])
        self.assertEqual(code, 0)
        self.assertIn("merged:", out.getvalue())
        self.assertTrue((self.root / "all_junit.xml").is_file())

    def test_cli_flag_needs_an_input(self):
        with self.assertRaises(WebRunnerExecuteException):
            with patch("builtins.print"):
                main(["--merge-reports", "all", "--no-config"])


if __name__ == "__main__":
    unittest.main()
