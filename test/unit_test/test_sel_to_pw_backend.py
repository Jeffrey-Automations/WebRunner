"""Translating an action file for the other backend: every table row, the refusals, blocks and documents."""
import copy
import inspect
import unittest

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.linter.action_linter import lint_action
from je_web_runner.utils.sel_to_pw import (
    BackendTranslationError,
    SelToPwError,
    how_translated,
    translatable_commands,
    translate_action_list,
    translate_for_backend,
    untranslatable_commands,
)
from je_web_runner.utils.sel_to_pw import backend_rules as rules
from je_web_runner.utils.sel_to_pw.backend_binding import SELENIUM, backend_of
from je_web_runner.utils.sel_to_pw.backend_rules import Rule

_ARGUMENT_RULES = {"unknown_command", "unknown_argument", "missing_argument", "too_many_arguments"}
_LOCATOR = rules.TRANSLATED_LOCATOR

# Keyword arguments for each row of the table that has a required parameter (Selenium parameter names).
SAMPLES = {
    "WR_new_driver": {"webdriver_name": "chrome", "options": ["--headless=new", "--lang=en"]},
    "WR_set_driver": {"webdriver_name": "chrome", "options": ["--headless=new", "--disable-gpu"]},
    "WR_assert_title": {"value": "Home"},
    "WR_press_keys": {"keys": ["Control", "a", "Enter"]},
    "WR_send_keys": {"keys_to_send": "ab"},
    "WR_press_key": {"keycode_on_key_class": ""},
    "WR_release_key": {"keycode_on_key_class": ""},
    "WR_pause": {"seconds": 1},
    "WR_clear_origin_storage": {"origin": "https://example.test"},
    "WR_touch_gesture_dispatch": {"frames": [{"type": "touchStart", "touchPoints": [{"x": 1, "y": 2}]}]},
    "WR_geo_locale_apply": {"latitude": 25.0, "longitude": 121.5, "timezone": "Asia/Taipei", "locale": "zh-TW"},
    "WR_change_index_of_webdriver": {"index_of_webdriver": 1},
    "WR_attach_to_existing_browser": {"debugger_address": "127.0.0.1:9222"},
    "WR_to_url": {"url": "https://example.test/"},
    "WR_find_recorded_element": {"element_name": "login"},
    "WR_find_recorded_elements": {"element_name": "rows"},
    "WR_find_element_by": {"selector": "//a", "by": "xpath"},
    "WR_find_elements_by": {"selector": "li", "by": "tag name"},
    "WR_element_value_of_css_property": {"property_name": "color"},
    "WR_element_get_property": {"name": "value"},
    "WR_element_screenshot": {"filename": "shot"},
    "WR_element_input": {"input_value": "hi"},
    "WR_element_get_dom_attribute": {"name": "href"},
    "WR_element_change_web_element": {"element_index": 1},
    "WR_element_assert": {"check_dict": {"tag_name": "a", "text": "Go"}},
    "WR_element_select_by_value": {"value": "tw"},
    "WR_emulate_device": {"name": "iPhone SE"},
    "WR_grant_permissions": {"permissions": ["geolocation"], "origin": "https://example.test"},
    "WR_clock_freeze": {"moment": "2026-01-01T00:00:00Z"},
    "WR_wait_for_element": {"selector": "#go", "by": "css selector", "timeout": 5, "state": "present"},
    "WR_wait_for_url": {"pattern": "/home", "timeout": 2.5},
    "WR_wait_for_ready_state": {"timeout": 5},
    "WR_set_page_load_timeout": {"time_to_wait": 20},
    "WR_execute_script": {"script": "return 1"},
    "WR_execute_async_script": {"script": "arguments[0](1)"},
    "WR_save_screenshot": {"file_path": "a.png"},
    "WR_save_full_page_screenshot": {"file_path": "full.png"},
    "WR_print_page": {"file_path": "a.pdf"},
    "WR_get_cookie": {"name": "sid"},
    "WR_delete_cookie": {"name": "sid"},
    "WR_add_cookie": {"cookie_dict": {"name": "sid", "value": "1", "domain": "example.test", "expiry": 1893456000}},
    "WR_check_current_webdriver": {"check_dict": {"title": "Home", "current_url": "https://example.test/"}},
    "WR_switch": {"switch_type": "frame", "switch_target_name": "payment"},
    "WR_switch_to_window_by_url": {"pattern": "/cart"},
    "WR_switch_to_window_by_title": {"pattern": "Cart"},
    "WR_scroll": {"scroll_x": 0, "scroll_y": 300},
    "WR_add_script_to_evaluate_on_new_document": {"source": "window.x = 1"},
    "WR_block_urls": {"patterns": ["*.ads.test/*"]},
    "WR_iframe_switch_chain": {"selectors": ["#outer", "#inner"]},
    "WR_set_device_metrics": {"width": 390, "height": 844},
    "WR_set_window_size": {"width": 800, "height": 600},
    "WR_set_user_agent": {"user_agent": "UA"},
    "WR_set_timezone": {"timezone_id": "Asia/Taipei"},
    "WR_set_locale": {"locale": "zh-TW"},
    "WR_set_extra_http_headers": {"headers": {"X-A": "1"}},
    "WR_set_cache_disabled": {"disabled": False},
    "WR_set_geolocation": {"latitude": 25.0, "longitude": 121.5, "accuracy": 10},
    "WR_visual_capture_baseline": {"baseline_path": "b.png"},
    "WR_visual_compare": {"baseline_path": "b.png", "threshold": 3},
    "WR_recorder_save": {"output_path": "rec.json"},
    "WR_route_mock": {"url_pattern": "**/api/user", "response": {"status": 200, "body": "{}"}},
    "WR_route_mock_json": {"url_pattern": "**/api/user", "json_data": {"a": 1}, "status": 201},
    "WR_route_unmock": {"url_pattern": "https://example.test/api"},
    "WR_throttle": {"preset": "slow_3g"},
    "WR_cdp": {"method": "Page.enable", "params": {"a": 1}},
    "WR_set_network_conditions": {"offline": True},
    "WR_execute_cdp_cmd": {"cmd": "Page.enable", "cmd_args": {"a": 1}},
    "WR_local_storage_set": {"key": "k", "value": "v"},
    "WR_local_storage_get": {"key": "k"},
    "WR_local_storage_remove": {"key": "k"},
    "WR_session_storage_set": {"key": "k", "value": "v"},
    "WR_session_storage_get": {"key": "k"},
    "WR_indexed_db_drop": {"db_name": "db"},
    "WR_sw_bypass": {"bypass": False},
    "WR_shadow_query": {"host_chain": ["#host"], "inner_selector": "button"},
    "WR_upload_file": {"input_selector": "#f", "file_path": "a.txt"},
    "WR_find_with_healing": {"name": "login"},
    "WR_a11y_run_audit": {"axe_source": "src"},
    "WR_perf_collect": {"observe_ms": 500},
}


