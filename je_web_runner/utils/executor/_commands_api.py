"""
API 測試類函式庫的命令轉接層（一）
Command adapters for the API-testing libraries, part one: contracts and OpenAPI, GraphQL, gRPC,
idempotency, pagination and rate limits. Each ``WR_*`` command takes JSON values, builds what the library
needs and returns JSON values. Part two is ``_commands_api_2.py``.
"""
# pylint: disable=import-outside-toplevel,too-many-arguments,too-many-positional-arguments
# Each library is imported inside its adapter so that importing je_web_runner stays fast. The project's
# parameter limit is 7 (S107), and an action file passes a command's arguments by name.
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor._command_helpers import to_plain

_STATE: dict[str, Any] = {}


def _json_argument(value: Any, path: str | None, label: str) -> Any:
    """``value`` when it is given, otherwise the JSON document stored at ``path``."""
    if value is not None:
        return value
    if path is None:
        raise WebRunnerException(f"{label}: give the document itself or the path of its JSON file")
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------- api_version_compat -------------------------------------------------
def _field_specs(fields: list[dict[str, Any]] | None) -> list[Any]:
    from je_web_runner.utils.api_version_compat.compat import FieldSpec
    return [
        FieldSpec(str(item.get("name", "")), str(item.get("type", "string")), bool(item.get("required", True)))
        for item in fields or []
    ]


def _contract(
        endpoint: str, response_fields: list[dict[str, Any]] | None = None,
        request_fields: list[dict[str, Any]] | None = None,
) -> Any:
    from je_web_runner.utils.api_version_compat.compat import ApiContract
    return ApiContract(endpoint, _field_specs(response_fields), _field_specs(request_fields))


def _matrix_rows(rows: list[dict[str, Any]]) -> list[Any]:
    from je_web_runner.utils.api_version_compat.compat import CompatMatrixRow
    return [
        CompatMatrixRow(
            client_version=str(row.get("client_version", "")),
            server_version=str(row.get("server_version", "")),
            passed=bool(row.get("passed", False)),
            notes=str(row.get("notes", "")),
        )
        for row in rows
    ]


def api_version_compat_check_response(
        endpoint: str, response_fields: list[dict[str, Any]], response: dict[str, Any],
) -> dict[str, Any]:
    """
    Check a new server's response against the fields an old client reads, without failing the run.

    ``response_fields`` is a list of ``{"name", "type", "required"}``; ``type`` is one of string, integer,
    number, boolean, object, array. Returns ``{"endpoint", "passed", "error"}``.
    """
    from je_web_runner.utils.api_version_compat.compat import ApiVersionCompatError, assert_response_compatible
    try:
        assert_response_compatible(_contract(endpoint, response_fields=response_fields), response)
    except ApiVersionCompatError as error:
        return {"endpoint": endpoint, "passed": False, "error": str(error)}
    return {"endpoint": endpoint, "passed": True, "error": ""}


def api_version_compat_assert_response(
        endpoint: str, response_fields: list[dict[str, Any]], response: dict[str, Any],
) -> bool:
    """Fail when a new server's response drops or retypes a field the old client reads."""
    from je_web_runner.utils.api_version_compat.compat import assert_response_compatible
    assert_response_compatible(_contract(endpoint, response_fields=response_fields), response)
    return True


def api_version_compat_assert_request(
        endpoint: str, request_fields: list[dict[str, Any]], server_required_fields: list[str],
) -> bool:
    """Fail when the new server requires a request field the old client never sends."""
    from je_web_runner.utils.api_version_compat.compat import assert_request_compatible
    assert_request_compatible(_contract(endpoint, request_fields=request_fields), server_required_fields)
    return True


def api_version_compat_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarise client/server rows (``client_version``, ``server_version``, ``passed``, ``notes``)."""
    from je_web_runner.utils.api_version_compat.compat import matrix_summary
    return to_plain(matrix_summary(_matrix_rows(rows)))


def api_version_compat_assert_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fail when any client/server combination of the matrix did not pass; returns the summary."""
    from je_web_runner.utils.api_version_compat.compat import assert_full_matrix_passes, matrix_summary
    parsed = _matrix_rows(rows)
    assert_full_matrix_passes(parsed)
    return to_plain(matrix_summary(parsed))


