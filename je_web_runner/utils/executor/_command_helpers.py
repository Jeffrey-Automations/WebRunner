"""
命令轉接層的共用工具
Shared tools for the command adapters (``_commands_<theme>.py``): the modules that make a library written
for Python callers usable from an action file, where arguments and results are JSON values.

An adapter takes plain values (text, numbers, lists, objects), builds what the library needs, and returns
:func:`to_plain` of the result. One that reads the page takes the browser from :func:`browser_driver`
(imported by the adapters under its first name, ``selenium_driver``), which answers with the Selenium
driver or with a stand-in for one over the Playwright page; so such a command runs on either backend.
One that needs what only Selenium has (window handles, the BiDi connection) takes it from
:func:`selenium_only_driver`.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

from je_web_runner.utils.driver_dispatch.playwright_driver import PlaywrightDriver, playwright_page_is_open
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_PLAIN = (str, int, float, bool, type(None))
_PLAYWRIGHT = "playwright"


def _runs_on_playwright() -> bool:
    """Whether the executor was told to run its action lists on the Playwright backend."""
    from je_web_runner.utils.executor.action_executor import executor

    return executor.backend == _PLAYWRIGHT


def browser_driver(command: str) -> Any:
    """
    目前的瀏覽器：Selenium driver，或以 Playwright 頁面充當的替身
    The browser the action list is driving, as a Selenium driver.

    * Only a Selenium browser is open: its driver.
    * Only Playwright has a page: a :class:`~je_web_runner.utils.driver_dispatch.playwright_driver.
      PlaywrightDriver` over it, which offers the part of a Selenium driver the adapters use and raises
      ``SeleniumBackendRequired`` for the rest.
    * Both are open: the backend the executor runs on (``executor.backend``, set by ``--backend`` or
      ``Executor.set_backend``); Selenium when it names none.

    :raises WebRunnerWebDriverIsNoneException: when no browser was started; ``command`` names the caller.
    """
    driver = webdriver_wrapper_instance.current_webdriver
    if not playwright_page_is_open(playwright_wrapper_instance):
        if driver is None:
            raise WebRunnerWebDriverIsNoneException(f"{command} needs a browser; start one first")
        return driver
    if driver is not None and not _runs_on_playwright():
        return driver
    return PlaywrightDriver(command, playwright_wrapper_instance)


# The adapters and their tests import and patch the helper under this name, from when Selenium was the
# only browser it knew.
selenium_driver = browser_driver  # pylint: disable=invalid-name  # an alias of a function, kept for its importers


def selenium_only_driver(command: str, needs: str) -> Any:
    """
    The Selenium driver, for a command that uses what only a Selenium driver has.

    :param needs: what that is, for the message (``"Selenium window handles"``).
    :raises WebRunnerWebDriverIsNoneException: when no Selenium browser was started.
    """
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise WebRunnerWebDriverIsNoneException(
            f"{command} needs the Selenium backend ({needs}); start a Selenium browser first")
    return driver


def page_source(command: str) -> str:
    """The HTML of the current page."""
    return str(browser_driver(command).page_source)


def _plain_collection(value: Any) -> Any:
    """The second half of :func:`to_plain`: mappings, sequences, bytes, then ``str`` for the rest."""
    if isinstance(value, dict):
        # An enum key gives its value ("script"), not its repr ("AssetKind.SCRIPT").
        return {str(to_plain(key)): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_plain(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


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
    return _plain_collection(value)
