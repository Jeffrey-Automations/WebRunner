"""A network entry whose status is not a number does not crash the tagger."""
from je_web_runner.utils.failure_auto_tag.tag import FailureBundle, heuristic_tags


def test_unreadable_status_is_skipped_and_the_rest_is_tagged():
    bundle = FailureBundle(network_errors=[
        {"url": "https://x.test/a", "status": "(failed)"},
        {"url": "https://x.test/b", "status": None},
        {"url": "https://x.test/c", "status": [503]},
        {"url": "https://x.test/d", "status": "503"},
    ])
    tags = heuristic_tags(bundle)
    assert [tag.name for tag in tags] == ["network-5xx"]
    assert "https://x.test/d" in tags[0].reason
    assert "https://x.test/a" not in tags[0].reason


def test_only_unreadable_statuses_give_no_network_tag():
    bundle = FailureBundle(exception_text="AssertionError", network_errors=[{"status": "net::ERR_FAILED"}])
    assert [tag.name for tag in heuristic_tags(bundle)] == ["assertion-failed"]
