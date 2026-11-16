"""Every standard gRPC status code is kept, not folded into UNKNOWN."""
import pytest

from je_web_runner.utils.grpc_tester.client import GrpcStatus, call

STANDARD = {
    0: "OK", 1: "CANCELLED", 2: "UNKNOWN", 3: "INVALID_ARGUMENT", 4: "DEADLINE_EXCEEDED", 5: "NOT_FOUND",
    6: "ALREADY_EXISTS", 7: "PERMISSION_DENIED", 8: "RESOURCE_EXHAUSTED", 9: "FAILED_PRECONDITION",
    10: "ABORTED", 11: "OUT_OF_RANGE", 12: "UNIMPLEMENTED", 13: "INTERNAL", 14: "UNAVAILABLE",
    15: "DATA_LOSS", 16: "UNAUTHENTICATED",
}


class _RpcError(Exception):
    def __init__(self, code):
        super().__init__("rpc failed")
        self._code = code

    def code(self):
        return self._code


class _StatusCode:
    """Shaped like ``grpc.StatusCode``: ``value`` is ``(number, text)``."""

    def __init__(self, number):
        self.value = (number, "text")


def _failing(code):
    def stub(_request):
        raise _RpcError(code)
    return stub


def test_the_enum_has_the_seventeen_standard_codes():
    assert {status.value: status.name for status in GrpcStatus} == STANDARD


@pytest.mark.parametrize("number", range(1, 17))
def test_a_failed_call_keeps_its_status(number):
    assert call("svc/Method", _failing(number), {}).status.name == STANDARD[number]
    assert call("svc/Method", _failing(_StatusCode(number)), {}).to_dict()["status"] == STANDARD[number]


def test_a_code_outside_the_standard_is_unknown():
    assert call("svc/Method", _failing(99), {}).status is GrpcStatus.UNKNOWN
