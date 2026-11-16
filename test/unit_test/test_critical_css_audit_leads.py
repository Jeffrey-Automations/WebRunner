"""critical_css_audit: attributes are read as attributes, not as substrings of the tag."""
from je_web_runner.utils.critical_css_audit.audit import analyse


def _head(*links: str) -> str:
    return "<html><head>" + "".join(links) + "</head><body></body></html>"


def test_a_url_containing_disabled_is_still_render_blocking():
    report = analyse(_head('<link rel="stylesheet" href="/css/disabled-state.css">'))
    assert report.external_blocking == ["/css/disabled-state.css"]


def test_the_disabled_attribute_still_excludes_a_stylesheet():
    report = analyse(_head('<link rel="stylesheet" href="/a.css" disabled>',
                           '<link disabled="" rel="stylesheet" href="/b.css">'))
    assert report.external_blocking == []


def test_print_media_is_recognised_however_it_is_quoted():
    report = analyse(_head("<link rel='stylesheet' href='/p1.css' media='print'>",
                           '<link rel="stylesheet" href="/p2.css" media=print>',
                           '<link rel="stylesheet" href="/p3.css" media="PRINT">',
                           '<link rel="stylesheet" href="/screen.css" media="screen">'))
    assert report.external_blocking == ["/screen.css"]


def test_a_data_attribute_is_not_mistaken_for_media_or_href():
    report = analyse(_head('<link rel="stylesheet" data-media="print" href="/a.css">',
                           '<link data-href="/wrong.css" rel="stylesheet" href="/right.css">',
                           '<link rel="preload" as="style" data-href="/wrong.css" href="/right.css">'))
    assert report.external_blocking == ["/a.css", "/right.css"]
    assert report.preloaded == ["/right.css"]
