"""
物件形式動作檔的 ``meta``
What the ``meta`` of an object document (``{"meta": {...}, "webdriver_wrapper": [...]}``) asks of the run:

``skip``           a reason; the file's actions do not run and the reason is recorded
``vars``           default variables: set unless a variable of that name already exists
``setup``          actions run before the file's own
``teardown``       actions run after them, also when an earlier action failed
``retries``        extra attempts for each action of this file (``retry_backoff``: seconds between them)
``fail_fast``      ``true``: after the first failed action, skip the rest (``teardown`` still runs)
``dataset``        a ``.csv`` / ``.json`` file or a list of rows: the file's actions run once per row

``tags`` and ``depends_on`` are read by the CLI's file selection, not here.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.flow.variables import FlowError, VariableStore

MAX_META_RETRIES = 100
SKIP_COMMAND = "WR_note"


def read_meta(document: Any) -> dict[str, Any]:
    """The ``meta`` of ``document``; empty for a plain list and for an object without one."""
    if not isinstance(document, dict):
        return {}
    meta = document.get("meta")
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise FlowError(f"meta must be an object, got {type(meta).__name__}")
    return meta


def skip_reason(meta: dict[str, Any]) -> str | None:
    """The reason the file is skipped, or None when it runs. A skip without a reason is an error."""
    if "skip" not in meta or meta["skip"] is None or meta["skip"] is False:
        return None
    reason = meta["skip"]
    if not isinstance(reason, str) or not reason.strip():
        raise FlowError("meta.skip must be the reason as text, e.g. \"waiting for the new login page\"")
    return reason.strip()


def hook_actions(meta: dict[str, Any], key: str) -> list:
    """The actions of ``meta.setup`` or ``meta.teardown``."""
    actions = meta.get(key)
    if actions is None:
        return []
    if not isinstance(actions, list):
        raise FlowError(f"meta.{key} must be a list of actions, got {type(actions).__name__}")
    return actions


def apply_default_vars(meta: dict[str, Any], variables: VariableStore, scoped: bool = False) -> None:
    """
    Set every ``meta.vars`` name that is not a variable yet (placeholders in the value are expanded).
    ``scoped`` puts them in the innermost frame, so the defaults of a called file end with the call.
    """
    defaults = meta.get("vars")
    if defaults is None:
        return
    if not isinstance(defaults, dict):
        raise FlowError(f"meta.vars must be an object of name: value, got {type(defaults).__name__}")
    for name, value in defaults.items():
        if not variables.has(name):
            variables.set(name, variables.expand(value), local=scoped)


def retry_settings(meta: dict[str, Any]) -> tuple[int, float] | None:
    """``(retries, backoff)`` when the file sets ``meta.retries``, else None."""
    if "retries" not in meta:
        return None
    retries = meta["retries"]
    backoff = meta.get("retry_backoff", 0.0)
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= MAX_META_RETRIES:
        raise FlowError(f"meta.retries must be an integer from 0 to {MAX_META_RETRIES}, got {retries!r}")
    if isinstance(backoff, bool) or not isinstance(backoff, (int, float)) or backoff < 0:
        raise FlowError(f"meta.retry_backoff must be a number of seconds, got {backoff!r}")
    return retries, float(backoff)


def fail_fast_setting(meta: dict[str, Any]) -> bool | None:
    """``meta.fail_fast`` when the file sets it, else None (the executor's setting applies)."""
    if "fail_fast" not in meta:
        return None
    if not isinstance(meta["fail_fast"], bool):
        raise FlowError(f"meta.fail_fast must be true or false, got {meta['fail_fast']!r}")
    return meta["fail_fast"]


def teardown_count(document: Any) -> int:
    """How many ``meta.teardown`` actions end the planned list of ``document`` (0 for a skipped file)."""
    meta = read_meta(document)
    if not meta or skip_reason(meta) is not None:
        return 0
    return len(hook_actions(meta, "teardown"))


def dataset_source(meta: dict[str, Any], default: Any = None) -> Any:
    """``meta.dataset`` when the file sets it, else ``default`` (the run's ``--dataset``); None for neither."""
    source = meta.get("dataset")
    return default if source is None else source


def planned_actions(document: Any, actions: list, variables: VariableStore, scoped: bool = False) -> list:
    """
    文件實際要執行的動作
    The actions to run for ``document`` whose own action list is ``actions``: a note carrying the reason
    for a skipped file, else ``setup`` + ``actions`` + ``teardown`` after the default variables are set.
    A document without those keys gives ``actions`` unchanged.
    """
    meta = read_meta(document)
    if not meta:
        return actions
    reason = skip_reason(meta)
    if reason is not None:
        return [[SKIP_COMMAND, {"text": f"skipped: {reason}"}]]
    apply_default_vars(meta, variables, scoped)
    return [*hook_actions(meta, "setup"), *actions, *hook_actions(meta, "teardown")]
