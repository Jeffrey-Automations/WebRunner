"""
專案設定檔
Project configuration: defaults for a run, read from ``webrunner.toml`` or the ``[tool.webrunner]`` table of
``pyproject.toml`` in the working directory. A command-line flag wins over the file, the file over the
built-in default; without a file nothing changes.

.. code-block:: toml

    # webrunner.toml (in pyproject.toml the same keys go under [tool.webrunner])
    env = "staging"                 # load .env.staging before the run
    fail_fast = true
    retries = 1
    report = "reports/run"
    ledger = ".webrunner/ledger.json"
    parallel = 4
    parallel_mode = "process"
    exclude_tag = ["sub-flow"]

    [vars]
    base = "${ENV.BASE_URL}"
    user = "alice"
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerException

CONFIG_FILE = "webrunner.toml"
PYPROJECT_FILE = "pyproject.toml"
PARALLEL_MODES = ("thread", "process", "async")
MAX_RETRIES = 100


class ProjectConfigError(WebRunnerException):
    """Raised when the configuration file cannot be read or holds a wrong key or value."""


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_list(value: Any) -> bool:
    return isinstance(value, list) and all(_text(item) for item in value)


def _whole(minimum: int, maximum: int) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _seconds(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


# key -> (check, what a valid value is)
_KEYS: dict[str, tuple[Callable[[Any], bool], str]] = {
    "vars": (lambda value: isinstance(value, dict), "a table of name = value"),
    "env": (_text, "an environment name"),
    "env_dir": (_text, "a directory"),
    "fail_fast": (lambda value: isinstance(value, bool), "true or false"),
    "retries": (_whole(0, MAX_RETRIES), f"an integer from 0 to {MAX_RETRIES}"),
    "retry_backoff": (_seconds, "a number of seconds"),
    "failure_screenshot_dir": (_text, "a directory"),
    "report": (_text, "a report base name"),
    "ledger": (_text, "a file path"),
    "parallel": (_whole(1, 256), "an integer from 1 to 256"),
    "parallel_mode": (lambda value: value in PARALLEL_MODES, "one of " + ", ".join(PARALLEL_MODES)),
    "tag": (_text_list, "a list of tags"),
    "exclude_tag": (_text_list, "a list of tags"),
}


@dataclass(frozen=True)
class ProjectConfig:
    """The settings of a configuration file; a field left out of the file keeps its default here."""

    source: str | None = None
    vars: dict[str, Any] = field(default_factory=dict)
    env: str | None = None
    env_dir: str = "."
    fail_fast: bool | None = None
    retries: int | None = None
    retry_backoff: float = 0.0
    failure_screenshot_dir: str | None = None
    report: str | None = None
    ledger: str | None = None
    parallel: int | None = None
    parallel_mode: str | None = None
    tag: list[str] = field(default_factory=list)
    exclude_tag: list[str] = field(default_factory=list)

    def cli_defaults(self) -> dict[str, Any]:
        """The values that replace the command line's built-in defaults (only what the file sets)."""
        defaults: dict[str, Any] = {}
        for name in ("report", "ledger", "parallel", "parallel_mode"):
            if getattr(self, name) is not None:
                defaults[name] = getattr(self, name)
        if self.tag:
            defaults["tag"] = ",".join(self.tag)
        if self.exclude_tag:
            defaults["exclude_tag"] = ",".join(self.exclude_tag)
        return defaults


def _table(path: Path) -> dict[str, Any]:
    """The settings table of ``path``: the whole file, or ``[tool.webrunner]`` of a pyproject.toml."""
    try:
        with open(path, "rb") as config_file:
            document = tomllib.load(config_file)
    except OSError as error:
        raise ProjectConfigError(f"cannot read {path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ProjectConfigError(f"{path} is not valid TOML: {error}") from error
    if path.name != PYPROJECT_FILE:
        return document
    table = document.get("tool", {}).get("webrunner", {})
    if not isinstance(table, dict):
        raise ProjectConfigError(f"{path}: [tool.webrunner] must be a table")
    return table


def load_config(path: str | Path) -> ProjectConfig:
    """
    讀取設定檔
    Read the configuration file at ``path`` (``webrunner.toml``, or a ``pyproject.toml`` whose
    ``[tool.webrunner]`` table is used).

    :raises ProjectConfigError: when the file cannot be read, a key is unknown or a value has the wrong type.
    """
    file_path = Path(path)
    table = _table(file_path)
    unknown = sorted(set(table) - set(_KEYS))
    if unknown:
        raise ProjectConfigError(
            f"{file_path}: unknown setting(s) {', '.join(unknown)}; known: {', '.join(sorted(_KEYS))}")
    for key, value in table.items():
        check, expected = _KEYS[key]
        if not check(value):
            raise ProjectConfigError(f"{file_path}: {key} must be {expected}, got {value!r}")
    return ProjectConfig(source=str(file_path), **table)


def find_config(directory: str | Path = ".") -> Path | None:
    """``webrunner.toml`` in ``directory``, else its ``pyproject.toml`` when that has ``[tool.webrunner]``."""
    base = Path(directory)
    own = base / CONFIG_FILE
    if own.is_file():
        return own
    shared = base / PYPROJECT_FILE
    if not shared.is_file():
        return None
    try:
        return shared if _table(shared) else None
    except ProjectConfigError:
        # A pyproject.toml that cannot be read is not a WebRunner configuration; the run goes on.
        return None


def discover_config(directory: str | Path = ".") -> ProjectConfig:
    """The configuration of ``directory``, or an empty one when it has no configuration file."""
    found = find_config(directory)
    return ProjectConfig() if found is None else load_config(found)
