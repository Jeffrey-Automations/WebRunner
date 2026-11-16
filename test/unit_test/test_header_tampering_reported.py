"""Header names are case-insensitive: a rule must reach the header however the request spells it."""
from je_web_runner.utils.header_tampering.tamper import HeaderRule, apply_to_request_headers

URL = "https://app.example/api"


def test_remove_reaches_a_lower_case_header():
    rules = [HeaderRule(name="strip", header="Authorization", action="remove")]
    assert apply_to_request_headers({"authorization": "Bearer x", "accept": "*/*"}, URL, rules) == {"accept": "*/*"}


def test_set_replaces_instead_of_adding_a_second_spelling():
    rules = [HeaderRule(name="origin", header="Origin", action="set", value="https://evil.example")]
    assert apply_to_request_headers({"origin": "https://app.example"}, URL, rules) == {
        "origin": "https://evil.example",
    }


def test_append_extends_the_existing_header():
    rules = [HeaderRule(name="cookie", header="Cookie", action="append", value="b=2")]
    assert apply_to_request_headers({"cookie": "a=1"}, URL, rules) == {"cookie": "a=1, b=2"}


def test_a_new_header_keeps_the_rule_spelling():
    rules = [HeaderRule(name="csrf", header="X-CSRF-Token", action="set", value="t")]
    assert apply_to_request_headers({}, URL, rules) == {"X-CSRF-Token": "t"}
