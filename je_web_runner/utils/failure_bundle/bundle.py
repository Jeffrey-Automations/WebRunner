"""
失敗時打包重現用素材：screenshot / DOM snapshot / 網路紀錄 / console / trace。
Failure bundle: collect screenshot bytes, DOM HTML, network log, console
log, OTel trace, and any extra files into a single zip with a manifest.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FailureBundleError(WebRunnerException):
    """Raised when bundle building or reading fails."""


_MANIFEST_NAME = "manifest.json"


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry_name(name: Any, prefix: str = "") -> str:
    """
    ``prefix + name`` as a zip entry name, once ``name`` is known to stay inside the bundle.

    A name is ``/``-separated parts, none empty, ``.`` or ``..``; it has no backslash, colon or NUL
    and does not start with ``/``, so extracting the bundle cannot write outside the target folder
    on any system. The manifest's name is refused too.
    """
    if not isinstance(name, str) or not name:
        raise FailureBundleError(f"bad entry name {name!r}: must be a non-empty string")
    if any(char in name for char in ("\\", ":", "\x00")):
        raise FailureBundleError(f"bad entry name {name!r}: backslash, colon and NUL are not allowed")
    if any(part in ("", ".", "..") for part in name.split("/")):
        raise FailureBundleError(f"bad entry name {name!r}: must be a relative path without '.' or '..' parts")
    target = prefix + name
    if target == _MANIFEST_NAME:
        raise FailureBundleError(f"bad entry name {name!r}: reserved for the manifest")
    return target


@dataclass
class FailureBundle:
    """Builder for one failure bundle."""

    test_name: str
    error_repr: str
    captured_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
    _entries: dict[str, bytes] = field(default_factory=dict)

    def add_screenshot(self, png_bytes: bytes, name: str = "screenshot.png") -> None:
        """Add a PNG screenshot under ``artifacts/``; raise ``FailureBundleError`` if it is not bytes
        or ``name`` could leave the bundle."""
        if not isinstance(png_bytes, (bytes, bytearray)):
            raise FailureBundleError("screenshot must be bytes")
        self._entries[_entry_name(name, "artifacts/")] = bytes(png_bytes)

    def add_dom(self, html: str, name: str = "dom.html") -> None:
        """Add the page HTML under ``artifacts/``; raise ``FailureBundleError`` if ``name`` could leave the bundle."""
        self._entries[_entry_name(name, "artifacts/")] = html.encode("utf-8")

    def add_console(self, messages: list[dict[str, Any]]) -> None:
        """Add the console messages as ``artifacts/console.json``."""
        self._entries["artifacts/console.json"] = json.dumps(
            messages, ensure_ascii=False, indent=2
        ).encode("utf-8")

    def add_network(self, responses: list[dict[str, Any]]) -> None:
        """Add the network responses as ``artifacts/network.json``."""
        self._entries["artifacts/network.json"] = json.dumps(
            responses, ensure_ascii=False, indent=2
        ).encode("utf-8")

    def add_trace(self, trace_path: str | Path) -> None:
        """Add a trace file under ``artifacts/``; raise ``FailureBundleError`` if it does not exist."""
        path = Path(trace_path)
        if not path.is_file():
            raise FailureBundleError(f"trace file not found: {trace_path!r}")
        self._entries[_entry_name(path.name, "artifacts/")] = path.read_bytes()

    def add_file(self, source: str | Path, inside_name: str | None = None) -> None:
        """Add any file, under ``inside_name`` or ``artifacts/<file name>``; raise ``FailureBundleError`` if it
        does not exist or ``inside_name`` could leave the bundle or is the manifest's name."""
        path = Path(source)
        if not path.is_file():
            raise FailureBundleError(f"file not found: {source!r}")
        target = _entry_name(inside_name) if inside_name else _entry_name(path.name, "artifacts/")
        self._entries[target] = path.read_bytes()

    def add_text(self, name: str, text: str) -> None:
        """Add ``text`` as a UTF-8 file under ``artifacts/``; raise ``FailureBundleError`` if ``name`` could leave
        the bundle."""
        self._entries[_entry_name(name, "artifacts/")] = text.encode("utf-8")

    def _manifest(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "error_repr": self.error_repr,
            "captured_at": self.captured_at,
            "metadata": self.metadata,
            "artifacts": [
                {"name": name, "size": len(data), "sha256": _sha256_bytes(data)}
                for name, data in sorted(self._entries.items())
            ],
        }

    def write(self, output_path: str | Path) -> Path:
        """Write the manifest and every entry to a zip at ``output_path`` and return that path."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                _MANIFEST_NAME,
                json.dumps(self._manifest(), ensure_ascii=False, indent=2),
            )
            for name, data in sorted(self._entries.items()):
                zf.writestr(name, data)
        return path


def extract_bundle(zip_path: str | Path) -> dict[str, Any]:
    """Read a bundle and return ``{manifest, files: {name: bytes}}``."""
    path = Path(zip_path)
    if not path.is_file():
        raise FailureBundleError(f"bundle not found: {zip_path!r}")
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        if _MANIFEST_NAME not in names:
            raise FailureBundleError("manifest.json missing from bundle")
        manifest = json.loads(zf.read(_MANIFEST_NAME).decode("utf-8"))
        for name in names:
            if name == _MANIFEST_NAME:
                continue
            files[name] = zf.read(name)
    return {"manifest": manifest, "files": files}
