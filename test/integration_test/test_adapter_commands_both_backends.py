"""
The adapter commands that read the page give the same result on Selenium and on Playwright.

Each command of :data:`_PLAN` runs once in a real headless Chrome through Selenium and once in a real
headless Chromium through Playwright, against the same page served from a loopback socket; the tests then
compare the two plain results. The plan covers every way the adapters use the browser: the page source, the
URL and title, cookies, a script with arguments, an asynchronous script, a screenshot, a DevTools command,
and a page loaded by the command itself. It skips when Playwright, its Chromium or Chrome is not available
(CI installs neither).
"""
import struct
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api", reason="Playwright is optional")

from je_web_runner.utils.driver_dispatch.playwright_driver import SeleniumBackendRequired  # noqa: E402
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException  # noqa: E402
from je_web_runner.utils.executor._command_helpers import browser_driver  # noqa: E402
from je_web_runner.utils.executor.action_executor import executor  # noqa: E402
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance  # noqa: E402
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance  # noqa: E402

_PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Adapter page</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preload" href="/a.css" as="style"><link rel="stylesheet" href="/a.css">
<script src="/lib.js"></script><style>body{font-family:sans-serif}</style></head>
<body><h1 id="h">Hello</h1><p>Contact: jane.doe@example.com, card 4111 1111 1111 1111</p>
<p id="tok">key AKIAIOSFODNN7EXAMPLE</p>
<button id="b" popovertarget="pop">Open</button><div id="pop" popover>Pop</div>
<script>localStorage.setItem('k','v'); sessionStorage.setItem('s','1');</script>
</body></html>"""
_EMAIL = {"message_id": "m1", "subject": "Welcome", "from_addr": "shop@example.test", "to": ["ann@example.test"],
          "html_body": "<html><body><h1>Welcome</h1></body></html>", "text_body": "Welcome", "headers": {},
          "raw": ""}
_VIEWPORT = [{"name": "phone", "width": 400, "height": 700, "dark_mode": True}]
_ASYNC_TIMER = ("const done = arguments[arguments.length - 1]; const count = arguments.length;"
                " setTimeout(() => done([count, arguments[0] + arguments[1]]), 20);")
_ASYNC_REJECTED = ("const done = arguments[arguments.length - 1];"
                   " Promise.reject(new Error('no')).then(done, (error) => done({error: String(error)}));")
_PNG = b"\x89PNG\r\n\x1a\n"


class _Site(BaseHTTPRequestHandler):
    """The page under test, with two cookies, and empty answers for what it links to."""

    def do_GET(self):  # noqa: N802  # the name http.server calls
        """Answer ``/`` with the page and anything else with an empty body."""
        is_page = self.path == "/"
        body = _PAGE.encode("utf-8") if is_page else b""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8" if is_page else "text/plain")
        if is_page:
            self.send_header("Set-Cookie", "sid=abc; Path=/")
            self.send_header("Set-Cookie", "pref=1; Path=/; HttpOnly; Max-Age=3600")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002  # pylint: disable=redefined-builtin  # http.server's name
        """Keep the test output quiet."""


def _plan(folder):
    """``(key, action or driver call)`` in the order it runs; a ``driver.`` key calls the driver itself."""
    return [
        # driver-level: scripts with arguments, asynchronous scripts (before a command changes the page)
        ("driver.script", ("execute_script", "return [arguments.length, arguments[0] + arguments[1], document.title]",
                           2, 3)),
        ("driver.script_nothing", ("execute_script", "document.body.dataset.seen = arguments[0];", "yes")),
        ("driver.async_timer", ("execute_async_script", _ASYNC_TIMER, 2, 3)),
        ("driver.async_rejected", ("execute_async_script", _ASYNC_REJECTED)),
        # the page source, the URL and the title
        ("pii_scanner", ["WR_pii_scanner_scan_page"]),
        ("sri_verify", ["WR_sri_verify_page"]),
        ("token_leak", ["WR_token_leak_detector_scan_page"]),
        ("critical_css", ["WR_critical_css_audit_page"]),
        ("resource_hints", ["WR_resource_hints_audit_page"]),
        ("viewport_audit", ["WR_viewport_audit_check_page"]),
        ("inbox_render", ["WR_inbox_render_outlook_audit_page"]),
        ("cross_browser", ["WR_cross_browser_capture", {"browser": "any"}]),
        # cookies
        ("cookie_scope", ["WR_cookie_scope_abuse_audit_page"]),
        ("consent_audit", ["WR_consent_audit_classify_page"]),
        ("state_diff", ["WR_state_diff_capture"]),
        # scripts the commands run
        ("popover", ["WR_popover_assert_harvest"]),
        ("cookie_store", ["WR_cookie_store_api_harvest"]),
        ("web_share_install", ["WR_web_share_assert_install"]),
        ("web_share", ["WR_web_share_assert_harvest"]),
        ("inp_install", ["WR_inp_tracker_install"]),
        ("inp", ["WR_inp_tracker_page"]),
        ("smart_wait_install", ["WR_smart_wait_install_hooks"]),
        ("smart_wait", ["WR_smart_wait_fetch_idle", {"quiet_for": 0.1, "timeout": 5}]),
        ("csp_install", ["WR_csp_reporter_install"]),
        ("csp", ["WR_csp_reporter_collect"]),
        ("taint_install", ["WR_dom_xss_taint_install", {"canaries": ["CANARY"]}]),
        ("taint", ["WR_dom_xss_taint_drain"]),
        # a screenshot
        ("failure_bundle", ["WR_failure_bundle_capture",
                            {"output_path": str(Path(folder) / "bundle.zip"), "test_name": "t", "error_repr": "e"}]),
        # DevTools commands, and a script that shows their effect
        ("forced_colors", ["WR_forced_colors_mode_apply", {"color_scheme": "dark"}]),
        ("driver.dark", ("execute_script", "return matchMedia('(prefers-color-scheme: dark)').matches")),
        ("geo_locale", ["WR_geo_locale_apply", {"timezone": "Asia/Tokyo"}]),
        ("driver.timezone", ("execute_script", "return Intl.DateTimeFormat().resolvedOptions().timeZone")),
        ("blocked", ["WR_third_party_block_test_block", {"vendors": ["google_analytics"]}]),
        ("unblocked", ["WR_third_party_block_test_unblock"]),
        ("webauthn", ["WR_webauthn_enable"]),
        # what only Selenium has
        ("console_budget", ["WR_console_error_budget_page"]),
        ("multi_tab", ["WR_multi_tab_register", {"alias": "main"}]),
        # last: it sizes the window, loads its own page and saves a screenshot
        ("email_render", ["WR_email_render_screenshots",
                          {"email": _EMAIL, "output_dir": str(Path(folder) / "mail"), "viewports": _VIEWPORT}]),
        ("driver.after_email", ("execute_script", "return [document.querySelector('h1').textContent,"
                                                  " matchMedia('(prefers-color-scheme: dark)').matches]")),
    ]


def _one(step):
    if isinstance(step, tuple):
        method, *arguments = step
        return getattr(browser_driver("the integration test"), method)(*arguments)
    return executor.execute_one(step)


def _run_plan(folder):
    """The result of every step of the plan, or the error it raised."""
    results = {}
    for key, step in _plan(folder):
        try:
            results[key] = _one(step)
        except Exception as error:  # pylint: disable=broad-exception-caught  # the tests compare what was raised
            results[key] = error.__cause__ or error
    credentials = results["webauthn"]
    if isinstance(credentials, dict):
        results["webauthn_credentials"] = executor.execute_one(
            ["WR_webauthn_list_credentials", {"authenticator_id": credentials["authenticator_id"]}])
        results["webauthn_removed"] = executor.execute_one(
            ["WR_webauthn_remove", {"authenticator_id": credentials["authenticator_id"]}])
    return results


def _png_size(path):
    data = Path(path).read_bytes()
    return struct.unpack(">II", data[16:24]) if data.startswith(_PNG) else None


class TestAdapterCommandsOnBothBackends(unittest.TestCase):
    """Every step ran on both browsers in :meth:`setUpClass`; each test compares one kind of result."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # closed in tearDownClass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        try:
            cls.selenium = cls._on_selenium(url)
            cls.playwright = cls._on_playwright(url)
        except unittest.SkipTest:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    @classmethod
    def _on_selenium(cls, url):
        try:
            from selenium import webdriver
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            driver = webdriver.Chrome(options=options)
        except Exception as error:  # no Chrome or chromedriver here
            raise unittest.SkipTest(f"Chrome for Selenium is not available: {error!r}")
        webdriver_wrapper_instance.current_webdriver = driver
        try:
            driver.get(url)
            return _run_plan(Path(cls.tmp.name) / "selenium")
        finally:
            driver.quit()
            webdriver_wrapper_instance.current_webdriver = None

    @classmethod
    def _on_playwright(cls, url):
        try:
            playwright_wrapper_instance.launch(browser="chromium", headless=True)
        except Exception as error:  # the browser build is not installed here
            raise unittest.SkipTest(f"Chromium for Playwright is not available: {error!r}")
        try:
            playwright_wrapper_instance.page.goto(url)
            return _run_plan(Path(cls.tmp.name) / "playwright")
        finally:
            playwright_wrapper_instance.quit()

    def _same(self, *keys):
        for key in keys:
            with self.subTest(step=key):
                self.assertNotIsInstance(self.selenium[key], Exception, self.selenium[key])
                self.assertEqual(self.playwright[key], self.selenium[key])

    def test_scripts_with_arguments(self):
        self._same("driver.script", "driver.script_nothing")
        self.assertEqual(self.playwright["driver.script"], [2, 5, "Adapter page"])
        self.assertIsNone(self.playwright["driver.script_nothing"])

    def test_asynchronous_scripts(self):
        self._same("driver.async_timer", "driver.async_rejected")
        self.assertEqual(self.playwright["driver.async_timer"], [3, 5])  # the callback is the third argument
        self.assertEqual(self.playwright["driver.async_rejected"], {"error": "Error: no"})

    def test_commands_that_read_the_page_source(self):
        self._same("pii_scanner", "sri_verify", "token_leak", "critical_css", "resource_hints", "viewport_audit",
                   "inbox_render", "cross_browser")
        self.assertEqual(self.playwright["pii_scanner"]["summary"], {"email": 1, "credit_card": 1})
        self.assertEqual(self.playwright["cross_browser"]["title"], "Adapter page")
        self.assertTrue(self.playwright["cross_browser"]["dom_text"].startswith('<html lang="en"><head>'))

    def test_commands_that_read_the_cookies(self):
        self._same("cookie_scope")
        by_name = sorted(self.selenium["consent_audit"], key=lambda cookie: cookie["name"])
        self.assertEqual(sorted(self.playwright["consent_audit"], key=lambda cookie: cookie["name"]), by_name)
        self.assertEqual([cookie["name"] for cookie in by_name], ["pref", "sid"])
        selenium, playwright = self.selenium["state_diff"], self.playwright["state_diff"]
        # The page was loaded once per browser, so the Max-Age cookie expires a few seconds apart.
        expiry = [results["cookies"]["pref"].pop("expiry") for results in (selenium, playwright)]
        self.assertLess(abs(expiry[0] - expiry[1]), 120)
        self.assertEqual(playwright, selenium)
        self.assertNotIn("expiry", playwright["cookies"]["sid"])  # a session cookie has none on Selenium

    def test_commands_that_run_their_own_scripts(self):
        self._same("popover", "cookie_store", "web_share_install", "web_share", "inp_install", "inp",
                   "smart_wait_install", "smart_wait", "csp_install", "csp", "taint_install", "taint")
        self.assertEqual(self.playwright["popover"][0]["id"], "pop")
        self.assertEqual(self.playwright["cookie_store"][0]["name"], "sid")  # the HttpOnly one is hidden from scripts

    def test_a_command_that_takes_a_screenshot(self):
        for results in (self.selenium, self.playwright):
            written = results["failure_bundle"]
            with zipfile.ZipFile(written["path"]) as bundle:
                self.assertTrue(bundle.read("artifacts/screenshot.png").startswith(_PNG))
        hashes = [{item["name"]: item["sha256"] for item in results["failure_bundle"]["manifest"]["artifacts"]}
                  for results in (self.selenium, self.playwright)]
        self.assertEqual(hashes[1]["artifacts/dom.html"], hashes[0]["artifacts/dom.html"])

    def test_commands_that_send_devtools_commands(self):
        self._same("forced_colors", "driver.dark", "geo_locale", "driver.timezone", "blocked", "unblocked",
                   "webauthn_credentials", "webauthn_removed")
        self.assertIs(self.playwright["driver.dark"], True)
        self.assertEqual(self.playwright["driver.timezone"], "Asia/Tokyo")
        for results in (self.selenium, self.playwright):
            self.assertEqual(len(results["webauthn"].pop("authenticator_id")), 36)  # a new id per browser
        self.assertEqual(self.playwright["webauthn"], self.selenium["webauthn"])

    def test_a_command_that_loads_its_own_page(self):
        self._same("driver.after_email")
        self.assertEqual(self.playwright["driver.after_email"], ["Welcome", True])
        shots = [results["email_render"][0] for results in (self.selenium, self.playwright)]
        for shot in shots:
            self.assertEqual((shot["viewport"], shot["width"], shot["height"]), ("phone", 400, 700))
        # Playwright's screenshot is the viewport asked for; Selenium sizes the window, whose page area is smaller.
        self.assertEqual(_png_size(shots[1]["screenshot_path"]), (400, 700))
        self.assertIsNotNone(_png_size(shots[0]["screenshot_path"]))

    def test_what_only_selenium_has_fails_by_name_on_playwright(self):
        self.assertTrue(self.selenium["console_budget"]["passed"])
        refused = self.playwright["console_budget"]
        self.assertIsInstance(refused, SeleniumBackendRequired)
        self.assertIn("WR_console_error_budget_page uses the Selenium driver's 'get_log'", str(refused))
        self.assertEqual(self.selenium["multi_tab"]["alias"], "main")
        refused = self.playwright["multi_tab"]
        self.assertIsInstance(refused, WebRunnerWebDriverIsNoneException)
        self.assertIn("WR_multi_tab_register needs the Selenium backend (Selenium window handles)", str(refused))


if __name__ == "__main__":
    unittest.main()
