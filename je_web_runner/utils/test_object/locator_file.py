"""
共用的定位器檔
A shared locator file: logical names for the elements a project's action files use, in one place.

.. code-block:: json

    {
      "login_button": {"by": "css selector", "value": "#login"},
      "user_field": {"by": "id", "value": "user"}
    }

Each entry becomes a test object stored under its logical name, so ``WR_find_recorded_element`` /
``WR_pw_find_element_with_test_object_record`` and the other recorded-name commands of both backends take
``login_button`` where they used to need the locator value itself. When the page changes, only this file does.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.test_object.test_object_class import TestObject, type_list
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record

DEFAULT_STRATEGY = "CSS_SELECTOR"


class LocatorFileError(WebRunnerException):
    """Raised when a locator file cannot be read or an entry is not a locator."""


def strategy_name(by: str) -> str:
    """
    The ``By`` name of a strategy written as ``"css selector"``, ``"CSS_SELECTOR"``, ``"xpath"`` …

    :raises LocatorFileError: when Selenium has no such strategy.
    """
    name = str(by).strip().upper().replace(" ", "_")
    if name not in type_list:
        raise LocatorFileError(f"unknown locator strategy {by!r}; use one of {', '.join(sorted(type_list))}")
    return name


def save_locator(name: str, value: str, by: str = DEFAULT_STRATEGY) -> str:
    """
    以邏輯名稱儲存定位器
    Store the locator ``value`` (with the strategy ``by``, CSS selector by default) under the logical
    ``name``; the recorded-name commands of both backends then find the element by ``name``. Return the name.
    """
    if not isinstance(name, str) or not name.strip():
        raise LocatorFileError(f"a locator needs a name, got {name!r}")
    if not isinstance(value, str) or not value:
        raise LocatorFileError(f"locator {name!r} needs a value, got {value!r}")
    test_object_record.test_object_record_dict[name] = TestObject(value, strategy_name(by))
    return name


def _entry(name: str, entry: Any) -> tuple[str, str]:
    """``(value, by)`` of one entry of a locator file."""
    if not isinstance(entry, dict) or "value" not in entry:
        raise LocatorFileError(f"locator {name!r} must be an object with \"value\" (and optionally \"by\")")
    unknown = sorted(set(entry) - {"by", "value"})
    if unknown:
        raise LocatorFileError(f"locator {name!r} has unknown key(s) {', '.join(unknown)}")
    return entry["value"], entry.get("by", DEFAULT_STRATEGY)


def read_locators(path: str | Path) -> dict[str, tuple[str, str]]:
    """
    The locators of the JSON file at ``path`` as ``{name: (value, strategy name)}``; nothing is stored.

    :raises LocatorFileError: when the file cannot be read or holds something else than locators.
    """
    try:
        with open(path, encoding="utf-8") as locator_file:
            document = json.load(locator_file)
    except (OSError, ValueError) as error:
        raise LocatorFileError(f"cannot read locator file {path}: {error}") from error
    if not isinstance(document, dict):
        raise LocatorFileError(f"locator file {path} must be an object of name: locator")
    locators = {}
    for name, entry in document.items():
        value, by = _entry(name, entry)
        locators[name] = (value, strategy_name(by))
    return locators


def load_locators(path: str | Path) -> list[str]:
    """
    Store every locator of the file at ``path`` and return their names, sorted. The file is checked as a
    whole first, so a bad entry stores nothing.
    """
    locators = read_locators(path)
    for name, (value, by) in locators.items():
        save_locator(name, value, by)
    return sorted(locators)
