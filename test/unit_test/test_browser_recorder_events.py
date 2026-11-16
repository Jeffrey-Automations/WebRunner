"""The recorder's translation of every event type, on both backends, and its masking."""
import inspect
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from selenium.webdriver.common.keys import Keys

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.linter.action_linter import lint_action
from je_web_runner.utils.recorder import browser_recorder
from je_web_runner.utils.recorder.browser_recorder import (
    MASKED_VALUE,
    PlaywrightScriptRunner,
    RecorderError,
    emitted_commands,
    events_to_actions,
    mask_sensitive_events,
    mask_url,
    pull_events,
    save_recording,
    start_recording,
    stop_recording,
)

PAGE = "https://shop.test/cart"
OTHER_PAGE = "https://shop.test/checkout"
BACKENDS = ("selenium", "playwright")
FORBIDDEN_RULES = {"legacy_name", "unknown_command", "unknown_argument", "missing_argument"}


def _every_event_type() -> list[dict]:
    """One event of each shape the injected script produces, as the module docstring lists them."""
    return [
        {"type": "navigate", "url": PAGE, "time": 1},
        {"type": "click", "selector": "#add", "url": PAGE, "time": 2},
        {"type": "input", "selector": "#coupon", "value": "SAVE10", "masked": False, "url": PAGE, "time": 3},
        {"type": "select", "selector": "#size", "value": "xl", "masked": False, "url": PAGE, "time": 4},
        {"type": "check", "selector": "#gift", "checked": True, "input_type": "checkbox", "url": PAGE, "time": 5},
        {"type": "check", "selector": "#news", "checked": False, "input_type": "checkbox", "url": PAGE, "time": 6},
        {"type": "check", "selector": "input[name=\"pay\"][value=\"card\"]", "checked": True,
         "input_type": "radio", "url": PAGE, "time": 7},
        {"type": "key", "key": "Tab", "selector": "#coupon", "url": PAGE, "time": 8},
        {"type": "key", "key": "Enter", "selector": "#coupon", "url": PAGE, "time": 9},
        {"type": "input", "selector": "#note", "value": "hi", "masked": False, "url": OTHER_PAGE, "time": 10},
        {"type": "navigate", "url": PAGE, "time": 11},
    ]


def _names(actions: list[list]) -> list[str]:
    return [action[0] for action in actions]


class TestEmittedCommandsGuard(unittest.TestCase):

    def test_every_emitted_command_is_registered(self):
        for backend in BACKENDS:
            for name in emitted_commands(backend):
                with self.subTest(backend=backend, command=name):
                    self.assertIn(name, executor.event_dict)

    def test_playwright_commands_carry_the_playwright_prefix(self):
        self.assertTrue(all(name.startswith("WR_pw_") for name in emitted_commands("playwright")))
        self.assertFalse(any(name.startswith("WR_pw_") for name in emitted_commands("selenium")))

    def test_translation_emits_only_declared_commands_and_uses_them_all(self):
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                actions = events_to_actions(_every_event_type(), backend)
                self.assertEqual(set(_names(actions)), set(emitted_commands(backend)))

    def test_lint_finds_no_naming_or_argument_problem(self):
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                findings = lint_action(events_to_actions(_every_event_type(), backend))
                bad = [finding for finding in findings if finding["rule"] in FORBIDDEN_RULES]
                self.assertEqual(bad, [])

    def test_arguments_bind_to_the_registered_signatures(self):
        for backend in BACKENDS:
            for action in events_to_actions(_every_event_type(), backend):
                with self.subTest(backend=backend, action=action):
                    arguments = action[1] if len(action) > 1 else {}
                    bound = inspect.signature(executor.event_dict[action[0]]).bind(**arguments)
                    self.assertEqual(set(bound.arguments) - {"options", "goto_options", "kwargs"}, set(arguments))

    def test_selenium_key_names_exist_on_keys(self):
        for event_key in browser_recorder._KEY_NAMES:
            actions = events_to_actions([{"type": "key", "key": event_key}])
            with self.subTest(key=event_key):
                self.assertIsInstance(getattr(Keys, actions[0][1]["keys"].upper(), None), str)

    def test_unknown_backend_is_rejected(self):
        with self.assertRaises(RecorderError):
            events_to_actions([], "cypress")
        with self.assertRaises(RecorderError):
            emitted_commands("cypress")


