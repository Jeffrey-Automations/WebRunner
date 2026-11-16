"""A failed action writes a failure bundle when a bundle directory is set; a skipped one writes nothing."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.cli.arguments import _build_parser
from je_web_runner.utils.cli.cli_main import _run_settings
from je_web_runner.utils.cli.run_settings import RunSettings, apply_run_settings
from je_web_runner.utils.executor import action_executor
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.failure_bundle import auto
from je_web_runner.utils.failure_bundle.auto import write_action_failure_bundle
from je_web_runner.utils.project_config.config import ProjectConfig, load_config

FAILING = ["WR_fail", {"message": "the ${reason} failed"}]


def _entries(path: str) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


class _BundleCase(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.bundles = self.folder / "bundles"
        self.addCleanup(executor.set_failure_bundle_dir, None)
        self.addCleanup(executor.set_failure_screenshot_dir, None)
        self.addCleanup(executor.set_fail_fast, False)
        self.addCleanup(executor.variables.unset, "reason")
        for target, value in (("_try_selenium_screenshot", None), ("_try_playwright_screenshot", None)):
            patcher = patch.object(action_executor, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for target in ("selenium_page_html", "playwright_page_html"):
            patcher = patch.object(auto, target, return_value=None)
            patcher.start()
            self.addCleanup(patcher.stop)

    def bundle_files(self) -> list[Path]:
        return sorted(self.bundles.glob("*.zip")) if self.bundles.exists() else []


class TestBundleOnFailure(_BundleCase):

    def test_off_by_default(self):
        executor.execute_action([FAILING])
        self.assertIsNone(executor.failure_bundle_dir)
        self.assertEqual(self.bundle_files(), [])

    def test_a_failed_action_writes_one_bundle_and_names_it_in_the_record(self):
        executor.set_failure_bundle_dir(str(self.bundles))
        executor.variables.set("reason", "s3cret")
        records = executor.execute_action([["WR_set_var", {"name": "ok", "value": 1}], FAILING])
        files = self.bundle_files()
        self.assertEqual(len(files), 1)
        self.assertIn("WR_fail", files[0].name)
        self.assertTrue(any(str(files[0]) in str(value) for value in records.values()))
        entries = _entries(str(files[0]))
        self.assertEqual(json.loads(entries["artifacts/action.json"]), FAILING)
        # The action is stored as written: the variable's value is in the error, not in the action.
        self.assertNotIn(b"s3cret", entries["artifacts/action.json"])
        self.assertIn(b"s3cret", entries["artifacts/error.txt"])
        manifest = json.loads(entries["manifest.json"])
        self.assertEqual(manifest["test_name"], "WR_fail")

    def test_screenshot_and_page_are_included_when_a_browser_is_open(self):
        executor.set_failure_bundle_dir(str(self.bundles))
        with patch.object(action_executor, "_try_selenium_screenshot", return_value=b"\x89PNG-bytes"), \
                patch.object(auto, "selenium_page_html", return_value="<html>page</html>"):
            executor.execute_action([FAILING])
        entries = _entries(str(self.bundle_files()[0]))
        self.assertEqual(entries["artifacts/screenshot.png"], b"\x89PNG-bytes")
        self.assertEqual(entries["artifacts/dom.html"], b"<html>page</html>")

    def test_the_source_file_is_recorded(self):
        executor.set_failure_bundle_dir(str(self.bundles))
        path = self.folder / "login.json"
        path.write_text(json.dumps([FAILING]), encoding="utf-8")
        executor.execute_file(str(path))
        manifest = json.loads(_entries(str(self.bundle_files()[0]))["manifest.json"])
        self.assertEqual(Path(manifest["metadata"]["file"]).name, "login.json")

    def test_skipped_actions_capture_nothing(self):
        executor.set_failure_bundle_dir(str(self.bundles))
        executor.set_failure_screenshot_dir(str(self.folder / "shots"))
        executor.set_fail_fast(True)
        with patch.object(action_executor, "_try_selenium_screenshot", return_value=b"png") as screenshot:
            executor.execute_action([FAILING, ["WR_set_var", {"name": "a", "value": 1}],
                                     ["WR_set_var", {"name": "b", "value": 2}]])
        # One failure: one bundle, and the screenshot was taken for it alone (once for the PNG, once for the zip).
        self.assertEqual(len(self.bundle_files()), 1)
        self.assertEqual(screenshot.call_count, 2)
        self.assertEqual(len(list((self.folder / "shots").glob("*.png"))), 1)

    def test_a_command_name_cannot_leave_the_directory(self):
        executor.set_failure_bundle_dir(str(self.bundles))
        executor.execute_action([["../../escape", {}]])
        for path in self.bundle_files():
            self.assertEqual(path.parent, self.bundles)
        self.assertFalse((self.folder.parent / "escape.zip").exists())

    def test_a_bundle_that_cannot_be_written_is_not_an_error(self):
        blocked = self.folder / "is_a_file"
        blocked.write_text("x", encoding="utf-8")
        self.assertIsNone(write_action_failure_bundle(blocked / "x.zip", FAILING, "boom"))


class TestBundleSettings(_BundleCase):

    def test_flag_wins_and_is_made_absolute(self):
        args = _build_parser().parse_args(["--failure-bundle", "relative/bundles"])
        args.project_config = ProjectConfig(failure_bundle_dir="from/config")
        self.assertEqual(_run_settings(args).failure_bundle_dir, str(Path("relative/bundles").resolve()))
        args = _build_parser().parse_args([])
        args.project_config = ProjectConfig(failure_bundle_dir="from/config")
        self.assertEqual(_run_settings(args).failure_bundle_dir, "from/config")

    def test_configuration_key(self):
        path = self.folder / "webrunner.toml"
        path.write_text('failure_bundle_dir = "artifacts/bundles"\n', encoding="utf-8")
        self.assertEqual(load_config(str(path)).failure_bundle_dir, "artifacts/bundles")

    def test_apply_sets_the_executor_and_creates_the_directory(self):
        apply_run_settings(RunSettings(failure_bundle_dir=str(self.bundles)))
        self.assertEqual(executor.failure_bundle_dir, str(self.bundles))
        self.assertTrue(self.bundles.is_dir())


if __name__ == "__main__":
    unittest.main()
