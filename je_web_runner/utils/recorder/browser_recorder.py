"""
透過注入 JS 監聽器的瀏覽器操作錄製器，將使用者的操作反向轉成 WR_* action JSON。
Browser action recorder via injected JS listeners; converts captured user
events back into WR_* action JSON consumable by the executor.

設計重點 / Design notes:
- 不使用 CDP，靠 ``execute_script`` 注入靜態腳本，因此 Chrome / Firefox / Edge
  都能用，並避免動態執行使用者輸入（CLAUDE.md 安全規則）。
- 所有 JS 都是常數字串：Python 不把任何值串接進腳本，事件資料以 JSON 格式從瀏覽器拉回 Python 端。
  Every script is a constant: no Python value is ever put into script text.
- 翻譯結果使用 ``CSS_SELECTOR`` 定位，後續可由人工微調。

Event shape (what ``_RECORDER_JS`` pushes and :func:`events_to_actions` reads).
Every event is a dict with ``type``, ``url`` (``location.href`` when it happened,
secrets masked) and ``time`` (``Date.now()``); the other keys depend on ``type``:

============  ==============================================  ==================================
``type``      Other keys                                      When
============  ==============================================  ==================================
``navigate``  none                                            once, when the recorder is installed
``click``     ``selector``                                    a click, except on a checkbox, a
                                                              radio button, a ``<select>`` or an
                                                              ``<option>`` (their ``change`` is
                                                              recorded) and except the click the
                                                              browser makes for an Enter press
``input``     ``selector``, ``value``, ``masked``             a field's value was committed
``select``    ``selector``, ``value``, ``masked``             a ``<select>`` choice
``check``     ``selector``, ``checked``, ``input_type``       a checkbox / radio button changed
``key``       ``key`` (a name of ``_KEY_NAMES``),             a named key went down with no
              ``selector`` (the focused element, or null)     modifier held
``assert``    ``selector``, ``text``, ``masked``              Alt+click on an element that shows
                                                              text: the text it should show. The
                                                              click does not reach the page.
============  ==============================================  ==================================

``url`` and ``time`` are optional on the Python side, so event logs written by
older versions (``click`` / ``input`` with ``selector`` only) still translate.
A sensitive ``value`` or ``text`` arrives as ``***MASKED***`` with ``masked: true``. A
``key`` event never carries a typed character: the script records the named
keys only, and the Python side drops any other key.

Navigation heuristic of :func:`events_to_actions`: the first event that has a
``url`` yields a navigate action; afterwards a ``url`` that differs from the
previous event's yields one unless the event before it was a click or an Enter
press, which are taken to have caused the change themselves.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.json.json_file.json_file import write_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class RecorderError(WebRunnerException):
    """Raised when the recorder cannot install or read events."""


class PlaywrightScriptRunner:
    """
    讓錄製器以 Playwright 頁面執行腳本
    Give the recorder the ``execute_script`` it expects, on the current Playwright
    page: each constant script runs as the body of a function, as Selenium runs it.
    """

    def __init__(self, wrapper) -> None:
        self._wrapper = wrapper

    def execute_script(self, script: str):
        """Run ``script`` as a function body in the current page and return its result."""
        return self._wrapper.page.evaluate(f"() => {{ {script} }}")


_RECORDER_JS = r"""
(function() {
  if (window.__wr_recorder_installed) { return; }
  window.__wr_recorder_installed = true;
  window.__wr_events = [];

  var MASK = '***MASKED***';
  var SENSITIVE = /(passw(?:or)?d|card[\-_]?number|cvv|cvc|ssn|secret|token|api[\-_]?key|otp|passcode)/;
  var URL_SECRET = new RegExp(
    '([?&#;][^=&#;]*' + SENSITIVE.source + '[^=&#;]*=)[^&#;]*', 'gi'
  );
  var URL_USERINFO = /(\/\/[^\/@:?#]*:)[^\/@?#]*@/;
  var NAMED_KEYS = [
    'Enter', 'Escape', 'Tab', 'Backspace', 'Delete', 'Insert', 'Home', 'End',
    'PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
    'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12'
  ];
  var COMMIT_KEYS = ['Enter', 'Escape', 'Tab'];
  var dirtyField = null;
  var lastField = null;
  var lastValue = null;
  var enterDown = false;

  function maskUrl(url) {
    return String(url).replace(URL_USERINFO, '$1' + MASK + '@').replace(URL_SECRET, '$1' + MASK);
  }

  function record(event) {
    if (!window.__wr_recorder_installed) return;
    event.url = maskUrl(window.location.href);
    event.time = Date.now();
    window.__wr_events.push(event);
  }

  record({type: 'navigate'});
  if (window.__wr_recorder_hooked) { return; }
  window.__wr_recorder_hooked = true;

  function kindOf(el) {
    var tag = (el.tagName || '').toLowerCase();
    var type = (el.type || '').toLowerCase();
    if (tag === 'select') return 'select';
    if (tag === 'option' || tag === 'optgroup') return 'option';
    if (tag === 'input' && (type === 'checkbox' || type === 'radio')) return 'check';
    if (tag === 'textarea' || el.isContentEditable) return 'text';
    if (tag === 'input' && !/^(button|submit|reset|image|file|range|color)$/.test(type)) return 'text';
    return 'other';
  }

  function quoted(text) {
    return '"' + String(text).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  }

  function matchCount(selector) {
    try {
      return document.querySelectorAll(selector).length;
    } catch (error) {
      return 0;
    }
  }

  function namePath(el) {
    var base = el.tagName.toLowerCase() + '[name=' + quoted(el.name) + ']';
    if (matchCount(base) === 1) return base;
    if (kindOf(el) === 'check' && el.hasAttribute('value')) {
      var withValue = base + '[value=' + quoted(el.getAttribute('value')) + ']';
      if (matchCount(withValue) === 1) return withValue;
    }
    return null;
  }

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return null;
    if (el.id) {
      return '#' + (window.CSS && window.CSS.escape ? window.CSS.escape(el.id) : el.id);
    }
    if (el.name) {
      var named = namePath(el);
      if (named) return named;
    }
    var parts = [];
    while (el && el.nodeType === 1 && el.tagName.toLowerCase() !== 'html') {
      var idx = 1;
      var sib = el;
      while ((sib = sib.previousElementSibling)) {
        if (sib.tagName === el.tagName) idx++;
      }
      parts.unshift(el.tagName.toLowerCase() + ':nth-of-type(' + idx + ')');
      el = el.parentElement;
    }
    return parts.join(' > ');
  }

  function looksSensitive(target, value) {
    if (target.type === 'password') return true;
    var label = ((target.name || target.id || target.autocomplete || '') + '').toLowerCase();
    if (SENSITIVE.test(label)) return true;
    var digits = (value || '').replace(/[\s-]/g, '');
    if (/^[0-9]{13,19}$/.test(digits)) return true;
    return false;
  }

  function recordValue(target, type) {
    var sel = cssPath(target);
    if (!sel) return;
    var value = String(target.value || '');
    dirtyField = null;
    if (lastField === target && lastValue === value) return;
    lastField = target;
    lastValue = value;
    var masked = looksSensitive(target, value);
    record({type: type, selector: sel, value: masked ? MASK : value, masked: masked});
  }

  function recordAssert(target) {
    var sel = cssPath(target);
    var text = String(target.innerText || target.textContent || '').trim();
    if (!sel || !text) return;
    var masked = looksSensitive(target, text);
    record({type: 'assert', selector: sel, text: masked ? MASK : text, masked: masked});
  }

  document.addEventListener('click', function(ev) {
    if (ev.altKey) {
      // Alt+click marks what the page should show: it is recorded as an assertion and kept from the page.
      ev.preventDefault();
      ev.stopPropagation();
      recordAssert(ev.target);
      return;
    }
    var kind = kindOf(ev.target);
    if (kind === 'select' || kind === 'option' || kind === 'check') return;
    if (enterDown && ev.detail === 0) return;
    var sel = cssPath(ev.target);
    if (sel) record({type: 'click', selector: sel});
  }, true);

  document.addEventListener('input', function(ev) {
    if (kindOf(ev.target) === 'text') dirtyField = ev.target;
  }, true);

  document.addEventListener('change', function(ev) {
    var kind = kindOf(ev.target);
    if (kind === 'check') {
      var sel = cssPath(ev.target);
      if (sel) {
        record({type: 'check', selector: sel, checked: !!ev.target.checked, input_type: ev.target.type});
      }
      return;
    }
    recordValue(ev.target, kind === 'select' ? 'select' : 'input');
  }, true);

  document.addEventListener('keydown', function(ev) {
    if (ev.isComposing || ev.ctrlKey || ev.altKey || ev.metaKey || ev.shiftKey) return;
    if (NAMED_KEYS.indexOf(ev.key) < 0) return;
    var kind = kindOf(ev.target);
    if ((kind === 'text' || kind === 'select') && COMMIT_KEYS.indexOf(ev.key) < 0) return;
    if (dirtyField && dirtyField === ev.target) recordValue(ev.target, 'input');
    record({type: 'key', key: ev.key, selector: cssPath(ev.target)});
    if (ev.key === 'Enter') enterDown = true;
  }, true);

  document.addEventListener('keyup', function(ev) {
    if (ev.key === 'Enter') enterDown = false;
  }, true);
})();
"""

_DRAIN_JS = (
    "var events = window.__wr_events || []; "
    "window.__wr_events = []; "
    "return events;"
)

_RESET_JS = "window.__wr_recorder_installed = false; window.__wr_events = [];"

MASKED_VALUE = "***MASKED***"
BACKEND_SELENIUM = "selenium"
BACKEND_PLAYWRIGHT = "playwright"

_SENSITIVE_WORDS = r"passw(?:or)?d|card[-_]?number|cvv|cvc|ssn|secret|token|api[-_]?key|otp|passcode"
_SENSITIVE_NAME_RE = re.compile(f"({_SENSITIVE_WORDS})", re.IGNORECASE)
_LONG_DIGIT_RE = re.compile(r"^\d{13,19}$")
_URL_SECRET_RE = re.compile(f"([?&#;][^=&#;]*(?:{_SENSITIVE_WORDS})[^=&#;]*=)[^&#;]*", re.IGNORECASE)
_URL_USERINFO_RE = re.compile(r"(//[^/@:?#]*:)[^/@?#]*@")
_VALUE_EVENT_TYPES = frozenset({"input", "select"})

# The named keys the script records, with the name ``WR_press_keys`` knows each by
# (an attribute of Selenium's ``Keys``, in any case). Playwright uses the JS name.
_KEY_NAMES: dict[str, str] = {
    "Enter": "Enter", "Escape": "Escape", "Tab": "Tab", "Backspace": "Backspace", "Delete": "Delete",
    "Insert": "Insert", "Home": "Home", "End": "End", "PageUp": "Page_Up", "PageDown": "Page_Down",
    "ArrowUp": "Arrow_Up", "ArrowDown": "Arrow_Down", "ArrowLeft": "Arrow_Left", "ArrowRight": "Arrow_Right",
    **{f"F{number}": f"F{number}" for number in range(1, 13)},
}


@dataclass(frozen=True)
class _Backend:
    """How one backend spells what the recorder emits."""

    commands: Mapping[str, str]
    value_arguments: Mapping[str, str]
    key_names: Mapping[str, str]
    by_selector: bool
    # Operations whose command acts on the current element even where the others take a selector.
    on_current_element: frozenset[str] = frozenset()


_BACKENDS: dict[str, _Backend] = {
    BACKEND_SELENIUM: _Backend(
        commands={
            "navigate": "WR_to_url",
            "save": "WR_save_test_object",
            "find": "WR_find_recorded_element",
            "click": "WR_element_click",
            "input": "WR_element_input",
            "select": "WR_element_select_by_value",
            "check": "WR_element_check",
            "uncheck": "WR_element_uncheck",
            "key": "WR_press_keys",
            "assert": "WR_element_assert",
        },
        value_arguments={"navigate": "url", "input": "input_value", "select": "value", "key": "keys",
                         "assert": "check_dict"},
        key_names=_KEY_NAMES,
        by_selector=False,
    ),
    BACKEND_PLAYWRIGHT: _Backend(
        commands={
            "navigate": "WR_pw_to_url",
            "click": "WR_pw_click",
            "input": "WR_pw_fill",
            "select": "WR_pw_select_option",
            "check": "WR_pw_check",
            "uncheck": "WR_pw_uncheck",
            "key": "WR_pw_keyboard_press",
            # The assertion reads the current element, so it is looked up first. The locator table is
            # shared by both backends, hence the one command here without the ``WR_pw_`` prefix.
            "save": "WR_save_test_object",
            "find": "WR_pw_find_element_with_test_object_record",
            "assert": "WR_pw_element_assert",
        },
        value_arguments={"navigate": "url", "input": "value", "select": "value", "key": "key",
                         "assert": "check_dict"},
        key_names={name: name for name in _KEY_NAMES},
        by_selector=True,
        on_current_element=frozenset({"assert"}),
    ),
}


def _backend(name: str) -> _Backend:
    backend = _BACKENDS.get(name) if isinstance(name, str) else None
    if backend is None:
        raise RecorderError(f"unknown recorder backend {name!r}; use one of {sorted(_BACKENDS)}")
    return backend


def emitted_commands(backend: str = BACKEND_SELENIUM) -> frozenset[str]:
    """
    錄製器在某個 backend 下可能產生的所有命令名稱
    Every command name :func:`events_to_actions` can emit for ``backend``.

    :raises RecorderError: for a backend other than ``"selenium"`` / ``"playwright"``.
    """
    return frozenset(_backend(backend).commands.values())


def mask_url(url: str) -> str:
    """
    遮罩 URL 中的密碼與敏感參數值
    Mask the password of ``user:password@host`` and the value of every query or
    fragment parameter whose name looks sensitive (``token``, ``api_key`` …).
    """
    without_password = _URL_USERINFO_RE.sub(rf"\g<1>{MASKED_VALUE}@", url)
    return _URL_SECRET_RE.sub(rf"\g<1>{MASKED_VALUE}", without_password)


def _looks_sensitive(selector: str, value: str) -> bool:
    if not isinstance(value, str):
        return False
    if _SENSITIVE_NAME_RE.search(selector or ""):
        return True
    digits = re.sub(r"[\s-]", "", value)
    return bool(_LONG_DIGIT_RE.match(digits))


def mask_sensitive_events(events: Iterable[dict]) -> list[dict]:
    """
    在 Python 端再做一次遮罩，保險起見
    Defensive Python-side masking pass; mainly useful when consuming raw
    events that bypassed the JS-side masking (e.g. loaded from disk).

    Masks the value of ``input`` / ``select`` events, the text of ``assert`` events, the secrets in every
    event's ``url``, and the ``key`` of a ``key`` event that is not a named key
    (a typed character must never be kept).
    """
    masked: list[dict] = []
    for event in events:
        copy = dict(event)
        if copy.get("type") in _VALUE_EVENT_TYPES and not copy.get("masked"):
            value = copy.get("value", "")
            if _looks_sensitive(copy.get("selector", ""), value):
                copy["value"] = MASKED_VALUE
                copy["masked"] = True
        if copy.get("type") == "assert" and not copy.get("masked"):
            if _looks_sensitive(copy.get("selector", ""), copy.get("text", "")):
                copy["text"] = MASKED_VALUE
                copy["masked"] = True
        if copy.get("type") == "key" and _named_key(copy.get("key"), _KEY_NAMES) is None:
            copy["key"] = MASKED_VALUE
            copy["masked"] = True
        if isinstance(copy.get("url"), str):
            copy["url"] = mask_url(copy["url"])
        masked.append(copy)
    return masked


def _resolve_driver(driver_or_wrapper) -> Any:
    """Accept either a raw WebDriver or a WebDriverWrapper exposing current_webdriver."""
    if hasattr(driver_or_wrapper, "current_webdriver") and driver_or_wrapper.current_webdriver:
        return driver_or_wrapper.current_webdriver
    if hasattr(driver_or_wrapper, "execute_script"):
        return driver_or_wrapper
    raise RecorderError("driver has no execute_script and no current_webdriver")


def start_recording(driver_or_wrapper) -> None:
    """
    在當前頁面注入錄製器腳本。再次呼叫可在新頁面重新注入（idempotent）。
    Inject the recorder script into the current page (idempotent). The buffer
    lives in the document, so after a navigation to a new document pull the
    events first and call this again on the new page.
    """
    web_runner_logger.info("recorder: start_recording")
    driver = _resolve_driver(driver_or_wrapper)
    driver.execute_script(_RECORDER_JS)


def pull_events(driver_or_wrapper) -> list[dict]:
    """
    從瀏覽器拉回累積事件並清空緩衝
    Drain accumulated events from the browser side and clear the buffer.
    """
    driver = _resolve_driver(driver_or_wrapper)
    events = driver.execute_script(_DRAIN_JS) or []
    if not isinstance(events, list):
        raise RecorderError(f"unexpected events payload type: {type(events).__name__}")
    return events


def stop_recording(driver_or_wrapper) -> None:
    """
    停用錄製器並清掉狀態
    Disable the recorder flag and clear buffered events. The listeners stay on
    the current document but record nothing until the recorder is started again.
    """
    web_runner_logger.info("recorder: stop_recording")
    driver = _resolve_driver(driver_or_wrapper)
    driver.execute_script(_RESET_JS)


# What one event asks for: (operation, selector or None, value or None).
_Operation = tuple[str, Optional[str], Any]


def _named_key(key: Any, key_names: Mapping[str, str]) -> str | None:
    """The backend's name of a recorded key, or None for anything that is not a named key."""
    return key_names.get(key) if isinstance(key, str) else None


def _click_operation(event: dict, _backend_names: _Backend) -> _Operation | None:
    return "click", event["selector"], None


def _value_operation(event: dict, _backend_names: _Backend) -> _Operation | None:
    return event["type"], event["selector"], event.get("value", "")


def _check_operation(event: dict, _backend_names: _Backend) -> _Operation | None:
    return ("check" if event.get("checked") else "uncheck"), event["selector"], None


def _key_operation(event: dict, backend: _Backend) -> _Operation | None:
    name = _named_key(event.get("key"), backend.key_names)
    if name is None:
        # The key itself is not logged: it may be a typed character.
        web_runner_logger.warning("recorder: key event skipped, not a named key")
        return None
    return "key", None, name


def _assert_operation(event: dict, _backend_names: _Backend) -> _Operation | None:
    text = event.get("text")
    if not isinstance(text, str) or not text:
        web_runner_logger.warning("recorder: assert event skipped, it has no text")
        return None
    return "assert", event["selector"], {"text": text}


_OPERATIONS: dict[str, Callable[[dict, _Backend], "_Operation | None"]] = {
    "assert": _assert_operation,
    "click": _click_operation,
    "input": _value_operation,
    "select": _value_operation,
    "check": _check_operation,
    "key": _key_operation,
}


def _render(backend: _Backend, operation: str, selector: str | None, value: Any) -> list[list]:
    """The actions of one operation, in the backend's command names and argument names."""
    command = backend.commands[operation]
    arguments: dict[str, Any] = {}
    if value is not None:
        arguments[backend.value_arguments[operation]] = value
    if selector is None:
        return [[command, arguments]]
    if backend.by_selector and operation not in backend.on_current_element:
        return [[command, {"selector": selector, **arguments}]]
    return [
        [backend.commands["save"], {"test_object_name": selector, "object_type": "CSS_SELECTOR"}],
        [backend.commands["find"], {"element_name": selector}],
        [command, arguments] if arguments else [command],
    ]


class _Translation:
    """One pass over the events: the actions so far and what decides a navigate action."""

    def __init__(self, backend: _Backend) -> None:
        self.actions: list[list] = []
        self._backend = backend
        self._current_url: str | None = None
        self._after_trigger = False

    def _follow_url(self, url: Any) -> None:
        """Emit a navigate action for a new URL that the previous click / Enter did not cause."""
        if not isinstance(url, str) or not url or url == self._current_url:
            return
        if self._current_url is None or not self._after_trigger:
            self.actions.extend(_render(self._backend, "navigate", None, url))
        self._current_url = url

    def add(self, event: dict) -> None:
        """Translate one event."""
        self._follow_url(event.get("url"))
        event_type = event.get("type")
        if event_type == "navigate":
            self._after_trigger = False
            return
        handler = _OPERATIONS.get(event_type) if isinstance(event_type, str) else None
        if handler is None:
            web_runner_logger.warning(f"recorder: unsupported event type {event_type!r}")
            return
        operation = handler(event, self._backend)
        if operation is None:
            return
        self.actions.extend(_render(self._backend, *operation))
        self._after_trigger = event_type == "click" or (event_type == "key" and event.get("key") == "Enter")


def events_to_actions(events: Iterable[dict], backend: str = BACKEND_SELENIUM) -> list[list]:
    """
    將事件清單翻譯成 WR_* action 序列
    Translate captured events into a WR_* action list.

    未支援的事件類型會被忽略並寫入日誌。
    Unsupported event types are skipped and logged.

    :param events: 事件清單（格式見模組說明）/ events shaped as the module docstring says
    :param backend: ``"selenium"`` (default) emits ``WR_*`` commands that act on a saved
                    ``TestObject``; ``"playwright"`` emits the ``WR_pw_*`` commands, which
                    take the selector themselves
    :raises RecorderError: for an unknown ``backend``
    """
    translation = _Translation(_backend(backend))
    for event in events:
        translation.add(event)
    return translation.actions


def save_recording(
    driver_or_wrapper,
    output_path: str,
    raw_events_path: str | None = None,
    backend: str = BACKEND_SELENIUM,
) -> str:
    """
    便捷函式：拉回事件、轉成 actions、寫出 JSON
    Convenience: drain events, mask them once more on the Python side, translate
    to actions, write JSON.

    :param driver_or_wrapper: 已注入錄製器的 driver 或 wrapper
                               driver / wrapper that has been started
    :param output_path: action JSON 輸出路徑 / action JSON output path
    :param raw_events_path: 可選的原始事件輸出路徑（除錯用）
                             optional path for the raw event log (debugging)
    :param backend: ``"selenium"`` (default) or ``"playwright"``; see :func:`events_to_actions`
    :return: 寫出的 action JSON 路徑 / path written
    :raises RecorderError: for an unknown ``backend``; nothing is pulled then
    """
    _backend(backend)
    events = mask_sensitive_events(pull_events(driver_or_wrapper))
    if raw_events_path:
        Path(raw_events_path).parent.mkdir(parents=True, exist_ok=True)
        with open(raw_events_path, "w", encoding="utf-8") as raw_out:
            json.dump(events, raw_out, indent=2)
    actions = events_to_actions(events, backend)
    write_action_json(output_path, actions)
    return output_path
