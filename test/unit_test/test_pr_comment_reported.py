"""The token is only ever sent to ``https://api.github.com/``."""
from unittest.mock import patch

import pytest

from je_web_runner.utils.pr_comment.poster import PrCommentError, _request

URLOPEN = "je_web_runner.utils.pr_comment.poster.urllib.request.urlopen"


@pytest.mark.parametrize("url", [
    "http://api.github.com/repos/o/r/issues/1/comments",
    "https://api.github.com.evil.example/repos/o/r",
    "https://api.github.com@evil.example/repos/o/r",
    "HTTP://api.github.com/repos/o/r",
])
def test_no_request_leaves_for_anything_but_https_github(url):
    with patch(URLOPEN) as urlopen_mock:
        with pytest.raises(PrCommentError, match="refusing"):
            _request("GET", url, token="ghp_secret")
    urlopen_mock.assert_not_called()
