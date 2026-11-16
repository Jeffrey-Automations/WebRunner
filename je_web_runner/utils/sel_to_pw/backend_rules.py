"""
Selenium 命令對應 Playwright 命令的翻譯表
The translation table between the Selenium commands (``WR_*``) and the Playwright ones (``WR_pw_*``).

It follows the "Equivalent commands" table of ``docs/source/Eng/doc/backends/backends_doc.rst``;
``test/unit_test/test_sel_to_pw_backend_doc.py`` fails when a Selenium command of that table is neither
in :data:`SELENIUM_TO_PLAYWRIGHT` nor in :data:`CANNOT_TRANSLATE`.

Two kinds of entry:

* a :class:`Rule`: one command becomes one command. Arguments keep their name unless ``rename`` says
  otherwise, ``convert`` changes a value (seconds to milliseconds …), ``add`` gives the target constant
  arguments and ``defaults`` fills what the source left out when the two commands default differently.
  A rule is read backwards for the other direction unless ``inverse`` is false.
* a builder function: it gets the action's arguments by the Selenium parameter names and returns the
  Playwright actions (one Selenium action may need several), or raises :class:`Untranslatable`.

Argument names and defaults are not repeated here: they are read from the signatures of the registered
commands, so positional arguments are mapped by the source command's parameter order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from je_web_runner.utils.device_emulation.presets import DeviceEmulationError, playwright_kwargs
from je_web_runner.utils.test_object.locator_file import LocatorFileError, strategy_name
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.time_freezer.freezer import TimeFreezerError, to_epoch_ms
from je_web_runner.webdriver.playwright_locator import test_object_to_selector

Action = list[Any]
Builder = Callable[[dict[str, Any]], list[Action]]

# The logical locator name a translated raw-selector lookup is stored under (see ``_find_by``).
TRANSLATED_LOCATOR = "sel_to_pw.selector"


class Untranslatable(Exception):
    """One action cannot be translated; the message is the reason."""


@dataclass(frozen=True)
class Conversion:
    """How an argument value changes: ``forward`` to Playwright, ``backward`` to Selenium."""

    forward: Callable[[Any], Any]
    backward: Callable[[Any], Any] | None = None


@dataclass(frozen=True)
class Rule:
    """One Selenium command that becomes one Playwright command (see the module docstring)."""

    target: str
    rename: Mapping[str, str] = field(default_factory=dict)
    convert: Mapping[str, Conversion] = field(default_factory=dict)
    add: Mapping[str, Any] = field(default_factory=dict)
    defaults: Mapping[str, Any] = field(default_factory=dict)
    # Selenium arguments filled when a Playwright action leaves them out (the other direction of ``defaults``).
    inverse_defaults: Mapping[str, Any] = field(default_factory=dict)
    inverse: bool = True


# ----- value conversions -------------------------------------------------------------------------

def _number(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Untranslatable(f"{what} must be a literal number to be converted, got {value!r}")
    return value


def _tidy(number: float) -> float:
    rounded = round(number, 6)
    return int(rounded) if float(rounded).is_integer() else rounded


def seconds_to_ms(value: Any) -> float:
    """Selenium waits in seconds, Playwright in milliseconds."""
    return _tidy(_number(value, "a time in seconds") * 1000)


def ms_to_seconds(value: Any) -> float:
    """The other direction of :func:`seconds_to_ms`."""
    return _tidy(_number(value, "a time in milliseconds") / 1000)


SECONDS = Conversion(seconds_to_ms, ms_to_seconds)


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise Untranslatable(f"{what} must be text, got {value!r}")
    return value


def _fields(allowed: Mapping[str, str], other_backend: str) -> Callable[[Any], dict[str, Any]]:
    """A converter for a ``check_dict``: keeps the fields both backends have, renamed by ``allowed``."""
    def convert(check_dict: Any) -> dict[str, Any]:
        if not isinstance(check_dict, dict):
            raise Untranslatable(f"check_dict must be an object, got {check_dict!r}")
        unknown = sorted(key for key in check_dict if key not in allowed)
        if unknown:
            raise Untranslatable(
                f"{other_backend} cannot check {', '.join(unknown)}; both backends check: "
                f"{', '.join(sorted(set(allowed.values())))}")
        return {allowed[key]: value for key, value in check_dict.items()}
    return convert


_PAGE_FIELDS = Conversion(
    _fields({"title": "title", "current_url": "current_url"}, "Playwright"),
    _fields({"title": "title", "current_url": "current_url", "url": "current_url"}, "Selenium"))
_ELEMENT_FIELDS = Conversion(
    _fields({"tag_name": "tag_name", "text": "text"}, "Playwright"),
    _fields({"tag_name": "tag_name", "text": "text"}, "Selenium"))

_GLOB_CHARACTERS = "*{}[]\\"


def _mock_pattern_to_playwright(pattern: Any) -> str:
    """Selenium mocks an exact URL, ``*/path`` or ``**/path``; in a Playwright glob only ``**`` crosses ``/``."""
    if isinstance(pattern, dict):
        raise Untranslatable("a URL pattern given as a dict of URL parts has no Playwright glob")
    text = _text(pattern, "url_pattern")
    return "**/" + text[2:] if text.startswith("*/") else text


def _mock_pattern_to_selenium(pattern: Any) -> str:
    text = _text(pattern, "url_pattern")
    path = text[3:] if text.startswith("**/") else text
    if any(character in path for character in _GLOB_CHARACTERS):
        raise Untranslatable(f"Selenium mocks an exact URL or '**/path', not the glob {text!r}")
    return text


_MOCK_PATTERN = Conversion(_mock_pattern_to_playwright, _mock_pattern_to_selenium)


def _mock_response(response: Any) -> Any:
    if isinstance(response, dict) and "reason" in response:
        raise Untranslatable("Playwright's mock has no 'reason' (the HTTP reason phrase)")
    return response


_MOCK_RESPONSE = Conversion(_mock_response, lambda response: response)


def playwright_selector(selector: Any, by: Any = "css selector") -> str:
    """The Playwright selector for a Selenium ``(by, selector)`` pair, as the ``TestObject`` translation gives it."""
    try:
        return test_object_to_selector(TestObject(_text(selector, "selector"), strategy_name(by)))
    except LocatorFileError as error:
        raise Untranslatable(str(error)) from error


# ----- builders: one Selenium action that needs more than a rename ---------------------------------

_BROWSERS: dict[str, dict[str, Any]] = {
    "chrome": {"browser": "chromium"},
    "chromium": {"browser": "chromium"},
    "edge": {"browser": "chromium", "channel": "msedge"},
    "firefox": {"browser": "firefox"},
}
_HEADLESS_OPTIONS = ("--headless", "-headless")


def _new_driver(args: dict[str, Any]) -> list[Action]:
    """``WR_new_driver`` -> ``WR_pw_new_browser`` (it also starts the first browser, like ``WR_new_driver``)."""
    if args.get("kwargs"):
        raise Untranslatable(f"Selenium driver arguments {sorted(args['kwargs'])} have no Playwright equivalent")
    name = args.get("webdriver_name")
    launch = _BROWSERS.get(name.lower() if isinstance(name, str) else "")
    if launch is None:
        raise Untranslatable(
            f"Playwright runs {', '.join(sorted(_BROWSERS))}, not {name!r} (its WebKit is not Safari)")
    options = list(args.get("options") or [])
    flags = [option for option in options if not str(option).startswith(_HEADLESS_OPTIONS)]
    # Selenium opens a window unless told otherwise; Playwright is headless unless told otherwise.
    arguments = {**launch, "headless": len(flags) != len(options)}
    if flags:
        arguments["args"] = flags
    return [["WR_pw_new_browser", arguments]]


def _attach(args: dict[str, Any]) -> list[Action]:
    extra = sorted(key for key in ("options", "experimental_options", "kwargs") if args.get(key))
    if extra:
        raise Untranslatable(f"{', '.join(extra)} cannot be given to a browser Playwright attaches to")
    if str(args.get("webdriver_name", "chrome")).lower() not in ("chrome", "chromium", "edge"):
        raise Untranslatable("Playwright attaches over the DevTools protocol, to Chromium browsers only")
    address = _text(args.get("debugger_address"), "debugger_address")
    endpoint = address if "://" in address else f"http://{address}"
    return [["WR_pw_connect_over_cdp", {"endpoint_url": endpoint}]]


def _find_by(command: str) -> Builder:
    """
    ``WR_find_element_by`` makes the match the current element; ``WR_pw_find_element`` does not. The
    selector is stored as a locator instead and found by name, which sets the current element.
    """
    def build(args: dict[str, Any]) -> list[Action]:
        selector = _text(args.get("selector"), "selector")
        by = args.get("by", "css selector")
        playwright_selector(selector, by)  # refuses a strategy Playwright has no selector for
        return [
            ["WR_save_locator", {"name": TRANSLATED_LOCATOR, "value": selector, "by": strategy_name(by)}],
            [command, {"element_name": TRANSLATED_LOCATOR}],
        ]
    return build


_find_one = _find_by("WR_pw_find_element_with_test_object_record")
_WAIT_STATES = {"present": "attached", "visible": "visible", "hidden": "hidden"}


def _wait_for_element(args: dict[str, Any]) -> list[Action]:
    state = args.get("state", "visible")
    if state == "clickable":
        raise Untranslatable(
            "Playwright's wait has no 'clickable' state (visible and enabled); wait for 'visible': "
            "Playwright waits for an enabled element before it clicks")
    if state not in _WAIT_STATES:
        raise Untranslatable(f"unknown wait state {state!r}")
    wait = ["WR_pw_wait_for_selector", {
        "selector": playwright_selector(args.get("selector"), args.get("by", "css selector")),
        "timeout": seconds_to_ms(args.get("timeout", 10.0)),
        "state": _WAIT_STATES[state],
    }]
    # Selenium's wait makes the element the current one, except for "hidden".
    return [wait] if state == "hidden" else [wait, *_find_one(args)]


def _wait_for_url(args: dict[str, Any]) -> list[Action]:
    pattern = _text(args.get("pattern"), "pattern")
    if any(character in pattern for character in _GLOB_CHARACTERS):
        raise Untranslatable(
            f"Selenium waits for a URL that contains {pattern!r}; its characters are wildcards in a Playwright glob")
    return [["WR_pw_wait_for_url", {"url": f"**{pattern}**", "timeout": seconds_to_ms(args.get("timeout", 10.0))}]]


def _script(wrapper: str) -> Builder:
    """Selenium runs a function body with ``arguments``; Playwright calls a function with one argument."""
    def build(args: dict[str, Any]) -> list[Action]:
        body = _text(args.get("script"), "script")
        expression = wrapper.replace("BODY", "(function () {\n" + body + "\n})")
        return [["WR_pw_evaluate", {"expression": expression, "arg": list(args.get("args") or ())}]]
    return build


_COOKIE_KEYS = {"name": "name", "value": "value", "domain": "domain", "path": "path", "secure": "secure",
                "httpOnly": "httpOnly", "sameSite": "sameSite", "expiry": "expires"}


def _add_cookie(args: dict[str, Any]) -> list[Action]:
    cookie = args.get("cookie_dict")
    if not isinstance(cookie, dict):
        raise Untranslatable(f"cookie_dict must be an object, got {cookie!r}")
    unknown = sorted(key for key in cookie if key not in _COOKIE_KEYS)
    if unknown:
        raise Untranslatable(f"cookie field(s) {', '.join(unknown)} have no Playwright equivalent")
    if not cookie.get("domain"):
        raise Untranslatable(
            "Selenium adds a cookie without 'domain' to the current page's domain; Playwright needs the domain")
    converted = {_COOKIE_KEYS[key]: value for key, value in cookie.items()}
    converted.setdefault("path", "/")
    return [["WR_pw_add_cookies", {"cookies": [converted]}]]


def _frame_selector(name: Any) -> str:
    if not isinstance(name, str) or not name or '"' in name or "\\" in name:
        raise Untranslatable(
            f"only a frame's id or name can be translated to a selector, not {name!r}; use WR_iframe_switch_chain")
    return ", ".join(f'{tag}[{attribute}="{name}"]' for attribute in ("id", "name") for tag in ("iframe", "frame"))


def _switch(args: dict[str, Any]) -> list[Action]:
    kind = str(args.get("switch_type")).lower()
    if kind == "default_content":
        return [["WR_pw_switch_to_main_frame"]]
    if kind == "parent_frame":
        return [["WR_pw_switch_to_parent_frame"]]
    if kind == "frame":
        return [["WR_pw_switch_to_frame", {"selectors": _frame_selector(args.get("switch_target_name"))}]]
    if kind == "window":
        raise Untranslatable(
            "a window handle is Selenium's own id; Playwright switches pages by index, URL or title "
            "(WR_switch_to_window_by_url and WR_switch_to_window_by_title translate)")
    raise Untranslatable(f"switch type {kind!r} returns a Selenium object and has no Playwright command")


def _iframe_chain(args: dict[str, Any]) -> list[Action]:
    """Selenium's chain starts at the top document; Playwright's is relative to the current frame."""
    selectors = args.get("selectors")
    if not isinstance(selectors, (list, tuple)):
        raise Untranslatable(f"selectors must be a list, got {selectors!r}")
    return [["WR_pw_switch_to_main_frame"], ["WR_pw_switch_to_frame", {"selectors": list(selectors)}]]


def _emulate_device(args: dict[str, Any]) -> list[Action]:
    """A WebRunner device preset as Playwright context options (Playwright's own device names differ)."""
    try:
        return [["WR_pw_set_context_options", playwright_kwargs(_text(args.get("name"), "name"))]]
    except DeviceEmulationError as error:
        raise Untranslatable(str(error)) from error


def _clock_freeze(args: dict[str, Any]) -> list[Action]:
    """
    ``WR_clock_freeze`` -> ``WR_pw_clock_set_time`` (Playwright's fixed time: ``Date`` stops, timers run).

    The moment is given as ISO text, which ``WR_pw_clock_set_time`` takes as well as milliseconds and
    which reads the same to a person.
    """
    if args.get("advance_ms_per_real_second"):
        raise Untranslatable("Playwright's fixed time does not advance; advance_ms_per_real_second has no equivalent")
    try:
        moment = datetime.fromtimestamp(to_epoch_ms(args.get("moment", "")) / 1000, tz=timezone.utc)
    except (TimeFreezerError, TypeError, ValueError, OverflowError, OSError) as error:
        raise Untranslatable(f"moment must be a literal time to be converted: {error}") from error
    return [["WR_pw_clock_set_time", {"time_ms": moment.isoformat(timespec="milliseconds")}]]


def _network_conditions(args: dict[str, Any]) -> list[Action]:
    """The same DevTools command Selenium's wrapper sends, through the Playwright page's CDP session."""
    params = {
        "offline": args.get("offline", False),
        "latency": args.get("latency", 0),
        "downloadThroughput": args.get("download_throughput", -1),
        "uploadThroughput": args.get("upload_throughput", -1),
    }
    return [["WR_pw_cdp", {"method": "Network.emulateNetworkConditions", "params": params}]]


# ----- the table ---------------------------------------------------------------------------------

def _same(*names: str) -> dict[str, Rule]:
    """``WR_<name>`` -> ``WR_pw_<name>`` with the same arguments."""
    return {f"WR_{name}": Rule(f"WR_pw_{name}") for name in names}


SELENIUM_TO_PLAYWRIGHT: dict[str, Rule | Builder] = {
    # start / stop, several browsers, attach
    "WR_new_driver": _new_driver,
    "WR_quit_all": Rule("WR_pw_quit"),
    "WR_quit_current": Rule("WR_pw_close_browser"),
    "WR_change_index_of_webdriver": Rule("WR_pw_switch_browser", rename={"index_of_webdriver": "index"}),
    "WR_attach_to_existing_browser": _attach,
    # navigation, page info
    **_same("to_url", "back", "forward", "refresh"),
    "WR_get_current_url": Rule("WR_pw_url"),
    "WR_get_title": Rule("WR_pw_title"),
    "WR_get_page_source": Rule("WR_pw_content"),
    # finding
    "WR_find_recorded_element": Rule("WR_pw_find_element_with_test_object_record"),
    "WR_find_recorded_elements": Rule("WR_pw_find_elements_with_test_object_record"),
    "WR_find_element_by": _find_one,
    "WR_find_elements_by": _find_by("WR_pw_find_elements_with_test_object_record"),
    # the current element
    **_same("element_click", "element_check", "element_uncheck", "element_hover", "element_inner_text",
            "element_inner_html", "element_submit", "element_value_of_css_property", "element_clear",
            "element_get_property", "element_is_enabled", "element_screenshot"),
    "WR_element_is_selected": Rule("WR_pw_element_is_checked"),
    "WR_element_is_displayed": Rule("WR_pw_element_is_visible"),
    # send_keys appends, and type_text is documented to; fill would replace the value. Playwright types at
    # the caret, though, which is at the start of a field that already holds text.
    "WR_element_input": Rule("WR_pw_element_type_text"),
    "WR_element_get_dom_attribute": Rule("WR_pw_element_get_attribute"),
    "WR_element_change_web_element": Rule("WR_pw_element_change"),
    "WR_element_assert": Rule("WR_pw_element_assert", convert={"check_dict": _ELEMENT_FIELDS}),
    # Playwright's value also matches an option's label, so the other direction is not offered.
    "WR_element_select_by_value": Rule("WR_pw_element_select_option", inverse=False),
    # devices, permissions, clock
    "WR_emulate_device": _emulate_device,
    **_same("grant_permissions", "clear_permissions"),
    "WR_clock_freeze": _clock_freeze,
    # waits and timeouts
    "WR_wait_for_element": _wait_for_element,
    "WR_wait_for_url": _wait_for_url,
    "WR_wait_for_ready_state": Rule("WR_pw_wait_for_load_state", convert={"timeout": SECONDS},
                                    add={"state": "load"}, defaults={"timeout": 30000}),
    "WR_set_page_load_timeout": Rule("WR_pw_set_default_navigation_timeout",
                                     rename={"time_to_wait": "timeout_ms"}, convert={"time_to_wait": SECONDS}),
    # JavaScript
    "WR_execute_script": _script("(args) => BODY.apply(null, args)"),
    "WR_execute_async_script": _script("(args) => new Promise((resolve) => BODY.apply(null, [...args, resolve]))"),
    # screenshots, PDF
    "WR_save_screenshot": Rule("WR_pw_screenshot", rename={"file_path": "path"}),
    "WR_save_full_page_screenshot": Rule("WR_pw_screenshot", rename={"file_path": "path"},
                                         add={"full_page": True}),
    "WR_get_screenshot_as_png": Rule("WR_pw_screenshot_bytes"),
    "WR_get_screenshot_as_base64": Rule("WR_pw_screenshot_base64"),
    "WR_print_page": Rule("WR_pw_print_page"),
    # cookies
    **_same("get_cookies", "get_cookie", "delete_cookie"),
    "WR_add_cookie": _add_cookie,
    "WR_delete_all_cookies": Rule("WR_pw_clear_cookies"),
    # assertions
    "WR_check_current_webdriver": Rule("WR_pw_check_current_page", convert={"check_dict": _PAGE_FIELDS}),
    # tabs
    "WR_new_window": Rule("WR_pw_new_page"),
    "WR_switch": _switch,
    "WR_switch_to_window_by_url": Rule("WR_pw_switch_to_page_by_url"),
    "WR_switch_to_window_by_title": Rule("WR_pw_switch_to_page_by_title"),
    "WR_close_window": Rule("WR_pw_close_page"),
    "WR_bring_to_front": Rule("WR_pw_bring_to_front"),
    # scrolling
    "WR_scroll": Rule("WR_pw_scroll", inverse=False),  # one of QUEUED_COMMANDS
    **_same("scroll_to_top", "scroll_to_bottom"),
    # init script, blocked URLs
    "WR_add_script_to_evaluate_on_new_document": Rule("WR_pw_add_init_script"),
    **_same("block_urls", "unblock_urls"),
    # frames
    "WR_iframe_switch_chain": _iframe_chain,
    "WR_iframe_back_to_default": Rule("WR_pw_switch_to_main_frame"),
    # emulation and context settings
    "WR_set_device_metrics": Rule("WR_pw_set_viewport_size"),
    # The nearest Playwright has to a window size; a viewport is not turned back into a window.
    "WR_set_window_size": Rule("WR_pw_set_viewport_size", inverse=False),
    **_same("set_user_agent", "set_timezone", "set_locale", "set_extra_http_headers", "set_cache_disabled"),
    "WR_set_geolocation": Rule("WR_pw_set_geolocation", defaults={"accuracy": 100},
                               inverse_defaults={"accuracy": 0}),
    "WR_clear_geolocation_override": Rule("WR_pw_clear_geolocation"),
    # visual regression, recorder
    **_same("visual_capture_baseline", "visual_compare", "recorder_start", "recorder_stop",
            "recorder_pull_events", "recorder_save"),
    # console, responses
    **_same("event_capture_start", "event_capture_stop", "event_capture_clear", "console_messages",
            "network_responses", "assert_no_console_errors", "assert_no_5xx", "assert_no_4xx_or_5xx"),
    # response mocks
    "WR_route_mock": Rule("WR_pw_route_mock", convert={"url_pattern": _MOCK_PATTERN, "response": _MOCK_RESPONSE}),
    "WR_route_mock_json": Rule("WR_pw_route_mock_json", convert={"url_pattern": _MOCK_PATTERN}),
    "WR_route_unmock": Rule("WR_pw_route_unmock", convert={"url_pattern": _MOCK_PATTERN}),
    "WR_route_clear": Rule("WR_pw_route_clear"),
    # throttling, raw CDP
    **_same("throttle", "throttle_clear", "cdp"),
    "WR_set_network_conditions": _network_conditions,
    "WR_execute_cdp_cmd": Rule("WR_pw_cdp", rename={"cmd": "method", "cmd_args": "params"}, inverse=False),
    # the same helper on both backends
    **_same("local_storage_set", "local_storage_get", "local_storage_remove", "local_storage_clear",
            "local_storage_all", "session_storage_set", "session_storage_get", "session_storage_clear",
            "indexed_db_drop", "sw_unregister", "sw_clear_caches", "sw_bypass", "shadow_query", "upload_file",
            "find_with_healing", "a11y_run_audit", "perf_collect"),
}

# ActionChains commands of the table: Selenium runs them at the next ``WR_perform``, so the translator
# places their translation there.
QUEUED_COMMANDS = frozenset({"WR_scroll"})
# The commands whose translation depends on the actions around them; the translator handles them itself.
PERFORM = "WR_perform"
HAR_START, HAR_STOP = "WR_start_har_recording", "WR_stop_har_recording"
PW_HAR_START, PW_HAR_STOP = "WR_pw_start_har_recording", "WR_pw_stop_har_recording"
SEQUENCE_COMMANDS = {
    PERFORM: "runs the ActionChains commands queued before it; the translated ones are placed here",
    HAR_START: f"{PW_HAR_START}, with the path the following {HAR_STOP} gives",
    HAR_STOP: PW_HAR_STOP,
}

_RECORDED_NAME = (
    "it acts on a recorded TestObject without making it the current element, and no Playwright command takes "
    "a recorded name that way; use WR_find_recorded_element and then {instead}")
_WINDOW = "Playwright controls the viewport, not the OS window (WR_set_window_size becomes the viewport size)"

# Selenium commands with no faithful Playwright translation, and why. A Selenium command that is neither
# here nor in the table is refused too, with a general reason.
CANNOT_TRANSLATE: dict[str, str] = {
    "WR_start_remote_driver": "Selenium Grid speaks the WebDriver protocol, which Playwright does not",
    "WR_appium_start": "Appium sessions are WebDriver sessions; Playwright has no mobile-app backend",
    "WR_appium_quit": "Appium sessions are WebDriver sessions; Playwright has no mobile-app backend",
    "WR_maximize_window": _WINDOW,
    "WR_minimize_window": _WINDOW,
    "WR_fullscreen_window": _WINDOW,
    "WR_set_window_position": _WINDOW,
    "WR_set_window_rect": _WINDOW,
    "WR_chrome_options_with_extension":
        "it builds Selenium ChromeOptions; on Playwright an extension needs WR_pw_launch_persistent with "
        "extension_paths and a profile directory",
    "WR_alert_accept": "Selenium answers the dialog that is open; Playwright needs WR_pw_set_dialog_policy "
                       "before the action that opens it",
    "WR_alert_dismiss": "Selenium answers the dialog that is open; Playwright needs WR_pw_set_dialog_policy "
                        "before the action that opens it",
    "WR_alert_text": "Selenium reads the dialog that is open; Playwright has handled it by then "
                     "(WR_pw_last_dialog reads it afterwards)",
    "WR_list_devices": "the device names differ: WebRunner's presets on Selenium, Playwright's descriptors there",
    "WR_left_click": _RECORDED_NAME.format(instead="WR_element_click"),
    "WR_move_to_element": _RECORDED_NAME.format(instead="WR_element_hover"),
    "WR_drag_and_drop_offset": "it drags a recorded TestObject by name; WR_pw_drag_and_drop_offset needs the "
                               "selector, which is known only when the file runs",
    "WR_implicitly_wait": "Playwright's element lookup does not wait; wait with WR_wait_for_element, which translates",
    "WR_wait_for_title": "Playwright has no wait for the page title",
    "WR_set_script_timeout": "WR_pw_evaluate has no timeout",
    "WR_save_cookies": "the file differs: Selenium saves a cookie list, WR_pw_save_storage_state saves cookies "
                       "and localStorage, and nothing loads it into an open Playwright context",
    "WR_load_cookies": "Playwright loads saved state only when a context is created (the storage_state option)",
    "WR_element_select_by_index": "WR_pw_element_select_option takes a value only; an index needs "
                                  "WR_pw_select_option with a selector and index=",
    "WR_element_select_by_visible_text": "WR_pw_element_select_option takes a value only; a label needs "
                                         "WR_pw_select_option with a selector and label=",
    "WR_set_download_directory": "Playwright saves a download with WR_pw_download(selector, save_to), in one step",
    "WR_wait_for_download": "Playwright keeps a download in its own directory until WR_pw_download saves it",
    "WR_dom_mutations": "DOM mutation capture exists only on Selenium (BiDi)",
}
