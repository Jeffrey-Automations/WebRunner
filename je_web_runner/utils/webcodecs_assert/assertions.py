"""
WebCodecs verification helpers.

Lets tests pin down the codec characteristics produced by a page (e.g.
"the recorder must emit H.264 baseline at 30 fps, not VP9 60 fps").
The harness side captures ``EncodedVideoChunk`` / ``EncodedAudioChunk``
metadata via a small JS shim; this module parses it and provides
assertions on resolution / framerate / keyframe interval / codec id.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebcodecsAssertError(WebRunnerException):
    """Raised when a WebCodecs invariant fails."""


# Installs the recorder ``window.__wr_codec__`` (idempotent); it does not read anything back. The page's
# encoder output callback calls ``__wr_codec__.record('video' | 'audio', chunk, metadata)``, and the
# harness reads the chunks with ``return window.__wr_codec__.drain('video');`` and gives them to
# ``parse_chunks``. As an expression (``page.evaluate``) the script's value is the recorder itself.
INSTALL_SCRIPT = r"""
(function () {
  if (window.__wr_codec__) return window.__wr_codec__;
  const captures = {video: [], audio: []};
  window.__wr_codec__ = {
    record: function (kind, chunk, meta) {
      captures[kind].push({
        type: chunk.type,
        timestamp: chunk.timestamp,
        duration: chunk.duration,
        byteLength: chunk.byteLength,
        codec: meta && meta.codec,
        width: meta && meta.width,
        height: meta && meta.height,
      });
    },
    drain: function (kind) { return captures[kind].splice(0); },
  };
  return window.__wr_codec__;
})();
"""

# The first name of ``INSTALL_SCRIPT``, kept for callers that import it: it installs, it does not harvest.
HARVEST_SCRIPT = INSTALL_SCRIPT


class ChunkType(str, Enum):
    """Whether an encoded chunk is a key frame or a delta frame."""
    KEY = "key"
    DELTA = "delta"


@dataclass
class EncodedChunk:
    """Metadata of one encoded video or audio chunk captured in the page."""
    type: ChunkType
    timestamp_us: int
    duration_us: int = 0
    bytes: int = 0
    codec: str = ""
    width: int = 0
    height: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return the fields as a plain dict, with the ``type`` enum replaced by its string value."""
        return {**asdict(self), "type": self.type.value}


def parse_chunks(payload: Any) -> list[EncodedChunk]:
    """Turn the list captured in the page into ``EncodedChunk`` records, skipping
    entries that are not objects. Raises ``WebcodecsAssertError`` when the payload is
    not a list or a chunk has an unknown type.
    """
    if not isinstance(payload, list):
        raise WebcodecsAssertError("payload must be a list")
    out: list[EncodedChunk] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        type_str = raw.get("type", "delta")
        try:
            chunk_type = ChunkType(type_str)
        except ValueError as exc:
            raise WebcodecsAssertError(
                f"unknown chunk type {type_str!r}"
            ) from exc
        out.append(EncodedChunk(
            type=chunk_type,
            timestamp_us=int(raw.get("timestamp") or 0),
            duration_us=int(raw.get("duration") or 0),
            bytes=int(raw.get("byteLength") or 0),
            codec=str(raw.get("codec") or ""),
            width=int(raw.get("width") or 0),
            height=int(raw.get("height") or 0),
        ))
    return out


def assert_codec(chunks: Sequence[EncodedChunk], expected: str) -> None:
    """Raise ``WebcodecsAssertError`` when there are no chunks, or when a chunk that
    declares a codec declares one other than ``expected``.
    """
    if not chunks:
        raise WebcodecsAssertError("chunks empty")
    bad = [c for c in chunks if c.codec and c.codec != expected]
    if bad:
        actual = {c.codec for c in bad}
        raise WebcodecsAssertError(
            f"expected codec {expected!r}, found {actual}"
        )


def assert_resolution(
    chunks: Sequence[EncodedChunk], *, width: int, height: int,
) -> None:
    """Raise ``WebcodecsAssertError`` when a chunk that carries a size is not
    ``width`` x ``height``.
    """
    if width <= 0 or height <= 0:
        raise WebcodecsAssertError("width/height must be positive")
    for c in chunks:
        if c.width and c.height and (c.width != width or c.height != height):
            raise WebcodecsAssertError(
                f"resolution {c.width}×{c.height} != {width}×{height}"
            )


def assert_keyframe_interval(
    chunks: Sequence[EncodedChunk], *, max_gap: int,
) -> None:
    """Raise ``WebcodecsAssertError`` when more than ``max_gap`` delta chunks follow
    one another without a key chunk.
    """
    if max_gap <= 0:
        raise WebcodecsAssertError("max_gap must be positive")
    gap = 0
    for c in chunks:
        if c.type == ChunkType.KEY:
            gap = 0
        else:
            gap += 1
        if gap > max_gap:
            raise WebcodecsAssertError(
                f"non-key gap {gap} exceeded max_gap {max_gap}"
            )


def estimate_framerate(chunks: Sequence[EncodedChunk]) -> float:
    """fps from median inter-chunk timestamp delta (in microseconds)."""
    if len(chunks) < 2:
        return 0.0
    deltas = [b.timestamp_us - a.timestamp_us
              for a, b in zip(chunks, chunks[1:], strict=False)
              if b.timestamp_us > a.timestamp_us]
    if not deltas:
        return 0.0
    median = statistics.median(deltas)
    if median <= 0:
        return 0.0
    return 1_000_000 / median


def assert_framerate_at_least(
    chunks: Sequence[EncodedChunk], *, min_fps: float,
) -> None:
    """Raise ``WebcodecsAssertError`` when the estimated frame rate is below ``min_fps``."""
    if min_fps <= 0:
        raise WebcodecsAssertError("min_fps must be positive")
    fps = estimate_framerate(chunks)
    if fps < min_fps:
        raise WebcodecsAssertError(
            f"framerate {fps:.1f} fps < required {min_fps}"
        )
