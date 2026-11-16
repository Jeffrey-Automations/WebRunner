"""
The frontend HARVEST_SCRIPTs are bodies of a function (Selenium's ``execute_script``): the value has to
leave through a top-level ``return``, and ``arguments`` has to be read at the top level, not inside a
nested function. The payloads fed to the parsers below are what headless Chromium returned for them
(``test/integration_test/test_library_scripts_real_browser_frontend.py`` runs the scripts themselves).
"""
import re

import pytest

from je_web_runner.utils.pull_to_refresh import refresh
from je_web_runner.utils.rtl_layout_verify import verify as rtl
from je_web_runner.utils.viewport_audit import audit as viewport
from je_web_runner.utils.virtual_keyboard import keyboard
from je_web_runner.utils.wcag22_touch_target import touch

SCRIPTS = {
    "rtl_layout_verify": rtl.HARVEST_SCRIPT,
    "wcag22_touch_target": touch.HARVEST_SCRIPT,
    "pull_to_refresh": refresh.HARVEST_SCRIPT,
    "viewport_audit": viewport.HARVEST_SCRIPT,
    "virtual_keyboard": keyboard.HARVEST_SCRIPT,
}


def _top_level(script: str) -> str:
    """The script without the bodies of its functions (everything inside braces)."""
    kept, depth = [], 0
    for char in script:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif depth == 0:
            kept.append(char)
    return "".join(kept)


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_the_script_returns_its_value_at_the_top_level(name):
    assert re.search(r"^return\b", _top_level(SCRIPTS[name]), re.MULTILINE)


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_the_script_still_works_behind_a_return_prefix(name):
    # A newline or a comment right after the prefix would end the return statement there.
    assert SCRIPTS[name].startswith("arguments.harvested = ")
    statements = [
        line for line in _top_level(SCRIPTS[name]).splitlines()
        if line.strip() and not line.startswith("//")
    ]
    assert not statements[0].startswith("return"), "'return ' + script needs an expression first"
    assert statements[-1].startswith("return")


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_arguments_are_not_read_inside_a_nested_function(name):
    script = SCRIPTS[name]
    assert script.count("arguments") == _top_level(script).count("arguments")


def test_rtl_parser_accepts_what_chromium_returned():
    payload = {"documentDir": "rtl", "items": [{"selector": ".item", "boxes": [
        {"tag": "li", "id": "", "text": "one", "left": 1213.5, "right": 1236, "top": 20, "bottom": 38,
         "direction": "rtl", "writingMode": "horizontal-tb", "marginLeft": "8px", "marginRight": "0px",
         "paddingLeft": "0px", "paddingRight": "0px", "unicodeBidi": "isolate"},
    ]}]}
    snapshot = rtl.parse_snapshot(payload)
    assert snapshot.document_dir == "rtl"
    assert snapshot.selectors[".item"][0].margin_left == "8px"
