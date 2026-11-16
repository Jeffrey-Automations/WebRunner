"""
以 Playwright 頁面充當 Selenium driver
A stand-in for a Selenium driver over the current Playwright page.

The command adapters and the libraries behind them were written against a Selenium driver, and use a
small part of it: run a script, read the page, its cookies and a screenshot, send a DevTools command.
:class:`PlaywrightDriver` offers that part with Selenium's meaning, so the same command gives the same
result when the browser is Playwright's:

=============================== =====================================================================
``execute_script(body, *args)``  the body of a function, ``arguments[i]``, the value it ``return``\\ s
``execute_async_script(...)``    the same, the value is what the body passes to its last argument
``page_source``                  the HTML of the current frame's root element, as Chrome's driver gives
``current_url``, ``title``       of the page
``get_screenshot_as_png()``      the viewport as PNG bytes; ``save_screenshot(path)`` writes it
``get_cookies()``                the cookies of the page's URL, with Selenium's field names
``execute_cdp_cmd(cmd, params)`` through the wrapper's CDP session (Chromium only, as on Selenium)
``get(url)``                     navigate the page (and leave any selected frame)
``set_window_size(w, h)``        the viewport size: Playwright has no OS window to size
=============================== =====================================================================

It goes through ``playwright_wrapper_instance``: scripts and the page source act in the frame selected
with ``WR_pw_switch_to_frame``, like the ``WR_pw_*`` commands, and everything follows the current page
and browser. Playwright itself is not imported here.

Anything else a Selenium driver has (``get_log``, ``window_handles``, ``switch_to``, ``find_element`` …)
raises :class:`SeleniumBackendRequired`, which names what was asked for. ``hasattr`` does not hide it:
only ``AttributeError`` means "no such attribute", and that is kept for private names.
"""
from __future__ import annotations

from typing import Any, Callable

from je_web_runner.utils.driver_dispatch.js_eval import DriverDispatchError
from je_web_runner.utils.driver_dispatch.selenium_script import as_async_function, as_function
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance

# What a Selenium Chrome answers for the page source: the root element, without the doctype that
# Playwright's ``content()`` puts in front of it.
_PAGE_SOURCE = "() => document.documentElement.outerHTML"
_COOKIE_FIELDS = ("name", "value", "domain", "path", "httpOnly", "secure", "sameSite")
_SESSION_COOKIE = -1


class SeleniumBackendRequired(DriverDispatchError):
    """Raised when a command asks the Playwright stand-in for something only a Selenium driver has."""


def selenium_cookie(cookie: dict[str, Any]) -> dict[str, Any]:
    """A Playwright cookie as Selenium gives it: ``expiry`` in whole seconds, absent for a session cookie."""
    converted = {field: cookie[field] for field in _COOKIE_FIELDS if field in cookie}
    expires = cookie.get("expires", _SESSION_COOKIE)
    if isinstance(expires, (int, float)) and expires != _SESSION_COOKIE:
        converted["expiry"] = int(expires)
    return converted


def _wrapper_cdp(method: str, params: dict[str, Any]) -> Any:
    from je_web_runner.utils.cdp.cdp_commands import playwright_cdp

    return playwright_cdp(method, params)


class PlaywrightDriver:
    """The part of a Selenium driver the command adapters use, over the current Playwright page."""

    def __init__(self, command: str = "this command", wrapper: Any = None,
                 cdp: Callable[[str, dict[str, Any]], Any] | None = None) -> None:
        """
        :param command: the command that asked for the browser; named in :class:`SeleniumBackendRequired`.
        :param wrapper: the Playwright wrapper (``playwright_wrapper_instance`` when None).
        :param cdp: sends a DevTools command (the wrapper's CDP session when None).
        """
        self._command = command
        self._wrapper = playwright_wrapper_instance if wrapper is None else wrapper
        self._cdp = _wrapper_cdp if cdp is None else cdp

    @property
    def _frame(self) -> Any:
        """The frame the selector commands act in, or the page."""
        return self._wrapper._target  # pylint: disable=protected-access  # the frame scope its commands use

    # ----- scripts -------------------------------------------------------

    def execute_script(self, script: str, *args: Any) -> Any:
        """Run the body ``script`` with ``args`` as ``arguments`` and return what it returns."""
        return self._frame.evaluate(as_function(script), list(args))

    def execute_async_script(self, script: str, *args: Any) -> Any:
        """Run the body ``script``; its value is what it passes to the callback after ``args``."""
        return self._frame.evaluate(as_async_function(script), list(args))

    # ----- the page ------------------------------------------------------

    @property
    def page_source(self) -> str:
        """The HTML of the current frame."""
        return self._frame.evaluate(_PAGE_SOURCE)

    @property
    def current_url(self) -> str:
        """The URL of the page."""
        return self._wrapper.page.url

    @property
    def title(self) -> str:
        """The title of the page."""
        return self._wrapper.page.title()

    def get(self, url: str) -> None:
        """Navigate the page to ``url``; a selected frame is left, as a navigation does on Selenium."""
        # Not switch_to_main_frame(): that adds a step to the test record, and Selenium's get adds none.
        self._wrapper._frame = None  # pylint: disable=protected-access  # what the wrapper's own to_url does
        self._wrapper.page.goto(url)

    def set_window_size(self, width: int, height: int) -> None:
        """Set the viewport to ``width`` x ``height`` (Playwright has no OS window to size)."""
        self._wrapper.page.set_viewport_size({"width": int(width), "height": int(height)})

    # ----- screenshots, cookies, DevTools --------------------------------

    def get_screenshot_as_png(self) -> bytes:
        """The viewport as PNG bytes."""
        return self._wrapper.page.screenshot()

    def save_screenshot(self, filename: str) -> bool:
        """Write the viewport as a PNG file; True, as Selenium answers when the file was written."""
        self._wrapper.page.screenshot(path=str(filename))
        return True

    def get_cookies(self) -> list[dict[str, Any]]:
        """The cookies the page's URL would be sent, in Selenium's shape."""
        return [selenium_cookie(cookie) for cookie in self._wrapper.context.cookies(self._wrapper.page.url)]

    def execute_cdp_cmd(self, cmd: str, cmd_args: dict[str, Any] | None = None) -> Any:
        """Send the DevTools command ``cmd`` to the page (Chromium only) and return its result."""
        return self._cdp(cmd, dict(cmd_args or {}))

    # ----- everything else -----------------------------------------------

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        raise SeleniumBackendRequired(
            f"{self._command} uses the Selenium driver's {name!r}, which the Playwright backend does not "
            "have; run it with a Selenium browser")


def playwright_page_is_open(wrapper: Any = None) -> bool:
    """Whether the Playwright wrapper has a page to act on."""
    try:
        return (playwright_wrapper_instance if wrapper is None else wrapper).page is not None
    except PlaywrightBackendError:
        return False
