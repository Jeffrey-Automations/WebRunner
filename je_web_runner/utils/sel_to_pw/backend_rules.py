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

A few builders give one Playwright action when the Playwright backend has the twin command and several
when it does not (:func:`available`): ``WR_find_element_by`` is ``WR_pw_find_element_by`` where that is
registered, and otherwise stores the selector as a locator, finds it by name and checks that an element
was found. The keyboard and pointer rows are in
:mod:`~je_web_runner.utils.sel_to_pw.backend_input`, the refusals in
:mod:`~je_web_runner.utils.sel_to_pw.backend_refusals`.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from je_web_runner.utils.device_emulation.presets import DeviceEmulationError, playwright_kwargs
from je_web_runner.utils.sel_to_pw.backend_binding import registered_command
from je_web_runner.utils.sel_to_pw.backend_input import INPUT_RULES, QUEUED_INPUT
from je_web_runner.utils.sel_to_pw.backend_refusals import CANNOT_TRANSLATE
from je_web_runner.utils.sel_to_pw.backend_types import (
    SECONDS,
    Action,
    Builder,
    Conversion,
    Rule,
    Untranslatable,
    seconds_to_ms,
)
from je_web_runner.utils.sel_to_pw.backend_types import text as _text
from je_web_runner.utils.test_object.locator_file import LocatorFileError, strategy_name
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.time_freezer.freezer import TimeFreezerError, to_epoch_ms
from je_web_runner.webdriver.playwright_locator import test_object_to_selector

__all__ = [
    "Action", "Builder", "CANNOT_TRANSLATE", "Conversion", "QUEUED_COMMANDS", "Rule", "SELENIUM_TO_PLAYWRIGHT",
    "SEQUENCE_COMMANDS", "TRANSLATED_LOCATOR", "Untranslatable", "available", "playwright_selector",
]

# The logical locator name a translated raw-selector lookup is stored under (see ``_stored_lookup``).
TRANSLATED_LOCATOR = "sel_to_pw.selector"
# Playwright twins of ``WR_find_element_by`` / ``WR_find_elements_by``; used once they are registered.
FIND_TWIN = "WR_pw_find_element_by"
FIND_ALL_TWIN = "WR_pw_find_elements_by"


def available(command: str, parameter: str | None = None) -> bool:
    """Whether the executor registers ``command`` (and, with ``parameter``, whether it takes that argument)."""
    registered = registered_command(command)
    if registered is None:
        return False
    return parameter is None or parameter in inspect.signature(registered).parameters


# ----- value conversions -------------------------------------------------------------------------

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


# Arguments about Selenium's driver binary and its BiDi channel: Playwright has no driver to download and
# captures console and network events without a switch, so leaving them out changes nothing.
_DRIVER_ONLY = ("install_driver", "webdriver_manager_option_dict", "enable_bidi")
_BROWSER_ARGUMENTS = ("webdriver_name", "options", "kwargs", *_DRIVER_ONLY)


def _start(command: str) -> Builder:
    """
    Start a browser. ``WR_new_driver`` adds one (``WR_pw_new_browser`` does too, also for the first);
    ``WR_set_driver`` makes a new browser the wrapper's only one, as ``WR_pw_launch`` does.
    """
    def build(args: dict[str, Any]) -> list[Action]:
        given = {**args, **(args.get("kwargs") or {})}
        extra = sorted(key for key, value in given.items() if key not in _BROWSER_ARGUMENTS and value)
        if extra:
            raise Untranslatable(f"Selenium driver arguments {extra} have no Playwright equivalent")
        name = given.get("webdriver_name")
        launch = _BROWSERS.get(name.lower() if isinstance(name, str) else "")
        if launch is None:
            raise Untranslatable(
                f"Playwright runs {', '.join(sorted(_BROWSERS))}, not {name!r} (its WebKit is not Safari)")
        options = list(given.get("options") or [])
        flags = [option for option in options if not str(option).startswith(_HEADLESS_OPTIONS)]
        # Selenium opens a window unless told otherwise; Playwright is headless unless told otherwise.
        arguments = {**launch, "headless": len(flags) != len(options)}
        if flags:
            arguments["args"] = flags
        return [[command, arguments]]
    return build


