"""
Playwright 同步 backend 包裝器，與既有 Selenium 路徑並行。
Playwright sync backend wrapper running side-by-side with the Selenium path.
It covers most everyday operations of ``WebDriverWrapper`` but is not a
one-to-one copy; ``docs/source/Eng/doc/backends/backends_doc.rst`` lists the
equivalent commands and what exists on one backend only.

設計原則 / Design notes:
- ``playwright`` 為軟相依，未安裝時呼叫才會丟出含安裝提示的錯誤。
  Playwright is a soft dependency; the import error only surfaces on first use.
- 不改寫 Selenium 的 ``WebDriverWrapper``；本 backend 完全獨立，使用 ``WR_pw_*``
  命名空間。
  Selenium ``WebDriverWrapper`` is untouched; this backend lives entirely under
  the ``WR_pw_*`` namespace and shares no mutable state with it.
- 元素層操作沿用「找完先存、後續對當前元素操作」流程，與既有 element wrapper
  一致；亦提供 page-level 直接快捷（``pw_click(selector)`` 等）。
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    test_object_record,
)
from je_web_runner.webdriver._playwright_mixins import (
    _ConnectMixin, _ContextMixin, _InteractionMixin, _PageMixin,
    _RecordingMixin, _ScopeMixin, _SessionsMixin, _StateMixin,
)
from je_web_runner.webdriver._playwright_mixins._common import (
    BROWSER_NOT_LAUNCHED,
    PlaywrightBackendError,
)
from je_web_runner.webdriver.playwright_element_wrapper import (
    PlaywrightElementWrapper,
    playwright_element_wrapper,
)
from je_web_runner.webdriver.playwright_locator import test_object_to_selector


def _require_playwright():
    """Import Playwright lazily; surface a clear install hint when missing."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        return sync_playwright
    except ImportError as error:
        raise PlaywrightBackendError(
            "Playwright is not installed. Install with: "
            "pip install playwright && python -m playwright install"
        ) from error


_SUPPORTED_BROWSERS = frozenset({"chromium", "firefox", "webkit"})


