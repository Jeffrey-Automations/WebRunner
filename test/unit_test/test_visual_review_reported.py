"""``POST /accept`` overwrites a baseline, so a form posted by another site must be refused."""
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from je_web_runner.utils.visual_review.review_server import VisualReviewServer


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Report the 303 of an accepted snapshot instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post_accept(url: str, headers: dict) -> int:
    request = urllib.request.Request(url + "/accept", data=b"name=home.png", method="POST", headers=headers)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=5) as response:  # nosec B310 — loopback test server
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


@pytest.fixture(name="review")
def _review():
    with tempfile.TemporaryDirectory() as tmp:
        baseline, current = Path(tmp) / "baseline", Path(tmp) / "current"
        baseline.mkdir()
        current.mkdir()
        (baseline / "home.png").write_bytes(b"old")
        (current / "home.png").write_bytes(b"new")
        server = VisualReviewServer(str(baseline), str(current))
        url = server.start()
        try:
            yield server, url, baseline / "home.png"
        finally:
            server.stop()


@pytest.mark.parametrize("headers", [
    {"Origin": "https://evil.example"},
    {"Origin": "null"},
    {"Referer": "https://evil.example/attack.html"},
])
def test_a_cross_site_post_does_not_change_the_baseline(review, headers):
    server, url, baseline_file = review
    assert _post_accept(url, headers) == 403
    assert baseline_file.read_bytes() == b"old"
    assert server.accepted == []


def test_the_review_page_own_form_is_accepted(review):
    server, url, baseline_file = review
    assert _post_accept(url, {"Origin": url, "Referer": url + "/"}) == 303
    assert baseline_file.read_bytes() == b"new"
    assert server.accepted == ["home.png"]


def test_a_client_that_is_not_a_browser_is_accepted(review):
    _, url, baseline_file = review
    assert _post_accept(url, {}) == 303
    assert baseline_file.read_bytes() == b"new"