def _parameters(command):
    return list(inspect.signature(executor.event_dict[command]).parameters.values())


def _keyword_action(command):
    sample = SAMPLES.get(command, {})
    return [command, copy.deepcopy(sample)] if sample else [command]


def _positional_action(command):
    """The sample of ``command`` with its values given by position, in the signature's order."""
    sample = copy.deepcopy(SAMPLES.get(command, {}))
    values = []
    for parameter in _parameters(command):
        if parameter.name not in sample:
            break
        values.append(sample.pop(parameter.name))
    return [command, values, sample] if sample else [command, values]


def _with_perform(command, action):
    """Queued ActionChains commands only appear once ``WR_perform`` runs them."""
    return [action, ["WR_perform"]] if command in rules.QUEUED_COMMANDS else [action]


def _argument_findings(actions):
    return [finding for finding in lint_action(actions) if finding["rule"] in _ARGUMENT_RULES]


def _invertible(rule):
    return (isinstance(rule, Rule) and rule.inverse
            and all(conversion.backward is not None for conversion in rule.convert.values()))


class TestEveryRow(unittest.TestCase):

    def test_every_row_with_a_required_parameter_has_a_sample(self):
        for command in rules.SELENIUM_TO_PLAYWRIGHT:
            required = [parameter.name for parameter in _parameters(command)
                        if parameter.default is inspect.Parameter.empty
                        and parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD]
            with self.subTest(command=command):
                self.assertEqual([name for name in required if name not in SAMPLES.get(command, {})], [])
        self.assertEqual(sorted(set(SAMPLES) - set(rules.SELENIUM_TO_PLAYWRIGHT)), [])

    def test_keyword_and_positional_arguments_translate_alike(self):
        for command in rules.SELENIUM_TO_PLAYWRIGHT:
            with self.subTest(command=command):
                by_keyword = translate_for_backend(_with_perform(command, _keyword_action(command)))
                by_position = translate_for_backend(_with_perform(command, _positional_action(command)))
                self.assertTrue(by_keyword)
                self.assertEqual(by_position, by_keyword)

    def test_translated_actions_are_registered_and_pass_the_argument_rules(self):
        for command in rules.SELENIUM_TO_PLAYWRIGHT:
            with self.subTest(command=command):
                translated = translate_for_backend(_with_perform(command, _keyword_action(command)))
                for action in translated:
                    self.assertIn(action[0], executor.event_dict)
                self.assertEqual(_argument_findings(translated), [])

    def test_every_rule_target_is_registered(self):
        for command, rule in rules.SELENIUM_TO_PLAYWRIGHT.items():
            self.assertIn(command, executor.event_dict)
            if isinstance(rule, Rule):
                self.assertIn(rule.target, executor.event_dict, command)

    def test_rules_that_read_backwards_give_the_selenium_action_back(self):
        for command, rule in rules.SELENIUM_TO_PLAYWRIGHT.items():
            if not _invertible(rule):
                continue
            with self.subTest(command=command):
                action = _keyword_action(command)
                back = translate_for_backend(translate_for_backend([action]), "selenium")
                self.assertEqual(back, [action])
                self.assertEqual(_argument_findings(back), [])

    def test_playwright_positional_arguments_translate_back_too(self):
        self.assertEqual(
            translate_for_backend([
                ["WR_pw_screenshot", ["a.png", True]],
                ["WR_pw_screenshot", ["b.png"]],
                ["WR_pw_set_default_navigation_timeout", [1500]],
                ["WR_pw_wait_for_load_state", ["load", 2000]],
                ["WR_pw_set_geolocation", [1, 2]],
                ["WR_pw_check_current_page", [{"url": "https://example.test/"}]],
            ], "selenium"),
            [
                ["WR_save_full_page_screenshot", {"file_path": "a.png"}],
                ["WR_save_screenshot", {"file_path": "b.png"}],
                ["WR_set_page_load_timeout", {"time_to_wait": 1.5}],
                ["WR_wait_for_ready_state", {"timeout": 2}],
                ["WR_set_geolocation", {"latitude": 1, "longitude": 2, "accuracy": 0}],
                ["WR_check_current_webdriver", {"check_dict": {"current_url": "https://example.test/"}}],
            ])


