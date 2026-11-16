"""The probe page must keep a hostile target URL inside the iframe's ``src`` attribute."""
from html.parser import HTMLParser

from je_web_runner.utils.clickjacking_audit.audit import build_probe_page


class _Tags(HTMLParser):
    """Collect the start tags of a document with their attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_probe_page_escapes_the_target_url():
    hostile = 'https://victim.example/"></iframe><script>window.__pwned = 1</script><iframe src="'
    parser = _Tags()
    parser.feed(build_probe_page(hostile))
    names = [name for name, _ in parser.tags]
    assert names.count("script") == 1
    assert names.count("iframe") == 1
    assert dict(parser.tags)["iframe"]["src"] == hostile


def test_probe_page_keeps_a_plain_url_with_a_query():
    parser = _Tags()
    parser.feed(build_probe_page("https://victim.example/a?b=1&c=2"))
    assert dict(parser.tags)["iframe"]["src"] == "https://victim.example/a?b=1&c=2"
