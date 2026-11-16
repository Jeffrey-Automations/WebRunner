"""
把 HAR 字串或 dict 轉成 dict，供各個讀 HAR 的稽核模組共用。
Turn the HAR a caller passed (a JSON string or an already-parsed dict) into a dict.
Shared by the modules that read a HAR; each one passes its own exception class so
its callers keep catching the error they always caught.
"""
from __future__ import annotations

import json
from typing import Any


def coerce_har(
    har: Any,
    error_class: type[Exception],
    caller: str,
    not_json: str = "har not JSON",
) -> dict[str, Any]:
    """
    Return ``har`` as a dict: a dict is returned as it is, a string is parsed as JSON.

    :param har: the HAR, as a JSON string or a dict
    :param error_class: the exception raised for input that is neither, or is not a JSON object
    :param caller: the public function named in the "expects str/dict" message
    :param not_json: the start of the message raised for a string that is not JSON
    """
    if isinstance(har, str):
        try:
            parsed = json.loads(har)
        except ValueError as error:
            raise error_class(f"{not_json}: {error}") from error
        if not isinstance(parsed, dict):
            raise error_class("har JSON must be an object")
        return parsed
    if isinstance(har, dict):
        return har
    raise error_class(f"{caller} expects str/dict, got {type(har).__name__}")
