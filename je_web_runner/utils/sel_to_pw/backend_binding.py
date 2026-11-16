"""
命令屬於哪個瀏覽器 backend
Which browser backend a registered command drives, decided by where it is implemented.

Both backends keep their browser in module-level singletons: Selenium in ``webdriver_wrapper_instance``,
the driver manager ``web_runner``, ``web_element_wrapper`` and ``selenium_bidi_events``; Playwright in
``playwright_wrapper_instance`` and ``playwright_element_wrapper``. A command belongs to a backend when its
callable reaches one of those objects:

* it is a bound method of one of them (``WR_to_url``, ``WR_element_click``, ``WR_route_mock`` …), or
* it is a function that refers to one of them: by a global name, by a name it imports when it runs, through
  a closure or a default argument, through an object that holds one (the Playwright recorder's script
  runner), or through a function of this package it calls (``WR_local_storage_set`` calls a helper that
  reads the driver). The search follows calls :data:`_DEPTH` levels deep.

Everything else is backend-neutral: variables, control flow, reports, HTTP, files, data.

So is a command that reaches both backends: it drives whichever browser is open, so it does not depend on
which backend a file is written for. That is how the adapter commands that read the page are neutral:
they take the browser from ``browser_driver`` (``utils/executor/_command_helpers.py``), which refers to
the Selenium wrapper and to the Playwright one and answers with the Selenium driver or with a stand-in
for it over the Playwright page. An adapter that needs what only Selenium has takes it from
``selenium_only_driver``, which refers to the Selenium wrapper alone, so that command stays Selenium's.

Nothing here is a list of command names, so a command added to the executor is classified without
touching this module.
"""
from __future__ import annotations

import inspect
from functools import lru_cache
from types import CodeType, FunctionType, ModuleType
from typing import Any, Callable, Iterator

SELENIUM = "selenium"
PLAYWRIGHT = "playwright"
NEUTRAL = "neutral"

_PACKAGE = "je_web_runner"
# How many calls deep a function is followed. The commands sit one or two helpers away from the browser
# (command -> helper that returns the driver); a deeper search reaches the executor's own plumbing.
_DEPTH = 3
_SINGLETON_NAMES = {
    "webdriver_wrapper_instance": SELENIUM,
    "web_runner": SELENIUM,
    "web_element_wrapper": SELENIUM,
    "selenium_bidi_events": SELENIUM,
    "playwright_wrapper_instance": PLAYWRIGHT,
    "playwright_element_wrapper": PLAYWRIGHT,
}


# The executor and the wrappers are imported when first needed: ``je_web_runner.api`` imports this package
# while the package ``je_web_runner`` itself is still being imported.
@lru_cache(maxsize=1)
def _singletons() -> dict[int, str]:
    """``id`` of every object that holds a browser -> its backend."""
    from je_web_runner.manager.webrunner_manager import web_runner
    from je_web_runner.utils.bidi.selenium_events import selenium_bidi_events
    from je_web_runner.webdriver.playwright_element_wrapper import playwright_element_wrapper
    from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
    from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

    selenium = (webdriver_wrapper_instance, web_runner, web_runner.webdriver_element,
                selenium_bidi_events, selenium_bidi_events.capture)
    playwright = (playwright_wrapper_instance, playwright_element_wrapper)
    return {**{id(item): SELENIUM for item in selenium}, **{id(item): PLAYWRIGHT for item in playwright}}


def _code_names(code: CodeType) -> Iterator[str]:
    """Every name ``code`` and the functions defined inside it refer to."""
    yield from code.co_names
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            yield from _code_names(constant)


def _object_backends(value: Any) -> set[str]:
    """The backends of ``value``: a singleton, or an object that holds one in an attribute."""
    singletons = _singletons()
    if id(value) in singletons:
        return {singletons[id(value)]}
    held = getattr(value, "__dict__", None)
    if isinstance(value, (ModuleType, type, FunctionType)) or not isinstance(held, dict):
        return set()
    return {singletons[id(item)] for item in held.values() if id(item) in singletons}


def _in_package(function: Any) -> bool:
    return isinstance(function, FunctionType) and str(function.__module__).startswith(_PACKAGE)


def _referenced(function: FunctionType) -> Iterator[tuple[str, Any]]:
    """``(name, value)`` for what ``function`` refers to: globals, attributes of package modules, closure."""
    names = set(_code_names(function.__code__))
    scope = function.__globals__
    modules = [scope[name] for name in names
               if isinstance(scope.get(name), ModuleType) and scope[name].__name__.startswith(_PACKAGE)]
    for name in names:
        if name in scope:
            yield name, scope[name]
            continue
        yield name, None
        for module in modules:
            if name in vars(module):
                yield name, vars(module)[name]
    for default in (*(function.__defaults__ or ()), *(function.__kwdefaults__ or {}).values()):
        yield "", default
    for cell in function.__closure__ or ():
        try:
            yield "", cell.cell_contents
        except ValueError:  # an empty cell: the variable is not bound yet
            continue


def _function_backends(function: FunctionType, depth: int, seen: set[int]) -> set[str]:
    """The backends ``function`` reaches, following the package functions it refers to."""
    if id(function) in seen:
        return set()
    seen.add(id(function))
    found: set[str] = set()
    for name, value in _referenced(function):
        if value is None:
            # A name that is not a global: the singleton may be imported inside the function.
            found.update({_SINGLETON_NAMES[name]} if name in _SINGLETON_NAMES else set())
            continue
        found.update(_object_backends(value))
        if depth > 0 and _in_package(value):
            found.update(_function_backends(value, depth - 1, seen))
    return found


def backends_reached(command: Callable[..., Any]) -> set[str]:
    """The backends the callable ``command`` reaches (empty: none)."""
    owner = getattr(command, "__self__", None)
    if owner is not None and not isinstance(owner, ModuleType):
        # A bound method drives what its object holds, and nothing else.
        return _object_backends(owner)
    function = inspect.unwrap(command)
    if not isinstance(function, FunctionType):
        return set()
    return _function_backends(function, _DEPTH, set())


@lru_cache(maxsize=1)
def _registered() -> dict[str, Callable[..., Any]]:
    from je_web_runner.utils.executor.action_executor import executor

    return {name: command for name, command in executor.event_dict.items() if isinstance(name, str)}


def registered_command(name: str) -> Callable[..., Any] | None:
    """The callable registered for ``name`` in the executor, or None."""
    return _registered().get(name)


@lru_cache(maxsize=None)
def backend_of(name: str) -> str:
    """
    ``"selenium"``, ``"playwright"`` or ``"neutral"`` for the command ``name``.

    A name the executor does not register is neutral: a plug-in command added at run time
    (``WR_add_package_to_executor``) cannot be told apart from a misspelt one here, and the linter reports
    the latter.
    """
    command = registered_command(name)
    if command is None:
        return NEUTRAL
    reached = backends_reached(command)
    return next(iter(reached)) if len(reached) == 1 else NEUTRAL
