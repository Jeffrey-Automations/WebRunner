"""
合併多份報告
Merge the reports of several runs (the shards of ``--shard``, or runs on different machines) into one:
``<base>_success.json`` / ``<base>_failure.json`` and ``<base>_junit.xml`` of every input base name become
one set under the output base name. An input that lacks one of the files simply adds nothing to that part.
"""
from __future__ import annotations

import json
from pathlib import Path
# Element/SubElement/tostring build XML; parsing goes through defusedxml.
from xml.etree.ElementTree import Element, tostring  # nosec B405 # nosemgrep: use-defused-xml

from defusedxml.ElementTree import parse as parse_xml  # type: ignore[import-untyped]

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.generate_report.report_path import report_path

_JSON_PARTS = (("_success.json", "Success_Test"), ("_failure.json", "Failure_Test"))
_COUNTERS = ("tests", "failures", "errors")


class ReportMergeError(WebRunnerException):
    """Raised when there is nothing to merge or an input report cannot be read."""


def _read_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as report_file:
            data = json.load(report_file)
    except (OSError, ValueError) as error:
        raise ReportMergeError(f"cannot read report {path}: {error}") from error
    if not isinstance(data, dict):
        raise ReportMergeError(f"report {path} is not a JSON object")
    return data


def _merge_json(output_base: str, bases: list[str], suffix: str, prefix: str) -> str | None:
    """Merge one JSON part; entries are renumbered ``<prefix>1`` … in input order. None when no input has it."""
    entries: list = []
    found = False
    for base in bases:
        path = Path(base + suffix)
        if path.is_file():
            found = True
            entries.extend(_read_json(path).values())
    if not found:
        return None
    target = report_path(output_base + suffix)
    with open(target, "w", encoding="utf-8") as report_file:
        json.dump({f"{prefix}{number}": entry for number, entry in enumerate(entries, start=1)},
                  report_file, indent=4, ensure_ascii=False)
    return str(target)


def _suites_of(path: Path) -> list[Element]:
    try:
        root = parse_xml(str(path)).getroot()
    except Exception as error:  # defusedxml raises its own types as well as ParseError and OSError
        raise ReportMergeError(f"cannot read report {path}: {error}") from error
    return [root] if root.tag == "testsuite" else list(root.iter("testsuite"))


def _seconds(suite: Element) -> float:
    try:
        return float(suite.get("time", "0"))
    except ValueError:
        return 0.0


def _merge_junit(output_base: str, bases: list[str]) -> str | None:
    """Merge the JUnit files; a suite name that repeats gets the input's file name appended."""
    merged: list[Element] = []
    names: set[str] = set()
    for base in bases:
        path = Path(base + "_junit.xml")
        if not path.is_file():
            continue
        for suite in _suites_of(path):
            name = suite.get("name", "webrunner")
            if name in names:
                name = f"{name} [{Path(base).name}]"
                suite.set("name", name)
            names.add(name)
            merged.append(suite)
    if not merged:
        return None
    totals = {key: str(sum(int(suite.get(key, "0") or 0) for suite in merged)) for key in _COUNTERS}
    root = Element("testsuites", {"name": "webrunner", **totals,
                                  "time": f"{sum(_seconds(suite) for suite in merged):.3f}"})
    root.extend(merged)
    target = report_path(output_base + "_junit.xml")
    with open(target, "w", encoding="utf-8") as report_file:
        report_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        report_file.write(str(tostring(root, encoding="utf-8"), encoding="utf-8"))
    return str(target)


def merge_reports(output_base: str, bases: list[str]) -> list[str]:
    """
    合併多份報告並回傳寫出的檔案
    Merge the JSON and JUnit reports of ``bases`` (report base names, as given to ``--report``) into
    ``output_base`` and return the files written.

    :raises ReportMergeError: when ``bases`` is empty, an input cannot be read, or no input has any report.
    """
    if not bases:
        raise ReportMergeError("nothing to merge: give at least one report base name")
    written = [_merge_json(output_base, bases, suffix, prefix) for suffix, prefix in _JSON_PARTS]
    written.append(_merge_junit(output_base, bases))
    paths = [path for path in written if path is not None]
    if not paths:
        raise ReportMergeError(f"no report found for {', '.join(bases)}")
    return paths