# ---------- graphql_n_plus_1 ---------------------------------------------------
def _n_plus_1_findings(rows: list[dict[str, Any]], threshold: int, include_cartesian: bool) -> list[Any]:
    from je_web_runner.utils.graphql_n_plus_1.detect import detect, detect_cartesian, parse_rows
    parsed = parse_rows(rows)
    findings = detect(parsed, threshold=threshold)
    if include_cartesian:
        findings.extend(detect_cartesian(parsed))
    return findings


def graphql_n_plus_1_detect(
        rows: list[dict[str, Any]], threshold: int = 5, include_cartesian: bool = True,
) -> list[dict[str, Any]]:
    """
    Find N+1 query patterns in the backend queries of one GraphQL request.

    ``rows`` is a list of ``{"operation", "sql", "ms", "parent_field"}``; a query template repeated
    ``threshold`` times under one field is a finding (an error from twice the threshold).
    """
    return to_plain(_n_plus_1_findings(rows, threshold, include_cartesian))


def graphql_n_plus_1_assert(rows: list[dict[str, Any]], threshold: int = 5) -> list[dict[str, Any]]:
    """Fail when the query rows contain an error-level N+1 pattern; returns the findings otherwise."""
    from je_web_runner.utils.graphql_n_plus_1.detect import assert_no_n_plus_1
    findings = _n_plus_1_findings(rows, threshold, True)
    assert_no_n_plus_1(findings)
    return to_plain(findings)


def graphql_n_plus_1_report(rows: list[dict[str, Any]], threshold: int = 5) -> str:
    """Render the N+1 findings of the query rows as a Markdown section."""
    from je_web_runner.utils.graphql_n_plus_1.detect import report_markdown
    return report_markdown(_n_plus_1_findings(rows, threshold, True))


# ---------- grpc_streaming_assert ----------------------------------------------
def _stream_record(record: dict[str, Any]) -> Any:
    from je_web_runner.utils.grpc_streaming_assert.assertions import parse_record
    return parse_record(record)


def grpc_streaming_assert_parse(record: dict[str, Any]) -> dict[str, Any]:
    """
    Normalise a captured gRPC stream record.

    ``record`` has ``method``, ``mode`` (unary, server_stream, client_stream, bidi), ``status``, ``frames``
    (``payload_size``, ``body``, ``ts_ms``, ``direction`` in/out), ``half_closed_ts_ms`` and ``duration_ms``.
    """
    return to_plain(_stream_record(record))


def grpc_streaming_assert_status(record: dict[str, Any], expected: str = "OK") -> bool:
    """Fail when the stream did not end with the ``expected`` status (for example OK or CANCELLED)."""
    from je_web_runner.utils.grpc_streaming_assert.assertions import (
        GrpcStreamingAssertError, StatusCode, assert_status,
    )
    try:
        status = StatusCode(expected)
    except ValueError as error:
        raise GrpcStreamingAssertError(f"unknown status {expected!r}") from error
    assert_status(_stream_record(record), status)
    return True


def grpc_streaming_assert_frames(
        record: dict[str, Any], min_count: int = 0, max_count: int | None = None,
        max_bytes: int | None = None, direction: str = "in",
) -> int:
    """
    Fail when the number of frames in ``direction`` is outside ``min_count``..``max_count`` or a frame is
    larger than ``max_bytes``; returns the number of frames in that direction.
    """
    from je_web_runner.utils.grpc_streaming_assert.assertions import (
        assert_frame_count_between, assert_max_frame_size,
    )
    parsed = _stream_record(record)
    upper = sys.maxsize if max_count is None else max_count
    assert_frame_count_between(parsed, min_count=min_count, max_count=upper, direction=direction)
    if max_bytes is not None:
        assert_max_frame_size(parsed, max_bytes=max_bytes)
    return len(parsed.inbound if direction == "in" else parsed.outbound)


def grpc_streaming_assert_order(
        record: dict[str, Any], key: str, expected: list[Any], direction: str = "in",
) -> bool:
    """Fail when the ``key`` of the frame bodies, in arrival order, is not the ``expected`` list."""
    from je_web_runner.utils.grpc_streaming_assert.assertions import assert_frames_in_order
    assert_frames_in_order(_stream_record(record), key=key, expected=expected, direction=direction)
    return True


