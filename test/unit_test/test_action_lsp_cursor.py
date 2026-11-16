"""The tolerant scanner that says what the cursor is on; ``|`` marks the cursor in the test texts."""
import unittest

from je_web_runner.action_lsp._cursor import (
    ARRAY,
    COLON,
    KEY,
    OBJECT,
    VALUE,
    is_action,
    is_action_list,
    keys_after,
    keyword_command,
    scan,
)


def _scan(marked):
    offset = marked.index("|")
    return scan(marked.replace("|", "", 1), offset)


def _innermost_command(marked):
    frames = _scan(marked).frames
    return keyword_command(frames, len(frames) - 1)


def _innermost_is_action(marked):
    frames = _scan(marked).frames
    return is_action(frames, len(frames) - 1)


class TestScan(unittest.TestCase):

    def test_empty_text_has_no_frames(self):
        context = scan("", 0)
        self.assertEqual(context.frames, ())
        self.assertFalse(context.in_string)

    def test_half_typed_command_name(self):
        context = _scan('[\n  ["WR_to|')
        self.assertEqual([frame.kind for frame in context.frames], [ARRAY, ARRAY])
        self.assertEqual(context.string_start, 5)
        self.assertEqual(context.typed, "WR_to")
        self.assertEqual(context.frames[-1].index, 0)
        self.assertFalse(context.frames[-1].filled)

    def test_text_after_the_cursor_is_not_read(self):
        context = _scan('[["WR_a|", {"k": 1}], ["WR_b"]]')
        self.assertEqual(context.typed, "WR_a")
        self.assertEqual(len(context.frames), 2)

    def test_array_index_and_first_element(self):
        frame = _scan('[["WR_a", [1, 2], |').frames[-1]
        self.assertEqual((frame.index, frame.first, frame.filled), (2, "WR_a", False))

    def test_first_element_that_is_not_a_string(self):
        frame = _scan('[[12, |').frames[-1]
        self.assertEqual((frame.index, frame.first), (1, None))

    def test_closed_brackets_are_popped(self):
        context = _scan('[["WR_a", {"k": [1, {"x": 2}]}], [|')
        self.assertEqual([frame.index for frame in context.frames], [1, 0])

    def test_object_waits_for_a_key_then_a_colon_then_a_value(self):
        self.assertEqual(_scan('[["WR_a", {|').frames[-1].state, KEY)
        self.assertEqual(_scan('[["WR_a", {"url"|').frames[-1].state, COLON)
        value = _scan('[["WR_a", {"url": |').frames[-1]
        self.assertEqual((value.state, value.key, value.keys), (VALUE, "url", ["url"]))
        again = _scan('[["WR_a", {"url": "x", |').frames[-1]
        self.assertEqual((again.state, again.key, again.keys), (KEY, None, ["url"]))

    def test_cursor_inside_a_key(self):
        context = _scan('[["WR_a", {"url": 1, "ti|')
        self.assertTrue(context.in_string)
        self.assertEqual(context.typed, "ti")
        self.assertEqual((context.frames[-1].kind, context.frames[-1].state), (OBJECT, KEY))

    def test_brackets_inside_strings_are_text(self):
        context = _scan('[["WR_a", {"k": "x], [{", "other": "}}]]", "z": |')
        self.assertEqual([frame.kind for frame in context.frames], [ARRAY, ARRAY, OBJECT])
        self.assertEqual(context.frames[-1].keys, ["k", "other", "z"])

    def test_escaped_quotes_do_not_end_a_string(self):
        context = _scan('[["WR_a", {"k": "say \\"hi\\" [", "v": "a\\\\", "w": "in \\" here|')
        self.assertEqual(context.typed, 'in \\" here')
        self.assertEqual(context.frames[-1].keys, ["k", "v", "w"])
        self.assertEqual(len(context.frames), 3)

    def test_cursor_after_a_backslash_is_still_in_the_string(self):
        context = _scan('["a\\|"]')
        self.assertTrue(context.in_string)
        self.assertEqual(context.typed, "a\\")

    def test_cursor_after_a_closed_string_is_outside_it(self):
        context = _scan('[["WR_a"|')
        self.assertFalse(context.in_string)
        self.assertEqual(context.frames[-1].first, "WR_a")
        self.assertTrue(context.frames[-1].filled)

    def test_stray_closers_are_ignored(self):
        context = _scan(']}[["WR_a", |')
        self.assertEqual(len(context.frames), 2)
        self.assertEqual(context.frames[-1].index, 1)

    def test_offset_past_the_end_is_clamped(self):
        self.assertEqual(len(scan("[[", 99).frames), 2)

    def test_keys_after_the_cursor(self):
        text = '[["WR_a", {"a": 1, "": 2, "c": {"inner": 1}, "d": [{"deep": 1}]}], {"out": 1}]'
        cursor = text.index('""')
        self.assertEqual(keys_after(text, cursor, True), ["c", "d"])
        self.assertEqual(keys_after(text, cursor, False), ["", "c", "d"])


