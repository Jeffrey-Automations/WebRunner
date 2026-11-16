"""
不執行動作檔的 CLI 工具
CLI tools that do not run action files: list the commands, lint and format files, export the schema and
the command reference, write a starter workspace.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from je_web_runner.utils.action_formatter.formatter import format_file
from je_web_runner.utils.bootstrapper.bootstrapper import init_workspace
from je_web_runner.utils.cli.failure_count import note_failed_file
from je_web_runner.utils.docs.command_reference import export_command_reference
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.file_process.get_dir_file_list import get_dir_files_as_list
from je_web_runner.utils.linter.action_linter import lint_action_file
from je_web_runner.utils.schema.action_schema import export_schema

COMMAND_PREFIX = "WR_"
FAILING_SEVERITY = "warning"
# The argparse destinations of the flags handled here; any of them is enough for the CLI to have work.
TOOL_FLAGS = ("list_commands", "lint", "init", "format_path", "export_schema", "export_command_reference")


def _action_files(target: str, flag: str) -> list[str]:
    """``target`` itself, or the sorted ``.json`` files below it when it is a directory."""
    path = Path(target)
    if not path.exists():
        raise FileNotFoundError(f"{flag} target not found: {target}")
    return get_dir_files_as_list(target) if path.is_dir() else [target]


def list_commands() -> list[str]:
    """Print every registered ``WR_*`` command, one per line, and return them."""
    names = sorted(name for name in executor.event_dict if isinstance(name, str) and name.startswith(COMMAND_PREFIX))
    for name in names:
        print(name)
    return names


def lint_target(target: str) -> int:
    """
    Lint one action file, or every ``.json`` file below a directory, and print the findings as
    ``path: severity [rule] location: message``. A warning fails the run; information does not. Return
    the number of warnings.
    """
    files = _action_files(target, "--lint")
    warnings = 0
    for file_path in files:
        for finding in lint_action_file(file_path):
            print(f"{file_path}: {finding['severity']} [{finding['rule']}] "
                  f"{finding['location']}: {finding['message']}")
            warnings += finding["severity"] == FAILING_SEVERITY
    if warnings:
        note_failed_file()
    print(f"lint: {len(files)} file(s), {warnings} warning(s)")
    return warnings


def init_project(directory: str) -> dict[str, str]:
    """Write the starter workspace into ``directory`` (existing files are kept) and print what was done."""
    report = init_workspace(directory)
    for relative_path, outcome in report.items():
        print(f"{outcome}: {relative_path}")
    return report


def format_target(target: str, check: bool = False) -> list[str]:
    """
    Rewrite one action file, or every ``.json`` file below a directory, in the canonical layout, and print
    the files that changed. With ``check`` nothing is written and a file that would change fails the run.
    Return the files that changed (or would).
    """
    changed = [path for path in _action_files(target, "--format") if format_file(path, write=not check)[1]]
    for path in changed:
        print(f"{'would reformat' if check else 'reformatted'}: {path}")
    if check and changed:
        note_failed_file()
    return changed


def run_tools(args: argparse.Namespace) -> None:
    """Run the tool flags that were given."""
    if args.list_commands:
        list_commands()
    if args.lint:
        lint_target(args.lint)
    if args.format_path:
        format_target(args.format_path, check=args.format_check)
    if args.init:
        init_project(args.init)
    if args.export_schema:
        print(f"schema: {export_schema(args.export_schema)}")
    if args.export_command_reference:
        print(f"command reference: {export_command_reference(args.export_command_reference)}")
