"""
Web 平台 API 的命令轉接
Command adapters for the web-platform libraries (background sync, cookieStore, IndexedDB, payment, SSE ...).

Each library was written for Python callers; the functions here take and return JSON values so an action
file can use them. The ``..._install`` / ``..._harvest`` commands run the library's own fixed script on the
current page; every other command works on data given as an argument.
"""
# pylint: disable=import-outside-toplevel  # importing je_web_runner must not load every library
from __future__ import annotations

import base64
from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor._command_helpers import selenium_driver, to_plain

_BACKGROUND_SYNC_HARVEST = (
    "const hook = window.__wr_bg_sync__;"
    " return hook ? {registered: hook.drainRegistered(), fired: hook.drainFired()} : null;"
)
_CREDENTIAL_HARVEST = (
    "const hook = window.__wr_cm__; return hook ?"
    " {stored: hook.drainStored(), gets: hook.drainGets(), preventCount: hook.preventCount()} : null;"
)
_PAYMENT_HARVEST = (
    "const hook = window.__wr_payment__;"
    " return hook ? {constructed: hook.drainConstructed(), completed: hook.drainCompleted()} : null;"
)
_PIP_HARVEST = "return window.__wr_pip__ ? window.__wr_pip__.drain() : null;"
_SPEECH_HARVEST = "return window.__wr_speech__ ? window.__wr_speech__.drainSpoken() : null;"
_SPEECH_PUSH = "const hook = window.__wr_speech__; return hook ? (hook.pushTranscript(arguments[0]), true) : null;"
_SSE_STATE: dict[str, Any] = {}


def _run_script(command: str, script: str, *args: Any) -> Any:
    """Run one of the libraries' fixed scripts on the current page and return its value."""
    return selenium_driver(command).execute_script(script, *args)


def _read_recorder(command: str, script: str, *args: Any) -> Any:
    """Run a fixed script that talks to a page recorder; ``null`` back means the recorder is not installed."""
    result = _run_script(command, script, *args)
    if result is None:
        raise WebRunnerException(f"{command}: the recorder is not on this page; run its install command first")
    return result


def _text(entry: dict[str, Any], key: str, default: str = "") -> str:
    """The text of ``entry[key]``, or ``default`` when it is missing or empty."""
    return str(entry.get(key) or default)


def _objects(entries: list[dict[str, Any]] | None, error: type[Exception], what: str) -> list[dict[str, Any]]:
    """``entries`` (none = empty) once every one is known to be an object; ``error`` names the first that is not."""
    for entry in entries or []:
        if not isinstance(entry, dict):
            raise error(f"every {what} must be an object, got {entry!r}")
    return list(entries or [])


def background_sync_assert_install() -> bool:
    """Install the Background Sync recorder on the current page; run it before the page registers a sync."""
    from je_web_runner.utils.background_sync_assert.sync import INSTALL_SCRIPT
    _run_script("WR_background_sync_assert_install", INSTALL_SCRIPT)
    return True


def background_sync_assert_harvest() -> dict[str, Any]:
    """Read and empty the Background Sync recorder: ``{"registered": [tags], "fired": [{tag, lastChance, ts}]}``."""
    return to_plain(_read_recorder("WR_background_sync_assert_harvest", _BACKGROUND_SYNC_HARVEST))


def background_sync_assert_check(
        payload: dict[str, Any], tag: str, at_least: int = 1,
        require_retry: bool = False, forbid_last_chance: bool = False) -> dict[str, Any]:
    """Fail unless the harvested log shows sync ``tag`` registered and fired ``at_least`` times (0 = registration
    only); ``require_retry`` wants a second ``sync`` event, ``forbid_last_chance`` fails on a last-chance
    attempt. Raises BackgroundSyncAssertError when a check fails; returns the normalised log."""
    from je_web_runner.utils.background_sync_assert import sync
    log = sync.parse_log(payload)
    sync.assert_registered(log, tag=tag)
    if at_least > 0:
        sync.assert_fired(log, tag=tag, at_least=at_least)
    if require_retry:
        sync.assert_retry_happened(log, tag=tag)
    if forbid_last_chance:
        sync.assert_no_quota_exhaustion(log, tag=tag)
    return to_plain(log)


def _member(members: Any, value: str, error: type[Exception]) -> Any:
    """The member of the enum ``members`` whose value is ``value``; ``error`` lists the valid ones otherwise."""
    try:
        return members(value)
    except ValueError as failure:
        raise error(f"expected one of {[member.value for member in members]}, got {value!r}") from failure


