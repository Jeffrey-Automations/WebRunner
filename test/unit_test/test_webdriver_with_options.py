"""Unit tests for ``webdriver_with_options`` option/capability builders.

These exercise the real Selenium ``Options`` classes (Selenium is a hard
dependency), and lock in the fix for the previously dead None-guard: an
unknown browser name must raise ``WebRunnerWebDriverNotFoundException`` from
the resolver instead of crashing with ``'NoneType' object is not callable``.
"""
import unittest

from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions

from je_web_runner.utils.exception.exceptions import (
    WebRunnerArgumentWrongTypeException,
    WebRunnerOptionsWrongTypeException,
    WebRunnerWebDriverNotFoundException,
)
from je_web_runner.utils.test_record.wrapper_failures import wrapper_failure_policy
from je_web_runner.webdriver.webdriver_with_options import (
    _new_options_for,
    set_webdriver_options_argument,
    set_webdriver_options_capability_wrapper,
)


class TestNewOptionsFor(unittest.TestCase):

    def test_known_names_return_matching_options(self):
        self.assertIsInstance(_new_options_for("chrome"), ChromeOptions)
        self.assertIsInstance(_new_options_for("chromium"), ChromeOptions)
        self.assertIsInstance(_new_options_for("firefox"), FirefoxOptions)

    def test_unknown_name_raises_not_found(self):
        with self.assertRaises(WebRunnerWebDriverNotFoundException):
            _new_options_for("not_a_real_browser")


class TestSetWebdriverOptionsArgument(unittest.TestCase):

    def test_arguments_are_applied(self):
        options = set_webdriver_options_argument(
            "chrome", ["--headless=new", "--disable-gpu"]
        )
        self.assertIsInstance(options, ChromeOptions)
        self.assertIn("--headless=new", options.arguments)
        self.assertIn("--disable-gpu", options.arguments)

    def test_unknown_name_fails_without_a_raw_typeerror(self):
        # The failure is recorded and then raised like every other wrapper failure; crucially it is the
        # "not found" error, not a raw TypeError from calling None().
        with self.assertRaises(WebRunnerWebDriverNotFoundException):
            set_webdriver_options_argument("nope", ["--x"])

    def test_non_string_argument_fails(self):
        with self.assertRaises(WebRunnerArgumentWrongTypeException):
            set_webdriver_options_argument("chrome", [123])

    def test_with_raising_switched_off_a_failure_yields_none(self):
        self.addCleanup(setattr, wrapper_failure_policy, "raise_errors", wrapper_failure_policy.raise_errors)
        wrapper_failure_policy.raise_errors = False
        self.assertIsNone(set_webdriver_options_argument("nope", ["--x"]))
        self.assertIsNone(set_webdriver_options_argument("chrome", [123]))


class TestSetWebdriverOptionsCapability(unittest.TestCase):

    def test_capabilities_are_applied(self):
        options = set_webdriver_options_capability_wrapper(
            "firefox", {"acceptInsecureCerts": True}
        )
        self.assertIsInstance(options, FirefoxOptions)
        self.assertTrue(options.accept_insecure_certs)

    def test_unknown_name_fails(self):
        with self.assertRaises(WebRunnerWebDriverNotFoundException):
            set_webdriver_options_capability_wrapper("nope", {"a": 1})

    def test_non_dict_capability_fails(self):
        with self.assertRaises(WebRunnerOptionsWrongTypeException):
            set_webdriver_options_capability_wrapper("chrome", ["not", "a", "dict"])

    def test_with_raising_switched_off_a_failure_yields_none(self):
        self.addCleanup(setattr, wrapper_failure_policy, "raise_errors", wrapper_failure_policy.raise_errors)
        wrapper_failure_policy.raise_errors = False
        self.assertIsNone(set_webdriver_options_capability_wrapper("nope", {"a": 1}))
        self.assertIsNone(set_webdriver_options_capability_wrapper("chrome", ["not", "a", "dict"]))


if __name__ == "__main__":
    unittest.main()
