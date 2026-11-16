"""chrome_profile: a snapshot directory that is, holds or lies inside the profile is refused, not deleted."""
import pytest

from je_web_runner.utils.chrome_profile.profile_manager import ChromeProfileError, snapshot_chrome_profile


def _profile(root):
    profile = root / "work" / "profile"
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("session", encoding="utf-8")
    (profile / "Local State").write_text("{}", encoding="utf-8")
    return profile


def test_snapshot_onto_the_profile_itself_is_refused(tmp_path):
    profile = _profile(tmp_path)
    with pytest.raises(ChromeProfileError, match="snapshot"):
        snapshot_chrome_profile(profile, profile)
    assert (profile / "Default" / "Cookies").read_text(encoding="utf-8") == "session"


def test_snapshot_onto_a_parent_of_the_profile_is_refused(tmp_path):
    profile = _profile(tmp_path)
    with pytest.raises(ChromeProfileError, match="snapshot"):
        snapshot_chrome_profile(profile, tmp_path / "work")
    assert (profile / "Default" / "Cookies").read_text(encoding="utf-8") == "session"


def test_snapshot_inside_the_profile_is_refused(tmp_path):
    profile = _profile(tmp_path)
    with pytest.raises(ChromeProfileError, match="snapshot"):
        snapshot_chrome_profile(profile, profile / "snapshot")
    assert not (profile / "snapshot").exists()
