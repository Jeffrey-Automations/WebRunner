"""Wrapper calls that fail must fail their action like every other wrapper call, and be recorded once."""
import unittest
from unittest.mock import MagicMock

from je_web_runner.element.web_element_wrapper import WebElementWrapper
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.utils.test_record.wrapper_failures import wrapper_failure_policy
from je_web_runner.webdriver.webdriver_with_options import (
    set_webdriver_options_argument,
    set_webdriver_options_capability_wrapper,
)


class _RecordedCase(unittest.TestCase):

    def setUp(self):
        saved, enabled = list(test_record_instance.test_record_list), test_record_instance.init_record
        self.addCleanup(setattr, test_record_instance, "test_record_list", saved)
        self.addCleanup(test_record_instance.set_record_enable, enabled)
        self.addCleanup(setattr, wrapper_failure_policy, "raise_errors", wrapper_failure_policy.raise_errors)
        test_record_instance.set_record_enable(True)
        test_record_instance.test_record_list = []
        wrapper_failure_policy.raise_errors = True

    @staticmethod
    def outcomes() -> list[bool]:
        """One entry per record: whether it is a failure."""
        return [str(record["program_exception"]) != "None" for record in test_record_instance.test_record_list]


class TestOptionsWrappers(_RecordedCase):

    def test_a_wrong_argument_type_fails_the_call(self):
        with self.assertRaises(Exception):
            set_webdriver_options_argument("chrome", ["--headless", 5])
        self.assertEqual(self.outcomes(), [True])

    def test_an_unknown_browser_fails_the_call(self):
        with self.assertRaises(Exception):
            set_webdriver_options_argument("netscape", ["--headless"])

    def test_capabilities_that_are_not_an_object_fail_the_call(self):
        with self.assertRaises(Exception):
            set_webdriver_options_capability_wrapper("chrome", ["acceptInsecureCerts"])
        self.assertEqual(self.outcomes(), [True])

    def test_with_raising_switched_off_the_caller_gets_none(self):
        wrapper_failure_policy.raise_errors = False
        self.assertIsNone(set_webdriver_options_argument("chrome", ["--headless", 5]))
        self.assertIsNone(set_webdriver_options_capability_wrapper("chrome", ["acceptInsecureCerts"]))

    def test_valid_input_still_returns_the_options(self):
        options = set_webdriver_options_argument("chrome", ["--headless=new"])
        self.assertIn("--headless=new", options.arguments)
        self.assertEqual(self.outcomes(), [False])


class TestElementScreenshot(_RecordedCase):

    def test_a_failed_screenshot_is_one_failure_record_not_a_success_then_a_failure(self):
        wrapper = WebElementWrapper()
        wrapper.current_web_element = MagicMock()
        wrapper.current_web_element.screenshot.side_effect = RuntimeError("element is detached")
        with self.assertRaises(RuntimeError):
            wrapper.screenshot("shot")
        self.assertEqual(self.outcomes(), [True])

    def test_a_successful_screenshot_is_one_success_record(self):
        wrapper = WebElementWrapper()
        wrapper.current_web_element = MagicMock()
        wrapper.current_web_element.screenshot.return_value = True
        self.assertTrue(wrapper.screenshot("shot"))
        wrapper.current_web_element.screenshot.assert_called_once_with("shot.png")
        self.assertEqual(self.outcomes(), [False])

    def test_the_failure_is_logged_as_an_error(self):
        wrapper = WebElementWrapper()
        wrapper.current_web_element = MagicMock()
        wrapper.current_web_element.screenshot.side_effect = RuntimeError("element is detached")
        with self.assertLogs("WEBRunner", level="ERROR") as logs, self.assertRaises(RuntimeError):
            wrapper.screenshot("shot")
        self.assertTrue(any("screenshot" in line and "detached" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
