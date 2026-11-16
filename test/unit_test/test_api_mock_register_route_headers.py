"""``register_route`` passes response headers and content type on to the global router."""
import pytest

from je_web_runner.utils.api_mock.router import global_router, register_route, reset_global_router


@pytest.fixture(autouse=True)
def _clean_router():
    reset_global_router()
    yield
    reset_global_router()


def test_headers_and_content_type_reach_the_response():
    register_route(
        "GET", "https://api.test/page", body="<h1>hi</h1>",
        headers={"access-control-allow-origin": "*"}, content_type="text/html",
    )
    payload = global_router().match("GET", "https://api.test/page").response.to_payload()
    assert payload["headers"] == {"access-control-allow-origin": "*", "content-type": "text/html"}
    assert payload["body"] == "<h1>hi</h1>"


def test_defaults_are_unchanged():
    route = register_route("GET", "https://api.test/items", body={"items": []}, status=201, times=2)
    assert route.response.to_payload() == {
        "status": 201, "headers": {"content-type": "application/json"}, "body": '{"items": []}',
    }
    assert route.times == 2
