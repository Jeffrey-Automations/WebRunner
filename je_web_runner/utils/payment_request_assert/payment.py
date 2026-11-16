"""
Payment Request API + Apple Pay / Google Pay sheet assertions.

Real payment sheets can't be driven by Selenium / Playwright (they're
out-of-process browser UI). This module installs a JS shim that:

* Replaces ``window.PaymentRequest`` with a recorder that captures the
  payment methods array, payment details, and shipping options the page
  passed to the constructor.
* Returns a canned ``PaymentResponse`` so the page's ``show()`` flow
  can complete without user interaction.
* Records the ``complete()`` call (and its status) so tests can confirm
  the page actually finalized the transaction.

Python-side assertions cover the common contract failures (missing
Apple Pay capability, total mismatched currency, no shipping option).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PaymentRequestAssertError(WebRunnerException):
    """Raised on malformed input or assertion failure."""


INSTALL_SCRIPT = r"""
(function (canned) {
  if (window.__wr_payment__) return;
  const constructed = [];
  const completed = [];
  function FakePaymentRequest(methodData, details, options) {
    constructed.push({methodData, details, options});
    this._methodData = methodData;
    this._details = details;
    this._options = options;
  }
  FakePaymentRequest.prototype.show = async function () {
    return {
      requestId: canned.requestId || 'wr-pr-1',
      methodName: canned.methodName ||
        (this._methodData[0] && this._methodData[0].supportedMethods) ||
        'basic-card',
      details: canned.details || {token: 'wr-token'},
      shippingAddress: canned.shippingAddress || null,
      shippingOption: canned.shippingOption || null,
      payerEmail: canned.payerEmail || null,
      payerName: canned.payerName || null,
      payerPhone: canned.payerPhone || null,
      complete: async function (status) {
        completed.push({status: status || 'unknown'});
      },
    };
  };
  FakePaymentRequest.prototype.canMakePayment = async function () {
    return canned.canMakePayment !== false;
  };
  FakePaymentRequest.prototype.abort = async function () {};
  window.PaymentRequest = FakePaymentRequest;
  window.__wr_payment__ = {
    drainConstructed: function () { return constructed.splice(0); },
    drainCompleted: function () { return completed.splice(0); },
  };
})(arguments[0]);
"""


@dataclass
class ConstructedPaymentRequest:
    """The arguments one ``new PaymentRequest(...)`` call was given."""
    method_data: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    def supports_method(self, method: str) -> bool:
        """Return True when ``method`` is one of the request's supportedMethods."""
        return any((m.get("supportedMethods") or "") == method
                   for m in self.method_data if isinstance(m, dict))


@dataclass
class CompletedPayment:
    """The status one ``PaymentResponse.complete()`` call was given."""
    status: str = "unknown"


@dataclass
class PaymentLog:
    """Every PaymentRequest the page constructed and every completion it reported."""
    constructed: list[ConstructedPaymentRequest] = field(default_factory=list)
    completed: list[CompletedPayment] = field(default_factory=list)


def parse_log(payload: Any) -> PaymentLog:
    """Build a PaymentLog from the dict recorded in the page, skipping entries that are not dicts.

    Raises PaymentRequestAssertError when the payload is not a dict.
    """
    if not isinstance(payload, dict):
        raise PaymentRequestAssertError("payload must be dict")
    constructed: list[ConstructedPaymentRequest] = []
    for raw in payload.get("constructed") or []:
        if not isinstance(raw, dict):
            continue
        constructed.append(ConstructedPaymentRequest(
            method_data=list(raw.get("methodData") or []),
            details=dict(raw.get("details") or {}),
            options=dict(raw.get("options") or {}),
        ))
    completed: list[CompletedPayment] = []
    for raw in payload.get("completed") or []:
        if not isinstance(raw, dict):
            continue
        completed.append(CompletedPayment(status=str(raw.get("status") or "unknown")))
    return PaymentLog(constructed=constructed, completed=completed)


def assert_supports(log: PaymentLog, *, method: str) -> None:
    """Raise PaymentRequestAssertError unless some constructed PaymentRequest supports ``method``."""
    if not method:
        raise PaymentRequestAssertError("method must be non-empty")
    if not log.constructed:
        raise PaymentRequestAssertError("page never constructed a PaymentRequest")
    if not any(c.supports_method(method) for c in log.constructed):
        offered = sorted({m.get("supportedMethods", "?")
                          for c in log.constructed for m in c.method_data
                          if isinstance(m, dict)})
        raise PaymentRequestAssertError(
            f"no PaymentRequest declared support for {method!r}; "
            f"offered={offered}"
        )


def assert_total_currency(log: PaymentLog, *, currency: str) -> None:
    """Raise PaymentRequestAssertError when a constructed PaymentRequest's total is not in ``currency``
    (a total without a readable ``amount.currency`` included), or none was constructed.
    """
    if not currency:
        raise PaymentRequestAssertError("currency must be non-empty")
    if not log.constructed:
        raise PaymentRequestAssertError("page never constructed a PaymentRequest")
    for c in log.constructed:
        total = c.details.get("total")
        amount = total.get("amount") if isinstance(total, dict) else None
        actual = amount.get("currency") if isinstance(amount, dict) else None
        if actual != currency:
            raise PaymentRequestAssertError(
                f"total currency {actual!r} != {currency!r}"
            )


def assert_completed(log: PaymentLog, *, status: str = "success") -> None:
    """Raise PaymentRequestAssertError unless ``complete()`` was called with ``status``
    (``success``, ``fail`` or ``unknown``).
    """
    if status not in ("success", "fail", "unknown"):
        raise PaymentRequestAssertError(f"invalid status {status!r}")
    if not log.completed:
        raise PaymentRequestAssertError(
            "page never called PaymentResponse.complete() — "
            "transaction left dangling"
        )
    actual = {c.status for c in log.completed}
    if status not in actual:
        raise PaymentRequestAssertError(
            f"complete() called with statuses {actual}, expected {status!r}"
        )


def assert_shipping_required(log: PaymentLog) -> None:
    """Raise PaymentRequestAssertError when a PaymentRequest was constructed without ``requestShipping``,
    or none was constructed.
    """
    if not log.constructed:
        raise PaymentRequestAssertError("page never constructed a PaymentRequest")
    for c in log.constructed:
        if not c.options.get("requestShipping"):
            raise PaymentRequestAssertError(
                "PaymentRequest constructed without requestShipping:true"
            )