class TestSeleniumTranslation(unittest.TestCase):

    def test_select_uses_select_by_value(self):
        actions = events_to_actions([{"type": "select", "selector": "#size", "value": "xl"}])
        self.assertEqual(_names(actions), ["WR_save_test_object", "WR_find_recorded_element",
                                           "WR_element_select_by_value"])
        self.assertEqual(actions[2][1], {"value": "xl"})

    def test_checkbox_ticked_and_unticked(self):
        ticked = events_to_actions([{"type": "check", "selector": "#gift", "checked": True}])
        unticked = events_to_actions([{"type": "check", "selector": "#gift", "checked": False}])
        self.assertEqual(ticked[1], ["WR_find_recorded_element", {"element_name": "#gift"}])
        self.assertEqual(ticked[2], ["WR_element_check"])
        self.assertEqual(unticked[2], ["WR_element_uncheck"])

    def test_named_key_becomes_press_keys(self):
        actions = events_to_actions([
            {"type": "key", "key": "Enter"}, {"type": "key", "key": "Escape"},
            {"type": "key", "key": "Tab"}, {"type": "key", "key": "ArrowDown"},
        ])
        self.assertEqual(actions, [
            ["WR_press_keys", {"keys": "Enter"}], ["WR_press_keys", {"keys": "Escape"}],
            ["WR_press_keys", {"keys": "Tab"}], ["WR_press_keys", {"keys": "Arrow_Down"}],
        ])

    def test_default_backend_is_selenium(self):
        events = _every_event_type()
        self.assertEqual(events_to_actions(events), events_to_actions(events, "selenium"))


class TestPlaywrightTranslation(unittest.TestCase):

    def test_each_event_is_one_selector_command(self):
        actions = events_to_actions([
            {"type": "click", "selector": "#add"},
            {"type": "input", "selector": "#coupon", "value": "SAVE10"},
            {"type": "select", "selector": "#size", "value": "xl"},
            {"type": "check", "selector": "#gift", "checked": True},
            {"type": "check", "selector": "#gift", "checked": False},
            {"type": "key", "key": "ArrowDown"},
        ], backend="playwright")
        self.assertEqual(actions, [
            ["WR_pw_click", {"selector": "#add"}],
            ["WR_pw_fill", {"selector": "#coupon", "value": "SAVE10"}],
            ["WR_pw_select_option", {"selector": "#size", "value": "xl"}],
            ["WR_pw_check", {"selector": "#gift"}],
            ["WR_pw_uncheck", {"selector": "#gift"}],
            ["WR_pw_keyboard_press", {"key": "ArrowDown"}],
        ])

    def test_navigation_uses_pw_to_url(self):
        actions = events_to_actions([{"type": "navigate", "url": PAGE}], backend="playwright")
        self.assertEqual(actions, [["WR_pw_to_url", {"url": PAGE}]])