def _attach(args: dict[str, Any]) -> list[Action]:
    """``WR_attach_to_existing_browser`` takes ``host:port``; Playwright takes the DevTools URL."""
    extra = sorted(key for key in ("options", "experimental_options", "kwargs") if args.get(key))
    if extra:
        raise Untranslatable(f"{', '.join(extra)} cannot be given to a browser Playwright attaches to")
    if str(args.get("webdriver_name", "chrome")).lower() not in ("chrome", "chromium", "edge"):
        raise Untranslatable("Playwright attaches over the DevTools protocol, to Chromium browsers only")
    address = _text(args.get("debugger_address"), "debugger_address")
    endpoint = address if "://" in address else f"http://{address}"
    return [["WR_pw_connect_over_cdp", {"endpoint_url": endpoint}]]


def _stored_lookup(command: str, args: dict[str, Any]) -> list[Action]:
    """
    ``WR_pw_find_element`` does not make the match the current element, as ``WR_find_element_by`` does.
    The selector is stored as a locator instead and found by name with ``command``, which sets it.
    """
    selector = _text(args.get("selector"), "selector")
    return [
        ["WR_save_locator", {"name": TRANSLATED_LOCATOR, "value": selector,
                             "by": strategy_name(args.get("by", "css selector"))}],
        [command, {"element_name": TRANSLATED_LOCATOR}],
    ]


def _find_by(twin: str, command: str, must_match: bool) -> Builder:
    """A raw-selector lookup: the Playwright twin when it is registered, else the stored lookup."""
    def build(args: dict[str, Any]) -> list[Action]:
        playwright_selector(args.get("selector"), args.get("by", "css selector"))  # refuses what has no selector
        if available(twin):
            return [[twin, {key: args[key] for key in ("selector", "by") if key in args}]]
        lookup = _stored_lookup(command, args)
        # Selenium fails when nothing matches; the lookup by name does not, and this check does.
        return [*lookup, ["WR_pw_element_assert", {"check_dict": {}}]] if must_match else lookup
    return build


_find_one = _find_by(FIND_TWIN, "WR_pw_find_element_with_test_object_record", must_match=True)
_WAIT_STATES = {"present": "attached", "visible": "visible", "hidden": "hidden"}
_WAIT, _MAKE_CURRENT = "WR_pw_wait_for_selector", "make_current"


def _wait_for_element(args: dict[str, Any]) -> list[Action]:
    """
    ``WR_wait_for_element`` -> ``WR_pw_wait_for_selector``. Selenium's wait also makes the element the
    current one (except for ``hidden``): with ``make_current`` where the Playwright command takes it,
    otherwise with a lookup after the wait.
    """
    state = args.get("state", "visible")
    if state == "clickable":
        raise Untranslatable(
            "Playwright's wait has no 'clickable' state (visible and enabled); wait for 'visible': "
            "Playwright waits for an enabled element before it clicks")
    if state not in _WAIT_STATES:
        raise Untranslatable(f"unknown wait state {state!r}")
    arguments = {
        "selector": playwright_selector(args.get("selector"), args.get("by", "css selector")),
        "timeout": seconds_to_ms(args.get("timeout", 10.0)),
        "state": _WAIT_STATES[state],
    }
    if state == "hidden":
        return [[_WAIT, arguments]]
    if available(_WAIT, _MAKE_CURRENT):
        return [[_WAIT, {**arguments, _MAKE_CURRENT: True}]]
    if available(FIND_TWIN):
        return [[_WAIT, arguments], *_find_one(args)]
    return [[_WAIT, arguments], *_stored_lookup("WR_pw_find_element_with_test_object_record", args)]


def _assert_title(args: dict[str, Any]) -> list[Action]:
    """``WR_assert_title`` -> the ``title`` field of ``WR_pw_check_current_page``; both name the title found."""
    return [["WR_pw_check_current_page", {"check_dict": {"title": args.get("value")}}]]


def _reload(args: dict[str, Any]) -> list[Action]:
    """``WR_reload``: a refresh, or the DevTools reload Selenium's wrapper sends to skip the cache."""
    if args.get("ignore_cache"):
        return [["WR_pw_cdp", {"method": "Page.reload", "params": {"ignoreCache": True}}]]
    return [["WR_pw_refresh"]]


def _clear_origin_storage(args: dict[str, Any]) -> list[Action]:
    """The same DevTools command Selenium's wrapper sends, through the Playwright page's CDP session."""
    params = {"origin": args.get("origin"), "storageTypes": "all"}
    return [["WR_pw_cdp", {"method": "Storage.clearDataForOrigin", "params": params}]]


