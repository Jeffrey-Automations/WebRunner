"""The dedup library reads action files in the shape the executor runs."""
import json
from pathlib import Path

import pytest

from je_web_runner.utils.test_dedup_ai.dedup import (
    ActionFile,
    TestDedupError,
    load_dir,
    semantic_clusters,
    stable_fingerprint,
    structural_clusters,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_loads_the_repository_action_files():
    smoke = ActionFile.load(EXAMPLES / "quick_smoke.json")
    assert smoke.fingerprint.startswith("WR_set_driver(")
    assert "WR_to_url(url=str[url])" in smoke.fingerprint
    suite = ActionFile.load(EXAMPLES / "flow" / "suite.json")
    assert suite.fingerprint.startswith("WR_for_each(")
    assert "WR_call_file(" in suite.fingerprint  # the loop body is part of the structure
    ci_smoke = ActionFile.load(EXAMPLES / "ci" / "smoke" / "smoke.json")
    assert ci_smoke.actions[0][0] == "WR_to_url"


def test_load_dir_reads_a_directory_of_real_files():
    files = load_dir(EXAMPLES / "flow" / "steps")
    assert [Path(file.path).name for file in files] == ["check_page.json", "greet.json"]
    assert all(file.fingerprint for file in files)


def test_fingerprint_ignores_the_data_of_list_actions():
    first = stable_fingerprint([["WR_to_url", {"url": "https://a.test"}], ["WR_quit_all"]])
    second = stable_fingerprint([["WR_to_url", {"url": "https://b.test"}], ["WR_quit_all"]])
    positional = stable_fingerprint([["WR_to_url", ["https://a.test"]], ["WR_quit_all"]])
    assert first == second
    assert first != positional
    assert first != stable_fingerprint([["WR_quit_all"]])


def test_fingerprint_sees_the_actions_inside_a_block():
    def loop(body):
        return [["WR_for_each", {"items": [1, 2], "do": body}]]
    assert stable_fingerprint(loop([["WR_element_click"]])) != stable_fingerprint(loop([["WR_element_clear"]]))


def test_structural_clusters_group_real_shaped_files(tmp_path):
    for name, url in (("a.json", "https://a.test"), ("b.json", "https://b.test")):
        (tmp_path / name).write_text(json.dumps({
            "meta": {"tags": ["x"]},
            "webdriver_wrapper": [["WR_to_url", {"url": url}], ["WR_element_click"]],
        }), encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps([["WR_quit_all"]]), encoding="utf-8")
    clusters = structural_clusters(load_dir(tmp_path))
    assert [[Path(member).name for member in cluster.members] for cluster in clusters] == [["a.json", "b.json"]]


def test_semantic_summary_names_the_commands_of_list_actions():
    seen = []

    def embedder(text):
        seen.append(text)
        return [1.0, 0.0]

    semantic_clusters([ActionFile.load(EXAMPLES / "quick_smoke.json")], embedder)
    assert "WR_to_url: https://example.com/" in seen[0]
    assert "WR_quit_all" in seen[0]


@pytest.mark.parametrize("bad", [[["WR_to_url", "https://x"]], [[]], [[1, {}]], [["WR_x", {}, {}, {}]]])
def test_misshapen_list_actions_are_rejected(bad):
    with pytest.raises(TestDedupError):
        stable_fingerprint(bad)


def test_an_object_without_actions_is_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"mode": "review"}), encoding="utf-8")
    with pytest.raises(TestDedupError):
        ActionFile.load(path)
