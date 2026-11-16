"""
CLI 的參數定義
The command-line arguments of ``python -m je_web_runner``, in groups: what to run, directory runs, impact
selection, and the project settings and tools.
"""
from __future__ import annotations

import argparse

from je_web_runner.utils.project_config.config import BACKENDS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="webrunner")
    _add_run_args(parser)
    _add_dir_args(parser)
    _add_impact_args(parser)
    _add_project_args(parser)
    return parser


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    """Which project configuration file to read; also parsed on their own before everything else."""
    parser.add_argument(
        "--config", type=str, default=None, metavar="FILE",
        help="project configuration file (default: webrunner.toml, else [tool.webrunner] of "
             "pyproject.toml, in the working directory)",
    )
    parser.add_argument(
        "--no-config", action="store_true", dest="no_config",
        help="do not read a project configuration file",
    )


def _add_project_args(parser: argparse.ArgumentParser) -> None:
    """Run settings (variables, .env, fail-fast) and the tools that run no action file."""
    _add_config_args(parser)
    parser.add_argument(
        "--var", action="append", default=None, dest="variables", metavar="NAME=VALUE",
        help="set a variable the action files read as ${NAME}; VALUE is JSON when it parses as JSON, "
             "else text; repeatable",
    )
    parser.add_argument("--env", type=str, default=None, metavar="NAME",
                        help="load .env.NAME before the run, for ${ENV.KEY} placeholders")
    parser.add_argument("--env-dir", type=str, default=None, dest="env_dir", metavar="DIR",
                        help="directory holding the .env files (default: the working directory)")
    parser.add_argument(
        "--fail-fast", action="store_true", dest="fail_fast",
        help="after the first failed action skip the rest of its file (teardown still runs), and with "
             "--execute_dir do not start the files after the first failed one (sequential runs)",
    )
    parser.add_argument(
        "--dataset", type=str, default=None, metavar="FILE",
        help="a .csv or .json dataset: every file without a meta.dataset of its own runs once per row, "
             "reading the row as ${ROW.column}",
    )
    parser.add_argument(
        "--plugin", action="append", default=None, dest="plugins", metavar="NAME",
        help="load an installed command plugin (an entry point of the group je_web_runner.commands) "
             "by name; repeatable",
    )
    parser.add_argument("--list-plugins", action="store_true", dest="list_plugins",
                        help="print the names of the installed command plugins")
    parser.add_argument(
        "--locators", action="append", default=None, metavar="FILE",
        help="a locator file ({name: {by, value}}) loaded before the run, so action files find "
             "elements by name; repeatable",
    )
    parser.add_argument(
        "--isolate-files", action="store_true", dest="isolate_files",
        help="give every file its own variables and saved locators, so no file depends on what an earlier "
             "one left behind (one file at a time; --parallel-mode process already isolates)",
    )
    parser.add_argument(
        "--failure-bundle", type=str, default=None, dest="failure_bundle", metavar="DIR",
        help="write one zip per failed action into DIR: the action, the error and, with a browser open, "
             "a screenshot and the page's HTML",
    )
    parser.add_argument(
        "--backend", choices=BACKENDS, default=None,
        help="run every action file on this backend: its commands are translated before they run, and "
             "a file with a command that has no faithful equivalent there is refused",
    )
    parser.add_argument(
        "--step", action="store_true",
        help="pause before every action and at every WR_breakpoint: n runs it, c continues, v shows "
             "the variables, q stops (sequential runs only)",
    )
    parser.add_argument("--lint", type=str, default=None, metavar="PATH",
                        help="lint an action JSON file or directory; a warning exits 1")
    parser.add_argument("--list-commands", action="store_true", dest="list_commands",
                        help="print every registered WR_* command")
    parser.add_argument("--init", type=str, default=None, metavar="DIR",
                        help="write a starter workspace into DIR (existing files are kept)")
    parser.add_argument("--format", type=str, default=None, dest="format_path", metavar="PATH",
                        help="rewrite an action JSON file, or every one below a directory, in the "
                             "canonical layout")
    parser.add_argument("--format-check", action="store_true", dest="format_check",
                        help="with --format, change nothing and exit 1 when a file would change")
    parser.add_argument("--export-schema", type=str, default=None, dest="export_schema", metavar="FILE",
                        help="write the JSON schema of action files, for editors, to FILE")
    parser.add_argument("--export-command-reference", type=str, default=None,
                        dest="export_command_reference", metavar="FILE",
                        help="write the Markdown reference of every WR_* command to FILE")


