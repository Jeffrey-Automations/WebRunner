"""resource_hints_audit: crossorigin is an attribute, and a used URL must be the hinted file."""
from je_web_runner.utils.resource_hints_audit.hints import Hint, HintKind, find_unused_hints, parse_hints


def test_crossorigin_in_the_url_is_not_the_crossorigin_attribute():
    hints = parse_hints('<link rel="preload" as="font" href="/fonts/crossorigin-test.woff2">')
    assert hints[0].crossorigin is False


def test_the_crossorigin_attribute_in_each_form():
    hints = parse_hints(
        '<link rel="preload" as="font" href="/a.woff2" crossorigin>'
        '<link rel="preload" as="font" href="/b.woff2" crossorigin="anonymous">'
        "<link crossorigin='' rel=preconnect href=https://cdn.test>"
    )
    assert [h.crossorigin for h in hints] == [True, True, True]
    assert hints[2].href == "https://cdn.test"


def test_a_data_attribute_does_not_replace_the_real_one():
    hints = parse_hints('<link rel="preload" as="script" href="/app.js" data-href="/other.js" data-rel="x">')
    assert [(h.kind, h.href) for h in hints] == [(HintKind.PRELOAD, "/app.js")]


def test_a_different_file_with_the_same_ending_does_not_make_a_hint_used():
    hint = Hint(kind=HintKind.PRELOAD, href="/js/app.js", as_="script")
    assert find_unused_hints([hint], ["https://site.test/js/myapp.js"]) == [hint]
    short = Hint(kind=HintKind.PRELOAD, href="app.js", as_="script")
    assert find_unused_hints([short], ["https://site.test/js/webapp.js"]) == [short]


def test_the_same_file_relative_or_absolute_is_used():
    hint = Hint(kind=HintKind.PRELOAD, href="/js/app.js", as_="script")
    assert find_unused_hints([hint], ["https://site.test/js/app.js"]) == []
    absolute = Hint(kind=HintKind.PREFETCH, href="https://site.test/js/app.js")
    assert find_unused_hints([absolute], ["/js/app.js"]) == []
    assert find_unused_hints([absolute], ["js/app.js"]) == []
