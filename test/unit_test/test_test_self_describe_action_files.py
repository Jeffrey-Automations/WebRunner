"""The describer reads the action shape the executor runs, with the registered command names."""
import json
from pathlib import Path

import pytest

from je_web_runner.utils.test_self_describe.describe import SelfDescribeError, describe, summarise

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _load(*parts):
    return json.loads(EXAMPLES.joinpath(*parts).read_text(encoding="utf-8"))


def test_describes_the_quick_smoke_file():
    text = describe(_load("quick_smoke.json"), title="Quick smoke")
    assert text.splitlines()[0] == "# Quick smoke"
    assert "Given the user opens https://example.com/" in text
    assert "the user waits up to 1s" in text


def test_describes_a_document_with_meta_and_element_commands():
    text = describe(_load("flow", "steps", "greet.json"))
    assert 'the user types "${name}" into "#name"' in text
    assert 'the user clicks "#submit"' in text
    assert "performs a step" not in text


def test_describes_the_ci_smoke_assertions():
    summaries = summarise(_load("ci", "smoke", "smoke.json"))
    assert [summary.phase for summary in summaries] == ["Given", "Then", "When", "Then"]
    assert summaries[1].sentence == 'the page title should be / contain "WebRunner smoke"'
    assert summaries[3].sentence == '"#hello" should be / contain "text=It runs"'


def test_describes_the_actions_inside_blocks():
    text = describe(_load("flow", "suite.json"))
    assert "Given the user opens ${base}/index.html" in text
    assert 'the page title should be / contain "A title this page does not have"' in text


def test_positional_arguments_are_read():
    summaries = summarise([["WR_to_url", ["https://x.test"]], ["WR_find_element_by", ["#go"]], ["WR_element_click"]])
    assert summaries[0].sentence == "the user opens https://x.test"
    assert summaries[2].sentence == 'the user clicks "#go"'


def test_a_misshapen_action_is_rejected():
    with pytest.raises(SelfDescribeError):
        summarise([["WR_to_url", "https://x.test"]])
    with pytest.raises(SelfDescribeError):
        summarise({"meta": {}})