def grpc_streaming_assert_half_close(record: dict[str, Any]) -> bool:
    """Fail when a bidi stream's client did not half-close before the server's last frame."""
    from je_web_runner.utils.grpc_streaming_assert.assertions import assert_half_close_before_final
    assert_half_close_before_final(_stream_record(record))
    return True


# ---------- grpc_tester --------------------------------------------------------
def _grpc_recorder() -> Any:
    from je_web_runner.utils.grpc_tester.client import GrpcCallRecorder
    if "grpc_tester" not in _STATE:
        _STATE["grpc_tester"] = GrpcCallRecorder()
    return _STATE["grpc_tester"]


def _grpc_status(value: Any) -> Any:
    from je_web_runner.utils.grpc_tester.client import GrpcStatus, GrpcTesterError
    try:
        return GrpcStatus[value] if isinstance(value, str) else GrpcStatus(value)
    except (KeyError, ValueError) as error:
        raise GrpcTesterError(f"unknown gRPC status {value!r}") from error


def _grpc_call(call: dict[str, Any]) -> Any:
    from je_web_runner.utils.grpc_tester.client import GrpcCall
    return GrpcCall(
        method=str(call.get("method", "")),
        request=call.get("request"),
        response=call.get("response"),
        status=_grpc_status(call.get("status", "OK")),
        duration_ms=float(call.get("duration_ms") or 0),
        metadata={str(name): str(value) for name, value in (call.get("metadata") or {}).items()},
        error=call.get("error"),
    )


def _from_base64(text: str) -> bytes:
    from je_web_runner.utils.grpc_tester.client import GrpcTesterError
    try:
        return base64.b64decode(text, validate=True)
    except ValueError as error:
        raise GrpcTesterError(f"not base64: {error}") from error


def grpc_tester_encode_message(payload_base64: str) -> str:
    """Frame a base64 message as a gRPC-Web body (flag byte and length prefix); returns base64."""
    from je_web_runner.utils.grpc_tester.client import encode_grpc_web_message
    return base64.b64encode(encode_grpc_web_message(_from_base64(payload_base64))).decode("ascii")


def grpc_tester_decode_message(framed_base64: str) -> list[dict[str, Any]]:
    """
    Split a base64 gRPC-Web body into its frames.

    Each frame is ``{"flag", "payload_base64", "trailer"}``; ``trailer`` holds ``grpc-status`` and
    ``grpc-message`` for a trailer frame and is ``null`` for a message frame.
    """
    from je_web_runner.utils.grpc_tester.client import decode_grpc_web_message, parse_trailer
    return [
        {
            "flag": flag,
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "trailer": parse_trailer(payload) if flag & 0x80 else None,
        }
        for flag, payload in decode_grpc_web_message(_from_base64(framed_base64))
    ]


def grpc_tester_record(call: dict[str, Any]) -> dict[str, Any]:
    """
    Add one observed gRPC call to the recorder that ``WR_grpc_tester_assert_called`` reads.

    ``call`` has ``method``, ``request``, ``response``, ``status`` (name such as OK or NOT_FOUND, or the
    number), ``duration_ms``, ``metadata`` and ``error``.
    """
    record = _grpc_call(call)
    _grpc_recorder().record(record)
    return to_plain(record)


def grpc_tester_assert_call(call: dict[str, Any], expected_status: str = "OK") -> dict[str, Any]:
    """Fail when the observed gRPC ``call`` did not end with ``expected_status``."""
    from je_web_runner.utils.grpc_tester.client import GrpcStatus, assert_call_fails, assert_call_ok
    record = _grpc_call(call)
    status = _grpc_status(expected_status)
    if status == GrpcStatus.OK:
        assert_call_ok(record)
    else:
        assert_call_fails(record, status=status)
    return to_plain(record)


def grpc_tester_assert_called(method: str, minimum: int = 1) -> int:
    """Fail when fewer than ``minimum`` recorded calls went to ``method``; returns how many did."""
    from je_web_runner.utils.grpc_tester.client import assert_called
    return assert_called(_grpc_recorder(), method, minimum=minimum)


def grpc_tester_reset() -> int:
    """Forget the recorded gRPC calls; returns how many were dropped."""
    recorder = _grpc_recorder()
    dropped = len(recorder)
    recorder.clear()
    return dropped


