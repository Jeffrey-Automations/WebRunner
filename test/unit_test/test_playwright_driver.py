"""The Playwright stand-in for a Selenium driver, and the helper that chooses between the two."""
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.driver_dispatch import evaluate_expression, run_script
from je_web_runner.utils.driver_dispatch.playwright_driver import (
    PlaywrightDriver,
    SeleniumBackendRequired,
    playwright_page_is_open,
    selenium_cookie,
)
from je_web_runner.utils.driver_dispatch.selenium_script import as_async_function, as_function
from je_web_runner.utils.exception.exceptions import WebRunnerException, WebRunnerWebDriverIsNoneException
from je_web_runner.utils.executor import _command_helpers as helpers
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError


class _FakeWrapper:
    """What the stand-in reads from ``playwright_wrapper_instance``: the page, the frame scope, the context."""

    def __init__(self):
        self.page = MagicMock(name="page")
        self.page.url = "https://example.test/cart"
        self.page.title.return_value = "Cart"
        self.page.screenshot.return_value = b"\x89PNG"
        self.context = MagicMock(name="context")
        self.frame = None
        self._frame = "an iframe"

    @property
    def _target(self):
        return self.page if self.frame is None else self.frame


@pytest.fixture(name="wrapper")
def _wrapper():
    return _FakeWrapper()


@pytest.fixture(name="driver")
def _driver(wrapper):
    return PlaywrightDriver("WR_demo", wrapper, cdp=MagicMock(return_value={"ok": True}))


def test_execute_script_runs_the_body_as_a_function_of_its_arguments(driver, wrapper):
    wrapper.page.evaluate.return_value = 3
    assert driver.execute_script("return arguments[0] + arguments[1]", 1, 2) == 3
    wrapper.page.evaluate.assert_called_once_with(as_function("return arguments[0] + arguments[1]"), [1, 2])
    driver.execute_script("return 1")
    assert wrapper.page.evaluate.call_args.args == (as_function("return 1"), [])


def test_execute_async_script_gives_what_the_callback_gets(driver, wrapper):
    driver.execute_async_script("arguments[arguments.length - 1](arguments[0])", "x")
    wrapper.page.evaluate.assert_called_once_with(
        as_async_function("arguments[arguments.length - 1](arguments[0])"), ["x"])


def test_the_wrapped_body_keeps_its_text_and_gets_the_callback_last():
    body = "return document.title"
    assert as_function(body) == "(args) => (function () {\nreturn document.title\n}).apply(null, args)"
    assert body in as_async_function(body)
    assert as_async_function(body).endswith(".apply(null, [...args, resolve]))")
    assert "new Promise" in as_async_function(body)


def test_scripts_and_page_source_act_in_the_selected_frame(driver, wrapper):
    wrapper.frame = MagicMock(name="frame")
    wrapper.frame.evaluate.return_value = "<html></html>"
    assert driver.page_source == "<html></html>"
    driver.execute_script("return 1")
    assert wrapper.frame.evaluate.call_count == 2
    wrapper.page.evaluate.assert_not_called()


def test_page_properties_come_from_the_page(driver, wrapper):
    assert driver.current_url == "https://example.test/cart"
    assert driver.title == "Cart"
    assert driver.get_screenshot_as_png() == b"\x89PNG"
    assert driver.save_screenshot("shot.png") is True
    wrapper.page.screenshot.assert_called_with(path="shot.png")


def test_get_navigates_and_leaves_the_frame(driver, wrapper):
    driver.get("https://example.test/")
    wrapper.page.goto.assert_called_once_with("https://example.test/")
    assert wrapper._frame is None  # pylint: disable=protected-access  # the state the stand-in resets


def test_set_window_size_sets_the_viewport(driver, wrapper):
    driver.set_window_size(390.0, 844)
    wrapper.page.set_viewport_size.assert_called_once_with({"width": 390, "height": 844})


def test_cookies_are_those_of_the_page_in_selenium_shape(driver, wrapper):
    wrapper.context.cookies.return_value = [
        {"name": "sid", "value": "1", "domain": "example.test", "path": "/", "expires": 1893456000.5,
         "httpOnly": True, "secure": False, "sameSite": "Lax"},
        {"name": "tmp", "value": "2", "domain": "example.test", "path": "/", "expires": -1,
         "httpOnly": False, "secure": False, "sameSite": "Lax"},
    ]
    assert driver.get_cookies() == [
        {"name": "sid", "value": "1", "domain": "example.test", "path": "/", "httpOnly": True, "secure": False,
         "sameSite": "Lax", "expiry": 1893456000},
        {"name": "tmp", "value": "2", "domain": "example.test", "path": "/", "httpOnly": False, "secure": False,
         "sameSite": "Lax"},
    ]
    wrapper.context.cookies.assert_called_once_with("https://example.test/cart")
    assert selenium_cookie({"name": "a", "value": "b"}) == {"name": "a", "value": "b"}


