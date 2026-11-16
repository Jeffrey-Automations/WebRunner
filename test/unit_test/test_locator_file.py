"""A shared locator file: logical names for elements, used by both backends."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cli.cli_main import main
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import Executor, executor
from je_web_runner.utils.project_config import load_config
from je_web_runner.utils.test_object.locator_file import (
    LocatorFileError,
    load_locators,
    read_locators,
    save_locator,
    strategy_name,
)
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.webdriver.playwright_locator import selector_for_recorded_name
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class _Workspace(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self.addCleanup(setattr, test_object_record, "test_object_record_dict",
                        test_object_record.test_object_record_dict)
        test_object_record.test_object_record_dict = {}

    def _write(self, name, content) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path

    @staticmethod
    def _stored(name):
        record = test_object_record.test_object_record_dict[name]
        return record.test_object_type, record.test_object_name


class TestLocatorFile(_Workspace):

    def test_strategy_names(self):
        self.assertEqual(strategy_name("css selector"), "CSS_SELECTOR")
        self.assertEqual(strategy_name("CSS_SELECTOR"), "CSS_SELECTOR")
        self.assertEqual(strategy_name(" id "), "ID")
        self.assertEqual(strategy_name("link text"), "LINK_TEXT")
        with self.assertRaises(LocatorFileError):
            strategy_name("magic")

    def test_save_locator_stores_under_the_logical_name(self):
        self.assertEqual(save_locator("login_button", "#login"), "login_button")
        self.assertEqual(self._stored("login_button"), ("CSS_SELECTOR", "#login"))
        save_locator("user", "user-field", "id")
        self.assertEqual(self._stored("user"), ("ID", "user-field"))

    def test_bad_locators(self):
        for arguments in (("", "#x"), ("name", ""), ("name", 3), (None, "#x"), ("name", "#x", "nope")):
            with self.subTest(arguments=arguments):
                with self.assertRaises(LocatorFileError):
                    save_locator(*arguments)

    def test_load_file(self):
        path = self._write("locators.json", {
            "login_button": {"by": "css selector", "value": "#login"},
            "user_field": {"by": "id", "value": "user"},
            "heading": {"value": "h1"},
        })
        self.assertEqual(load_locators(path), ["heading", "login_button", "user_field"])
        self.assertEqual(self._stored("heading"), ("CSS_SELECTOR", "h1"))
        self.assertEqual(read_locators(path)["user_field"], ("user", "ID"))

    def test_a_bad_entry_stores_nothing(self):
        path = self._write("locators.json", {"ok": {"value": "#ok"}, "bad": {"by": "magic", "value": "#x"}})
        with self.assertRaises(LocatorFileError):
            load_locators(path)
        self.assertEqual(test_object_record.test_object_record_dict, {})

    def test_bad_files(self):
        cases = {"list.json": ["#a"], "text.json": {"a": "#a"}, "extra.json": {"a": {"value": "#a", "css": "x"}},
                 "novalue.json": {"a": {"by": "id"}}}
        for name, content in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(LocatorFileError):
                    read_locators(self._write(name, content))
        with self.assertRaises(LocatorFileError):
            read_locators(self._write("broken.json", "{not json"))
        with self.assertRaises(LocatorFileError):
            read_locators(self.root / "missing.json")


class TestBothBackendsUseTheName(_Workspace):

    def test_selenium_finds_by_logical_name(self):
        save_locator("login_button", "#login")
        driver = MagicMock()
        with patch.object(webdriver_wrapper_instance, "current_webdriver", driver):
            webdriver_wrapper_instance.find_element_with_test_object_record("login_button")
        driver.find_element.assert_called_once_with("CSS_SELECTOR", "#login")

    def test_playwright_selector_for_logical_name(self):
        save_locator("login_button", "#login")
        save_locator("user", "user-field", "id")
        self.assertEqual(selector_for_recorded_name("login_button"), "#login")
        self.assertIn("user-field", selector_for_recorded_name("user"))


class TestCommandsAndRunSettings(_Workspace):

    def test_load_locators_command_is_relative_to_the_running_file(self):
        self._write("suite/locators.json", {"login_button": {"value": "#login"}})
        action_file = self._write("suite/login.json", [["WR_load_locators", {"path": "locators.json"}]])
        runner = Executor()
        with patch("builtins.print"):
            records = runner.execute_file(str(action_file))
        self.assertEqual(list(records.values()), [["login_button"]])
        self.assertEqual(self._stored("login_button"), ("CSS_SELECTOR", "#login"))

    def test_load_locators_command_is_fenced(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        other = Path(outside.name).resolve() / "locators.json"
        other.write_text("{}", encoding="utf-8")
        with self.assertRaises(WebRunnerExecuteException):
            Executor().execute_one(["WR_load_locators", {"path": str(other)}])

    def test_save_locator_command(self):
        Executor().execute_one(["WR_save_locator", {"name": "cart", "value": "//a[@id='cart']", "by": "xpath"}])
        self.assertEqual(self._stored("cart"), ("XPATH", "//a[@id='cart']"))

    def test_configuration_and_flag_load_locator_files(self):
        self._write("webrunner.toml", 'locators = ["shared.json"]\n')
        self._write("shared.json", {"from_config": {"value": "#a"}})
        self._write("more.json", {"from_flag": {"value": "#b"}})
        self.assertEqual(load_config(self.root / "webrunner.toml").locators, ["shared.json"])
        self.addCleanup(executor.variables.clear)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = main(["--execute_str", '[["WR_note"]]', "--locators", "more.json"])
        self.assertEqual(code, 0)
        self.assertEqual(sorted(test_object_record.test_object_record_dict), ["from_config", "from_flag"])


if __name__ == "__main__":
    unittest.main()