class TestConversions(unittest.TestCase):

    def _one(self, action):
        return translate_for_backend([action])

    def test_seconds_become_milliseconds(self):
        self.assertEqual(self._one(["WR_set_page_load_timeout", [1.5]]),
                         [["WR_pw_set_default_navigation_timeout", {"timeout_ms": 1500}]])
        self.assertEqual(self._one(["WR_wait_for_ready_state"]),
                         [["WR_pw_wait_for_load_state", {"timeout": 30000, "state": "load"}]])
        self.assertEqual(self._one(["WR_wait_for_url", ["/home"]]),
                         [["WR_pw_wait_for_url", {"url": "**/home**", "timeout": 10000}]])

    def test_wait_for_hidden_converts_selector_timeout_and_state(self):
        translated = self._one(["WR_wait_for_element", {"selector": "//a", "by": "xpath", "state": "hidden"}])
        self.assertEqual(translated, [
            ["WR_pw_wait_for_selector", {"selector": "xpath=//a", "timeout": 10000, "state": "hidden"}]])

    def test_a_script_body_becomes_a_function_that_gets_the_arguments(self):
        (name, arguments), = self._one(["WR_execute_script", ["return arguments[0] + arguments[1]", 1, 2]])
        self.assertEqual(name, "WR_pw_evaluate")
        self.assertEqual(arguments["arg"], [1, 2])
        self.assertIn("return arguments[0] + arguments[1]", arguments["expression"])
        self.assertTrue(arguments["expression"].startswith("(args) => (function () {"))
        (_, callback), = self._one(["WR_execute_async_script", ["arguments[0](1)"]])
        self.assertIn("new Promise", callback["expression"])

    def test_a_new_driver_is_headed_unless_an_option_says_headless(self):
        self.assertEqual(self._one(["WR_new_driver", ["firefox"]]),
                         [["WR_pw_new_browser", {"browser": "firefox", "headless": False}]])
        self.assertEqual(self._one(["WR_get_webdriver_manager", ["edge", ["--headless=new", "--lang=en"]]]), [
            ["WR_pw_new_browser", {"browser": "chromium", "channel": "msedge", "headless": True,
                                   "args": ["--lang=en"]}]])

    def test_a_cookie_becomes_a_one_cookie_list_with_playwright_field_names(self):
        self.assertEqual(self._one(_keyword_action("WR_add_cookie")), [["WR_pw_add_cookies", {"cookies": [
            {"name": "sid", "value": "1", "domain": "example.test", "expires": 1893456000, "path": "/"}]}]])

    def test_defaults_that_differ_are_filled_in(self):
        self.assertEqual(self._one(["WR_set_geolocation", [25.0, 121.5]]), [
            ["WR_pw_set_geolocation", {"latitude": 25.0, "longitude": 121.5, "accuracy": 100}]])
        self.assertEqual(self._one(["WR_set_window_size", [800, 600, "current"]]),
                         [["WR_pw_set_viewport_size", {"width": 800, "height": 600}]])

    def test_a_frozen_moment_is_given_as_text_whatever_its_form(self):
        expected = [["WR_pw_clock_set_time", {"time_ms": "2026-01-01T00:00:00.000+00:00"}]]
        for moment in ("2026-01-01T00:00:00Z", 1767225600, 1767225600000):
            with self.subTest(moment=moment):
                self.assertEqual(self._one(["WR_clock_freeze", [moment]]), expected)

    def test_a_single_star_mock_pattern_crosses_slashes_on_playwright(self):
        self.assertEqual(self._one(["WR_route_unmock", ["*/api/user"]]),
                         [["WR_pw_route_unmock", {"url_pattern": "**/api/user"}]])

    def test_frames_start_at_the_top_document(self):
        self.assertEqual(self._one(["WR_iframe_switch_chain", [["#a", "#b"]]]), [
            ["WR_pw_switch_to_main_frame"], ["WR_pw_switch_to_frame", {"selectors": ["#a", "#b"]}]])
        self.assertEqual(self._one(["WR_switch", ["default_content"]]), [["WR_pw_switch_to_main_frame"]])
        self.assertEqual(self._one(["WR_switch", ["parent_frame"]]), [["WR_pw_switch_to_parent_frame"]])

    def test_other_names_of_a_command_translate_like_it(self):
        self.assertEqual(translate_for_backend([["WR_quit"], ["WR_find_element", ["login"]], ["WR_click_element"]]), [
            ["WR_pw_quit"],
            ["WR_pw_find_element_with_test_object_record", {"element_name": "login"}],
            ["WR_pw_element_click"],
        ])

    def test_the_input_is_not_changed(self):
        actions = [["WR_add_cookie", {"cookie_dict": {"name": "a", "value": "b", "domain": "x.test"}}],
                   ["WR_if", {"condition": {"succeeds": ["WR_element_click"]}, "then": [["WR_back"]]}]]
        before = copy.deepcopy(actions)
        translate_for_backend(actions)
        self.assertEqual(actions, before)