def test_cdp_goes_through_the_given_session(wrapper):
    send = MagicMock(return_value={"frameId": "F"})
    driver = PlaywrightDriver("WR_demo", wrapper, cdp=send)
    assert driver.execute_cdp_cmd("Page.reload", {"ignoreCache": True}) == {"frameId": "F"}
    assert driver.execute_cdp_cmd("Network.enable") == {"frameId": "F"}
    assert [call.args for call in send.call_args_list] == [
        ("Page.reload", {"ignoreCache": True}), ("Network.enable", {})]


@pytest.mark.parametrize("name", ["get_log", "window_handles", "switch_to", "current_window_handle",
                                  "find_element", "script", "bidi_connection", "close"])
def test_what_only_selenium_has_raises_a_named_error(driver, name):
    with pytest.raises(SeleniumBackendRequired, match=f"WR_demo uses the Selenium driver's '{name}'"):
        getattr(driver, name)
    # hasattr and getattr-with-default must not turn it into "absent": the libraries test with them.
    with pytest.raises(SeleniumBackendRequired):
        hasattr(driver, name)
    with pytest.raises(SeleniumBackendRequired):
        getattr(driver, name, None)
    assert issubclass(SeleniumBackendRequired, WebRunnerException)


def test_private_names_are_plain_attribute_errors(driver):
    assert not hasattr(driver, "_no_such_thing")
    assert not hasattr(driver, "__deepcopy__")


def test_the_shared_dispatch_helpers_take_the_selenium_path(driver, wrapper):
    wrapper.page.evaluate.return_value = 7
    assert evaluate_expression(driver, "1 + 6") == 7
    assert wrapper.page.evaluate.call_args.args == (as_function("return 1 + 6;"), [])
    run_script(driver, "window.x = arguments[0];", 5)
    assert wrapper.page.evaluate.call_args.args == (as_function("window.x = arguments[0];"), [5])


def test_a_page_is_open_only_when_the_wrapper_has_one(wrapper):
    assert playwright_page_is_open(wrapper) is True

    class _Closed:
        @property
        def page(self):
            raise PlaywrightBackendError("Playwright page not launched; call launch() first")

    assert playwright_page_is_open(_Closed()) is False


# ----- the helper that chooses -------------------------------------------------------------------

@pytest.fixture(name="browsers")
def _browsers():
    """Set which browsers are open and which backend the executor runs on."""
    def choose(selenium=None, playwright=False, backend=None):
        return (patch.object(helpers.webdriver_wrapper_instance, "current_webdriver", selenium),
                patch.object(helpers, "playwright_page_is_open", return_value=playwright),
                patch.object(helpers, "_runs_on_playwright", return_value=backend == "playwright"))
    return choose


def _chosen(patches):
    first, second, third = patches
    with first, second, third:
        return helpers.browser_driver("WR_demo")


def test_only_selenium_open_gives_its_driver(browsers):
    selenium = object()
    assert _chosen(browsers(selenium=selenium)) is selenium
    assert _chosen(browsers(selenium=selenium, backend="playwright")) is selenium


def test_only_playwright_open_gives_the_stand_in(browsers):
    chosen = _chosen(browsers(playwright=True))
    assert isinstance(chosen, PlaywrightDriver)
    with pytest.raises(SeleniumBackendRequired, match="WR_demo"):
        chosen.get_log("browser")


def test_both_open_follow_the_executor_backend_else_selenium(browsers):
    selenium = object()
    assert _chosen(browsers(selenium=selenium, playwright=True)) is selenium
    assert _chosen(browsers(selenium=selenium, playwright=True, backend="selenium")) is selenium
    assert isinstance(_chosen(browsers(selenium=selenium, playwright=True, backend="playwright")), PlaywrightDriver)


def test_no_browser_is_the_same_error_as_before(browsers):
    with pytest.raises(WebRunnerWebDriverIsNoneException, match="WR_demo needs a browser; start one first"):
        _chosen(browsers())


def test_the_first_name_of_the_helper_is_still_importable():
    assert helpers.selenium_driver is helpers.browser_driver


def test_page_source_reads_the_chosen_browser(browsers):
    selenium = MagicMock(page_source="<html>s</html>")
    first, second, third = browsers(selenium=selenium)
    with first, second, third:
        assert helpers.page_source("WR_demo") == "<html>s</html>"


def test_selenium_only_driver_needs_a_selenium_browser(browsers):
    selenium = object()
    first, second, third = browsers(selenium=selenium, playwright=True, backend="playwright")
    with first, second, third:
        assert helpers.selenium_only_driver("WR_multi_tab_open", "Selenium window handles") is selenium
    first, second, third = browsers(playwright=True)
    with first, second, third, pytest.raises(
            WebRunnerWebDriverIsNoneException,
            match=r"WR_multi_tab_open needs the Selenium backend \(Selenium window handles\)"):
        helpers.selenium_only_driver("WR_multi_tab_open", "Selenium window handles")


def test_the_executor_backend_decides(monkeypatch):
    from je_web_runner.utils.executor.action_executor import executor

    monkeypatch.setattr(executor, "backend", "playwright")
    assert helpers._runs_on_playwright() is True  # pylint: disable=protected-access  # the rule under test
    monkeypatch.setattr(executor, "backend", None)
    assert helpers._runs_on_playwright() is False  # pylint: disable=protected-access  # the rule under test
