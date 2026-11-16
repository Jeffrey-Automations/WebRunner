"""分頁、導航、逾時、找元素 / Pages, navigation, timeouts and element lookup."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import recorded
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError, record
from je_web_runner.webdriver._playwright_mixins._host import _PlaywrightHost
from je_web_runner.webdriver.playwright_locator import raw_selector, selector_for_recorded_name


class _PageMixin(_PlaywrightHost):  # pylint: disable=too-many-public-methods  # one method per command
    """分頁切換、URL 導航、預設逾時、依 selector 或 TestObject 找元素。

    Page (tab) management, URL navigation, default timeouts, and element lookup
    by selector or recorded TestObject name.
    """

    @recorded()
    def new_page(self) -> int:
        """Open a new page in the current context; returns its index."""
        page = self.context.new_page()
        self._track_page(page)
        self._page_index = self._pages.index(page)
        self._frame = None
        return self._page_index

    def _reset_pages(self, page: Any) -> None:
        """Make ``page`` the only, current page (after a launch or a context rebuild)."""
        self._pages = [page]
        self._page_index = 0
        self._frame = None
        self._watch_dialogs(page)

    def _track_page(self, page: Any) -> None:
        """
        記住 context 開啟的每個分頁（包含網站自己開的 popup）
        Remember a page the context opened, including popups and ``window.open``
        pages the site opens itself; forget it again when it closes.
        """
        if any(known is page for known in self._pages):
            return
        self._pages.append(page)
        page.on("close", self._forget_page)
        self._watch_dialogs(page)

    def _forget_page(self, page: Any) -> None:
        index = next((i for i, known in enumerate(self._pages) if known is page), None)
        if index is None:
            return
        del self._pages[index]
        self._frame = None
        if not self._pages:
            self._page_index = -1
        elif index < self._page_index:
            self._page_index -= 1
        else:
            self._page_index = min(self._page_index, len(self._pages) - 1)

    @recorded()
    def switch_to_page(self, index: int) -> None:
        """Make the page at ``index`` in the page list current; ``PlaywrightBackendError`` if out of range."""
        if index < 0 or index >= len(self._pages):
            raise PlaywrightBackendError(f"page index {index} out of range")
        self._page_index = index
        self._frame = None

    @recorded()
    def close_page(self, index: int | None = None) -> None:
        """Close the page at ``index`` (the current page when None); ``PlaywrightBackendError`` if out of range."""
        target_index = self._page_index if index is None else index
        if target_index < 0 or target_index >= len(self._pages):
            raise PlaywrightBackendError(f"page index {target_index} out of range")
        page = self._pages[target_index]
        page.close()
        self._forget_page(page)

    @recorded()
    def bring_to_front(self) -> None:
        """Activate the current page's tab."""
        self.page.bring_to_front()

    def switch_to_page_by_url(self, pattern: str) -> bool:
        """Switch to the first page whose URL contains ``pattern`` (case-sensitive); False if none does."""
        return self._switch_to_first(lambda page: pattern in page.url)

    def switch_to_page_by_title(self, pattern: str) -> bool:
        """Switch to the first page whose title contains ``pattern`` (case-sensitive); False if none does."""
        return self._switch_to_first(lambda page: pattern in page.title())

    def _switch_to_first(self, matches: Any) -> bool:
        for index, page in enumerate(self._pages):
            if matches(page):
                self._page_index = index
                self._frame = None
                return True
        return False

    def page_count(self) -> int:
        """How many pages (tabs and popups) of the context are open."""
        return len(self._pages)

    # ----- navigation --------------------------------------------------

    def to_url(self, url: str, **goto_options: Any) -> None:
        """Navigate the current page to ``url`` (``goto_options`` go to ``goto``); a failure is recorded, not raised."""
        web_runner_logger.info(f"playwright to_url: {url}")
        params = {"url": url}
        try:
            self._frame = None
            self.page.goto(url, **goto_options)
            record("to_url", params, None)
        except Exception as error:  # pylint: disable=broad-exception-caught  # recorded; the executor decides
            web_runner_logger.error(f"playwright to_url failed: {error!r}")
            record("to_url", params, error)

    @recorded()
    def forward(self) -> None:
        """Go forward one entry in the current page's history."""
        self._frame = None
        self.page.go_forward()

    @recorded()
    def back(self) -> None:
        """Go back one entry in the current page's history."""
        self._frame = None
        self.page.go_back()

    @recorded()
    def refresh(self) -> None:
        """Reload the current page."""
        self._frame = None
        self.page.reload()

    def url(self) -> str:
        """The current page's URL."""
        return self.page.url

    def title(self) -> str:
        """The current page's title."""
        return self.page.title()

    def content(self) -> str:
        """The current page's full HTML source."""
        return self.page.content()

    @recorded()
    def set_default_timeout(self, timeout_ms: float) -> None:
        """Set the default timeout, in milliseconds, of the current page's actions and waits."""
        self.page.set_default_timeout(timeout_ms)

    @recorded()
    def set_default_navigation_timeout(self, timeout_ms: float) -> None:
        """Set the default timeout, in milliseconds, of the current page's navigations."""
        self.page.set_default_navigation_timeout(timeout_ms)

    # ----- finding -----------------------------------------------------

    def find_element(self, selector: str):
        """The first element matching ``selector`` in the current frame or page, or None; it does not wait."""
        web_runner_logger.info(f"playwright find_element: {selector}")
        return self._target.query_selector(selector)

    def find_elements(self, selector: str) -> list[Any]:
        """Every element matching ``selector`` in the current frame or page (an empty list when none)."""
        web_runner_logger.info(f"playwright find_elements: {selector}")
        return self._target.query_selector_all(selector)

    @recorded()
    def find_element_by(self, selector: str, by: str = "css selector") -> Any:
        """
        以原始 selector 找元素並設為目前元素
        Find by a raw selector (no saved ``TestObject``) and make the first match the current
        element; ``by`` is spelt as for ``WR_find_element_by`` (``css selector``, ``xpath``, ``id`` ...).
        It does not wait, and raises when nothing matches. The Playwright twin of ``WR_find_element_by``.
        """
        element = self._target.query_selector(raw_selector(selector, by))
        if element is None:
            raise PlaywrightBackendError(f"no element matches {by} {selector!r}")
        self.element_wrapper.current_element = element
        return element

    @recorded()
    def find_elements_by(self, selector: str, by: str = "css selector") -> list[Any]:
        """
        Find every match of a raw selector; they become the current element list (an empty list when
        nothing matches) and the current element stays as it is. The twin of ``WR_find_elements_by``.
        """
        elements = list(self._target.query_selector_all(raw_selector(selector, by)))
        self.element_wrapper.current_element_list = elements
        return elements

    def find_element_with_test_object_record(self, element_name: str):
        """
        Resolve ``element_name`` from ``test_object_record`` and capture the
        first matching element on ``element_wrapper``.
        """
        selector = selector_for_recorded_name(element_name)
        element = self._target.query_selector(selector)
        self.element_wrapper.current_element = element
        return element

    def find_elements_with_test_object_record(self, element_name: str):
        """Resolve ``element_name`` from ``test_object_record`` and capture every match (the first as current)."""
        selector = selector_for_recorded_name(element_name)
        elements = self._target.query_selector_all(selector)
        self.element_wrapper.current_element_list = list(elements)
        if elements:
            self.element_wrapper.current_element = elements[0]
        return elements
