"""
CompressionStream / DecompressionStream round-trip verification.

This module lets a Python test confirm that data the page compresses
with the Compression Streams API can be decompressed by the standard
``gzip`` / ``zlib`` / ``brotli`` libs (and vice versa). Helps catch:

* Wrong algorithm constant (``deflate-raw`` vs ``deflate``).
* Encoding stripped before transit (page calls ``.text()`` instead of
  ``.arrayBuffer()``).
* Brotli used where a CDN strips ``br`` Content-Encoding.
"""
from __future__ import annotations

import gzip
import zlib
from enum import Enum

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CompressionStreamsError(WebRunnerException):
    """Raised when a round-trip check fails or input is malformed."""


class Algorithm(str, Enum):
    """The formats ``decompress`` reads.

    ``gzip``, ``deflate`` and ``deflate-raw`` are also ``CompressionStream`` formats. ``br`` is the
    ``Content-Encoding`` token of Brotli, for bytes that come from elsewhere (a response body): it is
    not a ``CompressionStream`` format, and Chromium 148 refuses both ``br`` and ``brotli`` with
    "Unsupported compression format", so ``HARVEST_SCRIPT`` cannot be run with it.
    """
    GZIP = "gzip"
    DEFLATE = "deflate"
    DEFLATE_RAW = "deflate-raw"
    BROTLI = "br"


# An async function expression taking (algorithm, text) and resolving to the base64 of the compressed
# bytes: pass it to ``page.evaluate`` with its arguments, or call it from an ``execute_script`` body
# (``return (<script>)(arguments[0], arguments[1]);`` after dropping its final ``;``).
HARVEST_SCRIPT = r"""
async (algorithm, text) => {
  const stream = new Blob([text]).stream();
  const compressed = stream.pipeThrough(new CompressionStream(algorithm));
  const chunks = [];
  const reader = compressed.getReader();
  while (true) {
    const {value, done} = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const merged = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) { merged.set(c, off); off += c.length; }
  let bin = '';
  for (const b of merged) bin += String.fromCharCode(b);
  return btoa(bin);
};
"""


def _decompress_gzip(data: bytes) -> bytes:
    try:
        return gzip.decompress(bytes(data))
    except OSError as exc:
        raise CompressionStreamsError(
            f"gzip decompression failed: {exc!r}"
        ) from exc


def _decompress_deflate(data: bytes) -> bytes:
    try:
        return zlib.decompress(bytes(data))
    except zlib.error as exc:
        raise CompressionStreamsError(
            f"deflate decompression failed: {exc!r}"
        ) from exc


def _decompress_deflate_raw(data: bytes) -> bytes:
    try:
        return zlib.decompress(bytes(data), -zlib.MAX_WBITS)
    except zlib.error as exc:
        raise CompressionStreamsError(
            f"deflate-raw decompression failed: {exc!r}"
        ) from exc


def _decompress_brotli(data: bytes) -> bytes:
    # brotli is optional
    try:
        import brotli   # type: ignore
    except ImportError as exc:
        raise CompressionStreamsError(
            "brotli decompression requested but `brotli` package not installed"
        ) from exc
    try:
        return brotli.decompress(bytes(data))
    except brotli.error as exc:   # pragma: no cover - depends on optional dep
        raise CompressionStreamsError(
            f"brotli decompression failed: {exc!r}"
        ) from exc


def decompress(data: bytes, algorithm: Algorithm) -> bytes:
    """Decompress ``data`` with ``algorithm``; raise ``CompressionStreamsError`` for a wrong argument type."""
    if not isinstance(data, (bytes, bytearray)):
        raise CompressionStreamsError("data must be bytes")
    if not isinstance(algorithm, Algorithm):
        raise CompressionStreamsError(
            "algorithm must be Algorithm enum"
        )
    if algorithm == Algorithm.GZIP:
        return _decompress_gzip(data)
    if algorithm == Algorithm.DEFLATE:
        return _decompress_deflate(data)
    if algorithm == Algorithm.DEFLATE_RAW:
        return _decompress_deflate_raw(data)
    return _decompress_brotli(data)


def assert_round_trip(
    *, original: bytes, compressed: bytes, algorithm: Algorithm,
) -> None:
    """Verify ``decompress(compressed) == original``."""
    if not isinstance(original, (bytes, bytearray)):
        raise CompressionStreamsError("original must be bytes")
    recovered = decompress(compressed, algorithm)
    if recovered != bytes(original):
        raise CompressionStreamsError(
            f"round-trip mismatch: original {len(original)}B vs "
            f"recovered {len(recovered)}B"
        )


def compression_ratio(original_size: int, compressed_size: int) -> float:
    """Return compressed size divided by original size; raise if the original size is not positive."""
    if original_size <= 0:
        raise CompressionStreamsError("original_size must be positive")
    return compressed_size / original_size


def assert_ratio_under(
    *, original_size: int, compressed_size: int, max_ratio: float,
) -> None:
    """Compressed must be at most ``max_ratio`` × original (e.g. 0.5)."""
    if max_ratio <= 0 or max_ratio > 1:
        raise CompressionStreamsError("max_ratio must be in (0, 1]")
    ratio = compression_ratio(original_size, compressed_size)
    if ratio > max_ratio:
        raise CompressionStreamsError(
            f"compression ratio {ratio:.2f} exceeds {max_ratio:.2f} "
            f"(compressed {compressed_size}B vs original {original_size}B)"
        )
