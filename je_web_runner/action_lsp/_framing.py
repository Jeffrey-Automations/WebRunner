"""
LSP 訊息的分框
The framing of language-server messages: ``Content-Length: <bytes>`` headers, a blank line, a UTF-8 body.

``Content-Length`` counts bytes. A console stream is therefore read and written through its ``buffer``, as
bytes: text mode would count characters on the way in and write the locale's encoding (cp950, cp1252 …)
on the way out, and either one moves the boundary of every message after the first non-ASCII character.
A stream without a ``buffer`` (an in-memory text stream) is read one character at a time until the body has
the announced number of UTF-8 bytes.
"""
from __future__ import annotations

import json
from typing import Any, TextIO

from je_web_runner.utils.exception.exceptions import WebRunnerException

_ENCODING = "utf-8"
_CONTENT_LENGTH = "content-length"


class ActionLspError(WebRunnerException):
    """Raised when a request can't be parsed or handled."""


def _source(stream: Any) -> Any:
    """The byte stream under a console stream, or the stream itself when it has none."""
    return getattr(stream, "buffer", None) or stream


def _text(chunk: Any) -> str:
    return chunk.decode(_ENCODING, errors="replace") if isinstance(chunk, bytes) else chunk


def _read_headers(source: Any) -> dict[str, str] | None:
    """The headers of the next message, lower-cased; None at the end of the stream."""
    headers: dict[str, str] = {}
    while True:
        line = _text(source.readline())
        if line == "":
            return None
        line = line.rstrip("\r\n")
        if not line:
            return headers
        name, separator, value = line.partition(":")
        if separator:
            headers[name.strip().lower()] = value.strip()


def _read_text_body(source: Any, length: int) -> str:
    """Characters of a text stream until they make ``length`` UTF-8 bytes (or the stream ends)."""
    characters: list[str] = []
    remaining = length
    while remaining > 0:
        character = source.read(1)
        if not character:
            break
        characters.append(character)
        remaining -= len(character.encode(_ENCODING))
    return "".join(characters)


def _read_body(source: Any, length: int) -> str:
    probe = source.read(0)
    if isinstance(probe, bytes):
        return source.read(length).decode(_ENCODING, errors="replace")
    return _read_text_body(source, length)


def read_message(stream: TextIO) -> dict[str, Any] | None:
    """
    The next message of ``stream``, or None when the stream ended or a message has no ``Content-Length``.

    :raises ActionLspError: when ``Content-Length`` is not a number or the body is not JSON.
    """
    source = _source(stream)
    headers = _read_headers(source)
    if headers is None or _CONTENT_LENGTH not in headers:
        return None
    try:
        length = int(headers[_CONTENT_LENGTH])
    except ValueError as error:
        raise ActionLspError(f"invalid Content-Length: {error}") from error
    body = _read_body(source, length)
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError as error:
        raise ActionLspError(f"body is not JSON: {error}") from error


def write_message(stream: TextIO, message: dict[str, Any]) -> None:
    """Write ``message`` to ``stream`` with its ``Content-Length`` in UTF-8 bytes."""
    body = json.dumps(message, ensure_ascii=False)
    payload = body.encode(_ENCODING)
    header = f"Content-Length: {len(payload)}\r\n\r\n"
    binary = getattr(stream, "buffer", None)
    if binary is not None:
        stream.flush()
        binary.write(header.encode("ascii") + payload)
        binary.flush()
    else:
        stream.write(header + body)
        stream.flush()
