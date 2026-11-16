"""Playwright lookups by a raw selector, ``make_current`` on the wait, and the recorded launch and quit."""
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.sel_to_pw import translate_for_backend
from je_web_runner.utils.test_object.locator_file import LocatorFileError
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError
from je_web_runner.webdriver.playwright_locator import raw_selector
from je_web_runner.webdriver.playwright_wrapper import PlaywrightWrapper


def _launched():
    playwright = MagicMock(name="playwright")
    browser = MagicMock(name="browser")
    context = MagicMock(name="context")
    page = MagicMock(name="page")
    playwright.chromium.launch.return_value = browser
    browser.new_context.return_value = context
    context.new_page.return_value = page
    factory = MagicMock(return_value=MagicMock(start=MagicMock(return_value=playwright)))
    with patch.object(pw_module, "_require_playwright", return_value=factory):
        wrapper = PlaywrightWrapper()
        wrapper.launch(browser="chromium", headless=True, context_options={"storage_state": "secret.json"})
    return wrapper, page


class _RecordingCase(unittest.TestCase):

    def setUp(self):
        saved, enabled = list(test_record_instance.test_record_list), test_record_instance.init_record
        self.addCleanup(setattr, test_record_instance, "test_record_list", saved)
        self.addCleanup(test_record_instance.set_record_enable, enabled)
        test_record_instance.set_record_enable(True)
        test_record_instance.test_record_list = []

    @staticmethod
    def recorded_names() -> list[str]:
        return [record["function_name"] for record in test_record_instance.test_record_list]


class TestRawSelector(unittest.TestCase):

    def test_selenium_spellings_become_playwright_selectors(self):
        self.assertEqual(raw_selector("#go"), "#go")
        self.assertEqual(raw_selector("go", "id"), raw_selector("go", "ID"))
        self.assertTrue(raw_selector("//a", "xpath").startswith("xpath="))
        self.assertNotEqual(raw_selector("go", "id"), "go")

    def test_unknown_strategy_is_refused(self):
        with self.assertRaises(LocatorFileError):
            raw_selector("x", "by smell")


class TestFindBy(_RecordingCase):

    def test_first_match_becomes_the_current_element(self):
        wrapper, page = _launched()
        element = MagicMock(name="element")
        page.query_selector.return_value = element
        self.assertIs(wrapper.find_element_by("#go"), element)
        page.query_selector.assert_called_once_with("#go")
        self.assertIs(wrapper.element_wrapper.current_element, element)
        self.assertIn("Playwright find_element_by", self.recorded_names())

    def test_nothing_matching_fails_and_keeps_the_current_element(self):
        wrapper, page = _launched()
        before = MagicMock(name="before")
        wrapper.element_wrapper.current_element = before
        page.query_selector.return_value = None
        with self.assertRaises(PlaywrightBackendError) as caught:
            wrapper.find_element_by("missing", "id")
        self.assertIn("missing", str(caught.exception))
        self.assertIs(wrapper.element_wrapper.current_element, before)
        failed = test_record_instance.test_record_list[-1]
        self.assertEqual(failed["function_name"], "Playwright find_element_by")
        self.assertNotEqual(str(failed["program_exception"]), "None")

    def test_every_match_becomes_the_list_and_the_current_element_stays(self):
        wrapper, page = _launched()
        before = MagicMock(name="before")
        wrapper.element_wrapper.current_element = before
        page.query_selector_all.return_value = ["a", "b"]
        self.assertEqual(wrapper.find_elements_by("li"), ["a", "b"])
        self.assertEqual(wrapper.element_wrapper.current_element_list, ["a", "b"])
        self.assertIs(wrapper.element_wrapper.current_element, before)
        page.query_selector_all.return_value = []
        self.assertEqual(wrapper.find_elements_by("li"), [])


class TestWaitMakesCurrent(_RecordingCase):

    def test_off_by_default(self):
        wrapper, page = _launched()
        before = MagicMock(name="before")
        wrapper.element_wrapper.current_element = before
        wrapper.wait_for_selector("#go")
        page.wait_for_selector.assert_called_once_with("#go", state="visible")
        self.assertIs(wrapper.element_wrapper.current_element, before)

    def test_the_element_waited_for_becomes_current(self):
        wrapper, page = _launched()
        element = MagicMock(name="element")
        page.wait_for_selector.return_value = element
        wrapper.wait_for_selector("#go", timeout=500, state="attached", make_current=True)
        page.wait_for_selector.assert_called_once_with("#go", state="attached", timeout=500)
        self.assertIs(wrapper.element_wrapper.current_element, element)

    def test_a_wait_for_absence_keeps_the_current_element(self):
        wrapper, page = _launched()
        before = MagicMock(name="before")
        wrapper.element_wrapper.current_element = before
        page.wait_for_selector.return_value = None
        wrapper.wait_for_selector("#gone", state="hidden", make_current=True)
        self.assertIs(wrapper.element_wrapper.current_element, before)


class TestLifecycleIsRecorded(_RecordingCase):

    def test_launch_and_quit_are_steps_and_options_are_hidden(self):
        wrapper, _ = _launched()
        wrapper.quit()
        self.assertEqual(self.recorded_names(), ["Playwright launch", "Playwright quit"])
        launch = test_record_instance.test_record_list[0]
        self.assertNotIn("secret.json", str(launch["local_param"]))


class TestCommandsAndTranslation(unittest.TestCase):

    def test_commands_are_registered(self):
        for name in ("WR_pw_find_element_by", "WR_pw_find_elements_by"):
            self.assertIn(name, executor.event_dict)

    def test_a_lookup_translates_to_one_action(self):
        self.assertEqual(translate_for_backend([["WR_find_element_by", {"selector": "#go"}]], "playwright"),
                         [["WR_pw_find_element_by", {"selector": "#go"}]])

    def test_a_captured_lookup_translates(self):
        action = ["WR_capture", {"name": "found", "action": ["WR_find_elements_by", {"selector": "li"}]}]
        translated = translate_for_backend([action], "playwright")
        self.assertEqual(translated[0][1]["action"][0], "WR_pw_find_elements_by")


if __name__ == "__main__":
    unittest.main()
