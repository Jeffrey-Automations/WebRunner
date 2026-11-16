"""Tests for the API-theme command adapters (``_commands_api.py`` and ``_commands_api_2.py``)."""
from __future__ import annotations

import base64
import json
import smtplib
import time
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor import _commands_api as api
from je_web_runner.utils.executor import _commands_api_2 as api2

PACKAGES_ONE = (
    "api_version_compat", "graphql_n_plus_1", "grpc_streaming_assert", "grpc_tester", "har_to_openapi",
    "idempotency_check", "openapi_drift", "openapi_to_e2e", "pagination_audit", "rate_limit_assert",
    "contract_testing", "graphql",
)
PACKAGES_TWO = (
    "api_mock", "har_replay", "mock_services", "email_deliverability", "email_render",
    "inbox_render_outlook", "mq_assert", "otp_interceptor", "push_delivery", "slack_digest",
    "webhook_receiver",
)

HAR = {"log": {"entries": [
    {
        "request": {"method": "GET", "url": "https://api.test/users/42?verbose=1"},
        "response": {
            "status": 200, "headers": [],
            "content": {"mimeType": "application/json", "text": '{"id": 42, "name": "Ann"}'},
        },
    },
    {
        "request": {"method": "POST", "url": "https://api.test/orders"},
        "response": {"status": 201, "headers": [], "content": {"text": '{"ok": true}'}},
    },
]}}

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Shop"},
    "servers": [{"url": "https://api.test"}],
    "paths": {
        "/users/{id}": {"get": {
            "operationId": "getUser",
            "parameters": [{"name": "id", "in": "path", "schema": {"type": "integer"}}],
            "responses": {"200": {"content": {"application/json": {"schema": {
                "type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}},
            }}}}},
        }},
        "/orders": {"post": {"responses": {"201": {}}}},
    },
}