# ---------- har_to_openapi -----------------------------------------------------
def har_to_openapi_convert(har: dict[str, Any] | None = None, har_path: str | None = None) -> dict[str, Any]:
    """Draft an OpenAPI 3.1 document from a HAR (the object itself, or the path of a ``.har`` file)."""
    from je_web_runner.utils.har_to_openapi.converter import convert
    return to_plain(convert(_json_argument(har, har_path, "har")))


def har_to_openapi_assert_coverage(
        min_paths: int, har: dict[str, Any] | None = None, har_path: str | None = None,
) -> int:
    """Fail when the HAR yields fewer than ``min_paths`` API paths; returns the number of paths."""
    from je_web_runner.utils.har_to_openapi.converter import assert_spec_minimum_coverage, convert
    spec = convert(_json_argument(har, har_path, "har"))
    assert_spec_minimum_coverage(spec, min_paths=min_paths)
    return len(spec["paths"])


# ---------- idempotency_check --------------------------------------------------
def _idempotency_report(
        first: dict[str, Any], second: dict[str, Any],
        allow_status_change_to: list[int] | None, ignore_body_keys: list[str] | None,
) -> Any:
    from je_web_runner.utils.idempotency_check.check import IdemResponse, check
    recorded = iter((first, second))

    def replay() -> Any:
        raw = next(recorded)
        return IdemResponse(
            status_code=int(raw.get("status_code", 0)),
            body=raw.get("body"),
            side_effect_count=int(raw.get("side_effect_count", 0)),
        )

    return check(
        replay, allow_status_change_to=allow_status_change_to, ignore_body_keys=ignore_body_keys or (),
    )


