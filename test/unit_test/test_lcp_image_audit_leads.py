"""lcp_image_audit: a preload of another file whose name ends the same way is not a preload of the LCP image."""
import pytest

from je_web_runner.utils.lcp_image_audit.audit import LcpCandidate, LcpImageAuditError, assert_lcp_preloaded


def _html(href: str) -> str:
    return f'<link rel="preload" href="{href}" as="image">'


@pytest.mark.parametrize("candidate, preloaded", [
    ("hero.jpg", "https://cdn.test/img/not-hero.jpg"),
    ("https://cdn.test/img/not-hero.jpg", "hero.jpg"),
    ("/img/hero.jpg", "/other/img/superhero.jpg"),
])
def test_a_different_file_with_the_same_ending_does_not_count(candidate, preloaded):
    with pytest.raises(LcpImageAuditError, match="not in preload set"):
        assert_lcp_preloaded(LcpCandidate(url=candidate), _html(preloaded))


@pytest.mark.parametrize("candidate, preloaded", [
    ("https://cdn.test/img/hero.jpg", "https://cdn.test/img/hero.jpg"),
    ("https://cdn.test/img/hero.jpg", "/img/hero.jpg"),
    ("https://cdn.test/img/hero.jpg", "img/hero.jpg"),
    ("/img/hero.jpg", "https://cdn.test/img/hero.jpg"),
])
def test_the_same_file_written_relative_or_absolute_counts(candidate, preloaded):
    assert_lcp_preloaded(LcpCandidate(url=candidate), _html(preloaded))
    assert_lcp_preloaded(LcpCandidate(url=candidate), "", link_header_urls=[preloaded])
