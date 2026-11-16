"""A path recorded in a HAR file is matched as written, also when it holds ``*``."""
import json

from je_web_runner.utils.har_replay.server import HarEntry, HarReplayServer, load_har


def _har(tmp_path, *urls):
    entries = [
        {"request": {"method": "GET", "url": url},
         "response": {"status": 200, "content": {"text": f"body {index}"}}}
        for index, url in enumerate(urls)
    ]
    path = tmp_path / "recorded.har"
    path.write_text(json.dumps({"log": {"entries": entries}}), encoding="utf-8")
    return load_har(path)


def test_a_recorded_star_is_not_a_wildcard(tmp_path):
    entries = _har(
        tmp_path,
        "https://api.test/items?fields=*",
        "https://api.test/items?fields=*&page=2",
        "https://api.test/items?fields=name",
    )
    server = HarReplayServer(entries)
    assert server.find("GET", "/items?fields=*").body == "body 0"
    assert server.find("GET", "/items?fields=*&page=2").body == "body 1"
    assert server.find("GET", "/items?fields=name").body == "body 2"
    assert server.find("GET", "/items?fields=other") is None


def test_hand_written_entries_keep_their_patterns():
    server = HarReplayServer([
        HarEntry(method="GET", path="/api/users/*", status=200, body="user"),
        HarEntry(method="POST", path="re:/api/v\\d+/items", status=201, body="item"),
    ])
    assert server.find("GET", "/api/users/42").body == "user"
    assert server.find("POST", "/api/v2/items").body == "item"