def _compressed_bytes(compressed_base64: str) -> bytes:
    from je_web_runner.utils.compression_streams.streams import CompressionStreamsError
    try:
        return base64.b64decode(compressed_base64, validate=True)
    except (TypeError, ValueError) as error:
        raise CompressionStreamsError(f"compressed_base64 is not base64: {error}") from error


def compression_streams_compress(text: str, algorithm: str = "gzip") -> str:
    """Compress ``text`` with the current page's ``CompressionStream`` and return the bytes as base64."""
    from je_web_runner.utils.compression_streams import streams
    wanted = _member(streams.Algorithm, algorithm, streams.CompressionStreamsError)
    script = "return (" + streams.HARVEST_SCRIPT.strip().rstrip(";") + ")(arguments[0], arguments[1]);"
    return str(_run_script("WR_compression_streams_compress", script, wanted.value, text))


def compression_streams_decompress(compressed_base64: str, algorithm: str = "gzip") -> dict[str, Any]:
    """Decompress base64 bytes (``gzip`` / ``deflate`` / ``deflate-raw`` / ``br``): ``{"text": ..., "size": n}``."""
    from je_web_runner.utils.compression_streams import streams
    wanted = _member(streams.Algorithm, algorithm, streams.CompressionStreamsError)
    recovered = streams.decompress(_compressed_bytes(compressed_base64), wanted)
    return {"text": recovered.decode("utf-8", errors="replace"), "size": len(recovered)}


def compression_streams_assert_round_trip(original_text: str, compressed_base64: str, algorithm: str = "gzip") -> bool:
    """Fail unless the base64 ``compressed_base64`` decompresses back to ``original_text`` (as UTF-8).
    Raises CompressionStreamsError on a mismatch or bytes that do not decompress."""
    from je_web_runner.utils.compression_streams import streams
    streams.assert_round_trip(
        original=original_text.encode("utf-8"), compressed=_compressed_bytes(compressed_base64),
        algorithm=_member(streams.Algorithm, algorithm, streams.CompressionStreamsError),
    )
    return True


def compression_streams_assert_ratio(original_size: int, compressed_size: int, max_ratio: float) -> float:
    """Fail when the compressed size is more than ``max_ratio`` (0 to 1) of the original size; returns the ratio.
    Raises CompressionStreamsError when the ratio is above ``max_ratio``."""
    from je_web_runner.utils.compression_streams import streams
    streams.assert_ratio_under(original_size=original_size, compressed_size=compressed_size, max_ratio=max_ratio)
    return streams.compression_ratio(original_size, compressed_size)


def compute_pressure_assert(
        payload: dict[str, Any], level: str = "critical", name: str | None = None,
        only_if_fired: bool = False, require_disconnect: bool = False) -> dict[str, Any]:
    """Fail unless the log ``{"reactions": [{name, level, ts}], "fires": [levels], "disconnectCount": n}`` has a
    reaction (optionally called ``name``) at pressure ``level`` or above. ``only_if_fired`` demands it only
    when ``fires`` reached ``level``; ``require_disconnect`` fails when the observer never disconnected.
    Raises ComputePressureError when a check fails; returns the normalised log."""
    from je_web_runner.utils.compute_pressure import pressure
    log = pressure.parse_log(payload)
    wanted = _member(pressure.PressureLevel, level, pressure.ComputePressureError)
    if only_if_fired:
        pressure.assert_throttled_at_or_above(log, level=wanted)
    else:
        pressure.assert_reaction_to(log, level=wanted, name=name)
    if require_disconnect:
        pressure.assert_observer_disconnected(log)
    return to_plain(log)


def cookie_store_api_harvest() -> list[dict[str, Any]]:
    """Read the current page's cookies through ``cookieStore.getAll()`` (empty where the API is missing)."""
    from je_web_runner.utils.cookie_store_api.store import GET_ALL_SCRIPT, parse_cookies
    return to_plain(parse_cookies(_run_script("WR_cookie_store_api_harvest", "return " + GET_ALL_SCRIPT) or []))


def cookie_store_api_install_listener() -> bool:
    """Start recording the current page's cookie ``change`` events for ``WR_cookie_store_api_changes``."""
    from je_web_runner.utils.cookie_store_api.store import install_change_listener_script
    _run_script("WR_cookie_store_api_install_listener", install_change_listener_script())
    return True


def cookie_store_api_changes() -> list[dict[str, Any]]:
    """The cookie change events recorded so far: ``[{"changed": [cookies], "deleted": [names], "timestamp_ms"}]``."""
    from je_web_runner.utils.cookie_store_api.store import HARVEST_CHANGES_SCRIPT, parse_change_events
    return to_plain(parse_change_events(_run_script("WR_cookie_store_api_changes", HARVEST_CHANGES_SCRIPT)))


