"""Linter locations to offsets and lines, and LSP positions to offsets."""
import unittest

from je_web_runner.action_lsp._positions import LocationIndex, location_steps
from je_web_runner.action_lsp._text import offset_at, position_at, range_between, request_offset

_LIST_DOCUMENT = """[
  ["WR_to_url", {"url": "http://a.test"}],
  ["WR_if", {
    "condition": {"all": [
      {"succeeds": ["WR_one"]},
      {"not": {"succeeds":
        ["WR_two"]}}
    ]},
    "then": [
      ["WR_three"],
      ["WR_for_each", {"items": [1], "do": [
        ["WR_four", ["positional"], {
          "deep": "x"}]
      ]}]
    ],
    "otherwise": [["WR_five"]]
  }],
  ["WR_capture", {"name": "n", "action":
    ["WR_six"]}]
]"""

_OBJECT_DOCUMENT = """{
  "meta": {
    "setup": [
      ["WR_a"],
      ["WR_b"]
    ],
    "teardown": [["WR_c"]]
  },
  "webdriver_wrapper": [
    ["WR_d"],
    ["WR_e", {"do": [
      ["WR_f"]]}]
  ]
}"""


class TestLocationSteps(unittest.TestCase):

    def test_names_and_indexes(self):
        self.assertEqual(location_steps("action[1].do[0]"), ["action", 1, "do", 0])
        self.assertEqual(location_steps("action[2].condition.all[1].not.succeeds"),
                         ["action", 2, "condition", "all", 1, "not", "succeeds"])
        self.assertEqual(location_steps("meta"), ["meta"])
        self.assertEqual(location_steps(""), [])


class TestLocationIndex(unittest.TestCase):

    def setUp(self):
        self.index = LocationIndex(_LIST_DOCUMENT, False)

    def _text_at(self, location, length):
        offset = self.index.offset(location)
        return _LIST_DOCUMENT[offset:offset + length]

    def test_top_level_actions(self):
        self.assertEqual([self.index.line(f"action[{number}]") for number in range(3)], [1, 2, 17])

    def test_block_actions(self):
        self.assertEqual(self.index.line("action[1].then[0]"), 9)
        self.assertEqual(self.index.line("action[1].then[1]"), 10)
        self.assertEqual(self.index.line("action[1].then[1].do[0]"), 11)
        self.assertEqual(self.index.line("action[1].otherwise[0]"), 15)
        self.assertEqual(self._text_at("action[1].otherwise[0]", 10), '["WR_five"')

    def test_condition_actions(self):
        self.assertEqual(self.index.line("action[1].condition.all[0].succeeds"), 4)
        self.assertEqual(self.index.line("action[1].condition.all[1].not.succeeds"), 6)

    def test_single_action_argument(self):
        self.assertEqual(self.index.line("action[2].action"), 18)

    def test_argument_paths(self):
        self.assertEqual(self._text_at("action[0].args[0].url", 15), '"http://a.test"')
        self.assertEqual(self.index.line("action[1].then[1].do[0].args[1].deep"), 12)
        self.assertEqual(self._text_at("action[1].then[1].do[0].args[0][0]", 12), '"positional"')

    def test_keyword_arguments_in_the_third_slot(self):
        self.assertEqual(self._text_at("action[1].then[1].do[0].deep", 3), '"x"')

    def test_a_path_that_stops_gives_the_deepest_value_found(self):
        self.assertEqual(self.index.line("action[1].then[1].nothing[3]"), 10)
        self.assertEqual(self.index.line("action[1].then[7]"), 8)
        self.assertEqual(self.index.line("action[0].args[0].url.more"), 1)

    def test_unknown_roots_are_line_zero(self):
        self.assertIsNone(self.index.offset("meta"))
        self.assertIsNone(self.index.offset(""))
        self.assertEqual(self.index.line("action[9]"), 0)
        self.assertEqual(self.index.line("somewhere[1]"), 0)

    def test_object_document(self):
        index = LocationIndex(_OBJECT_DOCUMENT, True)
        self.assertEqual(index.line("action[0]"), 9)
        self.assertEqual(index.line("action[1].do[0]"), 11)
        self.assertEqual(index.line("meta"), 1)
        self.assertEqual(index.line("meta.setup[1]"), 4)
        self.assertEqual(index.line("meta.teardown[0]"), 6)

    def test_object_document_without_meta(self):
        self.assertEqual(LocationIndex('{\n"webdriver_wrapper": []}', True).line("meta"), 0)

    def test_text_that_is_not_a_document(self):
        self.assertEqual(LocationIndex("", False).line("action[0]"), 0)
        self.assertEqual(LocationIndex("12", True).line("meta.setup[0]"), 0)

    def test_keys_with_brackets_and_escapes_in_strings(self):
        text = '[["WR_a", {"k]": "[\\"", "do": [\n["WR_b"]]}]]'
        self.assertEqual(LocationIndex(text, False).line("action[0].do[0]"), 1)


class TestPositions(unittest.TestCase):

    def test_offset_at(self):
        text = "ab\ncde\n"
        self.assertEqual(offset_at(text, 0, 0), 0)
        self.assertEqual(offset_at(text, 1, 2), 5)
        self.assertEqual(offset_at(text, 2, 0), 7)

    def test_positions_past_the_end_are_clamped(self):
        text = "ab\r\ncde"
        self.assertEqual(offset_at(text, 0, 99), 2)
        self.assertEqual(offset_at(text, 1, 99), 7)
        self.assertEqual(offset_at(text, 9, 0), 7)

    def test_characters_are_utf16_code_units(self):
        text = '"\U0001F600x"'
        self.assertEqual(offset_at(text, 0, 3), 2)
        self.assertEqual(position_at(text, 2), {"line": 0, "character": 3})
        self.assertEqual(position_at("中文x", 2), {"line": 0, "character": 2})

    def test_position_at_round_trips(self):
        text = "[\n  1,\n  2\n]"
        for offset in range(len(text) + 1):
            position = position_at(text, offset)
            self.assertEqual(offset_at(text, position["line"], position["character"]), offset)

    def test_range_between(self):
        self.assertEqual(range_between("a\nbcd", 2, 5),
                         {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 3}})

    def test_request_offset(self):
        self.assertEqual(request_offset("a\nbc", {"position": {"line": 1, "character": 1}}), 3)
        self.assertIsNone(request_offset("a", {}))
        self.assertIsNone(request_offset("a", {"position": {"line": "1", "character": 0}}))
        self.assertIsNone(request_offset("a", {"position": [0, 0]}))


if __name__ == "__main__":
    unittest.main()