class TestNavigation(unittest.TestCase):

    def test_recording_starts_with_the_page_it_began_on(self):
        actions = events_to_actions([
            {"type": "navigate", "url": PAGE},
            {"type": "click", "selector": "#add", "url": PAGE},
        ])
        self.assertEqual(actions[0], ["WR_to_url", {"url": PAGE}])
        self.assertEqual(_names(actions).count("WR_to_url"), 1)

    def test_first_event_with_a_url_starts_the_recording_without_a_marker(self):
        actions = events_to_actions([{"type": "click", "selector": "#add", "url": PAGE}])
        self.assertEqual(actions[0], ["WR_to_url", {"url": PAGE}])

    def test_url_change_after_a_click_is_the_click_s_doing(self):
        actions = events_to_actions([
            {"type": "navigate", "url": PAGE},
            {"type": "click", "selector": "#checkout", "url": PAGE},
            {"type": "navigate", "url": OTHER_PAGE},
            {"type": "input", "selector": "#note", "value": "hi", "url": OTHER_PAGE},
        ])
        self.assertEqual(_names(actions).count("WR_to_url"), 1)

    def test_url_change_after_enter_is_the_key_s_doing(self):
        actions = events_to_actions([
            {"type": "input", "selector": "#q", "value": "shoes", "url": PAGE},
            {"type": "key", "key": "Enter", "url": PAGE},
            {"type": "click", "selector": "#first", "url": OTHER_PAGE},
        ])
        self.assertEqual(_names(actions).count("WR_to_url"), 1)

    def test_url_change_nothing_recorded_explains_is_a_navigation(self):
        actions = events_to_actions([
            {"type": "navigate", "url": PAGE},
            {"type": "input", "selector": "#coupon", "value": "SAVE10", "url": PAGE},
            {"type": "navigate", "url": OTHER_PAGE},
            {"type": "click", "selector": "#pay", "url": OTHER_PAGE},
        ])
        self.assertEqual(
            [action for action in actions if action[0] == "WR_to_url"],
            [["WR_to_url", {"url": PAGE}], ["WR_to_url", {"url": OTHER_PAGE}]],
        )
        self.assertEqual(_names(actions).index("WR_element_click"), len(actions) - 1)

    def test_url_change_after_tab_is_a_navigation(self):
        actions = events_to_actions([
            {"type": "key", "key": "Tab", "url": PAGE},
            {"type": "click", "selector": "#pay", "url": OTHER_PAGE},
        ])
        self.assertEqual(_names(actions).count("WR_to_url"), 2)

    def test_a_click_only_explains_the_next_change(self):
        actions = events_to_actions([
            {"type": "click", "selector": "#checkout", "url": PAGE},
            {"type": "input", "selector": "#note", "value": "hi", "url": OTHER_PAGE},
            {"type": "input", "selector": "#coupon", "value": "x", "url": PAGE},
        ])
        self.assertEqual(_names(actions).count("WR_to_url"), 2)

    def test_events_without_url_add_no_navigation(self):
        actions = events_to_actions([{"type": "navigate"}, {"type": "click", "selector": "#go"}])
        self.assertNotIn("WR_to_url", _names(actions))
        self.assertEqual(len(actions), 3)


class TestMaskingOfNewEvents(unittest.TestCase):

    def test_select_value_is_masked_by_selector(self):
        out = mask_sensitive_events([{"type": "select", "selector": "#card_number", "value": "visa-1"}])
        self.assertEqual(out[0]["value"], MASKED_VALUE)
        self.assertTrue(out[0]["masked"])

    def test_select_keeps_an_ordinary_value(self):
        out = mask_sensitive_events([{"type": "select", "selector": "#size", "value": "xl"}])
        self.assertEqual(out[0], {"type": "select", "selector": "#size", "value": "xl"})

    def test_masked_value_reaches_the_actions_on_both_backends(self):
        events = [{"type": "input", "selector": "#pw", "value": MASKED_VALUE, "masked": True},
                  {"type": "select", "selector": "#secret", "value": MASKED_VALUE, "masked": True}]
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                text = json.dumps(events_to_actions(events, backend))
                self.assertEqual(text.count(MASKED_VALUE), 2)

    def test_character_key_is_never_emitted(self):
        events = [{"type": "key", "key": "h"}, {"type": "key", "key": "hunter2"}, {"type": "key", "key": ["x"]},
                  {"type": "key"}]
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                self.assertEqual(events_to_actions(events, backend), [])

    def test_skipped_key_is_not_logged(self):
        with self.assertLogs(browser_recorder.web_runner_logger, level="WARNING") as captured:
            events_to_actions([{"type": "key", "key": "hunter2"}])
        self.assertNotIn("hunter2", "\n".join(captured.output))

    def test_character_key_is_masked_in_the_event_log(self):
        out = mask_sensitive_events([{"type": "key", "key": "h"}, {"type": "key", "key": "Enter"}])
        self.assertEqual(out[0]["key"], MASKED_VALUE)
        self.assertEqual(out[1], {"type": "key", "key": "Enter"})

    def test_url_secrets_are_masked(self):
        self.assertEqual(
            mask_url("https://bob:hunter2@shop.test/a?page=2&access_token=abc123&q=x#api_key=zzz"),
            f"https://bob:{MASKED_VALUE}@shop.test/a?page=2&access_token={MASKED_VALUE}&q=x#api_key={MASKED_VALUE}",
        )

    def test_url_without_secrets_is_untouched(self):
        for url in (PAGE, "https://shop.test:8443/a?mail=a@b.test&page=2#top", "about:blank"):
            with self.subTest(url=url):
                self.assertEqual(mask_url(url), url)

    def test_event_urls_are_masked_for_every_type(self):
        secret_url = "https://shop.test/reset?token=abc123"
        events = [dict(event, url=secret_url) for event in _every_event_type()]
        out = mask_sensitive_events(events)
        self.assertNotIn("abc123", json.dumps(out))
        self.assertEqual(len(out), len(events))
        self.assertIn("abc123", json.dumps(events))

    def test_save_recording_masks_values_urls_and_keys(self):
        driver = MagicMock(spec=["execute_script"])
        driver.execute_script.return_value = [
            {"type": "navigate", "url": "https://shop.test/reset?token=abc123"},
            {"type": "input", "selector": "#password", "value": "hunter2",
             "url": "https://shop.test/reset?token=abc123"},
            {"type": "select", "selector": "#secret_question", "value": "pet-name",
             "url": "https://shop.test/reset?token=abc123"},
            {"type": "key", "key": "z", "url": "https://shop.test/reset?token=abc123"},
        ]
        for backend in BACKENDS:
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as folder:
                output = os.path.join(folder, "rec.json")
                raw = os.path.join(folder, "raw.json")
                save_recording(driver, output, raw, backend=backend)
                with open(output, encoding="utf-8") as action_file:
                    written = action_file.read()
                with open(raw, encoding="utf-8") as raw_file:
                    written += raw_file.read()
                for secret in ("abc123", "hunter2", "pet-name", '"z"'):
                    self.assertNotIn(secret, written)


