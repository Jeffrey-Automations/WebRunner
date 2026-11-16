"""Which backend a command drives is decided by its implementation."""
import unittest

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.sel_to_pw.backend_binding import (
    NEUTRAL,
    PLAYWRIGHT,
    SELENIUM,
    backend_of,
    backends_reached,
    registered_command,
)
from je_web_runner.utils.storage.browser_storage import selenium_local_storage_set
from je_web_runner.utils.visual_regression.visual_diff import capture_baseline
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


def _calls_a_helper_outside_the_package():
    return _selenium_driver()


def _selenium_driver():
    return webdriver_wrapper_instance.current_webdriver


def _imports_playwright_when_called():
    # The import inside the function is what the test is about.
    from je_web_runner.webdriver.playwright_wrapper import (  # pylint: disable=import-outside-toplevel,reimported
        playwright_wrapper_instance as wrapper,
    )
    return wrapper


def _touches_both():
    return webdriver_wrapper_instance, playwright_wrapper_instance


def _touches_neither(value):
    return value + 1


class TestBackendOf(unittest.TestCase):

    def test_bound_methods_of_the_selenium_objects(self):
        for command in ("WR_to_url", "WR_element_click", "WR_new_driver", "WR_route_mock",
                        "WR_assert_no_console_errors", "WR_maximize_window"):
            with self.subTest(command=command):
                self.assertEqual(backend_of(command), SELENIUM)

    def test_functions_that_reach_the_selenium_driver(self):
        for command in ("WR_local_storage_set", "WR_cdp", "WR_throttle", "WR_recorder_start",
                        "WR_visual_compare", "WR_iframe_switch_chain", "WR_start_remote_driver",
                        "WR_appium_start", "WR_assert_title"):
            with self.subTest(command=command):
                self.assertEqual(backend_of(command), SELENIUM)

    def test_playwright_commands(self):
        for command in ("WR_pw_to_url", "WR_pw_element_click", "WR_pw_local_storage_set", "WR_pw_cdp",
                        "WR_pw_recorder_start", "WR_pw_tracing_start"):
            with self.subTest(command=command):
                self.assertEqual(backend_of(command), PLAYWRIGHT)

    def test_commands_that_touch_no_browser_are_neutral(self):
        for command in ("WR_set_var", "WR_if", "WR_for_each", "WR_try", "WR_capture", "WR_note", "WR_sleep",
                        "WR_generate_html_report", "WR_http_get", "WR_execute_action", "WR_execute_files",
                        "WR_save_test_object", "WR_save_locator", "WR_call_file", "WR_set_retry_policy",
                        "WR_faker_email", "WR_db_query"):
            with self.subTest(command=command):
                self.assertEqual(backend_of(command), NEUTRAL)

    def test_an_unregistered_name_is_neutral(self):
        self.assertIsNone(registered_command("a_plugin_command"))
        self.assertEqual(backend_of("a_plugin_command"), NEUTRAL)

    def test_most_commands_are_classified_as_some_backend_or_neutral(self):
        kinds = {backend_of(name) for name in executor.event_dict if isinstance(name, str)}
        self.assertEqual(kinds, {SELENIUM, PLAYWRIGHT, NEUTRAL})


class TestBackendsReached(unittest.TestCase):

    def test_through_a_helper_of_the_package(self):
        self.assertNotIn("webdriver_wrapper_instance", selenium_local_storage_set.__code__.co_names)
        self.assertEqual(backends_reached(selenium_local_storage_set), {SELENIUM})

    def test_only_functions_of_the_package_are_followed(self):
        self.assertEqual(backends_reached(_selenium_driver), {SELENIUM})
        self.assertEqual(backends_reached(_calls_a_helper_outside_the_package), set())

    def test_through_an_import_inside_the_function(self):
        self.assertEqual(backends_reached(_imports_playwright_when_called), {PLAYWRIGHT})

    def test_through_a_closure_and_a_default_argument(self):
        wrapper = webdriver_wrapper_instance

        def closes_over():
            return wrapper

        self.assertEqual(backends_reached(closes_over), {SELENIUM})
        # ``screenshot`` defaults to the function that reads the Selenium driver.
        self.assertEqual(backends_reached(capture_baseline), {SELENIUM})

    def test_both_or_neither(self):
        self.assertEqual(backends_reached(_touches_both), {SELENIUM, PLAYWRIGHT})
        self.assertEqual(backends_reached(_touches_neither), set())
        self.assertEqual(backends_reached(len), set())

    def test_a_bound_method_drives_what_its_object_holds(self):
        self.assertEqual(backends_reached(webdriver_wrapper_instance.to_url), {SELENIUM})
        self.assertEqual(backends_reached(playwright_wrapper_instance.to_url), {PLAYWRIGHT})
        self.assertEqual(backends_reached(executor.execute_action), set())


if __name__ == "__main__":
    unittest.main()