class TestStructure(unittest.TestCase):

    def test_top_level_action(self):
        self.assertTrue(_innermost_is_action('[["|'))
        self.assertTrue(_innermost_is_action('[["WR_a"], [|'))

    def test_the_action_list_is_not_an_action(self):
        frames = _scan('["|').frames
        self.assertFalse(is_action(frames, 0))
        self.assertTrue(is_action_list(frames, 0))

    def test_positional_arguments_are_not_an_action(self):
        self.assertFalse(_innermost_is_action('[["WR_a", ["|'))

    def test_object_document(self):
        self.assertTrue(_innermost_is_action('{"meta": {"tags": []}, "webdriver_wrapper": [["|'))
        self.assertFalse(_innermost_is_action('{"other": [["|'))
        self.assertTrue(_innermost_is_action('{"meta": {"setup": [["|'))
        self.assertTrue(_innermost_is_action('{"meta": {"teardown": [["WR_a"], ["|'))
        self.assertFalse(_innermost_is_action('{"meta": {"tags": [["|'))

    def test_keyword_arguments_of_a_top_level_action(self):
        self.assertEqual(_innermost_command('[["WR_to_url", {|'), "WR_to_url")
        self.assertEqual(_innermost_command('[["WR_a", [1], {"k": 1, |'), "WR_a")

    def test_objects_that_are_not_keyword_arguments(self):
        self.assertIsNone(_innermost_command('[["WR_a", {"k": {|'))
        self.assertIsNone(_innermost_command('[["WR_a", [{|'))
        self.assertIsNone(_innermost_command('[["WR_a", [], {}, {|'))
        self.assertIsNone(_innermost_command('[{|'))
        self.assertIsNone(_innermost_command('{|'))

    def test_block_actions(self):
        self.assertTrue(_innermost_is_action('[["WR_for_each", {"items": [1], "do": [["WR_a"], ["|'))
        self.assertEqual(_innermost_command('[["WR_if", {"condition": true, "otherwise": [["WR_b", {|'), "WR_b")
        self.assertEqual(
            _innermost_command('{"webdriver_wrapper": [["WR_try", {"do": [["WR_repeat", {"do": [["WR_c", {|'),
            "WR_c")

    def test_a_list_argument_that_is_not_a_block(self):
        self.assertFalse(_innermost_is_action('[["WR_for_each", {"items": [["|'))
        self.assertFalse(_innermost_is_action('[["WR_a", {"do": [["|'))

    def test_single_action_argument(self):
        self.assertTrue(_innermost_is_action('[["WR_capture", {"name": "x", "action": ["|'))
        self.assertFalse(_innermost_is_action('[["WR_capture", {"name": ["|'))

    def test_condition_actions(self):
        self.assertTrue(_innermost_is_action('[["WR_if", {"condition": {"succeeds": ["|'))
        self.assertTrue(_innermost_is_action(
            '[["WR_while", {"condition": {"all": [{"not": {"succeeds": ["WR_a", {"k": 1}]}}, {"succeeds": ["|'))
        self.assertFalse(_innermost_is_action('[["WR_a", {"params": {"succeeds": ["|'))


if __name__ == "__main__":
    unittest.main()
