"""
The frontend libraries' browser scripts, in a real headless Chromium.

Each ``HARVEST_SCRIPT`` is run with the semantics of Selenium's ``execute_script`` (the body of a
function that reads ``arguments[i]`` and returns its value), once as it is and once with ``"return "``
written in front of it, and the value goes to the library's own parser. The clickjacking probe page is
loaded with a target URL that tries to break out of the iframe's ``src``. It skips when Playwright or
its Chromium build is not installed.
"""
import pytest

pytest.importorskip("playwright.sync_api", reason="Playwright is optional")

from playwright.sync_api import sync_playwright  # noqa: E402

from je_web_runner.utils.clickjacking_audit.audit import build_probe_page  # noqa: E402
from je_web_runner.utils.driver_dispatch.selenium_script import as_function  # noqa: E402
from je_web_runner.utils.pull_to_refresh import refresh  # noqa: E402
from je_web_runner.utils.rtl_layout_verify import verify as rtl  # noqa: E402
from je_web_runner.utils.viewport_audit import audit as viewport  # noqa: E402
from je_web_runner.utils.virtual_keyboard import keyboard  # noqa: E402
from je_web_runner.utils.wcag22_touch_target import touch  # noqa: E402

_PAGE = """<html dir='rtl'><body style='padding:4px'>
<ul><li class='item' style='display:inline-block;margin-left:8px'>one</li>
<li class='item' style='display:inline-block'>two</li></ul>
<div id='scroller' data-pull-threshold='80'
     style='overscroll-behavior-y:contain;height:50px;overflow:auto'>feed</div>
<button style='width:10px;height:10px;padding:0;border:0;margin:0'>x</button
><button style='width:10px;height:10px;padding:0;border:0;margin:0'>y</button>
</body></html>"""


@pytest.fixture(name="page", scope="module")
def _page():
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as error:  # the browser build is not installed here
            pytest.skip(f"Chromium for Playwright is not available: {error!r}")
        page = browser.new_page()
        yield page
        browser.close()


def _both_ways(page, script, *arguments):
    """The script's value as ``execute_script(script)`` gives it, checked against the prefixed form."""
    page.set_content(_PAGE)
    value = page.evaluate(as_function(script), list(arguments))
    assert value is not None
    assert page.evaluate(as_function("return " + script.strip()), list(arguments)) == value
    assert page.evaluate(as_function("return " + script), list(arguments)) == value
    return value


def test_rtl_layout_verify(page):
    snapshot = rtl.parse_snapshot(_both_ways(page, rtl.HARVEST_SCRIPT, [".item", ".absent"]))
    rtl.assert_document_rtl(snapshot)
    assert [box.text for box in snapshot.selectors[".item"]] == ["one", "two"]
    assert snapshot.selectors[".absent"] == []
    rtl.assert_visual_order_reversed(snapshot, ".item")
    with pytest.raises(rtl.RtlLayoutVerifyError):
        rtl.assert_logical_properties(snapshot, ".item")


def test_rtl_layout_verify_without_selectors(page):
    assert rtl.parse_snapshot(_both_ways(page, rtl.HARVEST_SCRIPT)).selectors == {}


def test_wcag22_touch_target(page):
    targets = touch.parse_targets(_both_ways(page, touch.HARVEST_SCRIPT))
    assert [(target.tag, target.width, target.height) for target in targets] == [("button", 10.0, 10.0)] * 2
    assert sorted(violation.label for violation in touch.audit(targets)) == ["x", "y"]


def test_pull_to_refresh(page):
    snapshot = refresh.parse_snapshot(_both_ways(page, refresh.HARVEST_SCRIPT, "#scroller"))
    assert (snapshot.overscroll_y, snapshot.scroller_height, snapshot.pull_threshold_px) == ("contain", 50.0, 80.0)
    refresh.assert_overscroll_contained(snapshot)
    refresh.assert_threshold_sensible(snapshot)


def test_viewport_audit(page):
    snapshot = viewport.parse_safe_area(_both_ways(page, viewport.HARVEST_SCRIPT))
    assert snapshot.padding_top == "4px"
    viewport.assert_safe_area_padding(snapshot)


def test_virtual_keyboard(page):
    snapshot = keyboard.parse_snapshot(_both_ways(page, keyboard.HARVEST_SCRIPT))
    assert snapshot.viewport_width > 0 and snapshot.viewport_height > 0
    assert snapshot.scale == 1


def test_clickjacking_probe_page_keeps_a_hostile_url_in_the_src(page):
    hostile = 'https://victim.invalid/"></iframe><script>window.__pwned = 1</script><iframe src="'
    page.set_content(build_probe_page(hostile))
    assert page.evaluate("window.__pwned") is None
    assert page.evaluate("document.querySelectorAll('iframe').length") == 1
    assert page.evaluate("document.getElementById('probe').getAttribute('src')") == hostile
