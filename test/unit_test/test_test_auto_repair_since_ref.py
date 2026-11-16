"""``since_ref`` is checked before it becomes a ``git`` argument."""
import subprocess

import pytest

from je_web_runner.utils.test_auto_repair.repair import TestAutoRepairError, collect_git_diff


def _recording_runner(calls):
    def runner(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "diff --git a/x b/x", "")
    return runner


@pytest.mark.parametrize("hostile", ["--output=stolen.txt", "-O", "", None, "--no-index"])
def test_since_ref_that_is_not_a_revision_never_reaches_git(hostile):
    calls = []
    with pytest.raises(TestAutoRepairError):
        collect_git_diff(".", since_ref=hostile, runner=_recording_runner(calls))
    assert calls == []


def test_a_revision_still_reaches_git():
    calls = []
    text = collect_git_diff("repo", since_ref="HEAD~2", runner=_recording_runner(calls))
    assert text == "diff --git a/x b/x"
    assert calls == [["git", "-C", "repo", "diff", "HEAD~2..HEAD", "--unified=2"]]
