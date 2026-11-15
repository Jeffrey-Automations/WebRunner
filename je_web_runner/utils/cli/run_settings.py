"""
一次 CLI 執行的設定
The settings of one CLI run that live in the executor and the test record rather than in the argument
parser: recording, fail-fast, the retry policy, variables, the ``.env`` file. They come from the command
line and the project configuration, and are applied in the process that runs the files, which is why the
process pool hands them to each worker.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

from je_web_runner.utils.env_config.env_loader import load_env
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.flow.dataset import read_rows_file
from je_web_runner.utils.project_config.config import ProjectConfig
from je_web_runner.utils.test_record.test_record_class import test_record_instance


@dataclass(frozen=True)
class RunSettings:
    """What a run needs set up before its first action; picklable, so a worker process can receive it."""

    recording: bool = False
    fail_fast: bool = False
    env: str | None = None
    env_dir: str = "."
    retries: int | None = None
    retry_backoff: float = 0.0
    failure_screenshot_dir: str | None = None
    dataset: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)


def parse_variable(text: str) -> tuple[str, Any]:
    """
    ``NAME=VALUE`` of a ``--var`` flag. ``VALUE`` is read as JSON when it is JSON (``3``, ``true``,
    ``[1, 2]``, ``"quoted"``), else it is the text itself.
    """
    name, separator, raw = text.partition("=")
    if not separator or not name.strip():
        raise WebRunnerExecuteException(f"--var takes NAME=VALUE, got {text!r}")
    try:
        value: Any = json.loads(raw)
    except ValueError:
        value = raw
    return name.strip(), value


def build_run_settings(config: ProjectConfig, report: str | None, fail_fast: bool, env: str | None,
                       env_dir: str | None, variables: Sequence[str] | None) -> RunSettings:
    """The settings of a run: each flag that was given, else the project configuration's value."""
    merged = dict(config.vars)
    merged.update(parse_variable(text) for text in variables or ())
    return RunSettings(
        recording=bool(report),
        fail_fast=bool(fail_fast or config.fail_fast),
        env=env or config.env,
        env_dir=env_dir or config.env_dir,
        retries=config.retries,
        retry_backoff=config.retry_backoff,
        failure_screenshot_dir=config.failure_screenshot_dir,
        variables=merged,
    )


def apply_run_settings(settings: RunSettings) -> None:
    """
    Set this process up for the run. Recording is only ever turned on here: a run without ``--report``
    leaves it as the action files set it. The ``.env`` file is loaded before the variables, so a variable
    can be ``${ENV.KEY}``.
    """
    if settings.recording:
        # The report is built from the records, and recording is off until something turns it on.
        test_record_instance.set_record_enable(True)
    if settings.env is not None:
        load_env(settings.env, settings.env_dir)
    if settings.fail_fast:
        executor.set_fail_fast(True)
    if settings.retries is not None:
        executor.set_retry_policy(settings.retries, settings.retry_backoff)
    if settings.failure_screenshot_dir is not None:
        executor.set_failure_screenshot_dir(settings.failure_screenshot_dir)
    if settings.dataset is not None:
        # Read here, once: the operator named this file, so the fence on action files does not apply.
        executor.default_dataset = read_rows_file(settings.dataset)
    for name, value in settings.variables.items():
        executor.variables.set(name, executor.variables.expand(value))