class TestSaveRecordingBackend(unittest.TestCase):

    def test_playwright_backend_is_written(self):
        driver = MagicMock(spec=["execute_script"])
        driver.execute_script.return_value = [{"type": "click", "selector": "#go", "url": PAGE}]
        with tempfile.TemporaryDirectory() as folder:
            output = os.path.join(folder, "rec.json")
            self.assertEqual(save_recording(driver, output, backend="playwright"), output)
            with open(output, encoding="utf-8") as action_file:
                actions = json.load(action_file)
        self.assertEqual(actions, [["WR_pw_to_url", {"url": PAGE}], ["WR_pw_click", {"selector": "#go"}]])

    def test_unknown_backend_pulls_nothing(self):
        driver = MagicMock(spec=["execute_script"])
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(RecorderError):
            save_recording(driver, os.path.join(folder, "rec.json"), backend="cypress")
        driver.execute_script.assert_not_called()


class TestScriptsAreFixed(unittest.TestCase):

    def test_scripts_are_the_module_constants_with_no_argument_spliced_in(self):
        driver = MagicMock(spec=["execute_script"])
        driver.execute_script.return_value = []
        start_recording(driver)
        pull_events(driver)
        stop_recording(driver)
        self.assertEqual(
            [call.args for call in driver.execute_script.call_args_list],
            [(browser_recorder._RECORDER_JS,), (browser_recorder._DRAIN_JS,), (browser_recorder._RESET_JS,)],
        )

    def test_playwright_runner_wraps_the_constant_script_only(self):
        wrapper = MagicMock()
        start_recording(PlaywrightScriptRunner(wrapper))
        wrapper.page.evaluate.assert_called_once_with(f"() => {{ {browser_recorder._RECORDER_JS} }}")

    def test_script_and_python_agree_on_event_types_and_keys(self):
        script = browser_recorder._RECORDER_JS
        for event_type in ("navigate", "click", "check", "key", "select", "input"):
            with self.subTest(event_type=event_type):
                self.assertIn(f"'{event_type}'", script)
        for key in browser_recorder._KEY_NAMES:
            with self.subTest(key=key):
                self.assertIn(f"'{key}'", script)

    def test_every_documented_event_type_translates(self):
        documented = {"navigate", "click", "input", "select", "check", "key"}
        self.assertEqual(set(browser_recorder._OPERATIONS) | {"navigate"}, documented)
        for event_type in documented:
            with self.subTest(event_type=event_type):
                self.assertIn(f"``{event_type}``", browser_recorder.__doc__)


if __name__ == "__main__":
    unittest.main()
