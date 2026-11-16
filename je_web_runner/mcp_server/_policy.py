"""
MCP 呼叫端的安全政策 / What an MCP caller may do.

An MCP client is a model acting on text it read, so the server refuses the
commands that would let it widen its own powers, and can fence the file tools
to one directory:

* ``WR_add_package_to_executor`` / ``WR_add_package_to_callback_executor`` import
  any Python package and expose its functions, ``os`` and ``subprocess`` included;
* ``WR_set_allow_arbitrary_script`` would re-open a script gate the operator closed;
* ``WR_ac_run`` / ``WR_ac_run_actions`` and the native ``WR_ac_*`` commands drive or read
  the real mouse, keyboard and screen through AutoControl, outside the browser.

``WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS=1`` lifts the refusal. ``WEBRUNNER_MCP_ROOT``,
when set, is the only directory ``webrunner_run_action_files``,
``webrunner_compute_trend`` and ``webrunner_lint_action_file`` may read from, and the
only one an action list run through MCP may write files to (:func:`write_fence`).
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from je_web_runner.mcp_server._types import McpServerError
from je_web_runner.utils.executor._adapter_commands import NETWORK_COMMANDS, PROCESS_COMMANDS

UNSAFE_COMMANDS = frozenset({
    "WR_add_package_to_executor",
    "WR_add_package_to_callback_executor",
    "WR_set_allow_arbitrary_script",
    "WR_ac_run",
    "WR_ac_run_actions",
    "WR_ac_fill_native_file_dialog",
    "WR_ac_assert_image_on_screen",
    "WR_ac_click_element_native",
    "WR_ac_basic_auth",
    # Adapter commands that contact a host an argument names, or start a local process: a model must
    # not turn the server into a probe of other machines.
    *NETWORK_COMMANDS,
    *PROCESS_COMMANDS,
})
ALLOW_UNSAFE_ENV = "WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS"
ROOT_ENV = "WEBRUNNER_MCP_ROOT"
_TRUE = {"1", "true", "yes", "on"}


def denied_commands() -> frozenset[str]:
    """The commands an MCP call may not run: :data:`UNSAFE_COMMANDS` unless the operator lifted it."""
    if os.environ.get(ALLOW_UNSAFE_ENV, "").strip().lower() in _TRUE:
        return frozenset()
    return UNSAFE_COMMANDS


def checked_path(path: str) -> str:
    """
    檢查檔案路徑是否在 ``WEBRUNNER_MCP_ROOT`` 之內
    Return ``path`` when ``WEBRUNNER_MCP_ROOT`` is unset or ``path`` resolves inside it
    (``..`` and symlinks are resolved first); raise :class:`McpServerError` otherwise.
    """
    root = os.environ.get(ROOT_ENV)
    if not root:
        return path
    resolved_root = Path(root).resolve()
    resolved = Path(path).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise McpServerError(f"{path!r} is outside {ROOT_ENV} ({resolved_root})")
    return str(resolved)


# The directory writes are fenced to while an MCP run tool is running; None outside such a call.
_fenced_root: ContextVar[Path | None] = ContextVar("webrunner_mcp_fenced_root", default=None)
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_HOOK = {"installed": False}


def _opens_for_writing(mode: Any, flags: Any) -> bool:
    """Whether an ``open`` event is a write: by its text mode, or by its flags for ``os.open``."""
    if isinstance(mode, str):
        return any(character in mode for character in "wax+")
    return isinstance(flags, int) and bool(flags & _WRITE_FLAGS)


def _inside(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def _refuse_outside_writes(event: str, arguments: tuple[Any, ...]) -> None:
    """The audit hook: while a fence is up, an ``open`` for writing outside the root is a PermissionError."""
    root = _fenced_root.get()
    if root is None or event != "open" or len(arguments) < 3:
        return
    target, mode, flags = arguments[0], arguments[1], arguments[2]
    if not isinstance(target, (str, bytes, os.PathLike)) or not _opens_for_writing(mode, flags):
        return
    try:
        resolved = Path(os.fsdecode(target)).resolve()
    except (OSError, ValueError):
        return
    if _inside(resolved, root) or _inside(resolved, Path(tempfile.gettempdir()).resolve()):
        return
    # An OSError on purpose: code that treats a failed write as best effort (the import system writing
    # a .pyc, a log rollover) keeps working, and a command that must write fails with this message.
    raise PermissionError(f"{os.fsdecode(target)!r} is outside {ROOT_ENV} ({root}); an MCP run may not write there")


@contextlib.contextmanager
def write_fence() -> Iterator[None]:
    """
    限制 MCP 執行期間的寫檔位置
    While the block runs, refuse to open a file for writing outside ``WEBRUNNER_MCP_ROOT`` (after
    resolving ``..`` and symlinks). Without the variable nothing is fenced.

    It covers what Python opens in this process: reports, exports, screenshots saved by Selenium,
    recordings, ledgers. The system temporary directory stays writable, because libraries use it for
    scratch files. It is a fence for file arguments, not a sandbox: the browser itself is another process,
    and a download or a file Playwright's driver writes is not seen here.
    """
    root = os.environ.get(ROOT_ENV)
    if not root:
        yield
        return
    if not _HOOK["installed"]:
        # Once per process: an audit hook cannot be removed, so it stays and does nothing outside a fence.
        sys.addaudithook(_refuse_outside_writes)
        _HOOK["installed"] = True
    token = _fenced_root.set(Path(root).resolve())
    try:
        yield
    finally:
        _fenced_root.reset(token)
