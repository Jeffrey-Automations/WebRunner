"""
WebRunner CLI 進入點，提供執行、驗證、平行、報告等子命令。
WebRunner CLI entry point: execute, validate, parallel, and report flags.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from je_web_runner.utils.cli.arguments import _add_config_args, _build_parser
from je_web_runner.utils.cli.dependency_levels import run_in_levels
from je_web_runner.utils.cli.failure_count import FailureCount, note_failed_file, thread_failure_count
from je_web_runner.utils.cli.run_settings import RunSettings, apply_run_settings, build_run_settings
from je_web_runner.utils.exception.exception_tags import argparse_get_wrong_data
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import execute_action, execute_files, executor
from je_web_runner.utils.file_process.get_dir_file_list import get_dir_files_as_list
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.json.json_validator import validate_action_file
from je_web_runner.utils.project_config.config import ProjectConfig, discover_config, load_config
from je_web_runner.utils.run_ledger.ledger import failed_files, record_run
from je_web_runner.utils.test_filter.dependency import (
    build_dependency_graph,
    topological_order,
)
from je_web_runner.utils.test_filter.tag_filter import filter_paths
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


# The argparse destinations of the tool flags (``utils/cli/tooling.py`` handles them).
_TOOL_FLAGS = ("list_commands", "lint", "init", "format_path", "export_schema", "export_command_reference")


def _project_config(argv: Sequence[str] | None) -> ProjectConfig:
    """The project configuration for this run, read before the real parse so it can set defaults."""
    early = argparse.ArgumentParser(add_help=False)
    _add_config_args(early)
    chosen, _rest = early.parse_known_args(argv)
    if chosen.no_config:
        return ProjectConfig()
    return load_config(chosen.config) if chosen.config else discover_config()


def _split_csv(value: str | None) -> list:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_execute_str(execute_str: str) -> list:
    """Parse a JSON string from CLI; tolerate Windows double-encoding from older shells."""
    if sys.platform in ("win32", "cygwin", "msys"):
        first = json.loads(execute_str)
        return json.loads(first) if isinstance(first, str) else first
    return json.loads(execute_str)


def _run_one_file(path: str) -> bool:
    """Execute one file; return True if no failures were recorded."""
    failure_marker = "program_exception"
    baseline = len(test_record_instance.test_record_list)
    failure_baseline = thread_failure_count()
    failed = False
    try:
        with executor.files.scope(path):
            execute_action(read_action_json(path))
    except Exception:
        failed = True
        note_failed_file()
    if failure_baseline is not None:
        return not failed and thread_failure_count() == failure_baseline
    new_records = test_record_instance.test_record_list[baseline:]
    if any(record.get(failure_marker, "None") != "None" for record in new_records):
        failed = True
    return not failed


def _run_one_file_isolated(path: str) -> tuple[str, bool, list]:
    """
    Top-level picklable worker for ``ProcessPoolExecutor``: executes the file
    in its own process (so the WebRunner singletons are fresh) and returns
    ``(path, passed, records)``. The parent merges ``records`` into its own
    ``test_record_instance`` so report generators still see every step.
    """
    # Re-import inside the worker so the child process initialises its own
    # singletons; this is the whole point of parallel-mode=process.
    from je_web_runner.utils.executor.action_executor import execute_action as _execute
    from je_web_runner.utils.executor.action_executor import executor as _executor
    from je_web_runner.utils.json.json_file.json_file import read_action_json as _read_json
    from je_web_runner.utils.test_record.test_record_class import (
        test_record_instance as _records,
    )

    failure_marker = "program_exception"
    baseline = len(_records.test_record_list)
    failed = False
    try:
        with FailureCount() as failures, _executor.files.scope(path):
            _execute(_read_json(path))
        failed = bool(failures.failed)
    except Exception:  # pylint: disable=broad-except
        # Failure path — the tuple we return signals it to the parent.
        failed = True
    new_records = _records.test_record_list[baseline:]
    if any(record.get(failure_marker, "None") != "None" for record in new_records):
        failed = True
    return path, not failed, list(new_records)


def _run_with_dependencies(
    files: Sequence[str],
    ledger_path: str | None,
    fail_fast: bool = False,
) -> None:
    """Run files in topological order, skipping downstream when upstream fails."""
    graph = build_dependency_graph(files, allow_invalid=True)
    ordered = topological_order(graph)
    failed_set: set = set()
    for path in ordered:
        deps = graph.get(path, [])
        if any(dep in failed_set for dep in deps):
            web_runner_logger.warning(
                f"skipping {path!r}: upstream dependency failed"
            )
            failed_set.add(path)
            if ledger_path:
                record_run(ledger_path, path, passed=False)
            continue
        passed = _run_one_file(path)
        if not passed:
            failed_set.add(path)
        if ledger_path:
            record_run(ledger_path, path, passed=passed)
        if fail_fast and not passed:
            print(f"fail-fast: {path} failed; the files after it are not run", file=sys.stderr)
            return


def _run_dependency_levels(files: Sequence[str], ledger_path: str | None, run_batch,
                           fail_fast: bool = False) -> None:
    """Run files with ``depends_on`` in parallel: level by level, each level one batch for the pool."""
    def skipped(path: str) -> None:
        web_runner_logger.warning(f"skipping {path!r}: upstream dependency failed")
        note_failed_file()
        if ledger_path:
            record_run(ledger_path, path, passed=False)

    run_in_levels(build_dependency_graph(files, allow_invalid=True), run_batch, skipped, fail_fast)


@dataclass(frozen=True)
class FileSelection:
    """Which files under ``-d DIR`` run: impact, tags, the failures to re-run, the shard."""

    include_tags: Sequence[str] = ()
    exclude_tags: Sequence[str] = ()
    rerun_only: Sequence[str] | None = None
    shard_spec: str | None = None
    affected_by: Sequence[str] = ()
    changed_since: str | None = None
    impact_cache: str | None = None


def _select_files(directory: str, selection: FileSelection) -> list:
    """Apply impact / rerun-only / tag / shard filters to the directory listing."""
    files = get_dir_files_as_list(directory)
    if selection.affected_by or selection.changed_since:
        from je_web_runner.utils.impact_analysis.selection import select_by_impact
        files = select_by_impact(files, directory, affected_by=selection.affected_by,
                                 changed_since=selection.changed_since, cache_path=selection.impact_cache)
    if selection.rerun_only is not None:
        rerun_set = set(selection.rerun_only)
        files = [path for path in files if path in rerun_set]
    if selection.include_tags or selection.exclude_tags:
        files = filter_paths(files, include=list(selection.include_tags), exclude=list(selection.exclude_tags))
    if selection.shard_spec:
        from je_web_runner.utils.sharding.shard import partition_with_spec
        files = partition_with_spec(files, selection.shard_spec)
    return files


def _run_file_unrecorded(path: str) -> bool:
    """Run one file without a ledger; return whether it passed."""
    before = thread_failure_count()
    try:
        execute_files([path])
    except Exception as error:
        web_runner_logger.error(f"execute_file, path: {path}, failed: {error!r}")
        note_failed_file()
        return False
    return thread_failure_count() == before


def _run_sequential(files, ledger_path: str | None, fail_fast: bool = False) -> None:
    """Sequential execution with optional ledger recording; ``fail_fast`` stops at the first failed file."""
    for position, path in enumerate(files):
        if ledger_path:
            passed = _run_one_file(path)
            record_run(ledger_path, path, passed=passed)
        else:
            passed = _run_file_unrecorded(path)
        if fail_fast and not passed:
            left = len(files) - position - 1
            print(f"fail-fast: {path} failed; {left} file(s) not run", file=sys.stderr)
            return


def _configure_worker(settings: RunSettings) -> None:
    """Process-pool initializer: a worker starts with fresh singletons, so it is given the run's settings."""
    apply_run_settings(settings)