class PlaywrightWrapper(  # pylint: disable=too-many-ancestors,too-many-instance-attributes  # mixin facade
    _ContextMixin, _PageMixin, _InteractionMixin, _StateMixin,
    _RecordingMixin, _ScopeMixin, _ConnectMixin, _SessionsMixin,
):
    """
    Playwright 同步 API 的完整 backend 包裝
    Full sync-API wrapper for Playwright, organised around one browser /
    one context / multiple pages.
    """

    def __init__(self, element_wrapper: PlaywrightElementWrapper | None = None) -> None:
        self._playwright = None
        # One entry per open browser (see _SessionsMixin); the active one is None.
        self._sessions: list[dict[str, Any] | None] = []
        self._session_index = -1
        self._reset_state()
        self.element_wrapper = element_wrapper or playwright_element_wrapper

    def _reset_state(self) -> None:
        """Forget the browser, context, pages and every setting (start, and after quit)."""
        self._browser = None
        self._context = None
        self._pages: list[Any] = []
        self._page_index: int = -1
        # The merged options every new context gets (see _ContextMixin), and which
        # of them came from the current device descriptor.
        self._context_options: dict[str, Any] = {}
        self._emulation_keys: set[str] = set()
        # True for an adopted context (connect_over_cdp, launch_persistent): no rebuilds.
        self._fixed_context = False
        # Tracing options while a trace is being recorded (see _RecordingMixin), else None.
        self._trace_options: dict[str, Any] | None = None
        # Init scripts, URL blocks and the cache-off route, re-applied to every rebuilt context.
        self._init_scripts: list[str] = []
        self._blocked_urls: list[Any] = []
        self._cache_route: Any = None
        # The selected iframe (None: the page) and the dialog policy (see _ScopeMixin).
        self._frame: Any = None
        self._dialog_policy: tuple[str, str | None] | None = None
        self._dialog_pages: list[Any] = []
        self._last_dialog: dict[str, Any] | None = None

    # ----- lifecycle ---------------------------------------------------

    @property
    def page(self) -> Any:
        """The current page; raises ``PlaywrightBackendError`` when no page is open."""
        if not self._pages or self._page_index < 0:
            raise PlaywrightBackendError("Playwright page not launched; call launch() first")
        return self._pages[self._page_index]

    @property
    def context(self) -> Any:
        """The browser context; raises ``PlaywrightBackendError`` before a launch."""
        if self._context is None:
            raise PlaywrightBackendError("Playwright context not started; call launch() first")
        return self._context

    @property
    def browser(self) -> Any:
        """The browser; raises ``PlaywrightBackendError`` before a launch."""
        if self._browser is None:
            raise PlaywrightBackendError(BROWSER_NOT_LAUNCHED)
        return self._browser

    def launch(
        self,
        browser: str = "chromium",
        headless: bool = True,
        record_har_path: str | None = None,
        record_har_content: str = "omit",
        context_options: dict[str, Any] | None = None,
        **launch_options: Any,
    ) -> None:
        """
        啟動指定瀏覽器；可選擇於 context 開啟 HAR 錄製
        Launch the requested browser. ``context_options`` go to every context this
        wrapper creates (``user_agent``, ``viewport``, ``locale``, ``storage_state``,
        ``record_video_dir`` …); ``record_har_path`` starts HAR recording, with
        ``record_har_content`` ``"omit"`` / ``"embed"`` / ``"attach"``. Other keyword
        arguments go to ``browser_type.launch``.
        """
        web_runner_logger.info(f"playwright launch: browser={browser}, headless={headless}")
        self._browser = self._browser_type(browser).launch(headless=headless, **launch_options)
        self._context_options = dict(context_options or {})
        self._emulation_keys = set()
        if record_har_path:
            self._context_options.update({"record_har_path": record_har_path, "record_har_content": record_har_content})
        self._context = self._open_context()
        self._reset_pages(self._context.new_page())
        self._register_session()

    def _register_session(self) -> None:
        """Count the first browser as session 0 (``new_browser`` adds the next ones)."""
        if not self._sessions:
            self._sessions = [None]
            self._session_index = 0

    def _browser_type(self, browser: str) -> Any:
        """Return the runtime's ``chromium`` / ``firefox`` / ``webkit``, starting the runtime once."""
        if browser not in _SUPPORTED_BROWSERS:
            raise PlaywrightBackendError(
                f"unsupported playwright browser: {browser!r}; "
                f"choose one of {sorted(_SUPPORTED_BROWSERS)}"
            )
        if self._playwright is None:
            sync_playwright = _require_playwright()
            self._playwright = sync_playwright().start()
        return getattr(self._playwright, browser)

    def _stop_runtime(self) -> None:
        if self._playwright is not None:
            self._playwright.stop()
        self._playwright = None

    def _open_context(self, storage_state: Any = None) -> Any:
        """Create a context with the merged options (plus ``storage_state`` carried from the last one)."""
        kwargs = dict(self._context_options)
        if storage_state is not None:
            kwargs["storage_state"] = storage_state
        context = self._browser.new_context(**kwargs)
        context.on("page", self._track_page)
        self._reapply_context_setup(context)
        self._restart_tracing(context)
        return context

    def quit(self) -> None:
        """
        關閉所有瀏覽器並停止 Playwright
        Close every browser this wrapper opened (for ``connect_over_cdp``: disconnect,
        leaving it running; for a persistent profile: close its context), then stop
        the runtime.
        """
        web_runner_logger.info("playwright quit")
        try:
            self._close_current()
            for state in self._sessions:
                if state is not None:
                    self._restore(state)
                    self._close_current()
        finally:
            self._sessions = []
            self._session_index = -1
            self._reset_state()
            self._stop_runtime()


playwright_wrapper_instance = PlaywrightWrapper()


# ----- module-level shortcuts (executor binding) ----------------------

def pw_launch(browser: str = "chromium", headless: bool = True, **options: Any) -> None:
    """Launch ``chromium``, ``firefox`` or ``webkit`` and open a page (options: ``PlaywrightWrapper.launch``)."""
    playwright_wrapper_instance.launch(browser=browser, headless=headless, **options)


def pw_start_har_recording(har_path: str, content: str = "omit") -> None:
    """Rebuild the context with HAR recording to ``har_path``; ``content``: ``omit`` / ``embed`` / ``attach``."""
    playwright_wrapper_instance.start_har_recording(har_path, content=content)


def pw_stop_har_recording() -> None:
    """Stop HAR recording: the context is rebuilt, which writes the HAR file."""
    playwright_wrapper_instance.stop_har_recording()


