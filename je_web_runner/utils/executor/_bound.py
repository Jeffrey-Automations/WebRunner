"""
需要執行器本身的命令表項目
A command-table entry that needs the executor that owns the table.

Kept apart from the tables so each command module (``_event_table``, ``_authoring_commands`` …) can declare
such entries without importing another table.
"""
from __future__ import annotations

from typing import Any, Callable


class Bound:
    """A table entry built from the owning executor, e.g. ``WR_execute_action``."""

    def __init__(self, factory: Callable[[Any], Callable[..., Any]]) -> None:
        self.factory = factory
