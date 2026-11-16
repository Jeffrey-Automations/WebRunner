"""Translating keyboard and pointer commands, browser starts, lookups, and actions that sit alone."""
import unittest
from unittest import mock

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.sel_to_pw import BackendTranslationError, translate_for_backend, untranslatable_commands
from je_web_runner.utils.sel_to_pw import backend_rules as rules
from je_web_runner.utils.sel_to_pw.backend_binding import SELENIUM, backend_of

_LOCATOR = rules.TRANSLATED_LOCATOR
_SAVE_GO = ["WR_save_locator", {"name": _LOCATOR, "value": "#go", "by": "CSS_SELECTOR"}]
_FIND_SAVED = ["WR_pw_find_element_with_test_object_record", {"element_name": _LOCATOR}]
_MUST_EXIST = ["WR_pw_element_assert", {"check_dict": {}}]
_WAIT_GO = {"selector": "#go", "timeout": 10000, "state": "visible"}
# Selenium commands that touch no browser object themselves and are refused all the same.
_NOT_BROWSER_BOUND = {"WR_chrome_options_with_extension", "WR_wait_for_download", "WR_list_devices"}


def _one(action):
    return translate_for_backend([action])


def _performed(*actions):
    return translate_for_backend([*actions, ["WR_perform"]])


def _reason(action):
    try:
        translate_for_backend([action])
    except BackendTranslationError as error:
        return error.problems[0].reason
    return ""


def _twins(*present):
    """Pretend the Playwright backend has exactly the twin commands (or ``command.parameter``) in ``present``."""
    def available(command, parameter=None):
        return (command if parameter is None else f"{command}.{parameter}") in present
    return mock.patch.object(rules, "available", available)


class TestKeyboard(unittest.TestCase):

    def test_press_keys_acts_at_once_with_playwright_key_names(self):
        self.assertEqual(_one(["WR_press_keys", [["Ctrl", "a", "b", "Return", "Esc", "Arrow_Down", "F5"]]]), [
            ["WR_pw_keyboard_press", {"key": "Control"}],
            ["WR_pw_keyboard_press", {"key": "a"}],
            ["WR_pw_keyboard_press", {"key": "b"}],
            ["WR_pw_keyboard_press", {"key": "NumpadEnter"}],
            ["WR_pw_keyboard_press", {"key": "Escape"}],
            ["WR_pw_keyboard_press", {"key": "ArrowDown"}],
            ["WR_pw_keyboard_press", {"key": "F5"}],
        ])
        self.assertEqual(_one(["WR_press_keys", {"keys": "Enter"}]), [["WR_pw_keyboard_press", {"key": "NumpadEnter"}]])

    def test_send_keys_is_queued_and_presses_keys_but_types_other_text(self):
        self.assertEqual(_performed(["WR_send_keys", ["h 中文+"]]), [
            ["WR_pw_keyboard_press", {"key": "h"}],
            ["WR_pw_keyboard_press", {"key": " "}],
            ["WR_pw_keyboard_press", {"key": "Tab"}],
            ["WR_pw_keyboard_type", {"text": "中文+"}],
            ["WR_pw_keyboard_press", {"key": "Enter"}],
        ])
        self.assertEqual(_performed(["WR_send_keys", [["a", "B"]]]),
                         [["WR_pw_keyboard_press", {"key": "a"}], ["WR_pw_keyboard_press", {"key": "B"}]])
        self.assertIn("WR_perform", _reason(["WR_send_keys", ["hi"]]))

    def test_a_held_key_goes_down_and_up_around_the_keys_pressed_meanwhile(self):
        self.assertEqual(
            _performed(["WR_press_key", [""]], ["WR_send_keys", ["a"]], ["WR_release_key", [""]]),
            [["WR_pw_keyboard_down", {"key": "Control"}], ["WR_pw_keyboard_press", {"key": "a"}],
             ["WR_pw_keyboard_up", {"key": "Control"}]])
        self.assertIn("shifted", _reason(["WR_press_key", [""]]))

    def test_keys_without_a_playwright_name_are_refused(self):
        for action in (["WR_press_keys", ["NoSuchKey"]], ["WR_press_keys", [1]], ["WR_send_keys", [""]],
                       ["WR_press_key", [""]], ["WR_press_key", ["ab"]], ["WR_send_keys", ["${text}", 3]],
                       ["WR_press_key", ["", "login"]], ["WR_release_key", ["", "login"]]):
            with self.subTest(action=action):
                self.assertTrue(_reason(action))

    def test_a_pause_in_the_chain_is_a_wait_in_milliseconds(self):
        self.assertEqual(_performed(["WR_pause", [2]]), [["WR_pw_wait_for_timeout", {"timeout_ms": 2000}]])

    def test_reset_actions_forgets_what_was_queued(self):
        self.assertEqual(
            _performed(["WR_send_keys", ["dropped"]], ["WR_reset_actions"], ["WR_send_keys", ["k"]]),
            [["WR_pw_keyboard_press", {"key": "k"}]])
        self.assertEqual(translate_for_backend([["WR_scroll", [0, 9]], ["WR_reset_actions"]]), [])