def pw_route_mock(url_pattern: str, response: dict) -> None:
    """Answer requests matching ``url_pattern`` with ``response`` (``status``, ``body``, ``headers`` …)."""
    playwright_wrapper_instance.route_mock(url_pattern, response)


def pw_route_mock_json(url_pattern: str, json_data: Any, status: int = 200) -> None:
    """Answer requests matching ``url_pattern`` with ``json_data`` as a JSON body and ``status``."""
    playwright_wrapper_instance.route_mock_json(url_pattern, json_data, status=status)


def pw_route_unmock(url_pattern: str) -> None:
    """Remove the mock for ``url_pattern`` so its requests reach the network again."""
    playwright_wrapper_instance.route_unmock(url_pattern)


def pw_route_clear() -> None:
    """Remove every route handler of the current page."""
    playwright_wrapper_instance.route_clear()


def pw_emulate(device_name: str) -> None:
    """Apply Playwright's built-in device descriptor ``device_name`` (rebuilds the context)."""
    playwright_wrapper_instance.start_emulation(device_name)


def pw_stop_emulate() -> None:
    """Drop the emulated device's options, keeping the other context options (rebuilds the context)."""
    playwright_wrapper_instance.stop_emulation()


def pw_list_devices() -> list[str]:
    """The sorted device names ``pw_emulate`` accepts; needs a started Playwright runtime."""
    return playwright_wrapper_instance.list_device_names()


def pw_set_geolocation(latitude: float, longitude: float, accuracy: float | None = None) -> None:
    """Set the context's geolocation; grant the ``geolocation`` permission so pages can read it."""
    playwright_wrapper_instance.set_geolocation(latitude, longitude, accuracy=accuracy)


def pw_grant_permissions(permissions: list[str], origin: str | None = None) -> None:
    """Grant browser ``permissions`` (``geolocation``, ``clipboard-read`` …), to ``origin`` only when given."""
    playwright_wrapper_instance.grant_permissions(permissions, origin=origin)


def pw_clear_permissions() -> None:
    """Revoke every permission granted to the context."""
    playwright_wrapper_instance.clear_permissions()


def pw_set_timezone(timezone_id: str) -> None:
    """Rebuild the context with the timezone ``timezone_id``."""
    playwright_wrapper_instance.set_timezone(timezone_id)


def pw_clock_install(fake_now_ms: float | str | None = None) -> None:
    """Install Playwright's clock, starting at ``fake_now_ms`` (epoch milliseconds or an ISO date) when given."""
    playwright_wrapper_instance.clock_install(fake_now_ms)


def pw_clock_set_time(time_ms: float | str) -> None:
    """Freeze the page clock at ``time_ms`` (epoch milliseconds or an ISO date string)."""
    playwright_wrapper_instance.clock_set_time(time_ms)


def pw_clock_run_for(duration_ms: float) -> None:
    """Advance the installed clock by ``duration_ms`` milliseconds."""
    playwright_wrapper_instance.clock_run_for(duration_ms)


def pw_set_locale(locale: str, accept_language: str | None = None) -> None:
    """Rebuild the context with ``locale``; ``accept_language`` also sets the ``Accept-Language`` header."""
    playwright_wrapper_instance.set_locale(locale, accept_language=accept_language)


def pw_set_context_options(**options: Any) -> None:
    """Merge any ``browser.new_context`` options (``viewport``, ``color_scheme`` …) and rebuild the context."""
    playwright_wrapper_instance.set_context_options(**options)


def pw_set_user_agent(user_agent: str) -> None:
    """Rebuild the context with the user agent string ``user_agent``."""
    playwright_wrapper_instance.set_user_agent(user_agent)


def pw_set_extra_http_headers(headers: dict[str, str]) -> None:
    """Add ``headers`` to the extra HTTP headers sent with every request of the context."""
    playwright_wrapper_instance.set_extra_http_headers(headers)


def pw_save_storage_state(path: str) -> str:
    """Write the context's cookies and localStorage to ``path`` and return ``path``."""
    return playwright_wrapper_instance.save_storage_state(path)


def pw_tracing_start(screenshots: bool = True, snapshots: bool = True, sources: bool = False) -> None:
    """Start recording a trace of the context for Playwright's trace viewer."""
    playwright_wrapper_instance.start_tracing(screenshots=screenshots, snapshots=snapshots, sources=sources)