class TestSequences(unittest.TestCase):

    def test_a_queued_command_is_placed_at_its_perform(self):
        translated = translate_for_backend([
            ["WR_scroll", [0, 100]], ["WR_set_var", {"name": "x", "value": 1}], ["WR_perform"], ["WR_perform"]])
        self.assertEqual(translated, [
            ["WR_set_var", {"name": "x", "value": 1}], ["WR_pw_scroll", {"scroll_x": 0, "scroll_y": 100}]])

    def test_a_queued_command_without_perform_is_reported(self):
        with self.assertRaises(BackendTranslationError) as raised:
            translate_for_backend([["WR_scroll", [0, 100]], ["WR_if", {"condition": True, "then": [["WR_perform"]]}]])
        self.assertEqual([(problem.location, problem.command) for problem in raised.exception.problems],
                         [("action[0]", "WR_scroll")])

    def test_the_har_path_moves_from_stop_to_start(self):
        self.assertEqual(
            translate_for_backend([["WR_start_har_recording"], ["WR_to_url", ["https://example.test/"]],
                                   ["WR_stop_har_recording", ["run.har"]]]),
            [["WR_pw_start_har_recording", {"har_path": "run.har"}],
             ["WR_pw_to_url", {"url": "https://example.test/"}], ["WR_pw_stop_har_recording"]])

    def test_the_har_path_moves_from_start_to_stop(self):
        self.assertEqual(
            translate_for_backend([["WR_pw_start_har_recording", {"har_path": "run.har"}],
                                   ["WR_pw_stop_har_recording"]], "selenium"),
            [["WR_start_har_recording"], ["WR_stop_har_recording", {"har_path": "run.har"}]])

    def test_an_unpaired_har_command_is_reported(self):
        cases = [
            ([["WR_start_har_recording"]], "playwright", "WR_start_har_recording"),
            ([["WR_stop_har_recording", ["run.har"]]], "playwright", "WR_stop_har_recording"),
            ([["WR_start_har_recording"], ["WR_stop_har_recording", [None]]], "playwright", "WR_stop_har_recording"),
            ([["WR_pw_stop_har_recording"]], "selenium", "WR_pw_stop_har_recording"),
            ([["WR_pw_start_har_recording", ["run.har", "embed"]]], "selenium", "WR_pw_start_har_recording"),
        ]
        for actions, backend, command in cases:
            with self.subTest(actions=actions), self.assertRaises(BackendTranslationError) as raised:
                translate_for_backend(actions, backend)
            self.assertIn(command, [problem.command for problem in raised.exception.problems])


