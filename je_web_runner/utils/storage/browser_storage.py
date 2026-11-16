"""
瀏覽器端 Storage 操作命令：local/session storage 與 IndexedDB 清除。
Browser-side storage helpers: localStorage / sessionStorage CRUD plus
IndexedDB clear. Built on top of the active driver's script-execution API,
so they work without backend-specific shims.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class StorageError(WebRunnerException):
    """Raised when a storage command cannot proceed."""


def _selenium_evaluate(script: str, *args) -> Any:
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise StorageError("no Selenium driver active")
    return driver.execute_script(script, *args)


def _playwright_evaluate(expression: str, arg: Any = None) -> Any:
    if arg is None:
        return playwright_wrapper_instance.page.evaluate(expression)
    return playwright_wrapper_instance.page.evaluate(expression, arg)


# ----- Selenium -----------------------------------------------------------

def selenium_local_storage_set(key: str, value: str) -> None:
    """Set ``key`` to ``value`` in localStorage through the Selenium driver."""
    web_runner_logger.info(f"local_storage_set: {key}")
    _selenium_evaluate("window.localStorage.setItem(arguments[0], arguments[1]);", key, value)


def selenium_local_storage_get(key: str) -> str | None:
    """Return the localStorage value of ``key`` (``None`` when absent) through the Selenium driver."""
    return _selenium_evaluate("return window.localStorage.getItem(arguments[0]);", key)


def selenium_local_storage_remove(key: str) -> None:
    """Remove ``key`` from localStorage through the Selenium driver."""
    _selenium_evaluate("window.localStorage.removeItem(arguments[0]);", key)


def selenium_local_storage_clear() -> None:
    """Empty localStorage through the Selenium driver."""
    _selenium_evaluate("window.localStorage.clear();")


def selenium_local_storage_all() -> dict:
    """Return every localStorage key and value as a dict, through the Selenium driver."""
    script = (
        "var out = {};"
        "for (var i = 0; i < window.localStorage.length; i++) {"
        "  var k = window.localStorage.key(i);"
        "  out[k] = window.localStorage.getItem(k);"
        "} return out;"
    )
    return _selenium_evaluate(script) or {}


def selenium_session_storage_set(key: str, value: str) -> None:
    """Set ``key`` to ``value`` in sessionStorage through the Selenium driver."""
    _selenium_evaluate("window.sessionStorage.setItem(arguments[0], arguments[1]);", key, value)


def selenium_session_storage_get(key: str) -> str | None:
    """Return the sessionStorage value of ``key`` (``None`` when absent) through the Selenium driver."""
    return _selenium_evaluate("return window.sessionStorage.getItem(arguments[0]);", key)


def selenium_session_storage_clear() -> None:
    """Empty sessionStorage through the Selenium driver."""
    _selenium_evaluate("window.sessionStorage.clear();")


def selenium_indexed_db_drop(db_name: str) -> None:
    """Drop an IndexedDB database by name. Best-effort (Promise resolution skipped)."""
    _selenium_evaluate(
        "try { window.indexedDB.deleteDatabase(arguments[0]); } catch (e) {}",
        db_name,
    )


# ----- Playwright ---------------------------------------------------------

def playwright_local_storage_set(key: str, value: str) -> None:
    """Set ``key`` to ``value`` in localStorage on the Playwright page."""
    web_runner_logger.info(f"playwright local_storage_set: {key}")
    _playwright_evaluate(
        "kv => window.localStorage.setItem(kv[0], kv[1])",
        [key, value],
    )


def playwright_local_storage_get(key: str) -> str | None:
    """Return the localStorage value of ``key`` (``None`` when absent) on the Playwright page."""
    return _playwright_evaluate("k => window.localStorage.getItem(k)", key)


def playwright_local_storage_remove(key: str) -> None:
    """Remove ``key`` from localStorage on the Playwright page."""
    _playwright_evaluate("k => window.localStorage.removeItem(k)", key)


def playwright_local_storage_clear() -> None:
    """Empty localStorage on the Playwright page."""
    _playwright_evaluate("() => window.localStorage.clear()")


def playwright_local_storage_all() -> dict:
    """Return every localStorage key and value of the Playwright page as a dict."""
    expression = (
        "() => { var out = {}; "
        "for (var i = 0; i < window.localStorage.length; i++) {"
        "  var k = window.localStorage.key(i);"
        "  out[k] = window.localStorage.getItem(k);"
        "} return out; }"
    )
    return _playwright_evaluate(expression) or {}


def playwright_session_storage_set(key: str, value: str) -> None:
    """Set ``key`` to ``value`` in sessionStorage on the Playwright page."""
    _playwright_evaluate(
        "kv => window.sessionStorage.setItem(kv[0], kv[1])",
        [key, value],
    )


def playwright_session_storage_get(key: str) -> str | None:
    """Return the sessionStorage value of ``key`` (``None`` when absent) on the Playwright page."""
    return _playwright_evaluate("k => window.sessionStorage.getItem(k)", key)


def playwright_session_storage_clear() -> None:
    """Empty sessionStorage on the Playwright page."""
    _playwright_evaluate("() => window.sessionStorage.clear()")


def playwright_indexed_db_drop(db_name: str) -> None:
    """Ask the Playwright page to delete the IndexedDB database ``db_name``;
    errors in the page are swallowed and completion is not awaited.
    """
    _playwright_evaluate(
        "name => { try { indexedDB.deleteDatabase(name); } catch (e) {} }",
        db_name,
    )