def _isolated_results(pool, files, fail_fast: bool):
    """
    ``(path, passed, records)`` of each file run in ``pool``, in the order of ``files``. With
    ``fail_fast`` the files not started when one fails are cancelled and left out.
    """
    if not fail_fast:
        yield from pool.map(_run_one_file_isolated, files)
        return
    futures = [pool.submit(_run_one_file_isolated, path) for path in files]
    stopped = False
    for future in futures:
        if stopped and future.cancel():
            continue
        result = future.result()
        stopped = stopped or not result[1]
        yield result


def _run_with_process_pool(files, parallel: int, ledger_path: str | None,
                           settings: RunSettings | None = None) -> dict[str, bool]:
    """ProcessPool branch — true singleton isolation, records merged back; returns passed per file."""
    outcome: dict[str, bool] = {}
    # Workers record when this process does, however recording was turned on.
    worker_settings = replace(settings or RunSettings(), recording=test_record_instance.init_record)
    with ProcessPoolExecutor(
        max_workers=parallel,
        initializer=_configure_worker,
        initargs=(worker_settings,),
    ) as pool:
        for path, passed, records in _isolated_results(pool, files, worker_settings.fail_fast):
            outcome[path] = passed
            test_record_instance.test_record_list.extend(records)
            if not passed:
                note_failed_file()
            if ledger_path:
                record_run(ledger_path, path, passed=passed)
    _report_not_run(files, outcome)
    return outcome


