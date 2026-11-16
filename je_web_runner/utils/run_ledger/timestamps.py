"""
ISO-8601 時間字串解析：接受結尾的 ``Z``，沒有時區的一律視為 UTC。
Parse the ISO-8601 timestamps found in ledgers, registries and mail APIs: a trailing
``Z`` is accepted and a timestamp without an offset is taken as UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone


def parse_iso_utc(text: str) -> datetime:
    """
    Return ``text`` as a timezone-aware datetime.

    :param text: an ISO-8601 timestamp such as ``2026-05-24T10:00:00Z``
    :raises ValueError: when ``text`` is not an ISO-8601 timestamp
    """
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment
