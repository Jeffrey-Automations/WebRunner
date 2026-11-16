"""
動作失敗時自動產生 failure bundle
The failure bundle the executor writes when an action fails and a bundle directory is set: one zip per
failed action holding the action, the error, the file it came from and, when a browser is open, a
screenshot and the page's HTML.

The action is stored as it is written in the file, with its ``${placeholders}`` not replaced, so the
action itself does not carry a secret that arrives through a variable or the environment. The error
text, the page's HTML and the screenshot show whatever the run produced, values included: a bundle is
to be handled like a log.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from je_web_runner.utils.failure_bundle.bundle import FailureBundle
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


def selenium_page_html() -> str | None:
    """The HTML of the current Selenium page, or None when no driver is open or it cannot be read."""
    from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
    try:
        driver = webdriver_wrapper_instance.current_webdriver
        return None if driver is None else str(driver.page_source)
    except Exception as error:  # pylint: disable=broad-exception-caught  # best-effort capture after a failure
        web_runner_logger.warning(f"failure bundle: Selenium page source unavailable: {error!r}")
        return None


def playwright_page_html() -> str | None:
    """The HTML of the current Playwright page, or None when no page is open or it cannot be read."""
    from je_web_runner.webdriver import playwright_wrapper
    try:
        wrapper = playwright_wrapper.playwright_wrapper_instance
        return str(wrapper.page.content()) if wrapper._pages else None  # pylint: disable=protected-access
    except Exception as error:  # pylint: disable=broad-exception-caught  # best-effort capture after a failure
        web_runner_logger.warning(f"failure bundle: Playwright page content unavailable: {error!r}")
        return None


def write_action_failure_bundle(target: Path, action: Any, error_text: str, source_file: str | None = None,
                                screenshot: bytes | None = None, page_html: str | None = None) -> str | None:
    """
    Write the bundle of one failed action to ``target`` and return its path, or None when it cannot be
    written (the failure of the action is what matters; a bundle that cannot be saved is only logged).
    """
    name = str(action[0]) if isinstance(action, list) and action else "unknown"
    bundle = FailureBundle(test_name=name, error_repr=error_text, metadata={"file": source_file})
    bundle.add_text("action.json", json.dumps(action, ensure_ascii=False, indent=2, default=str))
    bundle.add_text("error.txt", error_text)
    if screenshot:
        bundle.add_screenshot(screenshot)
    if page_html:
        bundle.add_dom(page_html)
    try:
        return str(bundle.write(target))
    except OSError as error:
        web_runner_logger.error(f"failure bundle write failed: {error!r}")
        return None
