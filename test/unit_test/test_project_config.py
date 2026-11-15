"""Project configuration: webrunner.toml and [tool.webrunner] of pyproject.toml."""
import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.project_config import (
    ProjectConfig,
    ProjectConfigError,
    discover_config,
    find_config,
    load_config,
)


class TestProjectConfig(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def _write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_no_file_gives_an_empty_configuration(self):
        self.assertIsNone(find_config(self.root))
        config = discover_config(self.root)
        self.assertEqual(config, ProjectConfig())
        self.assertEqual(config.cli_defaults(), {})

    def test_webrunner_toml(self):
        path = self._write("webrunner.toml", "\n".join([
            'env = "staging"',
            'fail_fast = true',
            'retries = 2',
            'retry_backoff = 0.5',
            'report = "reports/run"',
            'ledger = "ledger.json"',
            'parallel = 4',
            'parallel_mode = "process"',
            'tag = ["smoke"]',
            'exclude_tag = ["sub-flow", "slow"]',
            '[vars]',
            'base = "https://example.test"',
            'count = 3',
        ]))
        config = load_config(path)
        self.assertEqual(config.source, str(path))
        self.assertEqual(config.vars, {"base": "https://example.test", "count": 3})
        self.assertEqual((config.env, config.fail_fast, config.retries, config.retry_backoff),
                         ("staging", True, 2, 0.5))
        self.assertEqual(config.cli_defaults(), {
            "report": "reports/run", "ledger": "ledger.json", "parallel": 4, "parallel_mode": "process",
            "tag": "smoke", "exclude_tag": "sub-flow,slow",
        })

    def test_pyproject_table(self):
        self._write("pyproject.toml", '[project]\nname = "demo"\n\n[tool.webrunner]\nfail_fast = true\n')
        found = find_config(self.root)
        self.assertEqual(found.name, "pyproject.toml")
        self.assertTrue(discover_config(self.root).fail_fast)

    def test_pyproject_without_the_table_is_not_a_configuration(self):
        self._write("pyproject.toml", '[project]\nname = "demo"\n')
        self.assertIsNone(find_config(self.root))

    def test_broken_pyproject_does_not_stop_discovery(self):
        self._write("pyproject.toml", "this is [not toml")
        self.assertIsNone(find_config(self.root))
        self.assertEqual(discover_config(self.root), ProjectConfig())

    def test_webrunner_toml_wins_over_pyproject(self):
        self._write("pyproject.toml", "[tool.webrunner]\nretries = 1\n")
        self._write("webrunner.toml", "retries = 5\n")
        self.assertEqual(discover_config(self.root).retries, 5)

    def test_unknown_key_names_the_known_ones(self):
        path = self._write("webrunner.toml", "retry = 3\n")
        with self.assertRaises(ProjectConfigError) as raised:
            load_config(path)
        self.assertIn("retry", str(raised.exception))
        self.assertIn("retries", str(raised.exception))

    def test_wrong_values(self):
        cases = ["retries = -1", "retries = true", 'retries = "2"', "parallel = 0", 'parallel_mode = "fork"',
                 "fail_fast = 1", 'tag = "smoke"', "tag = [1]", 'vars = "x"', 'env = ""', "retry_backoff = -1"]
        for line in cases:
            with self.subTest(line=line):
                path = self._write("webrunner.toml", line + "\n")
                with self.assertRaises(ProjectConfigError):
                    load_config(path)

    def test_invalid_toml_and_missing_file(self):
        with self.assertRaises(ProjectConfigError):
            load_config(self._write("webrunner.toml", "retries = = 2"))
        with self.assertRaises(ProjectConfigError):
            load_config(self.root / "nowhere.toml")

    def test_discovery_uses_the_working_directory(self):
        self._write("webrunner.toml", "retries = 7\n")
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self.assertEqual(discover_config().retries, 7)


if __name__ == "__main__":
    unittest.main()
