"""The translation table covers the "Equivalent commands" table of the backends page."""
import re
import unittest
from pathlib import Path

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.sel_to_pw import how_translated, untranslatable_commands
from je_web_runner.utils.sel_to_pw.backend_binding import PLAYWRIGHT, SELENIUM, backends_reached, registered_command

_PAGE = Path(__file__).resolve().parents[2] / "docs" / "source" / "Eng" / "doc" / "backends" / "backends_doc.rst"
_TABLE_START = "Equivalent commands"
_TABLE_END = "Only on Selenium"
_ROW = "\n   * - "
_CELL = "\n     - "
_SELENIUM_COLUMN = 1
# A full name, a family (``WR_sw_*``) or a suffix that replaces the end of the name before it (``_by_index``).
_TOKEN = re.compile(r"WR_[A-Za-z0-9_]*\*?|(?<![A-Za-z0-9_])_[a-z0-9_]+")


def _suffixed(previous: str, suffix: str) -> list[str]:
    """``WR_recorder_start`` and ``_stop`` -> ``WR_recorder_stop``: the longest registered combination."""
    cuts = [index for index, character in enumerate(previous) if character == "_"]
    for cut in sorted(cuts, reverse=True):
        if previous[:cut] + suffix in executor.event_dict:
            return [previous[:cut] + suffix]
    return []


def _expand(token: str, previous: str) -> list[str]:
    if token.endswith("*"):
        return sorted(name for name in executor.event_dict
                      if isinstance(name, str) and name.startswith(token[:-1]) and not name.startswith("WR_pw_"))
    if token.startswith("_"):
        return _suffixed(previous, token)
    return [token]


def selenium_commands_of_the_table() -> dict[str, str]:
    """Every Selenium command the equivalents table names -> the task of its row."""
    page = _PAGE.read_text(encoding="utf-8")
    table = page[page.index(_TABLE_START):page.index(_TABLE_END)]
    commands: dict[str, str] = {}
    for row in table.split(_ROW)[2:]:  # the text before the first row, then the header row
        cells = row.split(_CELL)
        previous = ""
        for token in _TOKEN.findall(cells[_SELENIUM_COLUMN]):
            names = _expand(token, previous)
            assert names, f"cannot tell which command {token!r} means in row {cells[0]!r}"  # nosec B101
            previous = names[-1]
            for name in names:
                commands.setdefault(name, " ".join(cells[0].split()))
    return commands


class TestTableAgainstTheBackendsPage(unittest.TestCase):

    def test_the_page_is_read(self):
        commands = selenium_commands_of_the_table()
        self.assertGreater(len(commands), 100)
        for name in ("WR_to_url", "WR_element_select_by_index", "WR_recorder_pull_events",
                     "WR_event_capture_clear", "WR_local_storage_set", "WR_sw_bypass"):
            self.assertIn(name, commands)
        self.assertEqual(sorted(name for name in commands if name not in executor.event_dict), [])

    def test_every_selenium_command_of_the_table_is_translated_or_listed_with_a_reason(self):
        listed = untranslatable_commands()
        undecided = []
        for command, task in sorted(selenium_commands_of_the_table().items()):
            status, _detail = how_translated(command)
            # A command that drives whichever browser is open is the same command on both backends.
            runs_on_both = backends_reached(registered_command(command)) == {SELENIUM, PLAYWRIGHT}
            if status != "translated" and not runs_on_both and not listed.get(command, "").strip():
                undecided.append(f"{command} (row: {task})")
        self.assertEqual(
            undecided, [],
            "add a rule to SELENIUM_TO_PLAYWRIGHT or a reason to CANNOT_TRANSLATE in "
            "je_web_runner/utils/sel_to_pw/backend_rules.py")

    def test_the_selenium_only_section_is_refused(self):
        for command in ("WR_start_remote_driver", "WR_appium_start", "WR_maximize_window", "WR_minimize_window",
                        "WR_fullscreen_window", "WR_set_window_position", "WR_set_window_rect"):
            with self.subTest(command=command):
                self.assertEqual(how_translated(command)[0], "untranslatable")


if __name__ == "__main__":
    unittest.main()