def idempotency_check_compare(
        first: dict[str, Any], second: dict[str, Any],
        allow_status_change_to: list[int] | None = None, ignore_body_keys: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compare the responses of the same request sent twice.

    ``first`` and ``second`` are ``{"status_code", "body", "side_effect_count"}``, for example what two
    ``WR_http_*`` calls returned. ``allow_status_change_to`` lists statuses the repeat may answer with
    (409, 304); ``ignore_body_keys`` names body fields that legitimately differ. Returns the report with
    ``violations`` and ``passed``.
    """
    return to_plain(_idempotency_report(first, second, allow_status_change_to, ignore_body_keys))


def idempotency_check_assert(
        first: dict[str, Any], second: dict[str, Any],
        allow_status_change_to: list[int] | None = None, ignore_body_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Fail when the repeated request's response differs from the first one; returns the report."""
    from je_web_runner.utils.idempotency_check.check import assert_idempotent
    report = _idempotency_report(first, second, allow_status_change_to, ignore_body_keys)
    assert_idempotent(report)
    return to_plain(report)


def idempotency_check_key(parts: list[Any]) -> str:
    """Build a stable ``Idempotency-Key`` value (SHA-256 hex) from ``parts`` such as user id and amount."""
    from je_web_runner.utils.idempotency_check.check import generate_idempotency_key
    return generate_idempotency_key(*parts)


# ---------- openapi_drift ------------------------------------------------------
def _drift_report(observations: list[dict[str, Any]], spec: dict[str, Any] | None, spec_path: str | None) -> Any:
    from je_web_runner.utils.openapi_drift.drift import ApiObservation, diff
    observed = [
        ApiObservation(
            method=str(item.get("method", "GET")),
            path=str(item.get("path", "")),
            status_code=int(item.get("status_code", 200)),
            count=int(item.get("count", 1)),
        )
        for item in observations
    ]
    return diff(_json_argument(spec, spec_path, "spec"), observed)


def openapi_drift_diff(
        observations: list[dict[str, Any]], spec: dict[str, Any] | None = None, spec_path: str | None = None,
) -> dict[str, Any]:
    """
    Compare observed API traffic with an OpenAPI document (the object, or the path of its JSON file).

    ``observations`` is a list of ``{"method", "path", "status_code"}``. Returns the endpoints, methods and
    statuses that are ``undocumented`` and the documented operations never seen (``zombie``).
    """
    return to_plain(_drift_report(observations, spec, spec_path))


def openapi_drift_assert(
        observations: list[dict[str, Any]], spec: dict[str, Any] | None = None,
        spec_path: str | None = None, max_zombies: int | None = None,
) -> dict[str, Any]:
    """
    Fail when the traffic used an endpoint or method the OpenAPI document does not declare, and, when
    ``max_zombies`` is given, when more documented operations than that were never seen.
    """
    from je_web_runner.utils.openapi_drift.drift import assert_no_undocumented, assert_no_zombies
    report = _drift_report(observations, spec, spec_path)
    assert_no_undocumented(report)
    if max_zombies is not None:
        assert_no_zombies(report, max_zombies=max_zombies)
    return to_plain(report)


# ---------- openapi_to_e2e -----------------------------------------------------
def _generated_tests(
        spec: dict[str, Any] | None, spec_path: str | None, include_negative: bool,
        method_filter: list[str] | None, path_prefix_filter: str | None,
) -> Any:
    from je_web_runner.utils.openapi_to_e2e.generator import (
        OpenAPIGeneratorError, generate_tests_from_spec, load_spec,
    )
    if spec is None and spec_path is None:
        raise OpenAPIGeneratorError("give the OpenAPI document as spec or the path of its file as spec_path")
    return generate_tests_from_spec(
        spec if spec is not None else load_spec(str(spec_path)),
        include_negative=include_negative,
        method_filter=method_filter,
        path_prefix_filter=path_prefix_filter,
    )


def openapi_to_e2e_generate(
        spec: dict[str, Any] | None = None, spec_path: str | None = None, include_negative: bool = True,
        method_filter: list[str] | None = None, path_prefix_filter: str | None = None,
) -> dict[str, Any]:
    """
    Generate ``WR_http_*`` action lists from an OpenAPI 3 / Swagger 2 document.

    Give the document as ``spec`` or a JSON / YAML file as ``spec_path``. Each generated test has ``name``,
    ``scenario`` (happy, missing_body, bad_path_param), ``expected_status`` and ``actions``.
    """
    return to_plain(_generated_tests(spec, spec_path, include_negative, method_filter, path_prefix_filter))


def openapi_to_e2e_write(
        output_dir: str, spec: dict[str, Any] | None = None, spec_path: str | None = None,
        include_negative: bool = True, method_filter: list[str] | None = None,
        path_prefix_filter: str | None = None,
) -> list[str]:
    """Generate the tests of an OpenAPI document and write one action file per test into ``output_dir``."""
    from je_web_runner.utils.openapi_to_e2e.generator import write_tests_to_dir
    result = _generated_tests(spec, spec_path, include_negative, method_filter, path_prefix_filter)
    return to_plain(write_tests_to_dir(result, output_dir))


# ---------- pagination_audit ---------------------------------------------------
def _item_key(item: Any, key: str | None) -> Any:
    value = item.get(key) if key and isinstance(item, dict) else item
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _pagination_findings(pages: list[dict[str, Any]], key: str | None, max_pages: int) -> Any:
    from je_web_runner.utils.pagination_audit.audit import Page, walk_all_pages
    recorded = iter(pages)

    def replay(_cursor: Any) -> Any:
        raw = next(recorded)
        return Page(items=list(raw.get("items") or []), next_cursor=raw.get("next_cursor"))

    # Never ask for more pages than were recorded: a last page that still has a cursor is "not terminated".
    limit = min(max_pages, max(len(pages), 1))
    fetcher: Any = replay
    return walk_all_pages(fetcher, lambda item: _item_key(item, key), max_pages=limit)


def pagination_audit_walk(
        pages: list[dict[str, Any]], key: str | None = "id", max_pages: int = 1000,
) -> dict[str, Any]:
    """
    Audit recorded API pages for duplicates, empty pages and a repeated cursor.

    ``pages`` is the list of fetched pages in order, each ``{"items", "next_cursor"}`` with ``next_cursor``
    ``null`` on the last. ``key`` names the field that identifies an item (``null`` compares whole items).
    """
    findings = _pagination_findings(pages, key, max_pages)
    return {**to_plain(findings), "passed": findings.passed()}


def pagination_audit_assert(
        pages: list[dict[str, Any]], key: str | None = "id", expected_total: int | None = None,
        sorted_by_key: bool = False, reverse: bool = False,
) -> dict[str, Any]:
    """
    Fail when the recorded pages repeat an item or a cursor, when the number of distinct items is not
    ``expected_total``, or, with ``sorted_by_key``, when the ``key`` values are not in order across pages.
    """
    from je_web_runner.utils.pagination_audit.audit import assert_clean, assert_expected_total, assert_sorted_by
    findings = _pagination_findings(pages, key, len(pages) or 1)
    assert_clean(findings)
    if expected_total is not None:
        assert_expected_total(findings, expected_total=expected_total)
    if sorted_by_key:
        assert_sorted_by(findings, lambda item_key: item_key, reverse=reverse)
    return {**to_plain(findings), "passed": True}


# ---------- rate_limit_assert --------------------------------------------------
def _rate_response(raw: dict[str, Any]) -> Any:
    from je_web_runner.utils.rate_limit_assert.rate import RateLimitResponse
    return RateLimitResponse(
        status_code=int(raw.get("status_code", 0)),
        headers={str(name): str(value) for name, value in (raw.get("headers") or {}).items()},
        body=raw.get("body"),
    )


def _rate_summary(response: Any) -> dict[str, Any]:
    return {
        "status_code": response.status_code,
        "is_429": response.is_429,
        "retry_after_seconds": response.retry_after_seconds,
        "limit": response.limit,
        "remaining": response.remaining,
    }


def rate_limit_assert_summary(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Read the rate-limit signals of a burst of responses (``{"status_code", "headers"}`` each): whether it
    is a 429, ``Retry-After`` seconds, ``X-RateLimit-Limit`` and ``X-RateLimit-Remaining``.
    """
    return [_rate_summary(_rate_response(raw)) for raw in responses]


def rate_limit_assert_burst(
        responses: list[dict[str, Any]], after: int, require_retry_after: bool = True,
) -> dict[str, Any]:
    """
    Fail when no 429 follows the first ``after`` responses of a burst, when ``X-RateLimit-Remaining`` goes
    up, or (unless ``require_retry_after`` is false) when the 429 has no positive ``Retry-After``.
    Returns the signals of the 429 response.
    """
    from je_web_runner.utils.rate_limit_assert.rate import (
        assert_429_after_burst, assert_remaining_monotonic, assert_retry_after_present,
    )
    parsed = [_rate_response(raw) for raw in responses]
    limited = assert_429_after_burst(parsed, after=after)
    assert_remaining_monotonic(parsed)
    if require_retry_after:
        assert_retry_after_present(limited)
    return _rate_summary(limited)


def rate_limit_assert_recovery(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Fail when the request sent after waiting out a 429's ``Retry-After`` is answered with 429 again."""
    from je_web_runner.utils.rate_limit_assert.rate import assert_recovery_after_retry_after
    assert_recovery_after_retry_after(before=_rate_response(before), after=_rate_response(after))
    return True


# ---------- contract_testing ---------------------------------------------------
def contract_testing_validate(response_body: Any, schema: dict[str, Any]) -> dict[str, Any]:
    """Validate a response body against a JSON schema subset; returns ``{"valid", "errors"}``."""
    from je_web_runner.utils.contract_testing.contract import validate_response
    return to_plain(validate_response(response_body, schema))


def contract_testing_validate_openapi(
        response_body: Any, path: str, method: str, status: int,
        openapi_doc: dict[str, Any] | None = None, openapi_path: str | None = None,
) -> dict[str, Any]:
    """
    Validate a response body against the schema an OpenAPI 3 document (the object, or the path of its JSON
    file) declares for ``method`` ``path`` and ``status``; returns ``{"valid", "errors"}``.
    """
    from je_web_runner.utils.contract_testing.contract import validate_against_openapi
    document = _json_argument(openapi_doc, openapi_path, "openapi_doc")
    return to_plain(validate_against_openapi(response_body, document, path, method, status))


def contract_testing_assert(response_body: Any, schema: dict[str, Any]) -> bool:
    """Fail when a response body does not match the JSON schema."""
    from je_web_runner.utils.contract_testing.contract import assert_valid
    assert_valid(response_body, schema)
    return True


# ---------- graphql ------------------------------------------------------------
def _graphql_client(endpoint: str, headers: dict[str, str] | None, timeout: float) -> Any:
    from je_web_runner.utils.graphql.client import GraphQLClient
    return GraphQLClient(endpoint=endpoint, headers=dict(headers or {}), timeout=timeout)


def graphql_execute(
        endpoint: str, query: str, variables: dict[str, Any] | None = None,
        operation_name: str | None = None, headers: dict[str, str] | None = None, timeout: float = 10.0,
) -> dict[str, Any]:
    """
    Send a GraphQL query or mutation to ``endpoint`` and return the response envelope.

    Fails when the response carries ``errors`` or the request cannot be sent.
    """
    client = _graphql_client(endpoint, headers, timeout)
    return to_plain(client.execute(query, variables=variables, operation_name=operation_name))


def graphql_introspect_types(
        endpoint: str, headers: dict[str, str] | None = None, timeout: float = 10.0,
) -> list[str]:
    """Run the introspection query on ``endpoint`` and return the names of the schema's types."""
    from je_web_runner.utils.graphql.client import introspect_types
    return to_plain(introspect_types(_graphql_client(endpoint, headers, timeout).introspect()))


def graphql_extract_field(payload: dict[str, Any], path: str) -> Any:
    """Read a value from a GraphQL response's ``data`` with a path such as ``user.posts[0].title``."""
    from je_web_runner.utils.graphql.client import extract_field
    return to_plain(extract_field(payload, path))


def graphql_assert_field(payload: dict[str, Any], path: str, expected: Any) -> Any:
    """Fail when the value at ``path`` of a GraphQL response's ``data`` is not ``expected``."""
    from je_web_runner.utils.graphql.client import GraphQLError, extract_field
    actual = extract_field(payload, path)
    if actual != expected:
        raise GraphQLError(f"field {path!r} is {actual!r}, expected {expected!r}")
    return to_plain(actual)


API_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_api_version_compat_check_response": api_version_compat_check_response,
    "WR_api_version_compat_assert_response": api_version_compat_assert_response,
    "WR_api_version_compat_assert_request": api_version_compat_assert_request,
    "WR_api_version_compat_matrix": api_version_compat_matrix,
    "WR_api_version_compat_assert_matrix": api_version_compat_assert_matrix,
    "WR_graphql_n_plus_1_detect": graphql_n_plus_1_detect,
    "WR_graphql_n_plus_1_assert": graphql_n_plus_1_assert,
    "WR_graphql_n_plus_1_report": graphql_n_plus_1_report,
    "WR_grpc_streaming_assert_parse": grpc_streaming_assert_parse,
    "WR_grpc_streaming_assert_status": grpc_streaming_assert_status,
    "WR_grpc_streaming_assert_frames": grpc_streaming_assert_frames,
    "WR_grpc_streaming_assert_order": grpc_streaming_assert_order,
    "WR_grpc_streaming_assert_half_close": grpc_streaming_assert_half_close,
    "WR_grpc_tester_encode_message": grpc_tester_encode_message,
    "WR_grpc_tester_decode_message": grpc_tester_decode_message,
    "WR_grpc_tester_record": grpc_tester_record,
    "WR_grpc_tester_assert_call": grpc_tester_assert_call,
    "WR_grpc_tester_assert_called": grpc_tester_assert_called,
    "WR_grpc_tester_reset": grpc_tester_reset,
    "WR_har_to_openapi_convert": har_to_openapi_convert,
    "WR_har_to_openapi_assert_coverage": har_to_openapi_assert_coverage,
    "WR_idempotency_check_compare": idempotency_check_compare,
    "WR_idempotency_check_assert": idempotency_check_assert,
    "WR_idempotency_check_key": idempotency_check_key,
    "WR_openapi_drift_diff": openapi_drift_diff,
    "WR_openapi_drift_assert": openapi_drift_assert,
    "WR_openapi_to_e2e_generate": openapi_to_e2e_generate,
    "WR_openapi_to_e2e_write": openapi_to_e2e_write,
    "WR_pagination_audit_walk": pagination_audit_walk,
    "WR_pagination_audit_assert": pagination_audit_assert,
    "WR_rate_limit_assert_summary": rate_limit_assert_summary,
    "WR_rate_limit_assert_burst": rate_limit_assert_burst,
    "WR_rate_limit_assert_recovery": rate_limit_assert_recovery,
    "WR_contract_testing_validate": contract_testing_validate,
    "WR_contract_testing_validate_openapi": contract_testing_validate_openapi,
    "WR_contract_testing_assert": contract_testing_assert,
    "WR_graphql_execute": graphql_execute,
    "WR_graphql_introspect_types": graphql_introspect_types,
    "WR_graphql_extract_field": graphql_extract_field,
    "WR_graphql_assert_field": graphql_assert_field,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset({
    "WR_graphql_execute",
    "WR_graphql_introspect_types",
})