class TestPointer(unittest.TestCase):

    def test_clicks_where_the_pointer_is(self):
        down, up = ["WR_pw_mouse_down"], ["WR_pw_mouse_up"]
        right = {"button": "right"}
        second = {"click_count": 2}
        self.assertEqual(_performed(["WR_left_click"]), [down, up])
        self.assertEqual(_performed(["WR_right_click"]), [["WR_pw_mouse_down", right], ["WR_pw_mouse_up", right]])
        self.assertEqual(_performed(["WR_left_double_click"]),
                         [down, up, ["WR_pw_mouse_down", second], ["WR_pw_mouse_up", second]])
        self.assertEqual(_performed(["WR_left_click_and_hold"], ["WR_pause", [0.5]], ["WR_release", [None]]),
                         [down, ["WR_pw_wait_for_timeout", {"timeout_ms": 500}], up])

    def test_a_recorded_name_is_refused_with_what_to_write_instead(self):
        self.assertIn("WR_element_click", _reason(["WR_left_click", ["login"]]))
        for command in ("WR_right_click", "WR_left_double_click", "WR_left_click_and_hold", "WR_release"):
            with self.subTest(command=command):
                self.assertIn("recorded TestObject", _reason([command, {"element_name": "login"}]))

    def test_the_two_results_do_not_share_their_arguments(self):
        first, second = _performed(["WR_right_click"]), _performed(["WR_right_click"])
        first[0][1]["button"] = "middle"
        self.assertEqual(second[0], ["WR_pw_mouse_down", {"button": "right"}])


class TestStartingABrowser(unittest.TestCase):

    def test_set_driver_launches_and_new_driver_adds_a_browser(self):
        options = ["--headless=new", "--disable-gpu"]
        expected = {"browser": "chromium", "headless": True, "args": ["--disable-gpu"]}
        self.assertEqual(_one(["WR_set_driver", {"webdriver_name": "chrome", "options": options}]),
                         [["WR_pw_launch", expected]])
        self.assertEqual(_one(["WR_new_driver", {"webdriver_name": "chrome", "options": options}]),
                         [["WR_pw_new_browser", expected]])

    def test_arguments_about_the_selenium_driver_change_nothing(self):
        expected = [["WR_pw_launch", {"browser": "firefox", "headless": False}]]
        self.assertEqual(_one(["WR_set_driver", {"webdriver_name": "Firefox", "enable_bidi": True,
                                                 "install_driver": False, "webdriver_manager_option_dict": {}}]),
                         expected)
        self.assertEqual(_one(["WR_new_driver", {"webdriver_name": "firefox", "enable_bidi": True}]),
                         [["WR_pw_new_browser", {"browser": "firefox", "headless": False}]])

    def test_other_driver_arguments_are_refused(self):
        for action in (["WR_set_driver", {"webdriver_name": "chrome", "experimental_options": {"detach": True}}],
                       ["WR_set_driver", {"webdriver_name": "chrome", "service": "x"}],
                       ["WR_set_driver", ["ie"]]):
            with self.subTest(action=action):
                self.assertTrue(_reason(action))