RAW_MAIL = (
    "Authentication-Results: mx.test; spf=pass; dkim=pass; dmarc=pass policy.dmarc=reject\r\n"
    "DKIM-Signature: v=1; a=rsa-sha256\r\n"
    "List-Unsubscribe: <https://x.test/u>\r\n"
    "List-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n"
    "Subject: Welcome aboard\r\n"
    "\r\nbody\r\n"
)

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http(url: str, data: bytes | None = None, headers: dict | None = None) -> tuple[int, str]:
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with _OPENER.open(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


@pytest.fixture(autouse=True)
def _clean_state():
    def reset() -> None:
        api.grpc_tester_reset()
        api2.api_mock_reset()
        api2.har_replay_stop()
        api2.mock_services_stop()
        api2.webhook_receiver_stop()
    reset()
    yield
    reset()


# ---------- tables ---------------------------------------------------------------

@pytest.mark.parametrize("module, commands, packages", [
    (api, api.API_COMMANDS, PACKAGES_ONE),
    (api2, api2.API_2_COMMANDS, PACKAGES_TWO),
])
def test_tables_are_consistent(module, commands, packages):
    covered = set(module.PYTHON_ONLY)
    for name, function in commands.items():
        owners = [package for package in packages if name.startswith(f"WR_{package}_")]
        assert owners, name
        assert name == name.lower().replace("wr_", "WR_", 1)
        assert callable(function) and (function.__doc__ or "").strip(), name
        covered.update(owners)
    assert covered == set(packages)
    assert module.NETWORK_COMMANDS <= set(commands)
    assert all(reason.strip() for reason in module.PYTHON_ONLY.values())


def test_the_two_modules_do_not_share_a_command_name():
    assert not set(api.API_COMMANDS) & set(api2.API_2_COMMANDS)


# ---------- api_version_compat ---------------------------------------------------

def test_api_version_compat_response():
    fields = [{"name": "id", "type": "integer"}, {"name": "nick", "type": "string", "required": False}]
    good = api.api_version_compat_check_response("/users", fields, {"id": 1})
    assert good == {"endpoint": "/users", "passed": True, "error": ""}
    bad = api.api_version_compat_check_response("/users", fields, {"id": "1"})
    assert bad["passed"] is False and "old client expects integer" in bad["error"]
    json.dumps(bad)
    assert api.api_version_compat_assert_response("/users", fields, {"id": 1}) is True
    with pytest.raises(WebRunnerException):
        api.api_version_compat_assert_response("/users", fields, {})


def test_api_version_compat_request_and_matrix():
    fields = [{"name": "email"}]
    assert api.api_version_compat_assert_request("/signup", fields, ["email"]) is True
    with pytest.raises(WebRunnerException):
        api.api_version_compat_assert_request("/signup", fields, ["email", "captcha"])
    rows = [{"client_version": "1.0", "server_version": "2.0", "passed": True, "notes": "ok"}]
    expected = [{"client": "1.0", "server": "2.0", "passed": True, "notes": "ok"}]
    assert api.api_version_compat_matrix(rows) == expected
    assert api.api_version_compat_assert_matrix(rows) == expected
    with pytest.raises(WebRunnerException):
        api.api_version_compat_assert_matrix(rows + [{"client_version": "0.9", "server_version": "2.0"}])


# ---------- graphql_n_plus_1 -----------------------------------------------------

def _query_rows(count: int) -> list[dict]:
    return [
        {"operation": "Feed", "sql": f"SELECT * FROM users WHERE id = {index}", "parent_field": "author"}
        for index in range(count)
    ]


def test_graphql_n_plus_1_commands():
    findings = api.graphql_n_plus_1_detect(_query_rows(6))
    assert [(item["rule"], item["severity"], item["repetitions"]) for item in findings] == [
        ("n-plus-one", "warn", 6),
    ]
    json.dumps(findings)
    assert api.graphql_n_plus_1_detect(_query_rows(3)) == []
    assert len(api.graphql_n_plus_1_assert(_query_rows(6))) == 1
    with pytest.raises(WebRunnerException):
        api.graphql_n_plus_1_assert(_query_rows(12))
    assert "`author` × 6" in api.graphql_n_plus_1_report(_query_rows(6))


# ---------- grpc_streaming_assert ------------------------------------------------

STREAM = {
    "method": "/chat.Chat/Talk", "mode": "bidi", "status": "OK", "half_closed_ts_ms": 5,
    "frames": [
        {"payload_size": 10, "body": {"seq": 1}, "ts_ms": 1, "direction": "in"},
        {"payload_size": 900, "body": {"seq": 2}, "ts_ms": 9, "direction": "in"},
        {"payload_size": 4, "body": {}, "ts_ms": 2, "direction": "out"},
    ],
}


def test_grpc_streaming_assert_commands():
    parsed = api.grpc_streaming_assert_parse(STREAM)
    assert parsed["mode"] == "bidi" and len(parsed["frames"]) == 3
    json.dumps(parsed)
    assert api.grpc_streaming_assert_status(STREAM) is True
    assert api.grpc_streaming_assert_frames(STREAM, min_count=1, max_count=2, max_bytes=1000) == 2
    assert api.grpc_streaming_assert_frames(STREAM, direction="out") == 1
    assert api.grpc_streaming_assert_order(STREAM, "seq", [1, 2]) is True
    assert api.grpc_streaming_assert_half_close(STREAM) is True


@pytest.mark.parametrize("call", [
    lambda: api.grpc_streaming_assert_status(STREAM, "CANCELLED"),
    lambda: api.grpc_streaming_assert_status(STREAM, "NOT_A_STATUS"),
    lambda: api.grpc_streaming_assert_frames(STREAM, max_count=1),
    lambda: api.grpc_streaming_assert_frames(STREAM, max_bytes=100),
    lambda: api.grpc_streaming_assert_order(STREAM, "seq", [2, 1]),
    lambda: api.grpc_streaming_assert_half_close({**STREAM, "half_closed_ts_ms": 50}),
])
def test_grpc_streaming_assert_failures(call):
    with pytest.raises(WebRunnerException):
        call()


# ---------- grpc_tester ----------------------------------------------------------

def test_grpc_tester_framing():
    framed = api.grpc_tester_encode_message(base64.b64encode(b"hello").decode("ascii"))
    assert base64.b64decode(framed) == b"\x00\x00\x00\x00\x05hello"
    trailer = b"grpc-status: 0\r\ngrpc-message: ok\r\n"
    body = base64.b64decode(framed) + b"\x80" + len(trailer).to_bytes(4, "big") + trailer
    frames = api.grpc_tester_decode_message(base64.b64encode(body).decode("ascii"))
    assert frames == [
        {"flag": 0, "payload_base64": base64.b64encode(b"hello").decode("ascii"), "trailer": None},
        {"flag": 128, "payload_base64": base64.b64encode(trailer).decode("ascii"),
         "trailer": {"grpc-status": "0", "grpc-message": "ok"}},
    ]
    json.dumps(frames)
    with pytest.raises(WebRunnerException):
        api.grpc_tester_decode_message("not base64!")


def test_grpc_tester_recorder_and_asserts():
    ok_call = {"method": "/shop.Cart/Add", "request": {"sku": "a"}, "response": {"count": 1}}
    missing = {"method": "/shop.Cart/Get", "status": 5, "error": "no cart"}
    assert api.grpc_tester_record(ok_call)["status"] == "OK"
    assert api.grpc_tester_record(missing)["status"] == "NOT_FOUND"
    assert api.grpc_tester_assert_called("/shop.Cart/Add") == 1
    with pytest.raises(WebRunnerException):
        api.grpc_tester_assert_called("/shop.Cart/Add", minimum=2)
    assert api.grpc_tester_assert_call(ok_call)["method"] == "/shop.Cart/Add"
    assert api.grpc_tester_assert_call(missing, "NOT_FOUND")["error"] == "no cart"
    with pytest.raises(WebRunnerException):
        api.grpc_tester_assert_call(missing)
    with pytest.raises(WebRunnerException):
        api.grpc_tester_assert_call(ok_call, "NOT_FOUND")
    with pytest.raises(WebRunnerException):
        api.grpc_tester_record({"method": "/x", "status": "NOPE"})
    assert api.grpc_tester_reset() == 2
    assert api.grpc_tester_reset() == 0


# ---------- har_to_openapi -------------------------------------------------------

def test_har_to_openapi_commands(tmp_path):
    spec = api.har_to_openapi_convert(HAR)
    assert sorted(spec["paths"]) == ["/orders", "/users/{id}"]
    assert spec["paths"]["/users/{id}"]["get"]["parameters"][0]["name"] == "verbose"
    json.dumps(spec)
    har_file = tmp_path / "traffic.har"
    har_file.write_text(json.dumps(HAR), encoding="utf-8")
    assert api.har_to_openapi_convert(har_path=str(har_file)) == spec
    assert api.har_to_openapi_assert_coverage(2, har=HAR) == 2
    with pytest.raises(WebRunnerException):
        api.har_to_openapi_assert_coverage(3, har_path=str(har_file))
    with pytest.raises(WebRunnerException):
        api.har_to_openapi_convert()


# ---------- idempotency_check ----------------------------------------------------

def test_idempotency_check_commands():
    first = {"status_code": 201, "body": {"id": 7, "request_id": "a"}, "side_effect_count": 1}
    repeat = {"status_code": 201, "body": {"id": 7, "request_id": "b"}, "side_effect_count": 1}
    report = api.idempotency_check_compare(first, repeat, ignore_body_keys=["request_id"])
    assert report["passed"] is True and report["violations"] == []
    json.dumps(report)
    assert api.idempotency_check_compare(first, repeat)["violations"] == ["response body differs between calls"]
    conflict = {"status_code": 409, "body": {"id": 7, "request_id": "a"}, "side_effect_count": 1}
    assert api.idempotency_check_assert(first, conflict, allow_status_change_to=[409])["passed"] is True
    with pytest.raises(WebRunnerException):
        api.idempotency_check_assert(first, conflict)
    key = api.idempotency_check_key(["user-1", 100])
    assert len(key) == 64 and key == api.idempotency_check_key(["user-1", 100])
    assert key != api.idempotency_check_key(["user-1", 101])


# ---------- openapi_drift --------------------------------------------------------

def test_openapi_drift_commands(tmp_path):
    seen = [
        {"method": "GET", "path": "/users/42", "status_code": 200},
        {"method": "GET", "path": "/users/42", "status_code": 500},
    ]
    report = api.openapi_drift_diff(seen, spec=SPEC)
    assert report == {
        "undocumented": [], "zombie": ["POST /orders"], "undocumented_methods": [],
        "undocumented_statuses": ["GET /users/{id} → 500"],
    }
    json.dumps(report)
    spec_file = tmp_path / "openapi.json"
    spec_file.write_text(json.dumps(SPEC), encoding="utf-8")
    assert api.openapi_drift_assert(seen, spec_path=str(spec_file))["zombie"] == ["POST /orders"]
    assert api.openapi_drift_assert(seen, spec=SPEC, max_zombies=1)["undocumented"] == []
    with pytest.raises(WebRunnerException):
        api.openapi_drift_assert(seen, spec=SPEC, max_zombies=0)
    with pytest.raises(WebRunnerException):
        api.openapi_drift_assert(seen + [{"method": "DELETE", "path": "/admin"}], spec=SPEC)


# ---------- openapi_to_e2e -------------------------------------------------------

def test_openapi_to_e2e_commands(tmp_path):
    result = api.openapi_to_e2e_generate(SPEC)
    assert result["base_url"] == "https://api.test"
    assert [test["name"] for test in result["tests"]] == [
        "getUser__happy", "getUser__bad_path_param", "post_orders__happy",
    ]
    assert result["tests"][0]["actions"][0] == ["WR_http_get", {"url": "https://api.test/users/1", "timeout": 15}]
    json.dumps(result)
    only_post = api.openapi_to_e2e_generate(SPEC, include_negative=False, method_filter=["post"])
    assert [test["name"] for test in only_post["tests"]] == ["post_orders__happy"]
    spec_file = tmp_path / "openapi.json"
    spec_file.write_text(json.dumps(SPEC), encoding="utf-8")
    written = api.openapi_to_e2e_write(str(tmp_path / "out"), spec_path=str(spec_file), path_prefix_filter="/orders")
    assert [name.replace("\\", "/").rsplit("/", 1)[-1] for name in written] == ["post_orders__happy.json"]
    actions = json.loads((tmp_path / "out" / "post_orders__happy.json").read_text(encoding="utf-8"))
    assert actions[1] == ["WR_http_assert_status", {"expected": 201}]
    with pytest.raises(WebRunnerException):
        api.openapi_to_e2e_generate()


# ---------- pagination_audit -----------------------------------------------------

def test_pagination_audit_commands():
    clean = [
        {"items": [{"id": 1}, {"id": 2}], "next_cursor": "p2"},
        {"items": [{"id": 3}], "next_cursor": None},
    ]
    findings = api.pagination_audit_walk(clean)
    assert findings["passed"] is True
    assert (findings["page_count"], findings["unique_items"], findings["duplicates"]) == (2, 3, [])
    json.dumps(findings)
    assert api.pagination_audit_assert(clean, expected_total=3, sorted_by_key=True)["total_items"] == 3
    repeated = [{"items": [{"id": 1}], "next_cursor": "p2"}, {"items": [{"id": 1}], "next_cursor": None}]
    assert api.pagination_audit_walk(repeated)["duplicates"] == [1]
    unfinished = [{"items": [{"id": 1}], "next_cursor": "p2"}]
    assert api.pagination_audit_walk(unfinished)["hit_max_pages"] is True
    whole_items = [{"items": [{"a": 1}, {"a": 1}], "next_cursor": None}]
    assert api.pagination_audit_walk(whole_items, key=None)["unique_items"] == 1
    for bad, options in (
            (repeated, {}), (unfinished, {}), (clean, {"expected_total": 4}),
            (clean, {"sorted_by_key": True, "reverse": True}),
    ):
        with pytest.raises(WebRunnerException):
            api.pagination_audit_assert(bad, **options)


# ---------- rate_limit_assert ----------------------------------------------------

def test_rate_limit_assert_commands():
    burst = [
        {"status_code": 200, "headers": {"X-RateLimit-Limit": 2, "X-RateLimit-Remaining": 1}},
        {"status_code": 200, "headers": {"X-RateLimit-Remaining": "0"}},
        {"status_code": 429, "headers": {"Retry-After": "30"}},
    ]
    summary = api.rate_limit_assert_summary(burst)
    assert summary[0] == {
        "status_code": 200, "is_429": False, "retry_after_seconds": None, "limit": 2, "remaining": 1,
    }
    json.dumps(summary)
    assert api.rate_limit_assert_burst(burst, after=2)["retry_after_seconds"] == pytest.approx(30.0)
    no_header = burst[:2] + [{"status_code": 429}]
    assert api.rate_limit_assert_burst(no_header, after=2, require_retry_after=False)["is_429"] is True
    with pytest.raises(WebRunnerException):
        api.rate_limit_assert_burst(no_header, after=2)
    with pytest.raises(WebRunnerException):
        api.rate_limit_assert_burst(burst[:2] + [{"status_code": 200}], after=2)
    assert api.rate_limit_assert_recovery(burst[2], {"status_code": 200}) is True
    with pytest.raises(WebRunnerException):
        api.rate_limit_assert_recovery(burst[2], {"status_code": 429})


# ---------- contract_testing -----------------------------------------------------

def test_contract_testing_commands(tmp_path):
    schema = {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}}
    assert api.contract_testing_validate({"id": 1}, schema) == {"valid": True, "errors": []}
    invalid = api.contract_testing_validate({"id": "1"}, schema)
    assert invalid == {"valid": False, "errors": ["$.id: expected integer, got str"]}
    json.dumps(invalid)
    assert api.contract_testing_validate_openapi({"id": 1}, "/users/{id}", "get", 200, openapi_doc=SPEC)["valid"]
    spec_file = tmp_path / "openapi.json"
    spec_file.write_text(json.dumps(SPEC), encoding="utf-8")
    from_file = api.contract_testing_validate_openapi({}, "/users/{id}", "GET", 200, openapi_path=str(spec_file))
    assert from_file["errors"] == ["$: missing required property 'id'"]
    assert api.contract_testing_assert({"id": 1}, schema) is True
    with pytest.raises(WebRunnerException):
        api.contract_testing_assert({}, schema)


