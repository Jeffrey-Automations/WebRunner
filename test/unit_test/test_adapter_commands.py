"""Every utils subpackage is reachable from an action file, or says why it is not."""
import ast
import inspect
import re
import unittest
from pathlib import Path

from je_web_runner.mcp_server._policy import UNSAFE_COMMANDS
from je_web_runner.utils.executor import _adapter_commands as adapters
from je_web_runner.utils.executor.action_executor import executor

REPO_ROOT = Path(__file__).resolve().parents[2]
UTILS_DIR = REPO_ROOT / "je_web_runner" / "utils"
EXECUTOR_DIR = UTILS_DIR / "executor"
# The command modules and the wrappers the table is built from: a subpackage they import has a command.
_TABLE_SOURCES = (
    "_event_table.py", "_playwright_commands.py", "_authoring_commands.py", "_flow_commands.py",
)
_WRAPPER_SOURCES = (
    REPO_ROOT / "je_web_runner" / "webdriver" / "_wrapper_mixins" / "_parity_mixin.py",
)
_IMPORTED = re.compile(r"je_web_runner\.utils(?:\.| import )(\w+)")


def _subpackages() -> set[str]:
    return {path.name for path in UTILS_DIR.iterdir() if (path / "__init__.py").is_file()}


def _registered_directly() -> set[str]:
    sources = [EXECUTOR_DIR / name for name in _TABLE_SOURCES] + list(_WRAPPER_SOURCES)
    return {name for source in sources for name in _IMPORTED.findall(source.read_text(encoding="utf-8"))}


def _adapted() -> set[str]:
    """The subpackages some adapter command is named after (``WR_<subpackage>_...``)."""
    packages = sorted(_subpackages(), key=len, reverse=True)
    found = set()
    for command in adapters.ADAPTER_COMMANDS:
        for package in packages:
            if command.startswith(f"WR_{package}_"):
                found.add(package)
                break
    return found


class TestEverySubpackageIsReachable(unittest.TestCase):

    def test_each_has_a_command_or_a_reason(self):
        reachable = _registered_directly() | _adapted() | set(adapters.PYTHON_ONLY)
        self.assertEqual(sorted(_subpackages() - reachable), [])

    def test_python_only_reasons_are_sentences_about_real_subpackages(self):
        self.assertEqual(sorted(set(adapters.PYTHON_ONLY) - _subpackages()), [])
        for package, reason in adapters.PYTHON_ONLY.items():
            with self.subTest(package=package):
                self.assertGreaterEqual(len(reason.split()), 3)
                self.assertTrue(reason.endswith("."))

    def test_a_subpackage_with_a_command_is_not_also_python_only(self):
        self.assertEqual(sorted(_adapted() & set(adapters.PYTHON_ONLY)), [])


class TestAdapterTable(unittest.TestCase):

    def test_every_adapter_module_on_disk_is_merged(self):
        on_disk = {path.stem for path in EXECUTOR_DIR.glob("_commands_*.py")}
        self.assertEqual(on_disk, set(adapters.ADAPTER_MODULES))

    def test_commands_are_registered_in_the_executor(self):
        self.assertEqual(sorted(set(adapters.ADAPTER_COMMANDS) - set(executor.event_dict)), [])

    def test_every_adapter_is_named_after_a_subpackage_and_documented(self):
        packages = _subpackages()
        for name, command in adapters.ADAPTER_COMMANDS.items():
            with self.subTest(command=name):
                self.assertTrue(any(name.startswith(f"WR_{package}_") for package in packages))
                self.assertTrue((inspect.getdoc(command) or "").strip())
                inspect.signature(command)

    def test_network_and_process_commands_exist_and_are_refused_over_mcp(self):
        guarded = adapters.NETWORK_COMMANDS | adapters.PROCESS_COMMANDS
        self.assertEqual(sorted(guarded - set(adapters.ADAPTER_COMMANDS)), [])
        self.assertEqual(sorted(guarded - UNSAFE_COMMANDS), [])
        self.assertIn("WR_tls_cipher_audit_handshake", guarded)

    def test_adapter_modules_import_no_library_at_module_level(self):
        # Adapters import their library when called, so `import je_web_runner` does not pay for 200 of them.
        allowed = ("je_web_runner.utils.executor.", "je_web_runner.utils.exception.")
        for module_name in adapters.ADAPTER_MODULES:
            tree = ast.parse((EXECUTOR_DIR / f"{module_name}.py").read_text(encoding="utf-8"))
            imported = [node.module for node in tree.body
                        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("je_web_runner.")]
            imported += [alias.name for node in tree.body if isinstance(node, ast.Import)
                         for alias in node.names if alias.name.startswith("je_web_runner.")]
            with self.subTest(module=module_name):
                self.assertEqual([name for name in imported if not name.startswith(allowed)], [])


if __name__ == "__main__":
    unittest.main()