def _geo_locale(args: dict[str, Any]) -> list[Action]:
    """``WR_geo_locale_apply`` sets up to three overrides; each has its own Playwright command."""
    latitude, longitude = args.get("latitude"), args.get("longitude")
    if (latitude is None) != (longitude is None):
        raise Untranslatable("latitude and longitude must be set together")
    actions: list[Action] = []
    if latitude is not None:
        actions.append(["WR_pw_set_geolocation", {
            "latitude": latitude, "longitude": longitude, "accuracy": args.get("accuracy_meters", 50.0)}])
    if args.get("timezone") is not None:
        actions.append(["WR_pw_set_timezone", {"timezone_id": args["timezone"]}])
    if args.get("locale") is not None:
        actions.append(["WR_pw_set_locale", {"locale": args["locale"]}])
    return actions


def _touch_frames(args: dict[str, Any]) -> list[Action]:
    """``WR_touch_gesture_dispatch`` sends one DevTools touch event per frame; so does this."""
    frames = args.get("frames")
    if not isinstance(frames, list) or not all(isinstance(frame, dict) for frame in frames):
        raise Untranslatable(f"frames must be a literal list of touch frames to be translated, got {frames!r}")
    return [["WR_pw_cdp", {"method": "Input.dispatchTouchEvent", "params": frame}] for frame in frames]


def _wait_for_url(args: dict[str, Any]) -> list[Action]:
    """Selenium waits for a URL that contains the pattern; Playwright for one that matches a glob."""
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
    "WR_new_driver": _start("WR_pw_new_browser"),
    "WR_set_driver": _start("WR_pw_launch"),
    "WR_quit_all": Rule("WR_pw_quit"),
    "WR_quit_current": Rule("WR_pw_close_browser"),
    "WR_change_index_of_webdriver": Rule("WR_pw_switch_browser", rename={"index_of_webdriver": "index"}),
    "WR_attach_to_existing_browser": _attach,
    # navigation, page info
    **_same("to_url", "back", "forward", "refresh"),
    "WR_reload": _reload,
    "WR_get_current_url": Rule("WR_pw_url"),
    "WR_get_title": Rule("WR_pw_title"),
    "WR_get_page_source": Rule("WR_pw_content"),
    # finding
    "WR_find_recorded_element": Rule("WR_pw_find_element_with_test_object_record"),
    "WR_find_recorded_elements": Rule("WR_pw_find_elements_with_test_object_record"),
    "WR_find_element_by": _find_one,
    "WR_find_elements_by": _find_by(FIND_ALL_TWIN, "WR_pw_find_elements_with_test_object_record",
                                    must_match=False),
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
    "WR_assert_title": _assert_title,
    # tabs
    "WR_new_window": Rule("WR_pw_new_page"),
    "WR_switch": _switch,
    "WR_switch_to_window_by_url": Rule("WR_pw_switch_to_page_by_url"),
    "WR_switch_to_window_by_title": Rule("WR_pw_switch_to_page_by_title"),
    "WR_close_window": Rule("WR_pw_close_page"),
    "WR_bring_to_front": Rule("WR_pw_bring_to_front"),
    # keyboard, pointer, scrolling (the ActionChains commands are in backend_input)
    **INPUT_RULES,
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
    "WR_geo_locale_apply": _geo_locale,
    "WR_clear_origin_storage": _clear_origin_storage,
    "WR_touch_gesture_dispatch": _touch_frames,
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
QUEUED_COMMANDS = QUEUED_INPUT
# The commands whose translation depends on the actions around them; the translator handles them itself.
PERFORM = "WR_perform"
RESET_ACTIONS = "WR_reset_actions"
HAR_START, HAR_STOP = "WR_start_har_recording", "WR_stop_har_recording"
PW_HAR_START, PW_HAR_STOP = "WR_pw_start_har_recording", "WR_pw_stop_har_recording"
SEQUENCE_COMMANDS = {
    PERFORM: "runs the ActionChains commands queued before it; the translated ones are placed here",
    RESET_ACTIONS: "forgets the ActionChains commands queued before it; so does the translation",
    HAR_START: f"{PW_HAR_START}, with the path the following {HAR_STOP} gives",
    HAR_STOP: PW_HAR_STOP,
}