class TestLookups(unittest.TestCase):

    def test_without_the_twin_the_selector_is_stored_found_and_checked(self):
        with _twins():
            self.assertEqual(_one(["WR_find_element_by", ["#go"]]), [_SAVE_GO, _FIND_SAVED, _MUST_EXIST])
            self.assertEqual(_one(["WR_find_elements_by", ["#go"]]), [
                _SAVE_GO, ["WR_pw_find_elements_with_test_object_record", {"element_name": _LOCATOR}]])
            self.assertEqual(_one(["WR_wait_for_element", ["#go"]]),
                             [["WR_pw_wait_for_selector", _WAIT_GO], _SAVE_GO, _FIND_SAVED])

    def test_with_the_twins_a_lookup_is_one_action(self):
        with _twins(rules.FIND_TWIN, rules.FIND_ALL_TWIN):
            self.assertEqual(_one(["WR_find_element_by", ["go", "id"]]),
                             [[rules.FIND_TWIN, {"selector": "go", "by": "id"}]])
            self.assertEqual(_one(["WR_find_elements_by", {"selector": "li"}]),
                             [[rules.FIND_ALL_TWIN, {"selector": "li"}]])
            self.assertEqual(_one(["WR_wait_for_element", ["#go"]]),
                             [["WR_pw_wait_for_selector", _WAIT_GO], [rules.FIND_TWIN, {"selector": "#go"}]])
            self.assertEqual(
                _one(["WR_capture", {"name": "found", "action": ["WR_find_element_by", ["#go"]]}]),
                [["WR_capture", {"name": "found", "action": [rules.FIND_TWIN, {"selector": "#go"}]}]])

    def test_a_wait_that_makes_the_element_current_is_one_action(self):
        with _twins("WR_pw_wait_for_selector.make_current"):
            self.assertEqual(_one(["WR_wait_for_element", ["#go"]]),
                             [["WR_pw_wait_for_selector", {**_WAIT_GO, "make_current": True}]])
            self.assertEqual(_one(["WR_wait_for_element", ["#go", "css selector", 10, "hidden"]]),
                             [["WR_pw_wait_for_selector", {**_WAIT_GO, "state": "hidden"}]])

    def test_the_twins_are_used_exactly_when_the_executor_registers_them(self):
        for command in (rules.FIND_TWIN, rules.FIND_ALL_TWIN):
            self.assertEqual(rules.available(command), command in executor.event_dict)
        self.assertTrue(rules.available("WR_pw_wait_for_selector", "selector"))
        self.assertFalse(rules.available("WR_pw_wait_for_selector", "no_such_parameter"))
        produced = _one(["WR_find_element_by", ["#go"]])
        self.assertEqual(len(produced), 1 if rules.FIND_TWIN in executor.event_dict else 3)

    def test_a_strategy_without_a_selector_is_refused_either_way(self):
        for present in ((), (rules.FIND_TWIN,)):
            with self.subTest(present=present), _twins(*present):
                self.assertTrue(_reason(["WR_find_element_by", ["a", "no such strategy"]]))


class TestActionsThatSitAlone(unittest.TestCase):

    def test_in_a_condition_several_actions_become_one_block_that_fails_when_one_does(self):
        with _twins():
            translated = _one(["WR_if", {"condition": {"succeeds": ["WR_find_element_by", ["#go"]]}, "then": []}])
        self.assertEqual(translated, [["WR_if", {
            "condition": {"succeeds": ["WR_try", {"do": [_SAVE_GO, _FIND_SAVED, _MUST_EXIST]}]}, "then": []}]])

    def test_in_a_condition_an_action_that_becomes_nothing_still_succeeds(self):
        self.assertEqual(
            _one(["WR_while", {"condition": {"not": {"succeeds": ["WR_reset_actions"]}}, "do": [],
                               "max_iterations": 1}]),
            [["WR_while", {"condition": {"not": {"succeeds": ["WR_try", {"do": []}]}}, "do": [],
                           "max_iterations": 1}]])

    def test_a_captured_action_has_to_stay_one_action(self):
        with _twins(), self.assertRaises(BackendTranslationError) as raised:
            _one(["WR_capture", {"name": "found", "action": ["WR_find_element_by", ["#go"]]}])
        problem, = raised.exception.problems
        self.assertEqual((problem.location, problem.command), ("action[0].action", "WR_find_element_by"))
        self.assertIn("3 actions", problem.reason)

    def test_a_refused_action_in_a_condition_is_reported_once(self):
        with self.assertRaises(BackendTranslationError) as raised:
            _one(["WR_if", {"condition": {"succeeds": ["WR_explicit_wait", [3]]}, "then": []}])
        self.assertEqual([problem.location for problem in raised.exception.problems],
                         ["action[0].condition.succeeds"])