def pw_tracing_save_chunk(path: str) -> str:
    """Write the trace recorded since the last save to ``path`` and keep tracing."""
    return playwright_wrapper_instance.save_trace_chunk(path)


def pw_tracing_stop(path: str) -> str:
    """Write the trace recorded since the last save to ``path`` and stop tracing."""
    return playwright_wrapper_instance.stop_tracing(path)


def pw_video_start(video_dir: str, width: int | None = None, height: int | None = None) -> None:
    """Rebuild the context with video recording into ``video_dir``; ``width`` and ``height`` set the video size."""
    playwright_wrapper_instance.start_video_recording(video_dir, width=width, height=height)


def pw_video_stop() -> list[str]:
    """Stop video recording (rebuilds the context) and return the paths of the video files."""
    return playwright_wrapper_instance.stop_video_recording()


def pw_add_init_script(source: str) -> None:
    """Run the JavaScript ``source`` in every new document of the context before the page's own scripts."""
    playwright_wrapper_instance.add_init_script(source)


def pw_block_urls(patterns: list[str]) -> None:
    """Abort requests whose whole URL matches any of ``patterns``, where ``*`` matches anything."""
    playwright_wrapper_instance.block_urls(patterns)


def pw_unblock_urls() -> None:
    """Remove every block added by ``pw_block_urls``."""
    playwright_wrapper_instance.unblock_urls()


def pw_clear_geolocation() -> None:
    """Remove the geolocation override."""
    playwright_wrapper_instance.clear_geolocation()


def pw_bring_to_front() -> None:
    """Activate the current page's tab."""
    playwright_wrapper_instance.bring_to_front()


def pw_switch_to_page_by_url(pattern: str) -> bool:
    """Switch to the first page whose URL contains ``pattern``; returns False when none does."""
    return playwright_wrapper_instance.switch_to_page_by_url(pattern)


def pw_switch_to_page_by_title(pattern: str) -> bool:
    """Switch to the first page whose title contains ``pattern``; returns False when none does."""
    return playwright_wrapper_instance.switch_to_page_by_title(pattern)


def pw_screenshot_base64(full_page: bool = False) -> str:
    """The page screenshot as a base64 PNG string (the whole scrollable page with ``full_page``)."""
    return playwright_wrapper_instance.screenshot_base64(full_page=full_page)


def pw_print_page(file_path: str) -> str:
    """Save the page as a PDF at ``file_path`` and return ``file_path`` (headless Chromium only)."""
    return playwright_wrapper_instance.print_page(file_path)


def pw_scroll(scroll_x: float, scroll_y: float) -> None:
    """Scroll by ``(scroll_x, scroll_y)`` pixels with the mouse wheel."""
    playwright_wrapper_instance.scroll(scroll_x, scroll_y)


def pw_scroll_to_top() -> None:
    """Scroll the page to its top (``window.scrollTo(0, 0)``)."""
    playwright_wrapper_instance.scroll_to_top()


def pw_scroll_to_bottom() -> None:
    """Scroll the page to the bottom of ``document.body``."""
    playwright_wrapper_instance.scroll_to_bottom()


def pw_drag_and_drop_offset(selector: str, target_x: float, target_y: float) -> None:
    """Drag the element matching ``selector`` by ``(target_x, target_y)`` pixels from its centre."""
    playwright_wrapper_instance.drag_and_drop_offset(selector, target_x, target_y)


def pw_get_cookie(name: str) -> dict | None:
    """The first cookie called ``name`` in the context, or None."""
    return playwright_wrapper_instance.get_cookie(name)


def pw_delete_cookie(name: str) -> None:
    """Delete every cookie called ``name`` from the context."""
    playwright_wrapper_instance.delete_cookie(name)


def pw_check_current_page(check_dict: dict) -> None:
    """Assert the ``title``, ``url``, ``viewport_size`` or ``page_count`` given in ``check_dict``."""
    playwright_wrapper_instance.check_current_page(check_dict)


def pw_switch_to_frame(selectors: str | list[str]) -> None:
    """Make selector commands act inside the iframe matching ``selectors`` (a list enters nested iframes)."""
    playwright_wrapper_instance.switch_to_frame(selectors)


