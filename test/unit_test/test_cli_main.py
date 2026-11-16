import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cli.cli_main import _build_parser, _parse_execute_str, main
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException


def _write_action_json(directory: str, name: str, action: list) -> str:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as file_to_write:
        json.dump(action, file_to_write)
    return path


class TestCliParser(unittest.TestCase):

    def test_default_parallel_is_one(self):
        parser = _build_parser()
        args = parser.parse_args(["-e", "x.json"])
        self.assertEqual(args.parallel, 1)
        self.assertEqual(args.parallel_mode, "thread")

    def test_parallel_mode_process_accepted(self):
        parser = _build_parser()
        args = parser.parse_args(["-d", "tests", "--parallel-mode", "process"])
        self.assertEqual(args.parallel_mode, "process")

    def test_validate_and_report_flags(self):
        parser = _build_parser()
        args = parser.parse_args(["--validate", "x.json", "--report", "out"])
        self.assertEqual(args.validate, "x.json")
        self.assertEqual(args.report, "out")

    def test_main_without_args_raises(self):
        with self.assertRaises(WebRunnerExecuteException):
            main([])


class TestCliDispatch(unittest.TestCase):

    def test_validate_calls_validator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_action_json(tmpdir, "ok.json", [["WR_quit"]])
            with patch("je_web_runner.utils.cli.cli_main.validate_action_file") as validate:
                main(["--validate", path])
                validate.assert_called_once_with(path)

    def test_execute_file_invokes_execute_action(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_action_json(tmpdir, "run.json", [["WR_quit"]])
            with patch("je_web_runner.utils.cli.cli_main.execute_action") as exec_mock:
                main(["-e", path])
                self.assertEqual(exec_mock.call_count, 1)

    def test_parallel_execution_uses_thread_pool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_action_json(tmpdir, "a.json", [["WR_quit"]])
            _write_action_json(tmpdir, "b.json", [["WR_quit"]])
            with patch("je_web_runner.utils.cli.cli_main.execute_action") as exec_mock, \
                    patch("je_web_runner.utils.cli.cli_main.read_action_json", return_value=[["WR_quit"]]):
                main(["-d", tmpdir, "--parallel", "2"])
                self.assertEqual(exec_mock.call_count, 2)

    def test_parallel_mode_process_uses_process_pool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_action_json(tmpdir, "a.json", [["WR_quit"]])
            _write_action_json(tmpdir, "b.json", [["WR_quit"]])
            fake_pool_cls = MagicMock()
            fake_pool = MagicMock()
            fake_pool_cls.return_value.__enter__.return_value = fake_pool
            fake_pool.map.return_value = [
                ("a.json", True, []),
                ("b.json", True, []),
            ]
            with patch(
                "je_web_runner.utils.cli.cli_main.ProcessPoolExecutor",
                fake_pool_cls,
            ):
                main(["-d", tmpdir, "--parallel", "2", "--parallel-mode", "process"])
                fake_pool.map.assert_called_once()

    def test_report_flag_invokes_all_generators(self):
        with patch("je_web_runner.utils.generate_report.generate_html_report.generate_html_report") as html_mock, \
                patch("je_web_runner.utils.generate_report.generate_json_report.generate_json_report") as json_mock, \
                patch("je_web_runner.utils.generate_report.generate_xml_report.generate_xml_report") as xml_mock, \
                patch(
                    "je_web_runner.utils.generate_report.generate_junit_xml_report.generate_junit_xml_report"
                ) as junit_mock, \
                patch("je_web_runner.utils.cli.cli_main._report_files", return_value=[]):
            # The writers are stand-ins, so the check that the report files exist has nothing to find.
            main(["--report", "demo"])
            html_mock.assert_called_once_with("demo")
            json_mock.assert_called_once_with("demo")
            xml_mock.assert_called_once_with("demo")
            junit_mock.assert_called_once_with("demo")


class TestReportEnablesRecording(unittest.TestCase):

    def setUp(self):
        from je_web_runner.utils.test_record.test_record_class import test_record_instance
        self.records = test_record_instance
        self.addCleanup(self.records.set_record_enable, self.records.init_record)
        self.records.set_record_enable(False)
        # The writers are stand-ins here, so no report file appears; the check that a report was written
        # is not what these tests are about (test_cli_report_directory.py covers it).
        no_files = patch("je_web_runner.utils.cli.cli_main._report_files", return_value=[])
        no_files.start()
        self.addCleanup(no_files.stop)

    def _generators(self):
        base = "je_web_runner.utils.generate_report."
        return (
            patch(base + "generate_html_report.generate_html_report"),
            patch(base + "generate_json_report.generate_json_report"),
            patch(base + "generate_xml_report.generate_xml_report"),
            patch(base + "generate_junit_xml_report.generate_junit_xml_report"),
        )

    def test_report_turns_recording_on_before_the_run(self):
        seen = []
        html, json_report, xml, junit = self._generators()
        with html, json_report, xml, junit, patch(
            "je_web_runner.utils.cli.cli_main.execute_action",
            side_effect=lambda _actions: seen.append(self.records.init_record),
        ):
            main(["--execute_str", '[["WR_sleep", [0]]]', "--report", "demo"])
        self.assertEqual(seen, [True])

    def test_no_report_leaves_recording_off(self):
        with patch("je_web_runner.utils.cli.cli_main.execute_action"):
            main(["--execute_str", '[["WR_sleep", [0]]]'])
        self.assertFalse(self.records.init_record)

    def test_process_workers_record_when_the_parent_does(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_action_json(tmpdir, "a.json", [["WR_quit"]])
            fake_pool_cls = MagicMock()
            fake_pool_cls.return_value.__enter__.return_value.map.return_value = [("a.json", True, [])]
            html, json_report, xml, junit = self._generators()
            with html, json_report, xml, junit, patch(
                "je_web_runner.utils.cli.cli_main.ProcessPoolExecutor", fake_pool_cls,
            ):
                main(["-d", tmpdir, "--parallel", "2", "--parallel-mode", "process", "--report", "demo"])
        initializer = fake_pool_cls.call_args.kwargs["initializer"]
        self.records.set_record_enable(False)
        initializer(*fake_pool_cls.call_args.kwargs["initargs"])
        self.assertTrue(self.records.init_record)


class TestParseExecuteStr(unittest.TestCase):

    def test_parses_plain_json(self):
        result = _parse_execute_str(json.dumps([["WR_quit"]]))
        self.assertEqual(result, [["WR_quit"]])


if __name__ == "__main__":
    unittest.main()
