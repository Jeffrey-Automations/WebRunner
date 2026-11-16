"""test_categorizer reads real action files: ``["WR_name", {...}]`` lists, blocks and object documents."""
import json

from je_web_runner.utils.test_categorizer.categorizer import categorize_actions, categorize_file

SMOKE = [
    ["WR_to_url", {"url": "https://shop.example/"}],
    ["WR_assert_var", {"name": "title", "expected": "Shop"}],
]


def test_list_actions_are_tagged():
    assert categorize_actions(SMOKE) == ["smoke"]
    assert categorize_actions([["WR_http_get", {"url": "https://api.example/health"}]]) == ["api"]


def test_an_action_inside_a_block_is_seen():
    actions = [["WR_if", {"condition": {"var": "slow"}, "then": [["WR_lighthouse_run", {"url": "https://x"}]]}]]
    assert categorize_actions(actions) == ["perf"]


def test_the_object_form_is_still_tagged():
    assert categorize_actions([{"WR_to_url": ["https://x"]}, {"WR_assert_title": ["Shop"]}]) == ["smoke"]


def test_an_object_document_file_is_read(tmp_path):
    path = tmp_path / "smoke.json"
    path.write_text(json.dumps({"meta": {"tags": ["x"]}, "webdriver_wrapper": SMOKE}), encoding="utf-8")
    assignment = categorize_file(path)
    assert (assignment.tags, assignment.action_count) == (["smoke"], 2)
