"""With ``WEBRUNNER_MCP_ROOT`` set, an action list run through MCP cannot write files outside that directory."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.mcp_server._policy import ROOT_ENV, write_fence
from je_web_runner.mcp_server.server import make_default_server
from je_web_runner.utils.test_record.test_record_class import test_record_instance

_RECORD = {"function_name": "probe", "local_param": {}, "time": "now", "program_exception": "None"}


def _run(server, actions):
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "webrunner_run_actions", "arguments": {"actions": actions}}}
    return server.handle(request)["result"]


class _FenceCase(unittest.TestCase):

    def setUp(self):
        # Not under the system temporary directory, which the fence leaves writable on purpose.
        base = Path(__file__).resolve().parent / "_mcp_fence_work"
        base.mkdir(exist_ok=True)
        folder = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(lambda: (folder.cleanup(), base.rmdir() if not any(base.iterdir()) else None))
        self.root = Path(folder.name) / "root"
        self.outside = Path(folder.name) / "outside"
        self.root.mkdir()
        self.outside.mkdir()
        saved, enabled = list(test_record_instance.test_record_list), test_record_instance.init_record
        self.addCleanup(setattr, test_record_instance, "test_record_list", saved)
        self.addCleanup(test_record_instance.set_record_enable, enabled)
        test_record_instance.set_record_enable(True)
        test_record_instance.test_record_list = [dict(_RECORD)]


class TestRunToolsAreFenced(_FenceCase):

    def test_a_report_outside_the_root_is_refused(self):
        with patch.dict(os.environ, {ROOT_ENV: str(self.root)}):
            result = _run(make_default_server(), [
                ["WR_generate_json_report", {"json_file_name": str(self.outside / "run")}]])
        self.assertEqual(list(self.outside.iterdir()), [])
        self.assertTrue(result["isError"])

    def test_a_report_inside_the_root_is_written(self):
        with patch.dict(os.environ, {ROOT_ENV: str(self.root)}):
            result = _run(make_default_server(), [
                ["WR_generate_json_report", {"json_file_name": str(self.root / "run")}]])
        self.assertFalse(result["isError"])
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["run_failure.json", "run_success.json"])

    def test_without_a_root_nothing_is_fenced(self):
        environment = {key: value for key, value in os.environ.items() if key != ROOT_ENV}
        with patch.dict(os.environ, environment, clear=True):
            result = _run(make_default_server(), [
                ["WR_generate_json_report", {"json_file_name": str(self.outside / "run")}]])
        self.assertFalse(result["isError"])
        self.assertEqual(len(list(self.outside.iterdir())), 2)


class TestWriteFence(_FenceCase):

    def test_writes_outside_are_refused_only_inside_the_block(self):
        target = self.outside / "note.txt"
        with patch.dict(os.environ, {ROOT_ENV: str(self.root)}):
            with write_fence():
                with self.assertRaises(PermissionError) as caught:
                    target.write_text("x", encoding="utf-8")
                self.assertIn(ROOT_ENV, str(caught.exception))
                (self.root / "note.txt").write_text("inside", encoding="utf-8")
                with self.assertRaises(PermissionError):
                    os.open(str(self.outside / "raw.bin"), os.O_WRONLY | os.O_CREAT)
            target.write_text("after the block", encoding="utf-8")
        self.assertEqual(target.read_text(encoding="utf-8"), "after the block")
        self.assertFalse((self.outside / "raw.bin").exists())

    def test_reading_outside_and_writing_to_the_temporary_directory_stay_possible(self):
        source = self.outside / "data.txt"
        source.write_text("readable", encoding="utf-8")
        with patch.dict(os.environ, {ROOT_ENV: str(self.root)}), write_fence():
            self.assertEqual(source.read_text(encoding="utf-8"), "readable")
            with tempfile.NamedTemporaryFile("w", suffix=".txt") as scratch:
                scratch.write("scratch")

    def test_a_path_that_climbs_out_of_the_root_is_refused(self):
        with patch.dict(os.environ, {ROOT_ENV: str(self.root)}), write_fence():
            with self.assertRaises(PermissionError):
                (self.root / ".." / "outside" / "escape.txt").write_text("x", encoding="utf-8")

    def test_no_root_means_no_fence(self):
        environment = {key: value for key, value in os.environ.items() if key != ROOT_ENV}
        with patch.dict(os.environ, environment, clear=True), write_fence():
            (self.outside / "free.txt").write_text("x", encoding="utf-8")
        self.assertTrue((self.outside / "free.txt").exists())


if __name__ == "__main__":
    unittest.main()
