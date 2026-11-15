"""
撰寫工具會產生的命令
The commands the authoring helpers emit: ``md_authoring`` (``- assert title "…"``, ``- press <Key>``,
``- run template <name>`` and the note it keeps for a bullet it does not know) and the built-in action
templates (``close_modal`` presses Escape, ``accept_cookies`` dismisses a consent banner). They are ordinary
commands, so an action file can use them too.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from je_web_runner.utils.action_templates.templates import render_template
from je_web_runner.utils.cookie_consent.consent import ConsentDismisser
from je_web_runner.utils.exception.exceptions import (
    WebRunnerAssertException,
    WebRunnerExecuteException,
    WebRunnerWebDriverIsNoneException,
)
from je_web_runner.utils.executor._bound import Bound
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

# Names people write that Selenium's ``Keys`` spells differently.
_KEY_ALIASES = {"ESC": "ESCAPE", "DEL": "DELETE", "CTRL": "CONTROL", "CMD": "COMMAND", "RETURN": "ENTER"}


def assert_title(value: str) -> str:
    """
    斷言目前頁面標題等於 ``value``
    Fail unless the current page title equals ``value``; return the title.

    :raises WebRunnerAssertException: when the title is anything else.
    """
    title = webdriver_wrapper_instance.get_title()
    if title != value:
        raise WebRunnerAssertException(f"page title is {title!r}, expected {value!r}")
    return title


def _key(name: str) -> str:
    """One character as it is, or the ``Keys`` value of a key name (``Enter``, ``Escape``, ``F5`` …)."""
    if len(name) == 1:
        return name
    upper = name.upper()
    resolved = getattr(Keys, _KEY_ALIASES.get(upper, upper), None)
    if not isinstance(resolved, str):
        raise WebRunnerExecuteException(f"WR_press_keys: unknown key {name!r}")
    return resolved


def _browser(command: str) -> Any:
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise WebRunnerWebDriverIsNoneException(f"{command} needs a browser; start one first")
    return driver


def press_keys(keys: str | Sequence[str]) -> None:
    """
    對目前聚焦的元素按下並放開按鍵
    Press and release ``keys`` on the focused element at once: one key name (``"Enter"``, ``"Escape"``),
    one character, or a list of them. Nothing queued with ``WR_press_key`` / ``WR_send_keys`` is sent.

    :raises WebRunnerExecuteException: for a key name Selenium does not have; nothing is sent then.
    """
    names = [keys] if isinstance(keys, str) else list(keys)
    resolved = [_key(str(name)) for name in names]
    ActionChains(_browser("WR_press_keys")).send_keys(*resolved).perform()


def dismiss_cookie_consent(timeout_per_selector: float = 0.5) -> str | None:
    """
    點掉常見的 cookie 同意橫幅
    Click the first common cookie-consent button on the page. Return the selector that was clicked, or
    ``None`` when the page shows no banner this knows.
    """
    return ConsentDismisser().dismiss(_browser("WR_dismiss_cookie_consent"), timeout_per_selector)


def note(text: str = "") -> str:
    """
    不做任何事的註記
    A remark in an action list: does nothing and returns ``text``.
    """
    return text


def _render_and_run(executor: Any) -> Callable[..., list]:
    def run_template(template: str, parameters: dict[str, Any] | None = None) -> list:
        """
        套用參數後執行一個動作範本
        Fill the action template ``template`` with ``parameters`` and run its actions in order; return
        what each returned. The first action that fails stops the template and fails this action.
        """
        return executor.run_nested(render_template(template, parameters))

    return run_template


AUTHORING_COMMANDS: dict[str, Any] = {
    "WR_assert_title": assert_title,
    "WR_press_keys": press_keys,
    "WR_dismiss_cookie_consent": dismiss_cookie_consent,
    "WR_note": note,
    "WR__note": note,  # what md_authoring emitted before WR_note existed
    "WR_render_template": Bound(_render_and_run),
}
