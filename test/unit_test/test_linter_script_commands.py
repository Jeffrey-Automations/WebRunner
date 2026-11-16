"""The linter warns on every command the executor's arbitrary-script gate covers."""
import unittest

from je_web_runner.utils.executor import action_executor
from je_web_runner.utils.linter.action_linter import lint_action


class TestArbitraryScriptRule(unittest.TestCase):

    def test_every_gated_command_gets_the_warning(self):
        for name in sorted(action_executor._ARBITRARY_SCRIPT_COMMANDS):
            with self.subTest(command=name):
                rules = [finding["rule"] for finding in lint_action([[name, {}]])]
                self.assertIn("arbitrary_script", rules)

    def test_an_ordinary_command_does_not(self):
        rules = [finding["rule"] for finding in lint_action([["WR_quit_all"]])]
        self.assertNotIn("arbitrary_script", rules)


if __name__ == "__main__":
    unittest.main()
