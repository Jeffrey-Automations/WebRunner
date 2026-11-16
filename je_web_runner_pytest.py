"""
pytest 的掛鉤：選項與動作檔的收集
The pytest hooks of the plugin: its options, and which files it collects.

This module imports only the standard library and pytest, and nothing else of WebRunner, so loading it adds
nothing to a pytest run; :mod:`je_web_runner.pytest_plugin.nodes` (and with it the executor) is imported
only when a ``.json`` file is found below a path the project opted in with.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

INI_PATHS = "webrunner_action_paths"
OPTION_PATHS = "webrunner_actions"
OPTION_FAIL_FAST = "webrunner_fail_fast"
MARKER = "webrunner"
_ROOTS = pytest.StashKey[tuple]()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Declare the ini option and the two command-line options; none of them is set by default."""
    group = parser.getgroup("webrunner", "WebRunner action files")
    group.addoption(
        "--webrunner-actions", action="append", default=[], dest=OPTION_PATHS, metavar="PATH",
        help="collect the WebRunner action files (.json) at PATH, a file or a directory, as tests; repeatable")
    group.addoption(
        "--webrunner-fail-fast", action="store_true", default=False, dest=OPTION_FAIL_FAST,
        help="stop each WebRunner action file at its first failed action")
    parser.addini(
        INI_PATHS, type="args", default=[],
        help="files or directories, relative to the rootdir, whose WebRunner action files are collected as tests")


def _resolved(base: Path, entries: list, origin: str) -> list:
    """Every entry as an absolute path below ``base``; a path that does not exist is a usage error."""
    paths = []
    for entry in entries:
        path = (base / str(entry)).resolve()
        if not path.exists():
            raise pytest.UsageError(f"{origin}: no such file or directory: {entry}")
        paths.append(path)
    return paths


def _covers(argument: str, base: Path, path: Path) -> bool:
    """Whether the collection argument ``argument`` (``path`` or ``path::name``) already holds ``path``."""
    start = (base / argument.split("::", 1)[0]).resolve()
    return start == path or start in path.parents


def _add_arguments(config: pytest.Config, paths: list) -> None:
    """Add every path of ``paths`` that the collection arguments do not hold yet."""
    base = Path(str(config.invocation_params.dir))
    for path in paths:
        if not any(_covers(argument, base, path) for argument in config.args):
            config.args.append(str(path))


def _explicit_arguments(config: pytest.Config) -> bool:
    """Whether the paths pytest collects were given on the command line."""
    source = getattr(config, "args_source", None)
    return source is not None and source == getattr(pytest.Config.ArgsSource, "ARGS", None)


def pytest_configure(config: pytest.Config) -> None:
    """Note the opted-in paths; with none of them the plugin stays inert."""
    from_ini = _resolved(config.rootpath, config.getini(INI_PATHS), f"ini option {INI_PATHS}")
    from_option = _resolved(
        Path(str(config.invocation_params.dir)), config.getoption(OPTION_PATHS), "--webrunner-actions")
    roots = tuple(sorted(set(from_ini) | set(from_option)))
    config.stash[_ROOTS] = roots
    if not roots:
        return
    config.addinivalue_line("markers", f"{MARKER}: a WebRunner action file collected as a test")
    _add_arguments(config, sorted(set(from_option)))
    if not _explicit_arguments(config):
        _add_arguments(config, sorted(set(from_ini)))


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> Any:
    """Collect ``file_path`` when it is a ``.json`` action document below an opted-in path."""
    roots = parent.config.stash.get(_ROOTS, ())
    if not roots or file_path.suffix.lower() != ".json":
        return None
    path = file_path.resolve()
    if not any(root == path or root in path.parents for root in roots):
        return None
    # Imported here, not at the top: it loads the executor, which only an opted-in project should pay for.
    from je_web_runner.pytest_plugin.nodes import collect_action_file  # pylint: disable=import-outside-toplevel
    return collect_action_file(
        parent, file_path, marker=MARKER, fail_fast=bool(parent.config.getoption(OPTION_FAIL_FAST)))
