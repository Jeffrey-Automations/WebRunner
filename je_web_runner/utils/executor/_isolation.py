"""
檔案之間的隔離
Isolation between the action files of one sequential run. Without it the files of a run share the
executor's variables and the table of saved locators, so a later file can pass only because an
earlier one left something behind, and fail when run alone or in another order.
"""
from __future__ import annotations

import contextlib
from typing import Any, Iterator

from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record


@contextlib.contextmanager
def isolated_file(executor: Any) -> Iterator[None]:
    """
    Run one file on its own: it starts with the variables and saved locators the run was set up with
    (``--var``, the project configuration, ``--locators``), and what it sets or saves ends with it.
    The browser is not part of this: a driver one file leaves open is still open for the next.

    The locator table is one object for the process, so this is for runs that execute one file at a
    time; ``--parallel-mode process`` gives every file its own process instead.
    """
    saved = dict(test_object_record.test_object_record_dict)
    try:
        with executor.isolated_variables():
            yield
    finally:
        test_object_record.test_object_record_dict = saved


def file_isolation(executor: Any) -> contextlib.AbstractContextManager[None]:
    """:func:`isolated_file` when the executor's ``isolate_files`` is on, else a block that changes nothing."""
    return isolated_file(executor) if executor.isolate_files else contextlib.nullcontext()