def _add_run_args(parser: argparse.ArgumentParser) -> None:
    """What to run or validate: a file, a directory, a JSON string; parallelism; reports."""
    parser.add_argument("-e", "--execute_file", type=str, help="execute a single action JSON file")
    parser.add_argument("-d", "--execute_dir", type=str, help="execute all JSON files in a directory")
    parser.add_argument("--execute_str", type=str, help="execute a JSON action string directly")
    parser.add_argument("--agent-task", type=str, help="run a local browser agent task JSON file")
    parser.add_argument("--validate", type=str, help="validate a single action JSON file (no execute)")
    parser.add_argument("--validate_dir", type=str, help="validate all JSON files in a directory (no execute)")
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="when used with --execute_dir, run files concurrently (worker count)",
    )
    parser.add_argument(
        "--parallel-mode",
        type=str,
        default="thread",
        choices=("thread", "process", "async"),
        dest="parallel_mode",
        help=(
            "thread: shares the WebRunner globals (FAST, but UNSAFE for browser "
            "actions because webdriver wrappers are module-level singletons). "
            "process: each file runs in its own process for true isolation. "
            "async: files run concurrently on asyncio in one headless Chromium, each in its own "
            "browser context for the WR_apw_* commands (needs Playwright)"
        ),
    )
    parser.add_argument(
        "--report",
        type=str,
        help="after execution, generate JSON / HTML / XML / JUnit reports with this base name",
    )
    parser.add_argument(
        "--report-format", type=str, default=None, dest="report_format", metavar="LIST",
        help="comma-separated reports for --report: json, html, xml, junit (these four by default), "
             "allure (into BASE_allure/), interactive (BASE_interactive.html)",
    )
    parser.add_argument(
        "--merge-reports", type=str, nargs="+", default=None, dest="merge_reports",
        metavar=("OUT", "BASE"),
        help="merge the JSON and JUnit reports of the BASE names (as given to --report, e.g. one per "
             "shard) into OUT",
    )


def _add_dir_args(parser: argparse.ArgumentParser) -> None:
    """For ``--execute_dir``: tags, ledger and re-runs, watching, migration, sharding."""
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="comma-separated tags; only run files whose meta.tags contains one",
    )
    parser.add_argument(
        "--exclude-tag",
        type=str,
        default=None,
        dest="exclude_tag",
        help="comma-separated tags; skip files whose meta.tags contains any",
    )
    parser.add_argument(
        "--ledger",
        type=str,
        default=None,
        help="path to a JSON ledger; pass/fail per file is appended after each run",
    )
    parser.add_argument(
        "--rerun-failed",
        type=str,
        default=None,
        dest="rerun_failed",
        help="path to a previously-written ledger; only files with a failed status are run",
    )
    parser.add_argument(
        "--watch",
        type=str,
        default=None,
        help="watch a directory and re-run --execute_dir whenever JSON files change",
    )
    parser.add_argument(
        "--migrate",
        type=str,
        default=None,
        help="path to action JSON file or directory; rewrites legacy command names in place",
    )
    parser.add_argument(
        "--migrate-dry-run",
        action="store_true",
        dest="migrate_dry_run",
        help="with --migrate, only report changes without writing files",
    )
    parser.add_argument(
        "--shard",
        type=str,
        default=None,
        help=(
            "shard spec INDEX/TOTAL (e.g. 1/4) for distributed --execute_dir; "
            "files are partitioned deterministically by SHA-1 path hash"
        ),
    )


def _add_impact_args(parser: argparse.ArgumentParser) -> None:
    """``--affected-by`` / ``--changed-since`` / ``--impact-cache``: run only what a change can affect."""
    parser.add_argument(
        "--affected-by",
        action="append",
        default=None,
        dest="affected_by",
        metavar="KIND:VALUE",
        help=(
            "with --execute_dir, run only the files that use this locator / url / template / command "
            "(e.g. locator:login_button); repeatable; @file reads one KIND:VALUE per line"
        ),
    )
    parser.add_argument(
        "--changed-since",
        type=str,
        default=None,
        dest="changed_since",
        metavar="REF",
        help=(
            "with --execute_dir, run the action files changed in git since REF (REF...HEAD) and the files "
            "sharing a locator or template with them"
        ),
    )
    parser.add_argument(
        "--impact-cache",
        type=str,
        default=None,
        dest="impact_cache",
        metavar="PATH",
        help="cache file for the impact index of --affected-by / --changed-since; only changed files are parsed",
    )
