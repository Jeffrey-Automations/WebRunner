"""The receiver binds a system-chosen port itself, and compares methods without case."""
import socket
from urllib.request import Request, urlopen

import pytest

from je_web_runner.utils.webhook_receiver.receiver import (
    WebhookReceiverError,
    WebhookServer,
    assert_received_path,
)


def _post(url):
    # nosec B310 — talks only to the local WebhookServer (loopback port).
    with urlopen(Request(url, data=b"{}", method="POST"), timeout=5) as response:  # nosec B310
        return response.status


def test_a_port_taken_after_construction_does_not_stop_the_server():
    server = WebhookServer()
    picked = server._port  # pylint: disable=protected-access  # the port the constructor reserved, if any
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as squatter:
        squatter.bind(("127.0.0.1", picked))
        squatter.listen()
        with server:
            assert _post(server.base_url + "/hook") == 200
            assert len(server.received()) == 1
            assert not server.base_url.endswith(f":{squatter.getsockname()[1]}")


def test_base_url_of_a_system_chosen_port_is_known_once_started():
    server = WebhookServer()
    with pytest.raises(WebhookReceiverError):
        _ = server.base_url
    with server:
        assert int(server.base_url.rsplit(":", 1)[1]) > 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        fixed = probe.getsockname()[1]
    assert WebhookServer(port=fixed).base_url == f"http://127.0.0.1:{fixed}"


def test_a_stopped_server_can_start_again_on_a_new_port():
    server = WebhookServer()
    with server:
        assert _post(server.base_url + "/a") == 200
    with server:
        assert _post(server.base_url + "/b") == 200
    assert [request.path for request in server.received()] == ["/a", "/b"]


def test_method_filter_ignores_case():
    with WebhookServer() as server:
        _post(server.base_url + "/hook")
        assert assert_received_path(server, "/hook", method="post") == 1
        assert assert_received_path(server, "/hook", method="POST") == 1
        with pytest.raises(WebhookReceiverError):
            assert_received_path(server, "/hook", method="get")