def _report_not_run(files, outcome: dict[str, bool]) -> None:
    """Say on stderr how many files fail-fast left out."""
    left = len(files) - len(outcome)
    if left:
        print(f"fail-fast: {left} file(s) not run", file=sys.stderr)


def _run_with_asyncio(files, parallel: int, ledger_path: str | None) -> dict[str, bool]:
    """asyncio branch: one browser, one context per file, at most ``parallel`` files at a time."""
    from je_web_runner.utils.async_executor.executor import run_action_lists
    outcome: dict[str, bool] = {}
    loaded_files = []
    action_lists = []
    for path in files:
        try:
            actions = read_action_json(path)
        except Exception as error:
            web_runner_logger.error(f"execute_file, path: {path}, failed: {error!r}")
            note_failed_file()
            outcome[path] = False
            if ledger_path:
                record_run(ledger_path, path, passed=False)
            continue
        loaded_files.append(path)
        action_lists.append(actions)
    if not loaded_files:
        return outcome
    results = run_action_lists(action_lists, concurrency=max(1, parallel))
    for path, (record, failed) in zip(loaded_files, results):
        for key, value in record.items():
            print(key)
            print(value)
        outcome[path] = not failed
        if failed:
            note_failed_file()
        if ledger_path:
            record_run(ledger_path, path, passed=not failed)
    return outcome


def _run_with_thread_pool(files, parallel: int, ledger_path: str | None,
                          fail_fast: bool = False) -> dict[str, bool]:
    """ThreadPool branch — shares singletons, only safe for non-browser flows; returns passed per file."""
    web_runner_logger.warning(
        "--parallel-mode=thread shares webdriver singletons across files; "
        "use --parallel-mode=process for browser-touching tests"
    )

    outcome: dict[str, bool] = {}
    stop = threading.Event()

    def _run_and_record(path: str) -> None:
        if fail_fast and stop.is_set():
            return
        passed = _run_one_file(path)
        outcome[path] = passed
        if not passed:
            stop.set()
        if ledger_path:
            record_run(ledger_path, path, passed=passed)

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        list(pool.map(_run_and_record, files))
    _report_not_run(files, outcome)
    return outcome


def _run_dir(
    directory: str,
    parallel: int,
    selection: FileSelection,
    ledger_path: str | None = None,
    parallel_mode: str = "thread",
    settings: RunSettings | None = None,
) -> None:
    files = _select_files(directory, selection)
    fail_fast = bool(settings and settings.fail_fast)
    has_dependencies = any(build_dependency_graph(files, allow_invalid=True).values())
    pooled = parallel_mode == "async" or parallel > 1
    if has_dependencies and not pooled:
        _run_with_dependencies(files, ledger_path, fail_fast)
        return
    if not pooled:
        _run_sequential(files, ledger_path, fail_fast=fail_fast)
        return

    def run_batch(batch):
        if parallel_mode == "async":
            return _run_with_asyncio(batch, parallel, ledger_path)
        if parallel_mode == "process":
            return _run_with_process_pool(batch, parallel, ledger_path, settings)
        return _run_with_thread_pool(batch, parallel, ledger_path, fail_fast)

    if has_dependencies:
        _run_dependency_levels(files, ledger_path, run_batch, fail_fast)
    else:
        run_batch(files)