def pw_switch_to_parent_frame() -> None:
    """Select the parent of the current iframe (the page, for a top-level iframe)."""
    playwright_wrapper_instance.switch_to_parent_frame()


def pw_switch_to_main_frame() -> None:
    """Leave every iframe: selector commands act on the page again."""
    playwright_wrapper_instance.switch_to_main_frame()


def pw_find_by(by: str, value: str, wait: bool = True, **options: Any):
    """Find elements by ``role``, ``text``, ``label``, ``test_id`` …; the first match becomes the current element."""
    return playwright_wrapper_instance.find_by(by, value, wait=wait, **options)


def pw_set_dialog_policy(action: str = "accept", prompt_text: str | None = None) -> None:
    """Choose what happens to JavaScript dialogs from now on: ``accept``, ``dismiss`` or ``default``."""
    playwright_wrapper_instance.set_dialog_policy(action, prompt_text=prompt_text)


def pw_last_dialog() -> dict | None:
    """``{type, message, default_value, action}`` of the last dialog handled, or None."""
    return playwright_wrapper_instance.last_dialog()


def pw_connect(ws_endpoint: str, browser: str = "chromium", context_options: dict | None = None) -> None:
    """Connect to a Playwright browser server at ``ws_endpoint`` and open a context and page there."""
    playwright_wrapper_instance.connect(ws_endpoint, browser=browser, context_options=context_options)


def pw_connect_over_cdp(endpoint_url: str) -> None:
    """Attach to a Chromium started with ``--remote-debugging-port``; adopts its first context and pages."""
    playwright_wrapper_instance.connect_over_cdp(endpoint_url)


def pw_launch_persistent(user_data_dir: str, browser: str = "chromium", headless: bool = True,
                         extension_paths: list[str] | None = None, **context_options: Any) -> None:
    """Launch with the persistent profile in ``user_data_dir``, loading unpacked ``extension_paths`` if given."""
    playwright_wrapper_instance.launch_persistent(
        user_data_dir, browser=browser, headless=headless, extension_paths=extension_paths, **context_options)


def pw_download(selector: str, save_to: str) -> str:
    """Click ``selector``, wait for the download it starts, save it to ``save_to`` and return the saved path."""
    return playwright_wrapper_instance.download(selector, save_to)


def pw_set_cache_disabled(disabled: bool = True) -> None:
    """Disable the HTTP cache of the context (``True``) or restore it (``False``)."""
    playwright_wrapper_instance.set_cache_disabled(disabled)


def pw_new_browser(browser: str = "chromium", headless: bool = True, **launch_kwargs: Any) -> int:
    """Launch another browser beside the open ones, make it current and return its index."""
    return playwright_wrapper_instance.new_browser(browser=browser, headless=headless, **launch_kwargs)


def pw_switch_browser(index: int) -> None:
    """Make browser ``index`` (0-based, in opening order) the one commands act on."""
    playwright_wrapper_instance.switch_browser(index)


def pw_close_browser() -> None:
    """Close the current browser and continue with a remaining one; closing the last stops Playwright."""
    playwright_wrapper_instance.close_browser()


def pw_browser_count() -> int:
    """How many browsers the Playwright wrapper holds."""
    return playwright_wrapper_instance.browser_count()


def pw_quit() -> None:
    """Close every browser the wrapper opened (a CDP-attached one is only disconnected) and stop Playwright."""
    playwright_wrapper_instance.quit()


def pw_to_url(url: str, **goto_options: Any) -> None:
    """Navigate the current page to ``url``; ``goto_options`` go to Playwright's ``goto``."""
    playwright_wrapper_instance.to_url(url, **goto_options)


def pw_forward() -> None:
    """Go forward one entry in the current page's history."""
    playwright_wrapper_instance.forward()


def pw_back() -> None:
    """Go back one entry in the current page's history."""
    playwright_wrapper_instance.back()


def pw_refresh() -> None:
    """Reload the current page."""
    playwright_wrapper_instance.refresh()


def pw_url() -> str:
    """The current page's URL."""
    return playwright_wrapper_instance.url()


def pw_title() -> str:
    """The current page's title."""
    return playwright_wrapper_instance.title()


def pw_content() -> str:
    """The current page's full HTML source."""
    return playwright_wrapper_instance.content()


