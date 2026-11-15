import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.file_process.get_dir_file_list import get_dir_files_as_list


class TestGetDirFilesAsList(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        (self.root / "nested" / "deeper").mkdir(parents=True)
        for relative in ("top.json", "notes.txt", "nested/inner.json", "nested/deeper/leaf.json"):
            (self.root / relative).write_text("[]", encoding="utf-8")

    def test_nested_files_keep_their_own_directory(self):
        found = {Path(path) for path in get_dir_files_as_list(str(self.root))}
        self.assertEqual(found, {
            self.root / "top.json",
            self.root / "nested" / "inner.json",
            self.root / "nested" / "deeper" / "leaf.json",
        })

    def test_every_path_exists(self):
        paths = get_dir_files_as_list(str(self.root))
        self.assertEqual([path for path in paths if not os.path.isfile(path)], [])

    def test_paths_are_sorted_whatever_order_the_file_system_gives(self):
        listing = [("/suite", ["z", "a"], ["m.json", "b.json"]), ("/suite/z", [], ["c.json"]),
                   ("/suite/a", [], ["y.json"])]
        with patch("je_web_runner.utils.file_process.get_dir_file_list.walk", return_value=listing):
            found = get_dir_files_as_list("/suite")
        self.assertEqual(found, sorted(found))
        self.assertEqual([Path(path).name for path in found], ["y.json", "b.json", "m.json", "c.json"])

    def test_extension_filter(self):
        found = get_dir_files_as_list(str(self.root), ".txt")
        self.assertEqual([Path(path) for path in found], [self.root / "notes.txt"])

    def test_no_match_gives_an_empty_list(self):
        self.assertEqual(get_dir_files_as_list(str(self.root), ".yaml"), [])

    def test_default_directory_is_the_current_one_at_call_time(self):
        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.root / "nested")
        found = {Path(path) for path in get_dir_files_as_list()}
        self.assertEqual(found, {
            self.root / "nested" / "inner.json",
            self.root / "nested" / "deeper" / "leaf.json",
        })


if __name__ == "__main__":
    unittest.main()