# ---------- graphql --------------------------------------------------------------

def _urlopen_returning(payload: dict) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    opened = MagicMock()
    opened.return_value.__enter__.return_value = response
    return opened


def test_graphql_network_commands():
    answer = {"data": {"user": {"name": "Ann"}}}
    with patch("je_web_runner.utils.graphql.client.urllib.request.urlopen", _urlopen_returning(answer)) as opened:
        result = api.graphql_execute(
            "https://api.test/graphql", "query Q($id: ID!) { user(id: $id) { name } }",
            variables={"id": "1"}, operation_name="Q", headers={"Authorization": "Bearer x"},
        )
    assert result == answer
    sent = opened.call_args.args[0]
    assert json.loads(sent.data)["variables"] == {"id": "1"} and sent.get_header("Authorization") == "Bearer x"
    json.dumps(result)
    schema = {"data": {"__schema": {"types": [{"name": "Query"}, {"name": "User"}]}}}
    with patch("je_web_runner.utils.graphql.client.urllib.request.urlopen", _urlopen_returning(schema)):
        assert api.graphql_introspect_types("https://api.test/graphql") == ["Query", "User"]
    failed = {"errors": [{"message": "boom"}]}
    with patch("je_web_runner.utils.graphql.client.urllib.request.urlopen", _urlopen_returning(failed)):
        with pytest.raises(WebRunnerException):
            api.graphql_execute("https://api.test/graphql", "{ user { name } }")
    with pytest.raises(WebRunnerException):
        api.graphql_execute("ftp://api.test/graphql", "{ user { name } }")


