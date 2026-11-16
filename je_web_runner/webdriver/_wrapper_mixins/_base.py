"""WebDriverWrapper mixin 共用的型別宣告 / Typing-only base shared by the WebDriverWrapper mixins.

``WebDriverWrapper`` is assembled from mixins that read attributes the final class sets
(``current_webdriver``, ``_action_chain``) and call a method another mixin defines
(``execute_cdp_cmd``). This base tells the type checker about them. It holds declarations
only: at runtime the class body is empty, so it adds no attribute, method or behaviour.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from selenium.webdriver import ActionChains
    from selenium.webdriver.remote.webdriver import WebDriver


class _WrapperBase:
    """Declares what the mixins share; the real attributes live on ``WebDriverWrapper``.

    ``current_webdriver`` and ``_action_chain`` are plain instance attributes that
    ``WebDriverWrapper`` sets to ``None`` while no driver is live (before ``set_driver``,
    after ``quit``). They are declared as properties here only to give reads and writes
    different types: a write accepts ``None``; a read is typed as the live object, because
    every wrapper method uses the driver inside its own ``try`` (or ``@recorded``) and lets
    the ``AttributeError`` raised on ``None`` be caught and recorded as that action's
    failure. Code that must tell "no driver" apart still compares with ``is None``.
    """

    if TYPE_CHECKING:
        @property
        def current_webdriver(self) -> WebDriver:
            """The active Selenium driver (``None`` at runtime while no driver is live)."""

        @current_webdriver.setter
        def current_webdriver(self, driver: WebDriver | None) -> None:
            """Set by ``set_driver`` / ``set_active_driver`` / ``quit``."""

        @property
        def _action_chain(self) -> ActionChains:
            """The ActionChains bound to the active driver (``None`` while no driver is live)."""

        @_action_chain.setter
        def _action_chain(self, chain: ActionChains | None) -> None:
            """Rebuilt whenever the active driver changes."""

        # Defined by ``_ScriptingMixin`` as ``execute_cdp_cmd(cmd, cmd_args=None)``; the other
        # mixins call it. Declared as an attribute, not a stub method, so no linter reads a
        # body-less method as "returns None" or "abstract".
        execute_cdp_cmd: Callable[..., Any]