def pw_set_default_timeout(timeout_ms: float) -> None:
    """Set the default timeout, in milliseconds, of the current page's actions and waits."""
    playwright_wrapper_instance.set_default_timeout(timeout_ms)


def pw_set_default_navigation_timeout(timeout_ms: float) -> None:
    """Set the default timeout, in milliseconds, of the current page's navigations."""
    playwright_wrapper_instance.set_default_navigation_timeout(timeout_ms)


def pw_new_page() -> int:
    """Open a new page in the current context, make it current and return its index."""
    return playwright_wrapper_instance.new_page()


def pw_switch_to_page(index: int) -> None:
    """Make the page at ``index`` in the page list the current page."""
    playwright_wrapper_instance.switch_to_page(index)


def pw_close_page(index: int | None = None) -> None:
    """Close the page at ``index``, or the current page when ``index`` is None."""
    playwright_wrapper_instance.close_page(index)


def pw_page_count() -> int:
    """How many pages (tabs and popups) of the context are open."""
    return playwright_wrapper_instance.page_count()


def pw_find_element(selector: str):
    """The first element matching ``selector`` in the current frame or page, or None; it does not wait."""
    return playwright_wrapper_instance.find_element(selector)


def pw_find_elements(selector: str) -> list[Any]:
    """Every element matching ``selector`` in the current frame or page (an empty list when none)."""
    return playwright_wrapper_instance.find_elements(selector)


def pw_find_element_with_test_object_record(element_name: str):
    """Find the saved test object ``element_name``; the first match becomes the current element."""
    return playwright_wrapper_instance.find_element_with_test_object_record(element_name)


def pw_find_elements_with_test_object_record(element_name: str):
    """Find every match of the saved test object ``element_name`` (the first becomes current)."""
    return playwright_wrapper_instance.find_elements_with_test_object_record(element_name)


def pw_click(selector: str, **options: Any) -> None:
    """Click the first element matching ``selector``; ``options`` go to Playwright's ``click``."""
    playwright_wrapper_instance.click(selector, **options)


def pw_dblclick(selector: str, **options: Any) -> None:
    """Double-click the first element matching ``selector``; ``options`` go to Playwright's ``dblclick``."""
    playwright_wrapper_instance.dblclick(selector, **options)


def pw_hover(selector: str, **options: Any) -> None:
    """Move the mouse over the first element matching ``selector``."""
    playwright_wrapper_instance.hover(selector, **options)


def pw_fill(selector: str, value: str, **options: Any) -> None:
    """Replace the value of the field matching ``selector`` with ``value``."""
    playwright_wrapper_instance.fill(selector, value, **options)


def pw_type_text(selector: str, value: str, delay: float = 0, **options: Any) -> None:
    """Type ``value`` into the element matching ``selector`` key by key, ``delay`` milliseconds apart."""
    playwright_wrapper_instance.type_text(selector, value, delay=delay, **options)


def pw_press(selector: str, key: str, **options: Any) -> None:
    """Focus the element matching ``selector`` and press ``key`` (``Enter``, ``Control+A`` …)."""
    playwright_wrapper_instance.press(selector, key, **options)


def pw_check(selector: str, **options: Any) -> None:
    """Tick the checkbox or radio button matching ``selector``."""
    playwright_wrapper_instance.check(selector, **options)


def pw_uncheck(selector: str, **options: Any) -> None:
    """Untick the checkbox matching ``selector``."""
    playwright_wrapper_instance.uncheck(selector, **options)


def pw_select_option(selector: str, value: Any, **options: Any) -> list[str]:
    """Select ``value`` in the ``<select>`` matching ``selector``; returns the selected values."""
    return playwright_wrapper_instance.select_option(selector, value, **options)


def pw_drag_and_drop(source_selector: str, target_selector: str, **options: Any) -> None:
    """Drag the element matching ``source_selector`` onto the one matching ``target_selector``."""
    playwright_wrapper_instance.drag_and_drop(source_selector, target_selector, **options)


def pw_evaluate(expression: str, arg: Any = None):
    """Run JavaScript ``expression`` in the current frame or page (with ``arg`` if given) and return its value."""
    return playwright_wrapper_instance.evaluate(expression, arg)


def pw_get_cookies() -> list[dict]:
    """Every cookie of the context, as a list of dicts."""
    return playwright_wrapper_instance.get_cookies()