_DEFAULT_REPORT_FORMATS = ("json", "html", "xml", "junit")
_REPORT_FORMATS = (*_DEFAULT_REPORT_FORMATS, "allure", "interactive")


def _report_formats(spec: str | None) -> Sequence[str]:
    """The report formats ``--report-format`` names, in the order the CLI writes them."""
    chosen = _split_csv(spec)
    if not chosen:
        return _DEFAULT_REPORT_FORMATS
    unknown = sorted(set(chosen) - set(_REPORT_FORMATS))
    if unknown:
        raise WebRunnerExecuteException(
            f"--report-format: unknown format(s) {', '.join(unknown)}; known: {', '.join(_REPORT_FORMATS)}")
    return [name for name in _REPORT_FORMATS if name in chosen]


def _generate_reports(base_name: str, formats: Sequence[str] = _DEFAULT_REPORT_FORMATS) -> None:
    # Imported lazily so the CLI does not pay the cost (or initialize globals)
    # for users who never request a report.
    from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
    from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
    from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
    from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report

    if "json" in formats:
        generate_json_report(base_name)
    if "html" in formats:
        generate_html_report(base_name)
    if "xml" in formats:
        generate_xml_report(base_name)
    if "junit" in formats:
        generate_junit_xml_report(base_name)
    if "allure" in formats:
        from je_web_runner.utils.generate_report.generate_allure_report import generate_allure_report
        generate_allure_report(base_name + "_allure")
    if "interactive" in formats:
        from je_web_runner.utils.generate_report.interactive_html_report import (
            generate_interactive_html_report,
        )
        generate_interactive_html_report(base_name + "_interactive")


def _merge_reports(names: Sequence[str]) -> None:
    """``--merge-reports OUT BASE...``: merge the reports of the BASE names into OUT."""
    from je_web_runner.utils.generate_report.report_merge import merge_reports
    if len(names) < 2:
        raise WebRunnerExecuteException("--merge-reports takes OUT and at least one BASE")
    for path in merge_reports(names[0], list(names[1:])):
        print(f"merged: {path}")


def _validate_dir(directory: str, include_tags=None, exclude_tags=None) -> None:
    paths = get_dir_files_as_list(directory)
    if include_tags or exclude_tags:
        paths = filter_paths(paths, include=include_tags, exclude=exclude_tags)
    for path in paths:
        validate_action_file(path)


def _dispatch(args: argparse.Namespace) -> None:
    """Run side-effects requested by the parsed args, in a sensible order."""
    if args.agent_task:
        _run_agent_task(args.agent_task, args.report)
        return
    settings = _run_settings(args)
    apply_run_settings(settings)
    _run_tools(args)
    include_tags = _split_csv(args.tag)
    exclude_tags = _split_csv(args.exclude_tag)
    if args.validate:
        validate_action_file(args.validate)
    if args.validate_dir:
        _validate_dir(args.validate_dir, include_tags=include_tags, exclude_tags=exclude_tags)
    if args.execute_file:
        with executor.files.scope(args.execute_file):
            execute_action(read_action_json(args.execute_file))
    if args.execute_dir:
        _dispatch_directory(args, include_tags, exclude_tags, settings)
    if args.execute_str:
        execute_action(_parse_execute_str(args.execute_str))
    if args.report:
        _generate_reports(args.report, _report_formats(args.report_format))
    if args.merge_reports:
        _merge_reports(args.merge_reports)
    if args.migrate:
        _do_migrate(args.migrate, dry_run=args.migrate_dry_run)


