"""JSON Schema types: a boolean is neither an integer nor a number."""
import pytest

from je_web_runner.utils.tool_call_assert.tool import ToolCall, ToolCallAssertError, assert_args_match_schema


@pytest.mark.parametrize("schema_type", ["integer", "number"])
def test_a_boolean_is_not_a_number(schema_type):
    schema = {"type": "object", "properties": {"limit": {"type": schema_type}}}
    with pytest.raises(ToolCallAssertError, match="limit"):
        assert_args_match_schema(ToolCall(name="search", arguments={"limit": True}), schema)


def test_numbers_and_booleans_still_match_their_own_types():
    schema = {"type": "object", "properties": {
        "limit": {"type": "integer"}, "score": {"type": "number"}, "exact": {"type": "boolean"},
    }}
    assert_args_match_schema(ToolCall(name="search", arguments={"limit": 3, "score": 0.5, "exact": False}), schema)
    assert_args_match_schema(ToolCall(name="search", arguments={"score": 2}), schema)
