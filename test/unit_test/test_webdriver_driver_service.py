"""The driver webdriver-manager downloads is the one Selenium starts."""
import unittest
from unittest.mock import MagicMock, patch

from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

from je_web_runner.webdriver import webdriver_wrapper
from je_web_runner.webdriver.webdriver_wrapper import WebDriverWrapper, _with_driver_service


class TestWithDriverService(unittest.TestCase):

    def test_each_browser_gets_its_own_service_class(self):
        chrome = _with_driver_service("chrome", "C:/drivers/chromedriver.exe", {})
        self.assertIsInstance(chrome["service"], ChromeService)
        self.assertEqual(chrome["service"].path, "C:/drivers/chromedriver.exe")
        self.assertIsInstance(_with_driver_service("chromium", "/d/chromedriver", {})["service"], ChromeService)
        self.assertIsInstance(_with_driver_service("firefox", "/d/geckodriver", {})["service"], FirefoxService)

    def test_other_arguments_are_kept_and_the_input_is_not_changed(self):
        given = {"keep_alive": True}
        result = _with_driver_service("chrome", "/d/chromedriver", given)
        self.assertEqual(result["keep_alive"], True)
        self.assertEqual(given, {"keep_alive": True})

    def test_a_service_the_caller_passed_wins(self):
        own = object()
        self.assertIs(_with_driver_service("chrome", "/d/chromedriver", {"service": own})["service"], own)

    def test_nothing_is_added_without_a_driver_file_or_a_known_browser(self):
        for name, path in (("chrome", None), ("chrome", ""), ("chrome", MagicMock()), ("safari", "/d/driver")):
            with self.subTest(name=name, path=path):
                self.assertEqual(_with_driver_service(name, path, {}), {})


class TestSetDriverUsesTheDownload(unittest.TestCase):

    def _start(self, **arguments):
        driver_class = MagicMock(name="Chrome")
        manager = MagicMock(name="manager")
        manager.return_value.install.return_value = "C:/wdm/chromedriver.exe"
        with patch.dict(webdriver_wrapper._webdriver_dict, {"chrome": driver_class}), \
                patch.dict(webdriver_wrapper._webdriver_manager_dict, {"chrome": manager}), \
                patch.object(webdriver_wrapper, "ActionChains"):
            WebDriverWrapper().set_driver("chrome", **arguments)
        return driver_class, manager

    def test_the_downloaded_driver_is_handed_to_selenium(self):
        driver_class, manager = self._start()
        manager.return_value.install.assert_called_once_with()
        service = driver_class.call_args.kwargs["service"]
        self.assertIsInstance(service, ChromeService)
        self.assertEqual(service.path, "C:/wdm/chromedriver.exe")

    def test_without_install_driver_selenium_resolves_the_driver_itself(self):
        driver_class, manager = self._start(install_driver=False)
        manager.return_value.install.assert_not_called()
        self.assertNotIn("service", driver_class.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