def _run_settings(args: argparse.Namespace) -> RunSettings:
    """The run settings of the parsed arguments and the project configuration ``main`` attached."""
    config = getattr(args, "project_config", None) or ProjectConfig()
    settings = build_run_settings(config, args.report, args.fail_fast, args.env, args.env_dir, args.variables)
    # An absolute path, so a worker process reads the same file whatever its working directory.
    return replace(settings, dataset=str(Path(args.dataset).resolve())) if args.dataset else settings


def _run_tools(args: argparse.Namespace) -> None:
    """The flags that run no action file (lint, format, exports …); imported only when one is given."""
    if any(getattr(args, flag) for flag in _TOOL_FLAGS):
        from je_web_runner.utils.cli import tooling
        tooling.run_tools(args)


def _dispatch_directory(args: argparse.Namespace, include_tags: Sequence[str],
                        exclude_tags: Sequence[str], settings: RunSettings | None = None) -> None:
    selection = FileSelection(
        include_tags=include_tags, exclude_tags=exclude_tags,
        rerun_only=failed_files(args.rerun_failed) if args.rerun_failed else None,
        shard_spec=args.shard, affected_by=args.affected_by or (),
        changed_since=args.changed_since, impact_cache=args.impact_cache,
    )

    def do_run() -> None:
        _run_dir(args.execute_dir, args.parallel, selection, ledger_path=args.ledger,
                 parallel_mode=args.parallel_mode, settings=settings)

    if args.watch:
        from je_web_runner.utils.cli.watch_mode import watch_directory
        watch_directory(args.watch, do_run)
    else:
        do_run()


def _has_any_action(args: argparse.Namespace) -> bool:
    return any([
        args.agent_task,
        args.execute_file,
        args.execute_dir,
        args.execute_str,
        args.validate,
        args.validate_dir,
        args.report,
        args.migrate,
        args.merge_reports,
        *(getattr(args, flag) for flag in _TOOL_FLAGS),
    ])


def _run_agent_task(path: str, report_base: str | None) -> None:
    """Run one validated agent task and count every unverified outcome as failure."""
    from je_web_runner.utils.agent import TaskSpec, run_agent
    from je_web_runner.utils.agent.report import write_agent_report
    task = TaskSpec.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    report = run_agent(task, artifact_dir=report_base + ".agent-artifacts" if report_base else None)
    if report_base:
        write_agent_report(report, report_base)
    print(json.dumps(report.to_dict(), ensure_ascii=False))
    if report.status != "success":
        note_failed_file()


def _do_migrate(target: str, dry_run: bool) -> None:
    from je_web_runner.utils.linter.migration import migrate_action_file, migrate_directory
    path = Path(target)
    if path.is_dir():
        results = migrate_directory(target, dry_run=dry_run)
    elif path.is_file():
        results = [migrate_action_file(target, dry_run=dry_run)]
    else:
        raise FileNotFoundError(f"--migrate target not found: {target}")
    for entry in results:
        if entry["changes"]:
            mode = "would update" if not entry["written"] else "updated"
            print(f"{mode} {entry['path']}: {len(entry['changes'])} changes")
            for change in entry["changes"]:
                print(f"  [{change['index']}] {change['from']} -> {change['to']}")


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m je_web_runner``."""
    parser = _build_parser()
    # A flag wins over the project configuration, which wins over the built-in default.
    config = _project_config(argv)
    parser.set_defaults(**config.cli_defaults())
    args = parser.parse_args(argv)
    args.project_config = config
    if args.agent_task and any((args.execute_file, args.execute_dir, args.execute_str, args.validate,
                               args.validate_dir, args.migrate, args.watch)):
        parser.error("--agent-task runs independently; only --report can be combined with it")
    if not _has_any_action(args):
        raise WebRunnerExecuteException(argparse_get_wrong_data)
    # A failed action does not stop its list, so the run is judged once everything has run.
    with FailureCount() as failures:
        _dispatch(args)
    if failures.failed:
        print(f"error: {failures.failed} action(s) or file(s) failed", file=sys.stderr)
        return 1
    return 0
