"""
產生 JUnit 格式 XML 測試報告，便於 GitHub Actions / Jenkins 等 CI 系統消費。
Generate JUnit-format XML test reports for CI consumption (GitHub Actions, Jenkins, etc.).

Records made while an action file was running (their ``file`` key) form one ``<testsuite>`` per file,
named after the file, with times taken from the records' timestamps: a step's time is the time since
the step before it in the same file, a suite's time its last timestamp minus its first. Records made
outside any file stay in one suite called ``webrunner`` with time 0, as before.
"""
import os
from datetime import datetime
from threading import Lock
# Element/SubElement/tostring are XML builders, not parsers; defusedxml does not provide builders.
from xml.etree.ElementTree import Element, SubElement, tostring  # nosec B405 # nosemgrep: use-defused-xml

from je_web_runner.utils.exception.exception_tags import cant_generate_json_report
from je_web_runner.utils.exception.exceptions import WebRunnerGenerateJsonReportException
from je_web_runner.utils.generate_report.report_path import report_path
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance

_lock = Lock()

_NO_EXCEPTION_MARKER = "None"


def _record_is_failure(record: dict) -> bool:
    """Whether the record represents a failed action."""
    return record.get("program_exception", _NO_EXCEPTION_MARKER) != _NO_EXCEPTION_MARKER


def _timestamp(record: dict) -> datetime | None:
    """When the record was made, or None when its ``time`` cannot be read."""
    try:
        return datetime.fromisoformat(str(record.get("time")))
    except ValueError:
        return None


def _seconds_between(earlier: dict | None, later: dict) -> str:
    """Seconds from ``earlier`` to ``later`` as JUnit text; ``0`` when either time is unknown."""
    start = _timestamp(earlier) if earlier is not None else None
    end = _timestamp(later)
    if start is None or end is None:
        return "0"
    return f"{max((end - start).total_seconds(), 0.0):.3f}"


def _suite_name(file_path: str) -> str:
    """The file relative to the working directory when it is below it, else as recorded."""
    try:
        relative = os.path.relpath(file_path)
    except ValueError:  # another drive on Windows
        return file_path
    return file_path if relative.startswith("..") else relative.replace(os.sep, "/")


def _records_by_file(records: list) -> dict:
    """``{file or None: [records]}`` in the order each file first appears."""
    groups: dict = {}
    for record in records:
        groups.setdefault(record.get("file"), []).append(record)
    return groups


def _build_testcase(suite: Element, record: dict, index: int, seconds: str = "0") -> None:
    """Append a single <testcase> child to the given <testsuite>."""
    function_name = str(record.get("function_name", "unknown"))
    testcase = SubElement(
        suite,
        "testcase",
        {
            "name": f"{function_name}_{index}",
            "classname": f"webrunner.{function_name}",
            "time": seconds,
        },
    )
    if _record_is_failure(record):
        failure = SubElement(
            testcase,
            "failure",
            {
                "message": str(record.get("program_exception", "")),
                "type": "WebRunnerExecutionError",
            },
        )
        failure.text = (
            f"function: {function_name}\n"
            f"param: {record.get('local_param')}\n"
            f"time: {record.get('time')}\n"
            f"exception: {record.get('program_exception')}"
        )


def generate_junit_xml() -> str:
    """
    產生 JUnit 格式 XML 字串
    Generate JUnit-format XML string

    :return: JUnit XML 字串 / JUnit XML string
    """
    web_runner_logger.info("generate_junit_xml")

    records = test_record_instance.test_record_list
    if len(records) == 0:
        raise WebRunnerGenerateJsonReportException(cant_generate_json_report)

    failures = sum(1 for record in records if _record_is_failure(record))
    total = len(records)
    attrs = {
        "name": "webrunner",
        "tests": str(total),
        "failures": str(failures),
        "errors": "0",
        "time": "0",
    }
    groups = _records_by_file(records)
    if list(groups) == [None]:
        suites = Element("testsuites", attrs)
        suite = SubElement(suites, "testsuite", attrs)
        for index, record in enumerate(records, start=1):
            _build_testcase(suite, record, index)
        return str(tostring(suites, encoding="utf-8"), encoding="utf-8")

    suites = Element("testsuites", attrs)
    total_seconds = 0.0
    for file_path, group in groups.items():
        suite_seconds = _seconds_between(group[0], group[-1]) if file_path is not None else "0"
        total_seconds += float(suite_seconds)
        suite = SubElement(suites, "testsuite", {
            "name": "webrunner" if file_path is None else _suite_name(file_path),
            "tests": str(len(group)),
            "failures": str(sum(1 for record in group if _record_is_failure(record))),
            "errors": "0",
            "time": suite_seconds,
        })
        if file_path is not None:
            suite.set("file", file_path)
        previous = None
        for index, record in enumerate(group, start=1):
            timed = file_path is not None and previous is not None
            _build_testcase(suite, record, index, _seconds_between(previous, record) if timed else "0")
            previous = record
    suites.set("time", f"{total_seconds:.3f}")
    return str(tostring(suites, encoding="utf-8"), encoding="utf-8")


def generate_junit_xml_report(junit_file_name: str = "default_name") -> None:
    """
    產生並輸出 JUnit XML 測試報告
    Generate and save a JUnit XML test report

    :param junit_file_name: 輸出檔案名稱 (不含副檔名)
                            Output file name (without extension)
    """
    web_runner_logger.info(f"generate_junit_xml_report, junit_file_name: {junit_file_name}")

    junit_xml = generate_junit_xml()
    target = report_path(junit_file_name + "_junit.xml")
    try:
        with _lock, open(target, "w", encoding="utf-8") as file_to_write:  # NOSONAR S8707 — developer-supplied path
            file_to_write.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            file_to_write.write(junit_xml)
    except OSError as error:
        web_runner_logger.error(
            f"generate_junit_xml_report, junit_file_name: {junit_file_name}, failed: {error!r}"
        )