class TestRefusals(unittest.TestCase):

    def _problems(self, actions, backend="playwright"):
        with self.assertRaises(BackendTranslationError) as raised:
            translate_for_backend(actions, backend)
        return raised.exception.problems

    def test_every_untranslatable_action_is_named_with_its_place_and_reason(self):
        problems = self._problems([
            ["WR_to_url", {"url": "https://example.test/"}],
            ["WR_maximize_window"],
            ["WR_start_remote_driver", {"hub_url": "http://grid:4444", "capabilities": {}}],
            ["WR_appium_start", {"server_url": "http://localhost:4723", "capabilities": {}}],
            ["WR_implicitly_wait", [5]],
        ])
        self.assertEqual([(problem.location, problem.command) for problem in problems], [
            ("action[1]", "WR_maximize_window"), ("action[2]", "WR_start_remote_driver"),
            ("action[3]", "WR_appium_start"), ("action[4]", "WR_implicitly_wait")])
        for problem in problems:
            self.assertEqual(problem.reason, untranslatable_commands()[problem.command])

    def test_the_message_lists_every_problem(self):
        with self.assertRaises(BackendTranslationError) as raised:
            translate_for_backend([["WR_maximize_window"], ["WR_alert_accept"]])
        message = str(raised.exception)
        self.assertIn("2 action(s) cannot be translated for playwright", message)
        self.assertIn("action[0] WR_maximize_window", message)
        self.assertIn("action[1] WR_alert_accept", message)
        self.assertIsInstance(raised.exception, SelToPwError)
        self.assertEqual(raised.exception.backend, "playwright")

    def test_a_selenium_command_outside_the_table_is_refused_not_passed_through(self):
        reasons = set(untranslatable_commands().values())  # a listed command, under any of its names
        outside = [name for name in executor.event_dict
                   if backend_of(name) == SELENIUM and how_translated(name)[0] != "translated"
                   and how_translated(name)[1] not in reasons]
        for command in outside:
            with self.subTest(command=command):
                problem, = self._problems([[command]])
                self.assertIn("selenium backend", problem.reason)
        self.assertNotIn("WR_to_url", outside)

    def test_arguments_without_an_equivalent_are_refused(self):
        cases = [
            ["WR_new_window", ["window"]],
            ["WR_event_capture_start", {"dom_mutations": True}],
            ["WR_set_device_metrics", {"width": 390, "height": 844, "mobile": True}],
            ["WR_wait_for_element", {"selector": "#go", "state": "clickable"}],
            ["WR_wait_for_element", {"selector": "#go", "timeout": "${seconds}"}],
            ["WR_wait_for_url", ["/a*b"]],
            ["WR_new_driver", ["safari"]],
            ["WR_new_driver", {"webdriver_name": "chrome", "experimental_options": {"detach": True}}],
            ["WR_set_driver", {"webdriver_name": "chrome", "extension_paths": ["a.crx"]}],
            ["WR_add_cookie", [{"name": "a", "value": "b"}]],
            ["WR_check_current_webdriver", [{"page_source": "<html>"}]],
            ["WR_element_assert", [{"size": {"width": 1, "height": 1}}]],
            ["WR_switch", ["window", "CDwindow-1"]],
            ["WR_switch", ["frame", 0]],
            ["WR_route_mock", [{"hostname": "example.test"}, {"status": 200}]],
            ["WR_clock_freeze", ["2026-01-01T00:00:00Z", 100.0]],
            ["WR_emulate_device", ["No Such Phone"]],
            ["WR_find_element_by", ["a", "no such strategy"]],
            ["WR_attach_to_existing_browser", {"debugger_address": "127.0.0.1:9222", "options": ["--x"]}],
            ["WR_to_url", {"uri": "https://example.test/"}],
            ["WR_to_url", "https://example.test/"],
        ]
        for action in cases:
            with self.subTest(action=action):
                problem, = self._problems([action])
                self.assertEqual((problem.location, problem.command), ("action[0]", action[0]))
                self.assertTrue(problem.reason)

    def test_playwright_only_commands_are_refused_for_selenium(self):
        problems = self._problems([
            ["WR_pw_tracing_start"],
            ["WR_pw_to_url", {"url": "https://example.test/", "wait_until": "commit"}],
            ["WR_pw_wait_for_load_state", ["networkidle"]],
            ["WR_pw_fill", ["#a", "b"]],
            ["WR_pw_screenshot_bytes", [True]],
            ["WR_pw_route_mock", ["**/*.png", {"status": 404}]],
        ], "selenium")
        self.assertEqual([problem.location for problem in problems], [f"action[{index}]" for index in range(6)])

    def test_commands_of_the_target_backend_and_neutral_ones_pass_unchanged(self):
        actions = [
            ["WR_pw_launch", {"browser": "firefox"}],
            ["WR_set_var", {"name": "x", "value": 1}],
            ["WR_note", {"text": "hello"}],
            ["WR_sleep", [0.1]],
            ["WR_http_get", {"url": "https://example.test/api"}],
            ["WR_generate_html_report", {"html_name": "report"}],
            ["WR_save_test_object", {"test_object_name": "login", "object_type": "ID"}],
            ["a_plugin_command", {"x": 1}],
            "not an action",
        ]
        self.assertEqual(translate_for_backend(actions), actions)
        self.assertEqual(translate_for_backend(actions[1:], "selenium"), actions[1:])

    def test_bad_input_raises(self):
        with self.assertRaises(SelToPwError):
            translate_for_backend("not actions")
        with self.assertRaises(SelToPwError):
            translate_for_backend([], backend="webkit")


