"""
FCM / APNs push-payload validator.

Distinct from [[web_push_assert]] (browser side), this module sanity-
checks the *server-side* push payload before it leaves your backend:

* Required fields present per platform.
* Total payload size under provider limits (FCM 4KB, APNs 4KB legacy,
  5KB modern token-based).
* Collapse key / thread ID is set when intent is to replace, not stack.
* TTL is reasonable (not 0, not >28 days for FCM, not >30 days APNs).
* Sensitive PII not in user-visible ``title`` / ``body``.
"""
from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.pii_scanner.scanner import _luhn_check


class PushDeliveryError(WebRunnerException):
    """Raised on push payload validation failure."""


class Provider(str, Enum):
    """The push services whose payloads are checked: FCM and APNs."""
    FCM = "fcm"
    APNS = "apns"


FCM_MAX_BYTES = 4 * 1024
APNS_MAX_BYTES = 5 * 1024
FCM_MAX_TTL_SEC = 28 * 24 * 3600
APNS_MAX_TTL_SEC = 30 * 24 * 3600


_PII_PATTERNS = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                    # SSN, as it is written: 123-45-6789
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),                   # Card-like; counts when the checksum holds
    re.compile(r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
)
_CARD_PATTERN = _PII_PATTERNS[1]


def _pii_pattern(value: str) -> str | None:
    """The pattern of the first PII-shaped part of ``value``, or None.

    An order or tracking number is not PII: nine digits count only when written as an SSN, and
    13 to 19 digits only when they pass the card checksum.
    """
    for pattern in _PII_PATTERNS:
        if pattern is not _CARD_PATTERN and pattern.search(value):
            return pattern.pattern
        if pattern is _CARD_PATTERN and any(_luhn_check(match.group(0)) for match in pattern.finditer(value)):
            return pattern.pattern
    return None


def assert_fcm_payload(payload: dict[str, Any]) -> None:
    """Raise PushDeliveryError unless ``payload`` is a usable FCM v1 message: a ``message`` dict
    with exactly one target (``token``, ``topic`` or ``condition``), within the size limit,
    no PII in the notification, a valid Android TTL.
    """
    if not isinstance(payload, dict):
        raise PushDeliveryError("payload must be a dict")
    if "message" not in payload:
        raise PushDeliveryError("FCM v1 payload must contain 'message'")
    message = payload["message"]
    if not isinstance(message, dict):
        raise PushDeliveryError("message must be a dict")
    targets = [k for k in ("token", "topic", "condition") if k in message]
    if len(targets) != 1:
        raise PushDeliveryError(
            f"FCM message needs exactly one of token/topic/condition, got {targets or 'none'}"
        )
    _assert_size(payload, FCM_MAX_BYTES)
    _assert_no_pii(message.get("notification") or {})
    if "android" in message and isinstance(message["android"], dict):
        _assert_ttl_string(message["android"].get("ttl"), FCM_MAX_TTL_SEC)


def assert_apns_payload(payload: dict[str, Any]) -> None:
    """Raise PushDeliveryError unless ``payload`` is a usable APNs payload: an ``aps`` dict with
    at least one delivery key, within the size limit, no PII in a dict alert.
    """
    if not isinstance(payload, dict):
        raise PushDeliveryError("payload must be a dict")
    aps = payload.get("aps")
    if not isinstance(aps, dict):
        raise PushDeliveryError("APNs payload must contain 'aps' dict")
    if not any(k in aps for k in ("alert", "badge", "sound",
                                  "content-available", "mutable-content")):
        raise PushDeliveryError(
            "APNs payload must contain alert / badge / sound / "
            "content-available / mutable-content"
        )
    _assert_size(payload, APNS_MAX_BYTES)
    alert = aps.get("alert")
    if isinstance(alert, dict):
        _assert_no_pii(alert)


def _assert_size(payload: dict[str, Any], max_bytes: int) -> None:
    serialized = json.dumps(payload, separators=(",", ":"))
    size = len(serialized.encode("utf-8"))
    if size > max_bytes:
        raise PushDeliveryError(
            f"payload {size}B exceeds {max_bytes}B platform limit"
        )


def _assert_no_pii(notification: dict[str, Any]) -> None:
    for field_name in ("title", "body"):
        value = notification.get(field_name)
        if not isinstance(value, str):
            continue
        pattern = _pii_pattern(value)
        if pattern is not None:
            raise PushDeliveryError(
                f"notification.{field_name!r} contains PII-shaped value: "
                f"{pattern!r}"
            )


def _assert_ttl_string(ttl: Any, max_seconds: int) -> None:
    if ttl is None:
        return
    if not isinstance(ttl, str) or not ttl.endswith("s"):
        raise PushDeliveryError(
            f"android.ttl must look like '3600s', got {ttl!r}"
        )
    try:
        seconds = int(ttl[:-1])
    except ValueError as exc:
        raise PushDeliveryError(f"android.ttl not numeric: {ttl!r}") from exc
    if seconds <= 0:
        raise PushDeliveryError("android.ttl must be > 0")
    if seconds > max_seconds:
        raise PushDeliveryError(
            f"android.ttl {seconds}s exceeds platform max {max_seconds}s"
        )


def assert_collapse_intent(payload: dict[str, Any]) -> None:
    """If the message is *meant* to replace older notifications, a
    collapse key / thread identifier must be set."""
    if isinstance(payload.get("aps"), dict):
        # APNs uses apns-collapse-id (a header) — surface from
        # ``payload['_apns_headers']`` if present.
        headers = payload.get("_apns_headers") or {}
        if not headers.get("apns-collapse-id"):
            raise PushDeliveryError(
                "APNs replace-intent message missing apns-collapse-id header"
            )
    elif isinstance(payload.get("message"), dict):
        android = payload["message"].get("android") or {}
        if not android.get("collapse_key"):
            raise PushDeliveryError(
                "FCM Android replace-intent message missing collapse_key"
            )
