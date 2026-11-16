"""An alias has to be a word (or a run of words) of the field's name, not letters inside another word."""
import pytest

from je_web_runner.utils.form_autofill.autofill import classify_field, match_fields


@pytest.mark.parametrize("name", [
    "quantity", "faq_answer", "passport", "hotel", "capacity", "discard", "cancellation", "frequency",
])
def test_letters_inside_another_word_do_not_classify(name):
    assert classify_field({"type": "text", "name": name}) is None


@pytest.mark.parametrize("name, expected", [
    ("q", "search"),
    ("shipping_city", "city"),
    ("confirmPassword", "password"),
    ("user-name", "username"),
    ("billing address", "address"),
    ("E-mail", "email"),
    ("phone2", "phone"),
    ("ZIP", "zip"),
])
def test_words_and_runs_of_words_classify(name, expected):
    assert classify_field({"type": "text", "name": name}) == expected


def test_a_quantity_field_is_not_filled_with_the_search_term():
    assert match_fields([{"type": "number", "id": "quantity"}], {"search": "shoes"}) == []