class TestBlocksAndDocuments(unittest.TestCase):

    def test_blocks_conditions_and_single_actions_are_translated(self):
        actions = [
            ["WR_if", {"condition": {"all": [{"succeeds": ["WR_element_click"]},
                                             {"not": {"succeeds": ["WR_wait_for_ready_state", [1]]}}]},
                       "then": [["WR_for_each", {"items": [1], "do": [["WR_refresh"]]}]],
                       "otherwise": [["WR_back"]]}],
            ["WR_try", {"do": [["WR_forward"]], "on_error": [["WR_save_screenshot", ["e.png"]]],
                        "always": [["WR_quit_current"]]}],
            ["WR_repeat", {"times": 2, "do": [["WR_scroll_to_bottom"]]}],
            ["WR_while", {"condition": {"any": [{"succeeds": ["WR_element_check"]}]}, "max_iterations": 3,
                          "do": [["WR_scroll_to_top"]]}],
            ["WR_retry_block", {"do": [["WR_find_recorded_element", ["login"]]]}],
            ["WR_capture", {"name": "title", "action": ["WR_get_title"]}],
        ]
        self.assertEqual(translate_for_backend(actions), [
            ["WR_if", {"condition": {"all": [
                {"succeeds": ["WR_pw_element_click"]},
                {"not": {"succeeds": ["WR_pw_wait_for_load_state", {"timeout": 1000, "state": "load"}]}}]},
                "then": [["WR_for_each", {"items": [1], "do": [["WR_pw_refresh"]]}]],
                "otherwise": [["WR_pw_back"]]}],
            ["WR_try", {"do": [["WR_pw_forward"]], "on_error": [["WR_pw_screenshot", {"path": "e.png"}]],
                        "always": [["WR_pw_close_browser"]]}],
            ["WR_repeat", {"times": 2, "do": [["WR_pw_scroll_to_bottom"]]}],
            ["WR_while", {"condition": {"any": [{"succeeds": ["WR_pw_element_check"]}]}, "max_iterations": 3,
                          "do": [["WR_pw_scroll_to_top"]]}],
            ["WR_retry_block", {"do": [["WR_pw_find_element_with_test_object_record", {"element_name": "login"}]]}],
            ["WR_capture", {"name": "title", "action": ["WR_pw_title"]}],
        ])
        self.assertEqual(_argument_findings(translate_for_backend(actions)), [])

    def test_problems_inside_blocks_say_where(self):
        with self.assertRaises(BackendTranslationError) as raised:
            translate_for_backend([
                ["WR_if", {"condition": {"not": {"succeeds": ["WR_alert_text"]}},
                           "then": [["WR_back"], ["WR_try", {"do": [["WR_maximize_window"]]}]]}],
                ["WR_capture", {"name": "frame", "action": ["WR_iframe_switch_chain", [["#a"]]]}],
            ])
        self.assertEqual([(problem.location, problem.command) for problem in raised.exception.problems], [
            ("action[0].then[1].do[0]", "WR_maximize_window"),
            ("action[0].condition.not.succeeds", "WR_alert_text"),
            ("action[1].action", "WR_iframe_switch_chain"),
        ])

    def test_a_document_keeps_its_shape_and_translates_its_hooks(self):
        document = {
            "meta": {"tags": ["smoke"], "setup": [["WR_new_driver", ["chrome"]]], "teardown": [["WR_quit_all"]]},
            "webdriver_wrapper": [["WR_to_url", ["https://example.test/"]]],
        }
        self.assertEqual(translate_for_backend(document), {
            "meta": {"tags": ["smoke"],
                     "setup": [["WR_pw_new_browser", {"browser": "chromium", "headless": False}]],
                     "teardown": [["WR_pw_quit"]]},
            "webdriver_wrapper": [["WR_pw_to_url", {"url": "https://example.test/"}]],
        })

    def test_problems_in_a_hook_say_which(self):
        with self.assertRaises(BackendTranslationError) as raised:
            translate_for_backend({"meta": {"teardown": [["WR_minimize_window"]]}, "webdriver_wrapper": []})
        self.assertEqual(raised.exception.problems[0].location, "meta.teardown[0]")


