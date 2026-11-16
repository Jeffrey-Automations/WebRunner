"""
函式庫轉接命令的總表
The command adapters of every theme, in one table.

Most ``je_web_runner/utils`` subpackages were written for Python callers. Each ``_commands_<theme>.py`` module
holds adapters that make such a library usable from an action file: they take JSON values, import the library
only when called, and return JSON values. This module merges their tables, the reasons some subpackages have
no command, and the names of the commands that contact a host an argument names (the MCP server refuses
those by default).
"""
from __future__ import annotations

import importlib
from typing import Any, Callable

_PACKAGE = "je_web_runner.utils.executor."
# module -> the name of its command table
ADAPTER_MODULES: dict[str, str] = {
    "_commands_ai": "AI_COMMANDS",
    "_commands_ai_2": "AI_2_COMMANDS",
    "_commands_api": "API_COMMANDS",
    "_commands_api_2": "API_2_COMMANDS",
    "_commands_audit": "AUDIT_COMMANDS",
    "_commands_audit_2": "AUDIT_2_COMMANDS",
    "_commands_frontend": "FRONTEND_COMMANDS",
    "_commands_frontend_2": "FRONTEND_2_COMMANDS",
    "_commands_governance": "GOVERNANCE_COMMANDS",
    "_commands_governance_2": "GOVERNANCE_2_COMMANDS",
    "_commands_infra": "INFRA_COMMANDS",
    "_commands_infra_2": "INFRA_2_COMMANDS",
    "_commands_performance": "PERFORMANCE_COMMANDS",
    "_commands_performance_2": "PERFORMANCE_2_COMMANDS",
    "_commands_web_platform_a": "WEB_PLATFORM_A_COMMANDS",
    "_commands_web_platform_b": "WEB_PLATFORM_B_COMMANDS",
}

# Subpackages that have no command of their own, and why. The adapter modules add theirs below.
_ENGINE_AND_ENTRY_POINTS: dict[str, str] = {
    "agent": "Has its own entry points: the --agent-task flag, api.ai.run_agent and the MCP agent tools.",
    "assert_value": "Result checks used inside the wrappers; the assertion commands call it.",
    "callback": "The callback executor, a second way to run commands from Python, not a command itself.",
    "cli": "The command-line entry point.",
    "driver_dispatch": "A helper other libraries use to run a script on either backend.",
    "exception": "The exception hierarchy.",
    "file_process": "The directory listing behind the -d flag.",
    "flow": "The action-file language; its commands are registered by _flow_commands.",
    "issue_worker": "Has its own entry point (python -m je_web_runner.issue_worker) and MCP tools.",
    "logging": "The log handler.",
    "project": "The legacy project template; the --init flag covers scaffolding.",
    "project_config": "Read by the CLI before a run; an action file cannot change the run it is part of.",
    "selenium_utils_wrapper": "Selenium key and capability tables used by the wrappers.",
    "socket_server": "A server that receives actions; started from Python, not from an action.",
    "xml": "XML helpers used by the report generators.",
}


def _load() -> tuple[dict[str, Callable[..., Any]], dict[str, str], frozenset[str]]:
    commands: dict[str, Callable[..., Any]] = {}
    python_only = dict(_ENGINE_AND_ENTRY_POINTS)
    network: set[str] = set()
    for module_name, table_name in ADAPTER_MODULES.items():
        module = importlib.import_module(_PACKAGE + module_name)
        table = getattr(module, table_name)
        repeated = sorted(set(table) & set(commands))
        if repeated:
            raise RuntimeError(f"{module_name} repeats command name(s): {', '.join(repeated)}")
        commands.update(table)
        python_only.update(module.PYTHON_ONLY)
        network.update(module.NETWORK_COMMANDS)
    return commands, python_only, frozenset(network)


ADAPTER_COMMANDS, PYTHON_ONLY, NETWORK_COMMANDS = _load()
# Commands that start a local process; kept from callers that are not the operator, like the network ones.
PROCESS_COMMANDS = frozenset({"WR_test_auto_repair_git_diff"})