def test_graphql_field_commands():
    payload = {"data": {"user": {"posts": [{"title": "First"}]}}}
    assert api.graphql_extract_field(payload, "user.posts[0].title") == "First"
    assert api.graphql_extract_field(payload, "user.posts") == [{"title": "First"}]
    assert api.graphql_assert_field(payload, "user.posts[0].title", "First") == "First"
    with pytest.raises(WebRunnerException):
        api.graphql_assert_field(payload, "user.posts[0].title", "Second")
    with pytest.raises(WebRunnerException):
        api.graphql_extract_field(payload, "user.missing")


# ---------- api_mock -------------------------------------------------------------

def test_api_mock_commands():
    route = api2.api_mock_register("GET", "https://api.test/users/*", body={"id": 1}, times=1)
    assert route["url_pattern"] == "https://api.test/users/*" and route["response"]["body"] == {"id": 1}
    json.dumps(route)
    answer = api2.api_mock_match("get", "https://api.test/users/1")
    assert answer == {"status": 200, "headers": {"content-type": "application/json"}, "body": '{"id": 1}'}
    assert api2.api_mock_match("GET", "https://api.test/users/1") is None
    assert api2.api_mock_calls() == [["GET", "https://api.test/users/1"], ["GET", "https://api.test/users/1"]]
    with pytest.raises(WebRunnerException):
        api2.api_mock_register("", "https://api.test/")
    assert api2.api_mock_reset() is True
    assert api2.api_mock_calls() == []


