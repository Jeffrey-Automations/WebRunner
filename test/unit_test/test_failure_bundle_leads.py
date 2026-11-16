"""failure_bundle: an entry name cannot point outside the bundle or replace its manifest."""
import zipfile

import pytest

from je_web_runner.utils.failure_bundle.bundle import FailureBundle, FailureBundleError, extract_bundle

HOSTILE = [
    "../x", "..\\x", "a/../../x", "/etc/passwd", "\\\\server\\share\\x", "C:\\Windows\\x", "c:x",
    "", ".", "a/./b", "a//b", "bad\x00name", "trailing/",
]


def _bundle() -> FailureBundle:
    return FailureBundle(test_name="t", error_repr="boom")


@pytest.mark.parametrize("name", HOSTILE)
def test_hostile_names_are_refused_by_every_method_that_takes_a_name(name, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("x", encoding="utf-8")
    bundle = _bundle()
    with pytest.raises(FailureBundleError, match="entry name"):
        bundle.add_text(name, "x")
    with pytest.raises(FailureBundleError, match="entry name"):
        bundle.add_dom("<p>x</p>", name)
    with pytest.raises(FailureBundleError, match="entry name"):
        bundle.add_screenshot(b"png", name)
    if name:
        with pytest.raises(FailureBundleError, match="entry name"):
            bundle.add_file(source, name)


def test_the_manifest_cannot_be_replaced(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("x", encoding="utf-8")
    with pytest.raises(FailureBundleError, match="entry name"):
        _bundle().add_file(source, "manifest.json")


def test_no_written_entry_leaves_the_bundle(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("x", encoding="utf-8")
    bundle = _bundle()
    bundle.add_text("notes.txt", "n")
    bundle.add_text("logs/run.txt", "nested")
    bundle.add_file(source)
    bundle.add_file(source, "extra/source.txt")
    path = bundle.write(tmp_path / "out.zip")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    assert sorted(names) == [
        "artifacts/logs/run.txt", "artifacts/notes.txt", "artifacts/source.txt", "extra/source.txt",
        "manifest.json",
    ]
    assert extract_bundle(path)["files"]["artifacts/logs/run.txt"] == b"nested"
