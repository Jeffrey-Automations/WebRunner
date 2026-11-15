"""
不執行動作檔的 CLI 工具
CLI tools that do not run action files: list the commands, lint files, write a starter workspace.
"""
from __future__ import annotations

from pathlib import Path

from je_web_runner.utils.bootstrapper.bootstrapper import init_workspace
from je_web_runner.utils.cli.failure_count import note_failed_file
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.file_process.get_dir_file_list import get_dir_files_as_list
from je_web_runner.utils.linter.action_linter import lint_action_file

COMMAND_PREFIX = "WR_"
FAILING_SEVERITY = "warning"


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
    path = Path(target)
    if not path.exists():
        raise FileNotFoundError(f"--lint target not found: {target}")
    files = get_dir_files_as_list(target) if path.is_dir() else [target]
    warnings = 0
    for file_path in sorted(files):
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
