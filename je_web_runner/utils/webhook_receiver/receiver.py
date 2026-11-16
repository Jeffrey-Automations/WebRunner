"""
跑一個臨時 HTTP server,接 app 寄出的 webhook 並做斷言。
Common scenarios: payment-provider callback, third-party SaaS event
notification, your own backend → backend webhook. End-to-end tests need
to *receive* those calls before declaring success.

Uses stdlib ``http.server`` so there's no extra dependency. Runs in a
background thread, picks a free port automatically, and exposes:

* :class:`WebhookServer` — start/stop context manager
* :class:`ReceivedRequest` — captured request record
* assertion helpers: ``received_path``, ``received_with_header``,
  ``received_json_matching``
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class WebhookReceiverError(WebRunnerException):
    """Raised on server start failure or failed assertion."""


# ---------- data --------------------------------------------------------

@dataclass
class ReceivedRequest:
    """One inbound HTTP request."""

    method: str
    path: str
    query: dict[str, list[str]] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    timestamp: float = field(default_factory=time.time)

    def body_text(self, encoding: str = "utf-8") -> str:
        """Return the body decoded as text, with undecodable bytes replaced."""
        return self.body.decode(encoding, errors="replace")

    def body_json(self) -> Any:
        """Return the body parsed as JSON; raises ``WebhookReceiverError`` when it is not JSON."""
        try:
            return json.loads(self.body_text())
        except ValueError as error:
            raise WebhookReceiverError(
                f"body is not JSON ({error}): {self.body[:80]!r}"
            ) from error

    def to_dict(self) -> dict[str, Any]:
        """Return the request as a plain dict, with the body decoded as UTF-8 text."""
        out = asdict(self)
        out["body"] = self.body.decode("utf-8", errors="replace")
        return out


# ---------- handler factory --------------------------------------------

ResponseFn = Callable[[ReceivedRequest], dict[str, Any] | None]


def _response_for(request: ReceivedRequest, response_fn: ResponseFn | None) -> dict[str, Any]:
    """The default 200 response, overridden by whatever ``response_fn`` returns for ``request``."""
    response: dict[str, Any] = {
        "status": 200,
        "headers": {"Content-Type": "application/json"},
        "body": b'{"received":true}',
    }
    if response_fn is not None:
        try:
            override = response_fn(request)
        except Exception as error:  # pylint: disable=broad-exception-caught  # logged; the default is sent
            web_runner_logger.warning(f"response_fn raised: {error!r}")
            override = None
        if override:
            response.update(override)
            body = response.get("body")
            if isinstance(body, str):
                response["body"] = body.encode("utf-8")
    return response


class _ResponseWriter(BaseHTTPRequestHandler):
    """The response plumbing every webhook handler shares; it holds no server state."""

    protocol_version = "HTTP/1.1"

    # Parameter names match the BaseHTTPRequestHandler signature.
    def log_message(self, format: str, *args: Any) -> None:  # pylint: disable=redefined-builtin
        web_runner_logger.debug("webhook %s", format % args)

    def _respond(self, response: dict[str, Any]) -> None:
        self.send_response(int(response["status"]))
        response_body = response.get("body") or b""
        if isinstance(response_body, str):
            response_body = response_body.encode("utf-8")
        for name, value in (response.get("headers") or {}).items():
            self.send_header(str(name), str(value))
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        if response_body:
            self.wfile.write(response_body)


def _build_handler(
    received: list[ReceivedRequest],
    lock: threading.Lock,
    response_fn: ResponseFn | None,
) -> type:
    class WebhookHandler(_ResponseWriter):
        """Records each request of one server and answers it."""

        def _handle(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
            url_parts = urlsplit(self.path)
            request = ReceivedRequest(
                method=method,
                path=url_parts.path,
                query=parse_qs(url_parts.query),
                headers=dict(self.headers.items()),
                body=body,
            )
            with lock:
                received.append(request)
            self._respond(_response_for(request, response_fn))

        def do_GET(self) -> None:  # pylint: disable=invalid-name  # stdlib HTTP verb dispatch contract
            """Record and answer a GET request."""
            self._handle("GET")

        def do_POST(self) -> None:  # pylint: disable=invalid-name  # stdlib HTTP verb dispatch contract
            """Record and answer a POST request."""
            self._handle("POST")

        def do_PUT(self) -> None:  # pylint: disable=invalid-name  # stdlib HTTP verb dispatch contract
            """Record and answer a PUT request."""
            self._handle("PUT")

        def do_PATCH(self) -> None:  # pylint: disable=invalid-name  # stdlib HTTP verb dispatch contract
            """Record and answer a PATCH request."""
            self._handle("PATCH")

        def do_DELETE(self) -> None:  # pylint: disable=invalid-name  # stdlib HTTP verb dispatch contract
            """Record and answer a DELETE request."""
            self._handle("DELETE")

        def do_OPTIONS(self) -> None:  # pylint: disable=invalid-name  # stdlib HTTP verb dispatch contract
            """Record and answer an OPTIONS request."""
            self._handle("OPTIONS")

    return WebhookHandler


# ---------- server ------------------------------------------------------

class WebhookServer:  # pylint: disable=too-many-instance-attributes  # settings plus server state
    """Threaded HTTP server. Use as a context manager."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int | None = None,
        response_fn: ResponseFn | None = None,
    ) -> None:
        if not isinstance(host, str) or not host:
            raise WebhookReceiverError("host must be non-empty string")
        if port is not None and (port <= 0 or port >= 65536):
            raise WebhookReceiverError("port must be a valid TCP port")
        self._host = host
        # Without a port the system picks one when the server binds, in ``start``. Picking it here
        # and binding later would leave a moment in which another process can take it.
        self._system_port = port is None
        self._port = port or 0
        self._response_fn = response_fn
        self._received: list[ReceivedRequest] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        """The ``http://host:port`` URL the app under test should send its webhooks to.

        Raises ``WebhookReceiverError`` before ``start`` when no port was given: the system
        chooses the port when the server binds.
        """
        if not self._port:
            raise WebhookReceiverError("base_url is known once the server is started (no port was given)")
        # S5332 ok: this is a localhost test-fixture HTTP server with random
        # port, intentionally plain HTTP so callers can hit it without certs.
        return f"http://{self._host}:{self._port}"  # NOSONAR S5332 — intentional plain HTTP

    def start(self) -> WebhookServer:
        """Bind the server and serve from a daemon thread; returns ``self``.
        Raises ``WebhookReceiverError`` when it is already started or the address cannot be bound.
        """
        if self._server is not None:
            raise WebhookReceiverError("server already started")
        handler_cls = _build_handler(
            self._received, self._lock, self._response_fn,
        )
        port = 0 if self._system_port else self._port
        try:
            self._server = ThreadingHTTPServer((self._host, port), handler_cls)
        except OSError as error:
            raise WebhookReceiverError(
                f"failed to bind {self._host}:{port}: {error}"
            ) from error
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="wr-webhook",
        )
        self._thread.start()
        web_runner_logger.info(f"webhook_receiver listening on {self.base_url}")
        return self

    def stop(self) -> None:
        """Shut the server down and wait up to 5 seconds for its thread; does nothing when not started."""
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self) -> WebhookServer:
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def received(self) -> list[ReceivedRequest]:
        """Return a copy of the requests received so far, in arrival order."""
        with self._lock:
            return list(self._received)

    def clear(self) -> None:
        """Forget the requests received so far."""
        with self._lock:
            self._received.clear()

    def wait_for(
        self,
        predicate: Callable[[ReceivedRequest], bool],
        *,
        timeout: float = 5.0,
        interval: float = 0.05,
    ) -> ReceivedRequest:
        """Poll for a request matching ``predicate`` within ``timeout`` seconds."""
        if timeout <= 0:
            raise WebhookReceiverError("timeout must be > 0")
        if interval <= 0:
            raise WebhookReceiverError("interval must be > 0")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for request in self.received():
                try:
                    if predicate(request):
                        return request
                except Exception as error:  # pylint: disable=broad-exception-caught  # logged; polling goes on
                    web_runner_logger.warning(f"wait_for predicate raised: {error!r}")
            time.sleep(interval)
        raise WebhookReceiverError(
            f"no webhook matched within {timeout}s "
            f"(received {len(self.received())} requests)"
        )


