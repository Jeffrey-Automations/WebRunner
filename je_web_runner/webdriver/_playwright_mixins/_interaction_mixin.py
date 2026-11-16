"""頁面層級的元素操作、腳本、滑鼠鍵盤、frame / Page-level interaction."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError, recorded
from je_web_runner.webdriver._playwright_mixins._host import _PlaywrightHost


class _InteractionMixin(_PlaywrightHost):  # pylint: disable=too-many-public-methods  # one method per command
    """以 selector 直接操作元素、執行腳本、滑鼠與鍵盤、frame 查詢。

    Selector-based element shortcuts, script evaluation, mouse and keyboard,
    and frame lookup.
    """

    @recorded()
    def click(self, selector: str, **options: Any) -> None:
        """Click the first element matching ``selector`` in the current frame or page."""
        web_runner_logger.info(f"playwright click: {selector}")
        self._target.click(selector, **options)

    @recorded()
    def dblclick(self, selector: str, **options: Any) -> None:
        """Double-click the first element matching ``selector`` in the current frame or page."""
        self._target.dblclick(selector, **options)

    @recorded()
    def hover(self, selector: str, **options: Any) -> None:
        """Move the mouse over the first element matching ``selector``."""
        self._target.hover(selector, **options)

    @recorded()
    def fill(self, selector: str, value: str, **options: Any) -> None:
        """Replace the value of the field matching ``selector`` with ``value``."""
        web_runner_logger.info(f"playwright fill: {selector}")
        self._target.fill(selector, value, **options)

    @recorded()
    def type_text(self, selector: str, value: str, delay: float = 0, **options: Any) -> None:
        """Type ``value`` into the element matching ``selector`` key by key, ``delay`` milliseconds apart."""
        self._target.type(selector, value, delay=delay, **options)

    @recorded()
    def press(self, selector: str, key: str, **options: Any) -> None:
        """Focus the element matching ``selector`` and press ``key`` (``Enter``, ``Control+A`` …)."""
        self._target.press(selector, key, **options)

    @recorded()
    def check(self, selector: str, **options: Any) -> None:
        """Tick the checkbox or radio button matching ``selector``."""
        self._target.check(selector, **options)

    @recorded()
    def uncheck(self, selector: str, **options: Any) -> None:
        """Untick the checkbox matching ``selector``."""
        self._target.uncheck(selector, **options)

    @recorded()
    def select_option(self, selector: str, value: Any, **options: Any) -> list[str]:
        """Select ``value`` in the ``<select>`` matching ``selector``; returns the selected values."""
        return self._target.select_option(selector, value, **options)

    @recorded()
    def drag_and_drop(self, source_selector: str, target_selector: str, **options: Any) -> None:
        """Drag the element matching ``source_selector`` onto the one matching ``target_selector``."""
        self._target.drag_and_drop(source_selector, target_selector, **options)

    @recorded()
    def drag_and_drop_offset(self, selector: str, target_x: float, target_y: float) -> None:
        """Drag the element matching ``selector`` by ``(target_x, target_y)`` pixels from its centre."""
        box = self._target.locator(selector).bounding_box()
        if box is None:
            raise PlaywrightBackendError(f"element {selector!r} is not visible")
        start_x, start_y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(start_x, start_y)
        self.page.mouse.down()
        self.page.mouse.move(start_x + target_x, start_y + target_y, steps=5)
        self.page.mouse.up()

    @recorded()
    def download(self, selector: str, save_to: str) -> str:
        """
        點擊並儲存它觸發的下載
        Click ``selector``, wait for the download it starts, and save it to ``save_to``:
        that file, or inside that directory under the name the site suggested.
        """
        with self.page.expect_download() as download_info:
            self._target.click(selector)
        download = download_info.value
        target = Path(save_to)
        if target.is_dir():
            target = target / download.suggested_filename
        download.save_as(str(target))
        return str(target)

    @recorded()
    def scroll(self, scroll_x: float, scroll_y: float) -> None:
        """Scroll by ``(scroll_x, scroll_y)`` pixels with the mouse wheel."""
        self.page.mouse.wheel(scroll_x, scroll_y)

    @recorded()
    def scroll_to_top(self) -> None:
        """Scroll the page to its top (``window.scrollTo(0, 0)``)."""
        self.page.evaluate("window.scrollTo(0, 0)")

    @recorded()
    def scroll_to_bottom(self) -> None:
        """Scroll the page to the bottom of ``document.body``."""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    # ----- script ------------------------------------------------------

    @recorded()
    def evaluate(self, expression: str, arg: Any = None):
        """Run JavaScript ``expression`` in the current frame or page (with ``arg`` if given) and return its value."""
        return self._target.evaluate(expression, arg) if arg is not None else self._target.evaluate(expression)

    def evaluate_handle(self, expression: str, arg: Any = None):
        """Like :meth:`evaluate`, but returns a handle to the result instead of its value."""
        if arg is not None:
            return self._target.evaluate_handle(expression, arg)
        return self._target.evaluate_handle(expression)

    @recorded()
    def mouse_click(self, x: float, y: float, button: str = "left", click_count: int = 1) -> None:
        """Click at page coordinates ``(x, y)`` with ``button``, ``click_count`` times."""
        self.page.mouse.click(x, y, button=button, click_count=click_count)

    @recorded()
    def mouse_move(self, x: float, y: float, steps: int = 1) -> None:
        """Move the mouse to page coordinates ``(x, y)`` in ``steps`` intermediate moves."""
        self.page.mouse.move(x, y, steps=steps)

    @recorded()
    def mouse_down(self, button: str = "left", click_count: int = 1) -> None:
        """Press ``button`` at the current mouse position and hold it."""
        self.page.mouse.down(button=button, click_count=click_count)

    @recorded()
    def mouse_up(self, button: str = "left", click_count: int = 1) -> None:
        """Release ``button`` at the current mouse position."""
        self.page.mouse.up(button=button, click_count=click_count)

    @recorded()
    def keyboard_press(self, key: str) -> None:
        """Press and release ``key`` on the page (``Enter``, ``Control+A`` …)."""
        self.page.keyboard.press(key)

    @recorded()
    def keyboard_type(self, text: str, delay: float = 0) -> None:
        """Type ``text`` into the focused element, ``delay`` milliseconds between keys."""
        self.page.keyboard.type(text, delay=delay)

    @recorded()
    def keyboard_down(self, key: str) -> None:
        """Hold ``key`` down until :meth:`keyboard_up`."""
        self.page.keyboard.down(key)

    @recorded()
    def keyboard_up(self, key: str) -> None:
        """Release ``key``."""
        self.page.keyboard.up(key)

    # ----- frames ------------------------------------------------------

    def frames(self) -> list[Any]:
        """A list of every frame attached to the current page."""
        return list(self.page.frames)

    def main_frame(self) -> Any:
        """The current page's top-level frame."""
        return self.page.main_frame