def test_api_mock_attach_routes_the_playwright_page():
    page = MagicMock()
    with patch("je_web_runner.webdriver.playwright_wrapper.playwright_wrapper_instance", MagicMock(page=page)):
        assert api2.api_mock_attach() is True
    assert page.route.call_args.args[0] == "**/*"


# ---------- har_replay -----------------------------------------------------------

def test_har_replay_commands(tmp_path):
    har_file = tmp_path / "traffic.har"
    har_file.write_text(json.dumps(HAR), encoding="utf-8")
    entries = api2.har_replay_load(str(har_file))
    assert [(entry["method"], entry["path"], entry["status"]) for entry in entries] == [
        ("GET", "/users/42?verbose=1", 200), ("POST", "/orders", 201),
    ]
    json.dumps(entries)
    with pytest.raises(WebRunnerException):
        api2.har_replay_calls()
    started = api2.har_replay_start(str(har_file))
    assert started["base_url"] == f"http://127.0.0.1:{started['port']}" and started["entries"] == 2
    with pytest.raises(WebRunnerException):
        api2.har_replay_start(str(har_file))
    assert _http(started["base_url"] + "/users/42?verbose=1") == (200, '{"id": 42, "name": "Ann"}')
    assert _http(started["base_url"] + "/nothing")[0] == 404
    expected_calls = [["GET", "/users/42?verbose=1"], ["GET", "/nothing"]]
    assert api2.har_replay_calls() == expected_calls
    assert api2.har_replay_stop() == expected_calls
    assert api2.har_replay_stop() == []
    with pytest.raises(WebRunnerException):
        api2.har_replay_start(str(tmp_path / "missing.har"))


# ---------- mock_services --------------------------------------------------------

def test_mock_services_commands():
    assert api2.mock_services_captured() == {"oauth_tokens": [], "smtp_messages": []}
    oauth = api2.mock_services_start_oauth()
    assert oauth["token_url"] == f"http://127.0.0.1:{oauth['port']}/token"
    json.dumps(oauth)
    with pytest.raises(WebRunnerException):
        api2.mock_services_start_oauth()
    status, body = _http(oauth["token_url"], data=b"grant_type=client_credentials")
    assert status == 200
    smtp = api2.mock_services_start_smtp()
    assert smtp["host"] == "127.0.0.1" and smtp["port"] > 0
    with smtplib.SMTP(smtp["host"], smtp["port"], timeout=5) as client:
        client.sendmail("app@x.test", ["user@x.test"], "Subject: Hi\r\n\r\nYour code is 1234\r\n")
    captured = api2.mock_services_captured()
    assert captured["oauth_tokens"] == [json.loads(body)["access_token"]]
    assert len(captured["smtp_messages"]) == 1 and "Your code is 1234" in captured["smtp_messages"][0]
    assert api2.mock_services_stop() == captured
    assert api2.mock_services_stop() == {"oauth_tokens": [], "smtp_messages": []}