class TestDescriptions(unittest.TestCase):

    def test_how_translated(self):
        self.assertEqual(how_translated("WR_to_url"), ("translated", "WR_pw_to_url"))
        self.assertEqual(how_translated("WR_quit"), ("translated", "WR_pw_quit"))
        self.assertEqual(how_translated("WR_pw_screenshot", "selenium"),
                         ("translated", "WR_save_full_page_screenshot / WR_save_screenshot"))
        self.assertEqual(how_translated("WR_perform")[0], "translated")
        self.assertEqual(how_translated("WR_maximize_window")[0], "untranslatable")
        self.assertEqual(how_translated("WR_explicit_wait")[0], "untranslatable")
        self.assertEqual(how_translated("WR_reset_actions")[0], "translated")
        self.assertEqual(how_translated("WR_set_var"), ("unchanged", "backend-neutral"))
        self.assertEqual(how_translated("WR_pw_click"), ("unchanged", "already a playwright command"))

    def test_the_lists_of_commands(self):
        self.assertIn("WR_to_url", translatable_commands())
        self.assertIn("WR_perform", translatable_commands())
        self.assertIn("WR_pw_to_url", translatable_commands("selenium"))
        self.assertNotIn("WR_pw_evaluate", translatable_commands("selenium"))
        self.assertEqual(untranslatable_commands("selenium"), {})
        for command, reason in untranslatable_commands().items():
            self.assertIn(command, executor.event_dict)
            self.assertNotIn(command, rules.SELENIUM_TO_PLAYWRIGHT)
            self.assertTrue(reason.strip())

    def test_the_draft_translator_still_passes_unknown_selenium_commands_through(self):
        self.assertEqual(translate_action_list([["WR_maximize_window"], ["WR_implicitly_wait", [5]]]),
                         [["WR_maximize_window"]])


if __name__ == "__main__":
    unittest.main()
