"""
把 Selenium 的腳本主體包成 Playwright 可呼叫的函式
A Selenium script as a function Playwright can call.

Selenium's ``execute_script`` takes the body of a function: it reads its arguments from ``arguments[i]`` and
gives its value with ``return``. ``execute_async_script`` adds a callback as the last argument, and the
script's value is what it calls that callback with. Playwright's ``evaluate`` takes a function (or an
expression) and one argument. :func:`as_function` and :func:`as_async_function` wrap a body so that the one
argument is the list of the Selenium arguments, and ``arguments`` inside the body is what it was.

Both the ``WR_execute_script`` translation and the Playwright stand-in for a Selenium driver
(:mod:`~je_web_runner.utils.driver_dispatch.playwright_driver`) use this, so a script means the same in an
action file as in a command that runs one.
"""
from __future__ import annotations

_BODY = "(function () {\n%s\n})"


def as_function(body: str) -> str:
    """The function for ``evaluate(function, list_of_arguments)`` that runs the ``execute_script`` body."""
    return f"(args) => {_BODY % body}.apply(null, args)"


def as_async_function(body: str) -> str:
    """
    The function for ``evaluate(function, list_of_arguments)`` that runs the ``execute_async_script`` body:
    it returns a promise of what the body passes to its callback, which ``evaluate`` waits for.
    """
    return f"(args) => new Promise((resolve) => {_BODY % body}.apply(null, [...args, resolve]))"