# ---------- email_deliverability -------------------------------------------------

def test_email_deliverability_commands():
    headers = api2.email_deliverability_parse(RAW_MAIL)
    assert headers["subject"] == ["Welcome aboard"] and "dkim-signature" in headers
    audit = api2.email_deliverability_audit(RAW_MAIL, expected_policy="reject")
    assert {name: result["passed"] for name, result in audit.items()} == {
        "spf": True, "dkim": True, "dmarc": True, "list_unsubscribe": True, "no_bcc_leak": True,
    }
    json.dumps(audit)
    unsigned = "Subject: Hi\r\nBcc: boss@x.test\r\n\r\nbody"
    bad = api2.email_deliverability_audit(unsigned)
    assert not any(result["passed"] for result in bad.values())
    assert "no DKIM-Signature" in bad["dkim"]["error"]
    assert api2.email_deliverability_assert(RAW_MAIL) == ["spf", "dkim", "dmarc"]
    assert api2.email_deliverability_assert(RAW_MAIL, ["list_unsubscribe", "no_bcc_leak"]) == [
        "list_unsubscribe", "no_bcc_leak",
    ]
    for arguments in ((unsigned,), (RAW_MAIL, ["dmarc"], "quarantine"), (RAW_MAIL, ["nope"])):
        with pytest.raises(WebRunnerException):
            api2.email_deliverability_assert(*arguments)


# ---------- email_render ---------------------------------------------------------

EML = (
    "Message-ID: <m1@x.test>\r\nSubject: Welcome aboard\r\nFrom: app@x.test\r\nTo: a@x.test, b@x.test\r\n"
    "Content-Type: text/html; charset=utf-8\r\n\r\n<table><tr><td>Hello</td></tr></table>\r\n"
)


def test_email_render_load_and_assert(tmp_path):
    (tmp_path / "one.eml").write_bytes(EML.encode("utf-8"))
    (tmp_path / "two.eml").write_bytes(EML.replace("Welcome aboard", "Reset").encode("utf-8"))
    loaded = api2.email_render_load_eml(str(tmp_path / "one.eml"))
    assert len(loaded) == 1
    assert loaded[0]["subject"] == "Welcome aboard" and loaded[0]["to"] == ["a@x.test", "b@x.test"]
    assert "<table>" in loaded[0]["html_body"]
    json.dumps(loaded)
    assert [mail["subject"] for mail in api2.email_render_load_eml(str(tmp_path))] == ["Welcome aboard", "Reset"]
    assert api2.email_render_assert_subject(loaded[0], "Welcome") is True
    with pytest.raises(WebRunnerException):
        api2.email_render_assert_subject(loaded[0], "Goodbye")
    with pytest.raises(WebRunnerException):
        api2.email_render_load_eml(str(tmp_path / "missing.eml"))


def test_email_render_fetch():
    listing = MagicMock()
    listing.json.return_value = {"items": [{"Content": {
        "Headers": {"Subject": ["Hello"], "From": ["app@x.test"], "To": ["a@x.test"]}, "Body": "hi",
    }}]}
    with patch("requests.get", return_value=listing) as get:
        mails = api2.email_render_fetch("http://127.0.0.1:8025/")
    assert get.call_args.args[0] == "http://127.0.0.1:8025/api/v2/messages"
    assert [(mail["subject"], mail["from_addr"], mail["to"]) for mail in mails] == [
        ("Hello", "app@x.test", ["a@x.test"]),
    ]
    with pytest.raises(WebRunnerException):
        api2.email_render_fetch("http://127.0.0.1:8025", provider="gmail")


def test_email_render_screenshots(tmp_path):
    driver = MagicMock()
    email = {"message_id": "<m1@x.test>", "html_body": "<p>Hello</p>"}
    with patch.object(api2, "selenium_driver", return_value=driver):
        shots = api2.email_render_screenshots(email, str(tmp_path))
        custom = api2.email_render_screenshots(
            email, str(tmp_path), viewports=[{"name": "tablet", "width": 768, "height": 1024}],
        )
    assert [shot["viewport"] for shot in shots] == ["desktop-light", "desktop-dark", "mobile-light"]
    assert shots[2]["width"] == 390 and shots[0]["screenshot_path"].endswith("m1_x_test__desktop-light.png")
    json.dumps(shots)
    assert driver.set_window_size.call_args_list[1].args == (800, 1200)
    schemes = [call.args[1]["features"][0]["value"] for call in driver.execute_cdp_cmd.call_args_list]
    assert schemes == ["light", "dark", "light", "light"]
    opened = driver.get.call_args.args[0]
    assert base64.b64decode(opened.split("base64,", 1)[1]) == b"<p>Hello</p>"
    assert [shot["viewport"] for shot in custom] == ["tablet"] and driver.save_screenshot.call_count == 4
    with patch.object(api2, "selenium_driver", return_value=driver), pytest.raises(WebRunnerException):
        api2.email_render_screenshots({"message_id": "m2", "text_body": "plain"}, str(tmp_path))