def cookie_store_api_assert(
        cookies: list[dict[str, Any]], present: str | None = None, value: str | None = None,
        absent: str | None = None, secure_only: bool = False) -> list[dict[str, Any]]:
    """Check a cookie list: ``present`` names a cookie that must exist (with ``value`` when given), ``absent`` one
    that must not, ``secure_only`` fails on any cookie without ``secure``.
    Raises CookieStoreApiError when a check fails; returns the normalised cookies."""
    from je_web_runner.utils.cookie_store_api import store
    records = store.parse_cookies(cookies)
    if present is not None:
        store.assert_cookie_present(records, name=present, value=value)
    if absent is not None:
        store.assert_cookie_absent(records, name=absent)
    if secure_only:
        store.assert_secure_only(records)
    return to_plain(records)


def cookie_store_api_assert_change(events: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Fail unless one recorded change event changed or deleted the cookie ``name``; returns that event.
    Raises CookieStoreApiError when no event mentions the cookie."""
    from je_web_runner.utils.cookie_store_api import store
    return to_plain(store.assert_change_for(store.parse_change_events(events), name=name))


def credential_management_install(credentials: list[dict[str, Any]] | None = None) -> bool:
    """Replace the page's ``navigator.credentials`` with a recording mock that answers ``get`` with the first of
    ``credentials`` (``[{"id", "type", "name", "password", "provider"}]``)."""
    from je_web_runner.utils.credential_management import credentials as library
    seeds = [
        library.SeedCredential(
            id=_text(entry, "id"), type=_text(entry, "type", "password"), name=_text(entry, "name"),
            password=_text(entry, "password"), provider=_text(entry, "provider"),
        )
        for entry in _objects(credentials, library.CredentialManagementError, "credential")
    ]
    _run_script("WR_credential_management_install", library.INSTALL_SCRIPT, library.build_seed(seeds))
    return True


def credential_management_harvest() -> dict[str, Any]:
    """Read and empty the credentials mock's log: ``{"stored": [...], "gets": [...], "preventCount": n}``."""
    return to_plain(_read_recorder("WR_credential_management_harvest", _CREDENTIAL_HARVEST))


def credential_management_assert(
        payload: dict[str, Any], stored_id: str | None = None, prevent_silent_access: int = 0,
        mediation: str | None = None, forbid_password: bool = False) -> dict[str, Any]:
    """Check a harvested credentials log: ``stored_id`` was passed to ``credentials.store``,
    ``preventSilentAccess`` was called ``prevent_silent_access`` times or more, every ``get`` used
    ``mediation``, and with ``forbid_password`` no stored credential exposed its password.
    Raises CredentialManagementError when a check fails; returns the normalised log."""
    from je_web_runner.utils.credential_management import credentials as library
    log = library.parse_log(payload)
    if stored_id is not None:
        library.assert_stored(log, credential_id=stored_id)
    if prevent_silent_access > 0:
        library.assert_prevent_silent_access_called(log, at_least=prevent_silent_access)
    if mediation is not None:
        library.assert_get_requested_mediation(log, mediation=mediation)
    if forbid_password:
        library.assert_no_password_in_clear(log)
    return to_plain(log)


def file_system_access_install(
        open_files: list[dict[str, Any]] | None = None, save_suggested_name: str | None = None) -> bool:
    """Replace the page's file pickers with mocks: ``showOpenFilePicker`` returns ``open_files``
    (``[{"name", "contents", "mime_type"}]``) and writes to the save picker's file are recorded."""
    from je_web_runner.utils.file_system_access import mock
    files = [
        mock.MockFile(
            name=_text(entry, "name"), contents=_text(entry, "contents"),
            mime_type=_text(entry, "mime_type", "text/plain"),
        )
        for entry in _objects(open_files, mock.FileSystemAccessError, "open file")
    ]
    _run_script(
        "WR_file_system_access_install", mock.build_install_script(files, save_suggested_name=save_suggested_name),
    )
    return True


def file_system_access_harvest() -> list[dict[str, Any]]:
    """The writes the page made to a mocked save file: ``[{"file_name", "sequence", "data"}]``."""
    from je_web_runner.utils.file_system_access.mock import HARVEST_SCRIPT, parse_writes
    return to_plain(parse_writes(_run_script("WR_file_system_access_harvest", HARVEST_SCRIPT)))


def file_system_access_assert(
        writes: list[dict[str, Any]], file_name: str | None = None, contains: str | None = None,
        no_writes: bool = False) -> dict[str, Any]:
    """Fail unless one write matches ``file_name`` and/or has ``contains`` in its data; with ``no_writes`` fail
    when the page wrote anything. Raises FileSystemAccessError when the check fails; returns
    ``{"match": the matching write, "combined": everything written to file_name, in order}``."""
    from je_web_runner.utils.file_system_access import mock
    events = mock.parse_writes(writes)
    if no_writes:
        mock.assert_no_writes(events)
        return {"match": None, "combined": ""}
    match = mock.assert_wrote(events, file_name=file_name, contains=contains)
    return {"match": to_plain(match), "combined": mock.combined_payload(events, match.file_name)}


def _idb_snapshot(snapshot: Any) -> Any:
    from je_web_runner.utils.indexed_db_explorer.explorer import IdbSnapshot
    return IdbSnapshot.from_dict(snapshot)


def _has_fields(wanted: dict[str, Any], record: Any) -> bool:
    """Whether ``record`` is an object that has every field of ``wanted`` with the same value."""
    return isinstance(record, dict) and all(key in record and record[key] == wanted[key] for key in wanted)


def indexed_db_explorer_harvest(db_name: str) -> dict[str, Any]:
    """Snapshot the IndexedDB database ``db_name`` of the current page: its stores, keys, indexes and records."""
    from je_web_runner.utils.indexed_db_explorer.explorer import build_harvest_script
    source = _run_script("WR_indexed_db_explorer_harvest", "return " + build_harvest_script(db_name))
    return to_plain(_idb_snapshot(source))


def indexed_db_explorer_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare two IndexedDB snapshots: stores added, stores removed and the record counts that changed."""
    from je_web_runner.utils.indexed_db_explorer.explorer import diff_snapshots
    return to_plain(diff_snapshots(_idb_snapshot(before), _idb_snapshot(after)))


def indexed_db_explorer_assert(
        snapshot: dict[str, Any], store: str | None = None, minimum: int = 0,
        maximum: int | None = None) -> dict[str, Any]:
    """Fail unless the snapshot's database exists and, with ``store``, that store is there and holds between
    ``minimum`` and ``maximum`` records. Raises IndexedDbExplorerError when a check fails."""
    from je_web_runner.utils.indexed_db_explorer import explorer
    parsed = _idb_snapshot(snapshot)
    explorer.assert_db_exists(parsed)
    count = None
    if store is not None:
        count = explorer.assert_record_count(parsed, store, minimum=minimum, maximum=maximum)
    return {"name": parsed.name, "stores": sorted(parsed.stores), "records": count}


def indexed_db_explorer_assert_record(
        snapshot: dict[str, Any], store: str, key: Any = None, index: str | None = None,
        record: dict[str, Any] | None = None) -> Any:
    """Fail unless ``store`` has the key ``key``, the index ``index`` and a record with every field of
    ``record`` (each one only when given); returns the matching record, if one was asked for.
    Raises IndexedDbExplorerError when a check fails."""
    from je_web_runner.utils.indexed_db_explorer import explorer
    parsed = _idb_snapshot(snapshot)
    explorer.assert_store_present(parsed, store)
    if key is not None:
        explorer.assert_key_present(parsed, store, key)
    if index is not None:
        explorer.assert_index_present(parsed, store, index)
    if record is None:
        return None
    return to_plain(explorer.assert_record_matching(
        parsed, store, lambda item: _has_fields(record, item), description=f"fields {record!r}",
    ))


def notifications_audit_install() -> bool:
    """Start recording the current page's ``Notification.requestPermission`` calls and shown notifications."""
    from je_web_runner.utils.notifications_audit.audit import build_install_script
    _run_script("WR_notifications_audit_install", build_install_script())
    return True


def notifications_audit_harvest() -> dict[str, Any]:
    """The notifications log recorded so far: ``{"permission_requests": [...], "notifications": [...]}``."""
    from je_web_runner.utils.notifications_audit.audit import HARVEST_SCRIPT, parse_log
    return to_plain(parse_log(_run_script("WR_notifications_audit_harvest", HARVEST_SCRIPT)))


def notifications_audit_assert(
        payload: dict[str, Any], require_gesture: bool = True, min_page_age_ms: float | None = None,
        no_spam_after_deny: bool = True, unique_tags: bool = False) -> dict[str, Any]:
    """Check a notifications log for policy violations: a permission prompt without a user gesture, a prompt
    before ``min_page_age_ms``, prompts or notifications after a denial, and (``unique_tags``) a reused tag.
    Raises NotificationsAuditError when a check fails; returns the normalised log."""
    from je_web_runner.utils.notifications_audit import audit
    log = audit.parse_log(payload)
    if require_gesture:
        audit.assert_no_prompt_without_gesture(log)
    if min_page_age_ms is not None:
        audit.assert_no_prompt_before(log, min_page_age_ms=min_page_age_ms)
    if no_spam_after_deny:
        audit.assert_no_spam_after_deny(log)
    if unique_tags:
        audit.assert_unique_tags(log)
    return to_plain(log)


def notifications_audit_assert_shown(
        payload: dict[str, Any], title_contains: str | None = None, body_contains: str | None = None,
        tag: str | None = None) -> dict[str, Any]:
    """Fail unless the log has a notification matching the given title text, body text and/or tag; returns it.
    Raises NotificationsAuditError when none matches or no filter was given."""
    from je_web_runner.utils.notifications_audit import audit
    return to_plain(audit.assert_notification_shown(
        audit.parse_log(payload), title_contains=title_contains, body_contains=body_contains, tag=tag,
    ))


def payment_request_assert_install(canned: dict[str, Any] | None = None) -> bool:
    """Replace the page's ``PaymentRequest`` with a recorder whose ``show()`` answers at once with ``canned``
    (``methodName``, ``details``, ``shippingAddress``, ``payerEmail``, ``canMakePayment`` ...)."""
    from je_web_runner.utils.payment_request_assert.payment import INSTALL_SCRIPT, PaymentRequestAssertError
    if canned is not None and not isinstance(canned, dict):
        raise PaymentRequestAssertError("canned must be an object")
    _run_script("WR_payment_request_assert_install", INSTALL_SCRIPT, canned or {})
    return True


def payment_request_assert_harvest() -> dict[str, Any]:
    """Read and empty the PaymentRequest recorder: ``{"constructed": [...], "completed": [{status}]}``."""
    return to_plain(_read_recorder("WR_payment_request_assert_harvest", _PAYMENT_HARVEST))


def payment_request_assert_check(
        payload: dict[str, Any], method: str | None = None, currency: str | None = None,
        completed: str | None = None, shipping_required: bool = False) -> dict[str, Any]:
    """Check a harvested payment log: a request offered payment ``method``, every total is in ``currency``,
    ``complete()`` was called with status ``completed`` (``success`` / ``fail`` / ``unknown``), and with
    ``shipping_required`` every request asked for shipping.
    Raises PaymentRequestAssertError when a check fails; returns the normalised log."""
    from je_web_runner.utils.payment_request_assert import payment
    log = payment.parse_log(payload)
    if method is not None:
        payment.assert_supports(log, method=method)
    if currency is not None:
        payment.assert_total_currency(log, currency=currency)
    if completed is not None:
        payment.assert_completed(log, status=completed)
    if shipping_required:
        payment.assert_shipping_required(log)
    return to_plain(log)


def pip_assert_install() -> bool:
    """Start recording the current page's Picture-in-Picture enter and exit calls (video and document)."""
    from je_web_runner.utils.pip_assert.pip import INSTALL_SCRIPT
    _run_script("WR_pip_assert_install", INSTALL_SCRIPT)
    return True


def pip_assert_harvest() -> list[dict[str, Any]]:
    """Read and empty the Picture-in-Picture recorder: ``[{"kind", "mode", "ts", "width", "height"}]``."""
    return to_plain(_read_recorder("WR_pip_assert_harvest", _PIP_HARVEST))


def pip_assert_check(
        payload: list[dict[str, Any]], mode: str = "video", entered: bool = True,
        exited_cleanly: bool = False, min_size: list[int] | None = None) -> dict[str, Any]:
    """Check harvested Picture-in-Picture events for ``mode`` (``video`` / ``document``): it was ``entered``,
    every enter has an exit (``exited_cleanly``), document windows are at least ``min_size`` ``[width, height]``.
    Raises PipAssertError when a check fails; returns the normalised events."""
    from je_web_runner.utils.pip_assert import pip
    log = pip.parse_log(payload)
    wanted = _member(pip.Mode, mode, pip.PipAssertError)
    if entered:
        pip.assert_entered(log, mode=wanted)
    if exited_cleanly:
        pip.assert_exited_cleanly(log, mode=wanted)
    if min_size is not None:
        if len(min_size) != 2:
            raise pip.PipAssertError("min_size must be [width, height]")
        pip.assert_size_at_least(log, min_width=min_size[0], min_height=min_size[1])
    return to_plain(log)


def popover_assert_harvest() -> list[dict[str, Any]]:
    """Describe every ``<dialog>`` and ``[popover]`` element of the current page: kind, id, open, modal, invoker."""
    from je_web_runner.utils.popover_assert.popover import HARVEST_SCRIPT, parse_snapshot
    return to_plain(parse_snapshot(_run_script("WR_popover_assert_harvest", "return " + HARVEST_SCRIPT)))


def popover_assert_check(
        snapshot: list[dict[str, Any]], open_id: str | None = None, closed_id: str | None = None,
        only_one_modal: bool = True, none_open: bool = False) -> list[dict[str, Any]]:
    """Check a popover / dialog snapshot: the element ``open_id`` is open, ``closed_id`` is not, at most one
    dialog is modal, and with ``none_open`` nothing is open at all.
    Raises PopoverAssertError when a check fails; returns the normalised snapshot."""
    from je_web_runner.utils.popover_assert import popover
    states = popover.parse_snapshot(snapshot)
    if open_id is not None:
        popover.assert_open(states, id_=open_id)
    if closed_id is not None:
        popover.assert_closed(states, id_=closed_id)
    if only_one_modal:
        popover.assert_only_one_modal(states)
    if none_open:
        popover.assert_no_open(states)
    return to_plain(states)


def popover_assert_invoker(snapshot: list[dict[str, Any]], popover_id: str, invoker_id: str) -> bool:
    """Fail unless the popover ``popover_id`` names ``invoker_id`` as its invoker (its ``data-invoker-id``).
    Raises PopoverAssertError when the popover is missing or points at another invoker."""
    from je_web_runner.utils.popover_assert import popover
    popover.assert_invoker_link(popover.parse_snapshot(snapshot), popover_id=popover_id, invoker_id=invoker_id)
    return True


def _speculation_rules(rules: list[dict[str, Any]] | None) -> list[Any]:
    from je_web_runner.utils.speculation_rules.rules import SpeculationRule, SpeculationRulesError
    return [
        SpeculationRule(
            source=_text(entry, "source", "list"), urls=tuple(entry.get("urls") or ()),
            where=entry.get("where"), eagerness=_text(entry, "eagerness", "moderate"),
        )
        for entry in _objects(rules, SpeculationRulesError, "rule")
    ]


def speculation_rules_build_tag(
        prefetch: list[dict[str, Any]] | None = None, prerender: list[dict[str, Any]] | None = None) -> str:
    """Render a ``<script type="speculationrules">`` tag from rules ``[{"source": "list", "urls": [...],
    "eagerness": "moderate"}]`` or ``[{"source": "document", "where": {...}}]``."""
    from je_web_runner.utils.speculation_rules.rules import build_script_tag
    return build_script_tag(_speculation_rules(prefetch), _speculation_rules(prerender))


def speculation_rules_install() -> bool:
    """Start recording the page's ``prerenderingchange`` events; the page counts events with ``__wr_spec_fire__``."""
    from je_web_runner.utils.speculation_rules.rules import INSTALL_LISTENER_SCRIPT
    _run_script("WR_speculation_rules_install", INSTALL_LISTENER_SCRIPT)
    return True


def speculation_rules_harvest() -> dict[str, Any]:
    """The prerender log recorded so far: ``{"events": [...], "fires": {name: count}}``."""
    from je_web_runner.utils.speculation_rules.rules import HARVEST_LOG_SCRIPT, parse_log
    return to_plain(parse_log(_run_script("WR_speculation_rules_harvest", HARVEST_LOG_SCRIPT)))


def speculation_rules_assert(
        payload: dict[str, Any], activated: bool = True, no_double_fire: list[str] | None = None,
        fire_counts: dict[str, int] | None = None) -> dict[str, Any]:
    """Check a prerender log: the page was ``activated`` after prerendering, none of the ``no_double_fire`` event
    names fired twice, and each name of ``fire_counts`` fired exactly that many times.
    Raises SpeculationRulesError when a check fails; returns the normalised log."""
    from je_web_runner.utils.speculation_rules import rules
    log = rules.parse_log(payload)
    if activated:
        rules.assert_activated(log)
    if no_double_fire is not None:
        rules.assert_no_double_fire(log, names=no_double_fire)
    for name, expected in (fire_counts or {}).items():
        rules.assert_fire_count(log, name=name, expected=expected)
    return to_plain(log)


def speech_api_assert_install() -> bool:
    """Record the page's ``speechSynthesis.speak`` calls and replace ``SpeechRecognition`` with a scripted mock."""
    from je_web_runner.utils.speech_api_assert.assertions import INSTALL_SCRIPT
    _run_script("WR_speech_api_assert_install", INSTALL_SCRIPT)
    return True


def speech_api_assert_push_transcript(text: str) -> bool:
    """Queue ``text`` as what the mocked ``SpeechRecognition`` hears on its next ``start()``."""
    return bool(_read_recorder("WR_speech_api_assert_push_transcript", _SPEECH_PUSH, text))


def speech_api_assert_harvest() -> list[dict[str, Any]]:
    """Read and empty the recorded utterances: ``[{"text", "lang", "rate", "pitch", "volume"}]``."""
    from je_web_runner.utils.speech_api_assert.assertions import parse_spoken
    return to_plain(parse_spoken(_read_recorder("WR_speech_api_assert_harvest", _SPEECH_HARVEST)))


def speech_api_assert_check(
        utterances: list[dict[str, Any]], text_contains: str | None = None, lang: str | None = None,
        no_speech: bool = False, volume_range: list[float] | None = None) -> list[dict[str, Any]]:
    """Check recorded utterances: one contains ``text_contains``, all that name a language use ``lang``, all
    volumes are inside ``volume_range`` ``[min, max]``; with ``no_speech`` fail when anything was spoken.
    Raises SpeechApiAssertError when a check fails; returns the normalised utterances."""
    from je_web_runner.utils.speech_api_assert import assertions
    spoken = assertions.parse_spoken(utterances)
    if no_speech:
        assertions.assert_no_speech(spoken)
    if text_contains is not None:
        assertions.assert_spoke(spoken, text_contains=text_contains)
    if lang is not None:
        assertions.assert_lang(spoken, expected_lang=lang)
    if volume_range is not None:
        if len(volume_range) != 2:
            raise assertions.SpeechApiAssertError("volume_range must be [min, max]")
        assertions.assert_within_volume(spoken, min_volume=volume_range[0], max_volume=volume_range[1])
    return to_plain(spoken)


def _sse_recorder(text: str | None = None) -> Any:
    """The shared recorder, or with ``text`` a fresh one that holds only that stream."""
    from je_web_runner.utils.sse_assert.stream import SseRecorder
    if text is not None:
        recorder = SseRecorder()
        recorder.feed(text)
        return recorder
    if "recorder" not in _SSE_STATE:
        _SSE_STATE["recorder"] = SseRecorder()
    return _SSE_STATE["recorder"]


def sse_assert_parse(text: str) -> list[dict[str, Any]]:
    """Parse Server-Sent Events wire text into ``[{"event", "data", "id", "retry", "timestamp"}]``."""
    from je_web_runner.utils.sse_assert.stream import parse_sse_stream
    return to_plain(parse_sse_stream(text))


def sse_assert_feed(chunk: str) -> dict[str, int]:
    """Add a chunk of an SSE stream to the recorder; an event counts once its closing blank line arrives."""
    recorder = _sse_recorder()
    parsed = recorder.feed(chunk)
    return {"parsed": parsed, "total": len(recorder)}


def sse_assert_events(event_type: str | None = None) -> list[dict[str, Any]]:
    """The events the recorder holds, optionally only those of ``event_type``."""
    return to_plain(_sse_recorder().events(event_type=event_type))


def sse_assert_reset() -> bool:
    """Empty the SSE recorder, including a half-received event."""
    _sse_recorder().clear()
    return True


def sse_assert_count(
        text: str | None = None, event_type: str | None = None, minimum: int = 1,
        maximum: int | None = None) -> int:
    """Fail unless the number of events (of ``event_type``, when given) is between ``minimum`` and ``maximum``.
    Checks the SSE wire ``text`` when given, otherwise what ``WR_sse_assert_feed`` recorded.
    Raises SseAssertError when the count is out of range; returns the count."""
    from je_web_runner.utils.sse_assert.stream import assert_event_count
    return assert_event_count(_sse_recorder(text), event_type=event_type, minimum=minimum, maximum=maximum)


def sse_assert_data(
        text: str | None = None, event_type: str | None = None, contains: str | None = None,
        json_keys: list[str] | None = None, increasing_ids: bool = False) -> dict[str, Any] | None:
    """Fail unless an event's data has the text ``contains``, an event's JSON data has every key of
    ``json_keys``, and (``increasing_ids``) the event ids only grow. Checks the SSE wire ``text`` when given,
    otherwise what ``WR_sse_assert_feed`` recorded. Raises SseAssertError when a check fails; returns the
    last event that matched."""
    from je_web_runner.utils.sse_assert import stream
    recorder = _sse_recorder(text)
    matched = None
    if contains is not None:
        matched = stream.assert_data_contains(recorder, contains, event_type=event_type)
    if json_keys is not None:
        matched = stream.assert_json_shape(recorder, json_keys, event_type=event_type)
    if increasing_ids:
        stream.assert_strictly_increasing_ids(recorder)
    return to_plain(matched)


def storage_buckets_harvest() -> dict[str, Any]:
    """Snapshot the current page's storage buckets: ``{"supported": bool, "buckets": [{name, idb_databases, ...}]}``."""
    from je_web_runner.utils.storage_buckets.buckets import HARVEST_SCRIPT, parse_snapshot
    return to_plain(parse_snapshot(_run_script("WR_storage_buckets_harvest", "return " + HARVEST_SCRIPT)))


def storage_buckets_assert(
        snapshot: dict[str, Any], supported: bool = True, bucket: str | None = None,
        durability: str | None = None, allowed: list[str] | None = None) -> dict[str, Any]:
    """Check a storage-buckets snapshot: the API is ``supported``, ``bucket`` exists (with ``durability``
    ``strict`` / ``relaxed`` when given), and no bucket outside ``allowed`` exists.
    Raises StorageBucketsError when a check fails; returns the normalised snapshot."""
    from je_web_runner.utils.storage_buckets import buckets
    report = buckets.parse_snapshot(snapshot)
    if supported:
        buckets.assert_supported(report)
    if bucket is not None:
        buckets.assert_bucket_present(report, name=bucket)
    if bucket is not None and durability is not None:
        buckets.assert_durability(report, name=bucket, expected=durability)
    if allowed is not None:
        buckets.assert_no_unexpected_buckets(report, allowed=allowed)
    return to_plain(report)


def storage_buckets_assert_isolated(snapshot: dict[str, Any], db_name: str, expected_bucket: str) -> bool:
    """Fail unless the IndexedDB database ``db_name`` lives in ``expected_bucket`` and in no other bucket.
    Raises StorageBucketsError when the database is missing there or also found elsewhere."""
    from je_web_runner.utils.storage_buckets import buckets
    buckets.assert_idb_isolated(buckets.parse_snapshot(snapshot), db_name=db_name, expected_bucket=expected_bucket)
    return True


_ADAPTERS: tuple[Callable[..., Any], ...] = (
    background_sync_assert_install, background_sync_assert_harvest, background_sync_assert_check,
    compression_streams_compress, compression_streams_decompress, compression_streams_assert_round_trip,
    compression_streams_assert_ratio, compute_pressure_assert,
    cookie_store_api_harvest, cookie_store_api_install_listener, cookie_store_api_changes,
    cookie_store_api_assert, cookie_store_api_assert_change,
    credential_management_install, credential_management_harvest, credential_management_assert,
    file_system_access_install, file_system_access_harvest, file_system_access_assert,
    indexed_db_explorer_harvest, indexed_db_explorer_diff, indexed_db_explorer_assert,
    indexed_db_explorer_assert_record,
    notifications_audit_install, notifications_audit_harvest, notifications_audit_assert,
    notifications_audit_assert_shown,
    payment_request_assert_install, payment_request_assert_harvest, payment_request_assert_check,
    pip_assert_install, pip_assert_harvest, pip_assert_check,
    popover_assert_harvest, popover_assert_check, popover_assert_invoker,
    speculation_rules_build_tag, speculation_rules_install, speculation_rules_harvest, speculation_rules_assert,
    speech_api_assert_install, speech_api_assert_push_transcript, speech_api_assert_harvest,
    speech_api_assert_check,
    sse_assert_parse, sse_assert_feed, sse_assert_events, sse_assert_reset, sse_assert_count, sse_assert_data,
    storage_buckets_harvest, storage_buckets_assert, storage_buckets_assert_isolated,
)

# Every adapter is named after its command: ``sse_assert_feed`` is ``WR_sse_assert_feed``.
WEB_PLATFORM_A_COMMANDS: dict[str, Callable[..., Any]] = {f"WR_{adapter.__name__}": adapter for adapter in _ADAPTERS}

PYTHON_ONLY: dict[str, str] = {
    "cross_tab_sync": "Every helper takes live Playwright Page objects, one per tab, and the waits take matcher "
                      "callables; an action file has no JSON value for either.",
}
NETWORK_COMMANDS: frozenset[str] = frozenset()
