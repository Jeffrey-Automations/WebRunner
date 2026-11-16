"""
其他伺服器的 console script 進入點
Console-script entry points for the servers that already start with ``python -m``:

``webrunner-mcp``           ``python -m je_web_runner.mcp_server``
``webrunner-lsp``           ``python -m je_web_runner.action_lsp``
``webrunner-issue-worker``  ``python -m je_web_runner.issue_worker``

Each imports its server only when called, so installing the scripts costs nothing at import time.
"""
from __future__ import annotations

import sys


def mcp_main() -> None:
    """Start the MCP stdio server."""
    from je_web_runner.mcp_server.server import serve_stdio
    serve_stdio()


def lsp_main() -> None:
    """Start the action-JSON language server on stdio, with newline translation off for its framing."""
    from je_web_runner.action_lsp.server import serve_stdio
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(newline="")
    serve_stdio()


def issue_worker_main() -> int:
    """Run the issue worker's command line and return its exit status."""
    from je_web_runner.issue_worker.__main__ import run
    return run()
