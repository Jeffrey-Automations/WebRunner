"""
把資料集綁到動作檔
A dataset bound to an action file: the file's actions run once per row, and read the row as ``${ROW.col}``.

``meta.dataset`` is a ``.csv`` or ``.json`` file (a relative path starts at the action file) or the rows
themselves, a list of objects. The planned list holds, for every row, one ``WR_use_row`` action that makes
the row current, then the file's own actions; ``meta.setup`` and ``meta.teardown`` run once, around all rows.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from je_web_runner.utils.data_driven.data_runner import load_dataset_csv, load_dataset_json
from je_web_runner.utils.flow.subflow import FileStack
from je_web_runner.utils.flow.variables import FlowError, VariableStore

ROW_COMMAND = "WR_use_row"
ROW_VARIABLE = "ROW"
ROW_INDEX_VARIABLE = "ROW_INDEX"
_LOADERS = {".csv": load_dataset_csv, ".json": load_dataset_json}


def _checked_rows(rows: Any, origin: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise FlowError(f"{origin} must be a list of objects, one per row")
    return rows


def read_rows_file(path: str | Path) -> list[dict[str, Any]]:
    """
    The rows of the ``.csv`` or ``.json`` file at ``path``, read as given: the caller decides whether the
    path is allowed (an action file's ``meta.dataset`` is fenced by :func:`load_rows`, the operator's
    ``--dataset`` is not).
    """
    loader = _LOADERS.get(Path(path).suffix.lower())
    if loader is None:
        raise FlowError(f"dataset {str(path)!r} must be a .csv or .json file")
    return _checked_rows(loader(str(path)), f"dataset {str(path)!r}")


def load_rows(source: Any, files: FileStack) -> list[dict[str, Any]]:
    """
    The rows ``source`` names: a list of objects as it is, or the content of a ``.csv`` / ``.json`` file.

    :raises FlowError: for another type, another file extension, or a path outside the allowed directories.
    """
    if isinstance(source, list):
        return _checked_rows(source, "meta.dataset")
    if not isinstance(source, str) or not source.strip():
        raise FlowError(f"a dataset is a .csv or .json file path, or a list of objects; got {source!r}")
    return read_rows_file(files.resolve_data(source, "dataset"))


def per_row_actions(actions: list, rows: list[dict[str, Any]], scoped: bool = False) -> list:
    """The actions of every row in order: a ``WR_use_row`` action for the row, then ``actions``."""
    planned: list = []
    for index, row in enumerate(rows):
        planned.append([ROW_COMMAND, {"index": index, "row": row, "local": scoped}])
        planned.extend(actions)
    return planned


def use_row(variables: VariableStore, row: dict[str, Any], index: int = 0, local: bool = False) -> dict:
    """
    把資料列設為目前的 ``${ROW}``
    Make ``row`` the current dataset row: later actions read its columns as ``${ROW.col}`` and its
    position from 0 as ``${ROW_INDEX}``. ``local`` keeps it to the block that is running (a called file).
    The run of a file with ``meta.dataset`` inserts this action before each row; return the row.
    """
    if not isinstance(row, dict):
        raise FlowError(f"WR_use_row row must be an object of column: value, got {row!r}")
    variables.bind(ROW_VARIABLE, row, local)
    variables.bind(ROW_INDEX_VARIABLE, index, local)
    return row
