"""The commands the authoring helpers emit exist, and do what their bullets say."""
import unittest
from unittest.mock import MagicMock, patch

from selenium.webdriver.common.keys import Keys

from je_web_runner.utils.action_templates.templates import available_templates, get_template
from je_web_runner.utils.exception.exceptions import (
    WebRunnerAssertException,
    WebRunnerExecuteException,
    WebRunnerWebDriverIsNoneException,
)
from je_web_runner.utils.executor import _authoring_commands as commands
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.md_authoring import parse_markdown

_EVERY_BULLET = "\n".join([
    "- open https://example.com",
    '- type "alice" into #user',
    "- click #submit",
    "- wait 2s",
    '- assert title "Welcome"',
    "- press Enter",
    "- screenshot",
    "- run template login_basic",
    "- something the parser does not know",
    "- quit",
])


# The templates WebRunner ships, read before any test registers one of its own.
_SHIPPED_TEMPLATES = tuple(available_templates())


def _command_names(actions):
    return {action[0] for action in actions if isinstance(action, list) and action}


class TestEmittedCommandsAreRegistered(unittest.TestCase):

    def test_markdown_bullets(self):
        emitted = _command_names(parse_markdown(_EVERY_BULLET))
        self.assertEqual(sorted(emitted - set(executor.event_dict)), [])

    def test_builtin_templates(self):
        emitted = set()
        self.assertIn("close_modal", _SHIPPED_TEMPLATES)
        for name in _SHIPPED_TEMPLATES:
            emitted |= _command_names(get_template(name).actions)
        self.assertEqual(sorted(emitted - set(executor.event_dict)), [])


class TestAssertTitle(unittest.TestCase):

    def test_matching_title_is_returned(self):
        with patch.object(commands.webdriver_wrapper_instance, "get_title", return_value="Welcome"):
            self.assertEqual(commands.assert_title("Welcome"), "Welcome")

    def test_other_title_raises(self):
        with patch.object(commands.webdriver_wrapper_instance, "get_title", return_value="Login"):
            with self.assertRaises(WebRunnerAssertException) as raised:
                commands.assert_title("Welcome")
        self.assertIn("'Login'", str(raised.exception))
        self.assertIn("'Welcome'", str(raised.exception))


class TestPressKeys(unittest.TestCase):

    def _press(self, keys):
        chain = MagicMock()
        chain.send_keys.return_value = chain
        with patch.object(commands.webdriver_wrapper_instance, "current_webdriver", MagicMock()), \
                patch.object(commands, "ActionChains", return_value=chain):
            commands.press_keys(keys)
        return chain

    def test_named_key(self):
        chain = self._press("Enter")
        chain.send_keys.assert_called_once_with(Keys.ENTER)
        chain.perform.assert_called_once_with()

    def test_several_keys_and_short_names(self):
        chain = self._press(["Esc", "a", "Tab"])
        chain.send_keys.assert_called_once_with(Keys.ESCAPE, "a", Keys.TAB)

    def test_unknown_key_raises_before_anything_is_sent(self):
        with patch.object(commands.webdriver_wrapper_instance, "current_webdriver", MagicMock()), \
                patch.object(commands, "ActionChains") as chains:
            with self.assertRaises(WebRunnerExecuteException):
                commands.press_keys("NoSuchKey")
        chains.assert_not_called()

    def test_without_a_browser(self):
        with patch.object(commands.webdriver_wrapper_instance, "current_webdriver", None):
            with self.assertRaises(WebRunnerWebDriverIsNoneException):
                commands.press_keys("Enter")


class TestDismissCookieConsent(unittest.TestCase):

    def test_clicks_the_first_banner_button_found(self):
        driver = MagicMock()
        driver.execute_script.side_effect = [False, True]
        with patch.object(commands.webdriver_wrapper_instance, "current_webdriver", driver):
            clicked = commands.dismiss_cookie_consent()
        self.assertEqual(clicked, driver.execute_script.call_args.args[1])
        self.assertEqual(driver.execute_script.call_count, 2)

    def test_no_banner_gives_none(self):
        driver = MagicMock()
        driver.execute_script.return_value = False
        with patch.object(commands.webdriver_wrapper_instance, "current_webdriver", driver):
            self.assertIsNone(commands.dismiss_cookie_consent())

    def test_without_a_browser(self):
        with patch.object(commands.webdriver_wrapper_instance, "current_webdriver", None):
            with self.assertRaises(WebRunnerWebDriverIsNoneException):
                commands.dismiss_cookie_consent()


class TestNoteAndTemplate(unittest.TestCase):

    def test_note_returns_its_text(self):
        self.assertEqual(executor.execute_one(["WR_note", {"text": "swipe here"}]), "swipe here")
        self.assertEqual(executor.execute_one(["WR__note", {"text": "old name"}]), "old name")

    def test_render_template_runs_the_rendered_actions(self):
        ran = []
        with patch.object(executor, "attempt", side_effect=lambda action: ran.append(action) or "ok"):
            result = executor.event_dict["WR_render_template"]("accept_cookies")
        self.assertEqual(ran, get_template("accept_cookies").actions)
        self.assertEqual(result, ["ok"] * len(ran))

    def test_render_template_fails_when_a_step_fails(self):
        with patch.object(executor, "attempt", side_effect=WebRunnerExecuteException("boom")):
            with self.assertRaises(WebRunnerExecuteException):
                executor.event_dict["WR_render_template"]("accept_cookies")


if __name__ == "__main__":
    unittest.main()
