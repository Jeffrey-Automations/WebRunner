"""
以 entry point 提供的命令外掛
Command plugins: an installed distribution can offer ``WR_*`` commands through the entry-point group
``je_web_runner.commands``.

.. code-block:: toml

    # the plugin's pyproject.toml
    [project.entry-points."je_web_runner.commands"]
    my_checks = "my_package.webrunner_commands:COMMANDS"

``COMMANDS`` is a dict of command name to function (or a function returning such a dict). Nothing is loaded
because it is installed: the operator names the plugins to load, with ``--plugin my_checks``, ``plugins =
["my_checks"]`` in the project configuration, or :func:`load_command_plugins` from Python. An action file has
no command for it, so a file cannot load code its operator did not choose.
"""
from __future__ import annotations

from importlib import metadata
from typing import Any, Callable, Iterable, Mapping

from je_web_runner.utils.exception.exceptions import WebRunnerException

ENTRY_POINT_GROUP = "je_web_runner.commands"
COMMAND_PREFIX = "WR_"


class CommandPluginError(WebRunnerException):
    """Raised when a named plugin is not installed or does not provide valid commands."""


def available_plugins() -> list[str]:
    """The names of the installed command plugins, sorted. Listing loads none of them."""
    return sorted(entry_point.name for entry_point in metadata.entry_points(group=ENTRY_POINT_GROUP))


def _commands_of(name: str, loaded: Any) -> Mapping[str, Callable[..., Any]]:
    """The command table a plugin's entry point gives: a mapping, or a function returning one."""
    table = loaded() if callable(loaded) and not isinstance(loaded, Mapping) else loaded
    if not isinstance(table, Mapping) or not table:
        raise CommandPluginError(f"plugin {name!r} must provide a non-empty dict of command name: function")
    for command, function in table.items():
        if not isinstance(command, str) or not command.startswith(COMMAND_PREFIX):
            raise CommandPluginError(f"plugin {name!r}: command name {command!r} must start with {COMMAND_PREFIX}")
        if not callable(function):
            raise CommandPluginError(f"plugin {name!r}: {command} is not callable")
    return table


def load_command_plugins(names: Iterable[str], executor: Any = None) -> list[str]:
    """
    載入指定名稱的命令外掛
    Load the installed plugins called ``names`` and register their commands in ``executor`` (the shared
    executor by default). Return the command names added, sorted.

    :raises CommandPluginError: when a name is not installed, a plugin's table is not valid, or a command
             name is already registered. Nothing is registered then.
    """
    if executor is None:
        from je_web_runner.utils.executor.action_executor import executor as shared_executor
        executor = shared_executor
    installed = {entry_point.name: entry_point for entry_point in metadata.entry_points(group=ENTRY_POINT_GROUP)}
    commands: dict[str, Callable[..., Any]] = {}
    for name in names:
        if name not in installed:
            known = ", ".join(sorted(installed)) or "none"
            raise CommandPluginError(f"command plugin {name!r} is not installed (installed: {known})")
        table = _commands_of(name, installed[name].load())
        taken = sorted(command for command in table if command in executor.event_dict or command in commands)
        if taken:
            raise CommandPluginError(f"plugin {name!r} repeats existing command(s): {', '.join(taken)}")
        commands.update(table)
    executor.add_command_to_executor(commands)
    return sorted(commands)
