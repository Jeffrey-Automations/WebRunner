"""The action files of examples/flow stay valid: shape, registered commands, files they call."""
import json
import unittest
from pathlib import Path

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.flow.structure import keyword_arguments
from je_web_runner.utils.json.json_validator import validate_action_json
from je_web_runner.utils.linter.action_linter import lint_action
from je_web_runner.utils.linter.flow_rules import every_action

FLOW_DIR = Path(__file__).resolve().parents[2] / "examples" / "flow"
FILES = sorted(FLOW_DIR.rglob("*.json"))


def _document(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _actions(document) -> list:
    meta = document.get("meta", {})
    blocks = [meta.get("setup", []), document["webdriver_wrapper"], meta.get("teardown", [])]
    return [action for block in blocks for _location, action in every_action(block)]


class TestFlowExamples(unittest.TestCase):

    def test_the_example_has_a_suite_and_its_steps(self):
        names = {path.relative_to(FLOW_DIR).as_posix() for path in FILES}
        self.assertEqual(names, {"suite.json", "steps/check_page.json", "steps/greet.json"})

    def test_every_file_validates(self):
        for path in FILES:
            with self.subTest(path=path.name):
                self.assertTrue(validate_action_json(_document(path)))

    def test_every_command_is_registered(self):
        for path in FILES:
            with self.subTest(path=path.name):
                unknown = [action[0] for action in _actions(_document(path)) if action[0] not in executor.event_dict]
                self.assertEqual(unknown, [])

    def test_no_lint_warnings(self):
        for path in FILES:
            with self.subTest(path=path.name):
                warnings = [finding for finding in lint_action(_document(path))
                            if finding["severity"] == "warning"]
                self.assertEqual(warnings, [])

    def test_called_files_exist(self):
        for path in FILES:
            for action in _actions(_document(path)):
                if action[0] != "WR_call_file":
                    continue
                with self.subTest(path=path.name, called=keyword_arguments(action)["path"]):
                    self.assertTrue((path.parent / keyword_arguments(action)["path"]).is_file())

    def test_steps_are_tagged_so_a_directory_run_can_leave_them_out(self):
        for path in FILES:
            if path.parent.name == "steps":
                with self.subTest(path=path.name):
                    self.assertIn("sub-flow", _document(path)["meta"]["tags"])


if __name__ == "__main__":
    unittest.main()
