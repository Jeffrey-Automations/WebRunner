"""
以原始 selector 找元素的 Playwright 命令
The Playwright commands that look an element up by a raw selector and make it current, the twins of
``WR_find_element_by`` / ``WR_find_elements_by``. They are functions over the shared wrapper like the
``pw_*`` functions of :mod:`playwright_wrapper`, kept here because that module is at its size limit.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance


def pw_find_element_by(selector: str, by: str = "css selector") -> Any:
    """
    Find by a raw selector (``by``: ``css selector``, ``xpath``, ``id`` ...) and make the first match the
    current element; it does not wait, and fails when nothing matches.
    """
    return playwright_wrapper_instance.find_element_by(selector, by)


def pw_find_elements_by(selector: str, by: str = "css selector") -> list[Any]:
    """
    Find every match of a raw selector; they become the current element list (empty when nothing
    matches) and the current element stays as it is.
    """
    return playwright_wrapper_instance.find_elements_by(selector, by)
