"""
在背景執行緒上跑 ``socketserver`` 伺服器的啟動 / 停止流程。
Start / stop plumbing for the in-process servers that run a ``socketserver`` server
(``HTTPServer`` included) on a daemon thread: the mock services, the HAR replay
server, the visual review UI.
"""
from __future__ import annotations

import socketserver
import threading


class BackgroundServer:
    """Base of a server object that owns one ``socketserver`` server and its thread."""

    host: str
    port: int
    _server: socketserver.BaseServer | None = None
    _thread: threading.Thread | None = None

    def _serve_in_background(self, server: socketserver.TCPServer) -> None:
        """Serve ``server`` on a daemon thread, keep both, and store the bound port in ``port``."""
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._server = server
        self._thread = thread
        self.port = server.server_address[1]

    def stop(self) -> None:
        """Shut the server down and release its socket; a no-op when it is not running."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