class TestOtherBuilders(unittest.TestCase):

    def test_assert_title_checks_the_title_field(self):
        self.assertEqual(_one(["WR_assert_title", ["Home"]]),
                         [["WR_pw_check_current_page", {"check_dict": {"title": "Home"}}]])

    def test_reload_refreshes_or_sends_the_same_devtools_reload(self):
        self.assertEqual(_one(["WR_reload"]), [["WR_pw_refresh"]])
        self.assertEqual(_one(["WR_reload", [False]]), [["WR_pw_refresh"]])
        self.assertEqual(_one(["WR_reload", {"ignore_cache": True}]),
                         [["WR_pw_cdp", {"method": "Page.reload", "params": {"ignoreCache": True}}]])

    def test_clear_origin_storage_sends_the_same_devtools_command(self):
        self.assertEqual(_one(["WR_clear_origin_storage", ["https://example.test"]]), [["WR_pw_cdp", {
            "method": "Storage.clearDataForOrigin",
            "params": {"origin": "https://example.test", "storageTypes": "all"}}]])

    def test_geo_locale_becomes_one_action_per_override(self):
        self.assertEqual(_one(["WR_geo_locale_apply", {"latitude": 25.0, "longitude": 121.5, "locale": "zh-TW"}]), [
            ["WR_pw_set_geolocation", {"latitude": 25.0, "longitude": 121.5, "accuracy": 50.0}],
            ["WR_pw_set_locale", {"locale": "zh-TW"}]])
        self.assertEqual(_one(["WR_geo_locale_apply", {"timezone": "Asia/Taipei"}]),
                         [["WR_pw_set_timezone", {"timezone_id": "Asia/Taipei"}]])
        self.assertTrue(_reason(["WR_geo_locale_apply", {"latitude": 25.0}]))

    def test_touch_frames_are_sent_one_devtools_event_each(self):
        frames = [{"type": "touchStart", "touchPoints": [{"x": 1, "y": 2}]}, {"type": "touchEnd", "touchPoints": []}]
        self.assertEqual(_one(["WR_touch_gesture_dispatch", [frames]]), [
            ["WR_pw_cdp", {"method": "Input.dispatchTouchEvent", "params": frame}] for frame in frames])
        self.assertTrue(_reason(["WR_touch_gesture_dispatch", ["${frames}"]]))


class TestRefusalList(unittest.TestCase):

    def test_the_core_commands_have_their_own_reason(self):
        listed = untranslatable_commands()
        for command in ("WR_explicit_wait", "WR_element_get_attribute", "WR_element_get_select", "WR_get_log",
                        "WR_execute", "WR_get_window_handles", "WR_get_current_window_handle",
                        "WR_get_window_position", "WR_get_window_rect", "WR_clear_device_metrics",
                        "WR_set_webdriver_options_capability", "WR_move_by_offset", "WR_drag_and_drop",
                        "WR_move_to_element_with_offset", "WR_send_keys_to_element", "WR_dismiss_cookie_consent",
                        "WR_multi_tab_open", "WR_enable_fetch_interception", "WR_fetch_fulfill_request",
                        "WR_webauthn_enable", "WR_cdp_tap_start", "WR_bidi_backend_subscribe",
                        "WR_cross_browser_capture"):
            with self.subTest(command=command):
                self.assertEqual(_reason([command]), listed[command])
                self.assertNotIn("has no playwright translation", listed[command])

    def test_another_name_of_a_listed_command_gets_the_same_reason(self):
        self.assertEqual(_reason(["WR_explict_wait", [3]]), untranslatable_commands()["WR_explicit_wait"])

    def test_a_listed_command_drives_selenium(self):
        # An entry for a command that became backend-neutral would refuse what now runs on both backends.
        stale = [command for command in untranslatable_commands()
                 if backend_of(command) != SELENIUM and command not in _NOT_BROWSER_BOUND]
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
