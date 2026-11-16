"""test_dup_dry compares real action lists (``["WR_name", {...}]``), not only step objects."""
from je_web_runner.utils.test_dup_dry.dedup import DupSpec, find_duplicates, find_prefix_overlap

LOGIN = [
    ["WR_to_url", {"url": "https://shop.example/login"}],
    ["WR_find_element_by", {"selector": "#user"}],
    ["WR_input_to_element", {"input_value": "alice"}],
    ["WR_find_element_by", {"selector": "#submit"}],
    ["WR_element_click"],
]
SEARCH = [
    ["WR_to_url", ["https://shop.example/search"]],
    ["WR_find_element_by", {"selector": "#q"}],
    ["WR_input_to_element", {"input_value": "shoes"}],
]


def test_different_real_action_lists_are_not_duplicates():
    assert find_duplicates([DupSpec("login", LOGIN), DupSpec("search", SEARCH)]) == []


def test_same_real_action_lists_are_duplicates():
    groups = find_duplicates([DupSpec("login", LOGIN), DupSpec("login_copy", list(LOGIN)), DupSpec("search", SEARCH)])
    assert [group.test_names for group in groups] == [["login", "login_copy"]]


def test_a_positional_target_counts():
    by_keyword = [["WR_to_url", {"url": "https://shop.example/search"}]]
    by_position = [["WR_to_url", ["https://shop.example/search"]]]
    other = [["WR_to_url", ["https://shop.example/cart"]]]
    groups = find_duplicates([DupSpec("a", by_keyword), DupSpec("b", by_position), DupSpec("c", other)])
    assert [group.test_names for group in groups] == [["a", "b"]]


def test_prefix_overlap_of_real_action_lists():
    checkout = LOGIN + [["WR_to_url", {"url": "https://shop.example/cart"}]]
    profile = LOGIN + [["WR_to_url", {"url": "https://shop.example/me"}]]
    overlaps = find_prefix_overlap([DupSpec("checkout", checkout), DupSpec("profile", profile)], min_prefix=5)
    assert [(o.a, o.b, o.common_prefix_len) for o in overlaps] == [("checkout", "profile", 5)]
