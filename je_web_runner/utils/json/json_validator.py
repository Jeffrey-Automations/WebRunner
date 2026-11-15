"""
驗證動作 JSON 結構，於執行前提前報錯。
Validate action JSON structure to surface errors before execution.

Action format accepted by the executor:
- top-level value is either a ``list`` of actions, or a ``dict`` with key
  ``"webdriver_wrapper"`` whose value is a list of actions.
- each action is itself a list of length 1, 2, or 3:
  - ``[command_name]``                              -- no-argument call
  - ``[command_name, {kwargs}]``                    -- keyword-argument call
  - ``[command_name, [positional]]``                -- positional-argument call
  - ``[command_name, [positional], {kwargs}]``      -- mixed positional + kwargs
- the actions a block command holds (``WR_if`` ``then`` / ``otherwise``, the ``do`` of the loops,
  ``WR_try`` …) and those of ``meta.setup`` / ``meta.teardown`` have the same shape.
"""
from __future__ import annotations

from typing import Iterable

from je_web_runner.utils.exception.exception_tags import executor_data_error, executor_list_error
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.flow.structure import misshapen_blocks, nested_actions
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

ACTION_LIST_KEY = "webdriver_wrapper"


def _extract_action_list(data: list | dict) -> list:
    """Pull the action list out of a top-level dict, or accept a list directly."""
    if isinstance(data, dict):
        action_list = data.get(ACTION_LIST_KEY)
        if action_list is None:
            raise WebRunnerExecuteException(
                f"{executor_list_error}: missing key '{ACTION_LIST_KEY}'"
            )
        return action_list
    if isinstance(data, list):
        return data
    raise WebRunnerExecuteException(
        f"{executor_list_error}: top-level must be list or dict, got {type(data).__name__}"
    )


def _validate_single_action(action: object, index: int | str) -> None:
    """Validate one action entry; raise on first problem."""
    if not isinstance(action, list):
        raise WebRunnerExecuteException(
            f"{executor_data_error}: action #{index} must be a list, got {type(action).__name__}"
        )
    if len(action) not in (1, 2, 3):
        raise WebRunnerExecuteException(
            f"{executor_data_error}: action #{index} must have 1, 2, or 3 elements, "
            f"got {len(action)}"
        )
    if not isinstance(action[0], str) or not action[0]:
        raise WebRunnerExecuteException(
            f"{executor_data_error}: action #{index} command name must be a non-empty string"
        )
    if len(action) == 2 and not isinstance(action[1], (dict, list, tuple)):
        raise WebRunnerExecuteException(
            f"{executor_data_error}: action #{index} arguments must be dict/list/tuple, "
            f"got {type(action[1]).__name__}"
        )
    if len(action) == 3:
        positional, kwargs = action[1], action[2]
        if not isinstance(positional, (list, tuple)):
            raise WebRunnerExecuteException(
                f"{executor_data_error}: action #{index} 3-element form requires "
                f"a positional list/tuple in slot 1, got {type(positional).__name__}"
            )
        if not isinstance(kwargs, dict):
            raise WebRunnerExecuteException(
                f"{executor_data_error}: action #{index} 3-element form requires "
                f"a kwargs dict in slot 2, got {type(kwargs).__name__}"
            )


def _validate_blocks(action: list, label: str) -> None:
    """Validate the actions ``action`` holds, and theirs; ``label`` names ``action`` in the error."""
    for key in misshapen_blocks(action):
        raise WebRunnerExecuteException(
            f"{executor_data_error}: action #{label} {key} must be a list of actions")
    for location, nested in nested_actions(action, label):
        _validate_single_action(nested, location)
        _validate_blocks(nested, location)


def _validate_hooks(data: list | dict) -> None:
    """Validate the actions of ``meta.setup`` and ``meta.teardown`` of an object document."""
    meta = data.get("meta") if isinstance(data, dict) else None
    if not isinstance(meta, dict):
        return
    for key in ("setup", "teardown"):
        hook = meta.get(key)
        if hook is None:
            continue
        if not isinstance(hook, list):
            raise WebRunnerExecuteException(f"{executor_list_error}: meta.{key} must be a list of actions")
        for index, action in enumerate(hook):
            label = f"meta.{key}[{index}]"
            _validate_single_action(action, label)
            _validate_blocks(action, label)


def validate_action_json(data: list | dict) -> bool:
    """
    驗證動作 JSON 是否符合執行器格式
    Validate that ``data`` matches the executor action format.

    :param data: 解析後的 JSON 資料 / parsed JSON value
    :return: True 若通過驗證 / True if valid
    :raises WebRunnerExecuteException: 結構錯誤時 / when the structure is invalid
    """
    web_runner_logger.info("validate_action_json")
    action_list = _extract_action_list(data)
    if not isinstance(action_list, list) or len(action_list) == 0:
        raise WebRunnerExecuteException(executor_list_error)
    for index, action in enumerate(action_list):
        _validate_single_action(action, index)
        _validate_blocks(action, str(index))
    _validate_hooks(data)
    return True


def validate_action_file(json_file_path: str) -> bool:
    """
    讀取並驗證動作 JSON 檔案
    Read and validate an action JSON file.

    :param json_file_path: 檔案路徑 / path to the action JSON file
    :return: True 若通過驗證 / True if valid
    """
    web_runner_logger.info(f"validate_action_file: {json_file_path}")
    return validate_action_json(read_action_json(json_file_path))


def validate_action_files(json_file_paths: Iterable[str]) -> bool:
    """
    驗證一組動作 JSON 檔案，全部通過才回傳 True
    Validate a batch of action JSON files; returns True only if all pass.
    """
    for path in json_file_paths:
        validate_action_file(path)
    return True
