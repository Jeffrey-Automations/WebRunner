"""download_verify: a PDF the reader cannot parse is a DownloadVerifyError, not the reader's own error."""
import sys
import types

import pytest

from je_web_runner.utils.download_verify.verifier import DownloadVerifyError, extract_pdf_text


class _BrokenPdfError(Exception):
    """Stands for pypdf's PdfReadError."""


def _reader_that_rejects(_path):
    raise _BrokenPdfError("EOF marker not found")


def test_corrupt_pdf_raises_the_library_error(tmp_path, monkeypatch):
    fake_pypdf = types.ModuleType("pypdf")
    fake_pypdf.PdfReader = _reader_that_rejects
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    corrupt = tmp_path / "broken.pdf"
    corrupt.write_bytes(b"%PDF-1.7 this is not a PDF")
    with pytest.raises(DownloadVerifyError, match="failed to extract PDF text"):
        extract_pdf_text(corrupt)