# ---------- inbox_render_outlook -------------------------------------------------

def test_inbox_render_outlook_commands():
    table_mail = "<table><tr><td style='display:flex'>Hi</td></tr></table>"
    findings = api2.inbox_render_outlook_audit(table_mail)
    assert [(item["rule"], item["severity"]) for item in findings] == [
        ("outlook-incompatible-css", "warn"), ("apple-mail-dark-mode", "info"),
    ]
    json.dumps(findings)
    assert api2.inbox_render_outlook_audit(table_mail, clients=["gmail"]) == []
    assert len(api2.inbox_render_outlook_assert(table_mail)) == 2
    with pytest.raises(WebRunnerException):
        api2.inbox_render_outlook_assert("<table><tr><td><svg></svg></td></tr></table>")
    with pytest.raises(WebRunnerException):
        api2.inbox_render_outlook_audit(table_mail, clients=["thunderbird"])
    with patch.object(api2, "page_source", return_value="<div>no table</div>") as source:
        from_page = api2.inbox_render_outlook_audit_page(clients=["outlook"])
    assert [item["rule"] for item in from_page] == ["outlook-needs-table-layout"]
    assert source.call_args.args == ("WR_inbox_render_outlook_audit_page",)


# ---------- mq_assert ------------------------------------------------------------

def test_mq_assert_commands():
    messages = [
        {"topic": "orders", "key": "o-1", "body": {"type": "created", "total": 5}, "headers": {"v": "1"}},
        {"topic": "orders", "key": "o-1", "body": '{"type": "paid"}'},
        {"topic": "audit", "key": "o-2", "body": {"type": "seen"}},
    ]
    found = api2.mq_assert_published(messages, body_contains={"type": "paid"}, key_matches="o-1")
    assert found == {"topic": "orders", "body": '{"type": "paid"}', "key": "o-1", "headers": {}}
    json.dumps(found)
    assert api2.mq_assert_published(messages, header_equals={"v": "1"})["body"]["total"] == 5
    with pytest.raises(WebRunnerException):
        api2.mq_assert_published(messages, body_contains={"type": "refunded"})
    assert api2.mq_assert_no_message(messages, topic="audit", body_contains={"type": "paid"}) is True
    with pytest.raises(WebRunnerException):
        api2.mq_assert_no_message(messages, topic="orders", body_contains={"type": "paid"})
    assert api2.mq_assert_idempotent(messages, "o-2") is True
    with pytest.raises(WebRunnerException):
        api2.mq_assert_idempotent(messages, "o-1")
    assert api2.mq_assert_ordered(messages, "o-1", ["created", "paid"]) is True
    with pytest.raises(WebRunnerException):
        api2.mq_assert_ordered(messages, "o-1", ["paid", "created"])


# ---------- otp_interceptor ------------------------------------------------------

def _mailhog_inbox(created: float) -> dict:
    return {"items": [{"ID": "m1", "Created": created, "Content": {
        "Headers": {"To": ["user@x.test"], "From": ["app@x.test"], "Subject": ["Your code"]},
        "Body": "Your code is 482913",
    }}]}


def test_otp_interceptor_extract():
    assert api2.otp_interceptor_extract("Your code is 482913.") == "482913"
    assert api2.otp_interceptor_extract("PIN: AB-77", pattern=r"PIN: ([A-Z]{2}-\d{2})") == "AB-77"
    assert api2.otp_interceptor_extract("no digits here") is None


def test_otp_interceptor_network_commands():
    fetch_path = "je_web_runner.utils.otp_interceptor.interceptor._http_get_json"
    with patch(fetch_path, return_value=_mailhog_inbox(time.time() + 60)) as fetch:
        messages = api2.otp_interceptor_messages("http://127.0.0.1:8025", recipient="USER@x.test", limit=5)
        assert api2.otp_interceptor_wait("http://127.0.0.1:8025", "user@x.test", timeout=2) == "482913"
    assert fetch.call_args_list[0].args == ("http://127.0.0.1:8025/api/v2/messages?limit=5",)
    assert [(message["message_id"], message["subject"]) for message in messages] == [("m1", "Your code")]
    json.dumps(messages)
    with patch(fetch_path, return_value=_mailhog_inbox(time.time() - 30)):
        code = api2.otp_interceptor_wait(
            "http://127.0.0.1:8025", "user@x.test", subject_contains="code", lookback_seconds=120,
        )
        assert code == "482913"
        with pytest.raises(WebRunnerException):
            api2.otp_interceptor_wait("http://127.0.0.1:8025", "user@x.test", timeout=0)
    with pytest.raises(WebRunnerException):
        api2.otp_interceptor_messages("http://127.0.0.1:8025", provider="pigeon")


