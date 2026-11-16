"""
命令轉接層的共用工具
Shared tools for the command adapters (``_commands_<theme>.py``): the modules that make a library written
for Python callers usable from an action file, where arguments and results are JSON values.

An adapter takes plain values (text, numbers, lists, objects), builds what the library needs, and returns
:func:`to_plain` of the result. One that reads the page takes it from :func:`selenium_driver`.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from pathlib import Path
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_PLAIN = (str, int, float, bool, type(None))


def selenium_driver(command: str) -> Any:
    """
    The Selenium browser the action list is driving.

    :raises WebRunnerWebDriverIsNoneException: when no browser was started; ``command`` names the caller.
    """
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise WebRunnerWebDriverIsNoneException(f"{command} needs a browser; start one first")
    return driver


def page_source(command: str) -> str:
    """The HTML of the current page."""
    return str(selenium_driver(command).page_source)


def to_plain(value: Any) -> Any:
    """
    ``value`` as JSON values: dataclasses and objects with ``to_dict`` become objects, enums their value,
    sets and tuples lists, paths and bytes text. Anything else that is not a JSON value becomes its ``str``.
    """
    if isinstance(value, Enum):
        return to_plain(value.value)
    if isinstance(value, _PLAIN):
        return value
    if callable(getattr(value, "to_dict", None)):
        return to_plain(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_plain(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        # An enum key gives its value ("script"), not its repr ("AssetKind.SCRIPT").
        return {str(to_plain(key)): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_plain(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Path):
        return str(value)
    return str(value)
