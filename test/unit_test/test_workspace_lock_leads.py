"""workspace_lock: ``allow_distributions`` keeps only the named packages, an empty list keeps none."""
from je_web_runner.utils.workspace_lock import lock as lock_module
from je_web_runner.utils.workspace_lock.lock import build_lock

INSTALLED = [("selenium", "4.41.0"), ("typing_extensions", "4.12.0"), ("requests", "2.32.0")]


def _python_names(monkeypatch, allow):
    monkeypatch.setattr(lock_module, "_scan_distributions", lambda: INSTALLED)
    return [entry.name for entry in build_lock(allow_distributions=allow).by_kind("python")]


def test_empty_allow_list_keeps_no_python_package(monkeypatch):
    assert _python_names(monkeypatch, []) == []


def test_no_allow_list_keeps_every_python_package(monkeypatch):
    assert _python_names(monkeypatch, None) == ["requests", "selenium", "typing-extensions"]


def test_allow_list_names_are_normalised_like_the_installed_ones(monkeypatch):
    assert _python_names(monkeypatch, ["Typing_Extensions", "selenium"]) == ["selenium", "typing-extensions"]