def pw_add_cookies(cookies: list[dict]) -> None:
    """Add ``cookies`` (a list of cookie dicts) to the context."""
    playwright_wrapper_instance.add_cookies(cookies)


def pw_clear_cookies() -> None:
    """Delete every cookie of the context."""
    playwright_wrapper_instance.clear_cookies()


def pw_screenshot(path: str, full_page: bool = False) -> str:
    """Save a screenshot of the page to ``path`` (the whole page with ``full_page``) and return ``path``."""
    return playwright_wrapper_instance.screenshot(path, full_page=full_page)


def pw_screenshot_bytes(full_page: bool = False) -> bytes:
    """The page screenshot as image bytes (the whole scrollable page with ``full_page``)."""
    return playwright_wrapper_instance.screenshot_bytes(full_page=full_page)


def pw_wait_for_selector(selector: str, timeout: float | None = None, state: str = "visible"):
    """Wait until an element matching ``selector`` reaches ``state``; ``timeout`` is in milliseconds."""
    return playwright_wrapper_instance.wait_for_selector(selector, timeout=timeout, state=state)


def pw_wait_for_load_state(state: str = "load", timeout: float | None = None) -> None:
    """Wait until the page reaches the load state ``state``; ``timeout`` is in milliseconds."""
    playwright_wrapper_instance.wait_for_load_state(state, timeout=timeout)


def pw_wait_for_timeout(timeout_ms: float) -> None:
    """Pause for ``timeout_ms`` milliseconds."""
    playwright_wrapper_instance.wait_for_timeout(timeout_ms)


def pw_wait_for_url(url: str, timeout: float | None = None) -> None:
    """Wait until the page has navigated to ``url``; ``timeout`` is in milliseconds."""
    playwright_wrapper_instance.wait_for_url(url, timeout=timeout)


def pw_set_viewport_size(width: int, height: int) -> None:
    """Resize the page's viewport to ``width`` x ``height`` pixels."""
    playwright_wrapper_instance.set_viewport_size(width, height)


def pw_viewport_size() -> dict | None:
    """The page's viewport as ``{width, height}``, or None when it has none."""
    return playwright_wrapper_instance.viewport_size()


def pw_mouse_click(x: float, y: float, button: str = "left", click_count: int = 1) -> None:
    """Click at page coordinates ``(x, y)`` with ``button``, ``click_count`` times."""
    playwright_wrapper_instance.mouse_click(x, y, button=button, click_count=click_count)


def pw_mouse_move(x: float, y: float, steps: int = 1) -> None:
    """Move the mouse to page coordinates ``(x, y)`` in ``steps`` intermediate moves."""
    playwright_wrapper_instance.mouse_move(x, y, steps=steps)


def pw_mouse_down(button: str = "left", click_count: int = 1) -> None:
    """Press ``button`` at the current mouse position and hold it."""
    playwright_wrapper_instance.mouse_down(button=button, click_count=click_count)


def pw_mouse_up(button: str = "left", click_count: int = 1) -> None:
    """Release ``button`` at the current mouse position."""
    playwright_wrapper_instance.mouse_up(button=button, click_count=click_count)


def pw_keyboard_press(key: str) -> None:
    """Press and release ``key`` on the page (``Enter``, ``Control+A`` …)."""
    playwright_wrapper_instance.keyboard_press(key)


def pw_keyboard_type(text: str, delay: float = 0) -> None:
    """Type ``text`` into the focused element, ``delay`` milliseconds between keys."""
    playwright_wrapper_instance.keyboard_type(text, delay=delay)


def pw_keyboard_down(key: str) -> None:
    """Hold ``key`` down until :meth:`keyboard_up`."""
    playwright_wrapper_instance.keyboard_down(key)


def pw_keyboard_up(key: str) -> None:
    """Release ``key``."""
    playwright_wrapper_instance.keyboard_up(key)


def pw_save_test_object_to_selector(test_object_name: str, object_type: str = "CSS_SELECTOR") -> str:
    """
    把 TestObject 存進 ``test_object_record`` 並回傳對應的 Playwright selector
    Save a TestObject under ``test_object_record`` and return its Playwright
    selector. Convenience for scripts that want to register and use a locator
    in one step.
    """
    test_object_record.save_test_object(test_object_name, object_type)
    return test_object_to_selector(test_object_record.test_object_record_dict[test_object_name])