# ---------- assertions -------------------------------------------------

def assert_received_path(
    server: WebhookServer,
    path: str,
    *,
    method: str | None = None,
    minimum: int = 1,
) -> int:
    """Assert at least ``minimum`` requests hit ``path``; ``method`` (any case) narrows them to one HTTP method."""
    if not isinstance(path, str) or not path:
        raise WebhookReceiverError("path must be non-empty string")
    matches = [
        r for r in server.received()
        if r.path == path and (method is None or r.method.upper() == method.upper())
    ]
    if len(matches) < minimum:
        raise WebhookReceiverError(
            f"expected >= {minimum} requests to {path!r}, got {len(matches)}"
        )
    return len(matches)


def assert_received_with_header(
    server: WebhookServer,
    header: str,
    value: str,
) -> ReceivedRequest:
    """Assert at least one request had ``header: value``."""
    if not header:
        raise WebhookReceiverError("header must be non-empty string")
    header_lower = header.lower()
    for request in server.received():
        for name, val in request.headers.items():
            if name.lower() == header_lower and val == value:
                return request
    raise WebhookReceiverError(
        f"no request had header {header}={value!r}"
    )


def assert_received_json_matching(
    server: WebhookServer,
    predicate: Callable[[Any], bool],
    *,
    description: str = "json predicate",
) -> ReceivedRequest:
    """Assert at least one JSON body satisfies ``predicate``."""
    for request in server.received():
        try:
            payload = request.body_json()
        except WebhookReceiverError:
            continue
        try:
            if predicate(payload):
                return request
        except Exception as error:  # pylint: disable=broad-exception-caught  # user predicate; logged, skipped
            web_runner_logger.warning(f"webhook json predicate raised: {error!r}")
    raise WebhookReceiverError(
        f"no JSON webhook matched: {description}"
    )
