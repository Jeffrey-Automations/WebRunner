"""
動作檔的 pytest 節點
The pytest nodes of an action file: :class:`ActionFile` (the ``.json`` file) holding one :class:`ActionItem`
(the test that runs it). Imported only once a project has opted in and a ``.json`` file was found.
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any, Iterator

import pytest

from je_web_runner.utils.exception.exceptions import WebRunnerException, describe_error
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.flow.document import read_meta, skip_reason
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.json.json_validator import ACTION_LIST_KEY, validate_action_json

_NOT_A_WORD = re.compile(r"\W", re.ASCII)


class ActionFileFailure(Exception):
    """An action file that failed; its text is the whole failure report of the test."""


def marker_name(tag: Any) -> str:
    """
    標籤對應的 marker 名稱
    The marker of a ``meta.tags`` entry: the tag with every character other than an ASCII letter, a digit
    or ``_`` replaced by ``_``; ``tag`` is put in front of a result that is empty or starts with ``_``
    (pytest refuses such marker names).
    """
    name = _NOT_A_WORD.sub("_", str(tag).strip())
    return f"tag{name}" if not name or name.startswith("_") else name


def tag_markers(document: Any) -> list:
    """The marker names of the ``meta.tags`` of ``document``, in order, without repeats."""
    meta = document.get("meta") if isinstance(document, dict) else None
    tags = meta.get("tags") if isinstance(meta, dict) else None
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        return []
    return list(dict.fromkeys(marker_name(tag) for tag in tags))


def document_problem(document: Any) -> tuple:
    """
    ``(is an action document, why it cannot run)``. An object with ``webdriver_wrapper`` is one even when
    it is not valid (the problem is then its validation error); a list is one only when it is valid, since
    a dataset is a list too.
    """
    try:
        validate_action_json(document)
    except WebRunnerException as error:
        claims = isinstance(document, dict) and ACTION_LIST_KEY in document
        return claims, describe_error(error)
    return True, None


def collect_action_file(
        parent: pytest.Collector, file_path: Path, marker: str, fail_fast: bool = False) -> "ActionFile | None":
    """
    The collector of ``file_path``, or None when the file is not an action document. ``marker`` is the
    marker every action file gets; ``fail_fast`` stops the file at its first failed action.
    """
    try:
        document = read_action_json(str(file_path))
    except (OSError, ValueError, WebRunnerException) as error:
        warnings.warn(pytest.PytestCollectionWarning(
            f"WebRunner: {file_path} is not collected, it cannot be read as JSON: {describe_error(error)}"))
        return None
    is_document, problem = document_problem(document)
    if not is_document:
        return None
    collector = ActionFile.from_parent(parent, path=file_path)
    collector.document = document
    collector.problem = problem
    collector.marker = marker
    collector.fail_fast = fail_fast
    return collector


class ActionFile(pytest.File):
    """One action file; it holds a single test, named after the file."""

    document: Any = None
    problem: str | None = None
    marker: str = "webrunner"
    fail_fast: bool = False

    def collect(self) -> Iterator["ActionItem"]:
        """The test of this file, marked with ``webrunner``, its tags and its ``meta.skip``."""
        item = ActionItem.from_parent(self, name=self.path.stem)
        item.action_file = self
        item.add_marker(self.marker)
        for name in tag_markers(self.document):
            self.config.addinivalue_line("markers", f"{name}: WebRunner action files tagged in meta.tags")
            item.add_marker(name)
        if self.problem is None:
            try:
                reason = skip_reason(read_meta(self.document))
            except WebRunnerException:
                reason = None  # a malformed meta fails the test when it runs, with the executor's message
            if reason is not None:
                item.add_marker(pytest.mark.skip(reason=reason))
        yield item


def run_document(path: Path, document: Any, fail_fast: bool) -> tuple:
    """
    Run ``document``, the content of the action file at ``path``, as ``Executor.execute_file`` runs it but
    without printing and with variables of its own; return ``(records, failed keys)``.
    """
    previous = executor.fail_fast.enabled
    if fail_fast:
        executor.set_fail_fast(True)
    try:
        with executor.isolated_variables(), executor.files.scope(path):
            return executor.collect_action_results(document)
    finally:
        executor.set_fail_fast(previous)


def failure_text(name: str, records: dict, failed: list) -> str:
    """The failure report: every failed action with its error text."""
    lines = [f"{name}: {len(failed)} of {len(records)} actions failed"]
    for number, key in enumerate(failed, start=1):
        lines.append(f"  {number}. {key}")
        lines.append(f"     {records.get(key)}")
    return "\n".join(lines)


class ActionItem(pytest.Item):
    """The test that runs one action file."""

    action_file: ActionFile

    def runtest(self) -> None:
        """Run the file; raise :class:`ActionFileFailure` when it cannot run or an action failed."""
        collector = self.action_file
        name = collector.nodeid
        if collector.problem is not None:
            raise ActionFileFailure(f"{name}: not a valid action file\n  {collector.problem}")
        try:
            records, failed = run_document(self.path, collector.document, collector.fail_fast)
        except WebRunnerException as error:
            raise ActionFileFailure(f"{name}: the file could not be run\n  {describe_error(error)}") from error
        if failed:
            raise ActionFileFailure(failure_text(name, records, failed))

    def repr_failure(self, excinfo: pytest.ExceptionInfo, style: Any = None) -> Any:
        """The failed actions and their errors; a traceback only for an error of another kind."""
        if isinstance(excinfo.value, ActionFileFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo, style)

    def reportinfo(self) -> tuple:
        """Where the test is (line 1: pytest needs a line to report a skip) and how the report heads it."""
        return self.path, 0, f"webrunner: {self.action_file.nodeid}"
