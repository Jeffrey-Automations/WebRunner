"""Mixin 共用的型別宣告（僅供型別檢查）/ What every PlaywrightWrapper mixin may use, for type checkers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from je_web_runner.webdriver.playwright_element_wrapper import PlaywrightElementWrapper


class _HostDeclarations:
    """The attributes and methods the mixins use on each other and on ``PlaywrightWrapper``.

    ``PlaywrightWrapper`` is composed from mixins, and each one reads state that
    ``PlaywrightWrapper._reset_state`` sets and calls methods another mixin defines.
    This lists those names with their types and nothing else; it is never a base
    class at runtime (see ``_PlaywrightHost``). Being a protocol, a type checker also
    reports ``PlaywrightWrapper`` if a method listed here is no longer defined.
    Playwright objects are ``Any`` because Playwright is an optional dependency that
    is never imported here.
    """

    # Set by PlaywrightWrapper.__init__.
    _playwright: Any
    _sessions: list[dict[str, Any] | None]
    _session_index: int
    element_wrapper: PlaywrightElementWrapper

    # Set by PlaywrightWrapper._reset_state (one browser session; see _SESSION_FIELDS).
    _browser: Any
    _context: Any
    _pages: list[Any]
    _page_index: int
    _context_options: dict[str, Any]
    _emulation_keys: set[str]
    _fixed_context: bool
    _trace_options: dict[str, Any] | None
    _init_scripts: list[str]
    _blocked_urls: list[Any]
    _cache_route: Any
    _frame: Any
    _dialog_policy: tuple[str, str | None] | None
    _dialog_pages: list[Any]
    _last_dialog: dict[str, Any] | None

    # ----- PlaywrightWrapper ---------------------------------------------

    @property
    def page(self) -> Any:
        """The current page."""

    @property
    def context(self) -> Any:
        """The current browser context."""

    @property
    def browser(self) -> Any:
        """The current browser."""

    def launch(
        self,
        browser: str = "chromium",
        headless: bool = True,
        record_har_path: str | None = None,
        record_har_content: str = "omit",
        context_options: dict[str, Any] | None = None,
        **launch_options: Any,
    ) -> None:
        """Launch a browser and open its first context and page."""

    def _reset_state(self) -> None:
        """Forget the browser, context, pages and every setting."""

    def _register_session(self) -> None:
        """Count the first browser as session 0."""

    def _browser_type(self, browser: str) -> Any:
        """The runtime's ``chromium`` / ``firefox`` / ``webkit``."""

    def _stop_runtime(self) -> None:
        """Stop the Playwright runtime."""

    # PlaywrightWrapper._open_context(storage_state=None): creates a context with the merged
    # options. Declared as an attribute because pylint reads a body-less method as one that
    # returns None and then reports every ``self._context = self._open_context()``.
    _open_context: Callable[..., Any]

    # ----- _ContextMixin -------------------------------------------------

    def _rebuild_context(self) -> None:
        """Close the context and open one with the current options."""

    def _reapply_context_setup(self, context: Any) -> None:
        """Give a freshly opened context the init scripts and URL blocks set so far."""

    # ----- _PageMixin ----------------------------------------------------

    def _reset_pages(self, page: Any) -> None:
        """Make ``page`` the only, current page."""

    def _track_page(self, page: Any) -> None:
        """Remember a page the context opened."""

    # ----- _RecordingMixin -----------------------------------------------

    def _restart_tracing(self, context: Any) -> None:
        """Continue tracing on a freshly opened context."""

    # ----- _ScopeMixin ---------------------------------------------------

    @property
    def _target(self) -> Any:
        """The current frame, or the page when no frame is selected."""

    def _watch_dialogs(self, page: Any) -> None:
        """Apply the dialog policy to ``page``."""

    # ----- _SessionsMixin ------------------------------------------------

    def _restore(self, state: dict[str, Any]) -> None:
        """Load a parked browser session."""

    def _close_current(self) -> None:
        """Close the current browser, or its adopted context."""


if not TYPE_CHECKING:
    class _PlaywrightHost:  # pylint: disable=too-few-public-methods
        """Runtime base of every mixin: empty, so only the real attributes and methods exist."""
else:
    _PlaywrightHost = _HostDeclarations