# ---------- push_delivery --------------------------------------------------------

def test_push_delivery_commands():
    fcm = {"message": {"token": "t", "notification": {"title": "Hi", "body": "Order shipped"},
                       "android": {"ttl": "3600s", "collapse_key": "order"}}}
    apns = {"aps": {"alert": {"title": "Hi", "body": "Order shipped"}}}
    checked = api2.push_delivery_check(fcm, collapse=True)
    assert checked["passed"] is True and checked["error"] == "" and checked["size_bytes"] > 50
    json.dumps(checked)
    leaked = {"message": {"token": "t", "notification": {"title": "Hi", "body": "mail ann@x.test"}}}
    assert "PII" in api2.push_delivery_check(leaked)["error"]
    assert api2.push_delivery_check(apns, collapse=True)["passed"] is False
    assert api2.push_delivery_assert(fcm) == "fcm"
    assert api2.push_delivery_assert(apns) == "apns"
    for payload, options in ((leaked, {}), (apns, {"provider": "fcm"}), (apns, {"collapse": True}),
                             (fcm, {"provider": "wns"})):
        with pytest.raises(WebRunnerException):
            api2.push_delivery_assert(payload, **options)


# ---------- slack_digest ---------------------------------------------------------

def test_slack_digest_commands():
    digest = {
        "period_label": "last week", "suite_pass_rate": 0.95, "suite_pass_rate_previous": 0.9,
        "flake_changes": [{"test_id": "login.json", "action": "added", "flake_score": 0.42}],
        "risky_prs": [{"number": 12, "title": "Rework cart", "score": 81.5}],
        "cost": {"current_usd": 120, "previous_usd": 100}, "extra_lines": ["Nightly is green"],
    }
    payload = api2.slack_digest_payload(digest, channel="#qa")
    assert payload["channel"] == "#qa" and len(payload["blocks"]) == 6
    assert payload["blocks"][1]["text"]["text"] == "*Suite pass rate:* 95.0% (▲5.0 pts vs prev)"
    json.dumps(payload)
    card = api2.slack_digest_teams_card(digest)
    assert card["type"] == "AdaptiveCard" and len(card["body"]) == 6
    text = api2.slack_digest_text(digest)
    assert "`login.json` (score 0.42)" in text and "<#12|#12> Rework cart — risk 81.5" in text
    assert "Nothing notable" in api2.slack_digest_text({})
    with pytest.raises(WebRunnerException):
        api2.slack_digest_payload({"suite_pass_rate": 95})


# ---------- webhook_receiver -----------------------------------------------------

def test_webhook_receiver_needs_a_started_server():
    with pytest.raises(WebRunnerException):
        api2.webhook_receiver_received()
    assert api2.webhook_receiver_stop() == []


def test_webhook_receiver_commands():
    base_url = api2.webhook_receiver_start()["base_url"]
    assert base_url.startswith("http://127.0.0.1:")
    with pytest.raises(WebRunnerException):
        api2.webhook_receiver_start()
    body = json.dumps({"event": "paid", "order": 7}).encode("utf-8")
    assert _http(base_url + "/hook?x=1", data=body, headers={"X-Signature": "abc"})[0] == 200
    assert _http(base_url + "/ping")[0] == 200
    received = api2.webhook_receiver_received(path="/hook", method="post")
    assert len(received) == 1 and received[0]["query"] == {"x": ["1"]}
    assert json.loads(received[0]["body"]) == {"event": "paid", "order": 7}
    json.dumps(received)
    assert len(api2.webhook_receiver_received()) == 2
    assert api2.webhook_receiver_wait("/ping", method="GET", timeout=1)["path"] == "/ping"
    assert api2.webhook_receiver_assert_path("/hook", method="post") == 1
    assert api2.webhook_receiver_assert_header("x-signature", "abc")["path"] == "/hook"
    assert api2.webhook_receiver_assert_json({"event": "paid"})["method"] == "POST"
    for failing in (
            lambda: api2.webhook_receiver_wait("/never", timeout=0.1),
            lambda: api2.webhook_receiver_assert_path("/hook", minimum=2),
            lambda: api2.webhook_receiver_assert_header("X-Signature", "nope"),
            lambda: api2.webhook_receiver_assert_json({"event": "refunded"}),
    ):
        with pytest.raises(WebRunnerException):
            failing()
    assert api2.webhook_receiver_clear() == 2
    assert api2.webhook_receiver_received() == []
    assert _http(base_url + "/late")[0] == 200
    assert [request["path"] for request in api2.webhook_receiver_stop()] == ["/late"]
