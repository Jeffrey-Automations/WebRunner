"""Gap versus overlap, unknown zones, and what a daily job fires on a transition day."""
from datetime import datetime, timezone

import pytest

from je_web_runner.utils.dst_boundary_test.boundary import (
    DstBoundaryError,
    Transition,
    expected_fires_around_boundary,
    find_boundaries,
    is_ambiguous_local_time,
    is_nonexistent_local_time,
)

NEW_YORK = "America/New_York"


def _boundary(transition: Transition):
    return next(b for b in find_boundaries(NEW_YORK, 2024, 2024) if b.transition == transition)


def test_a_time_in_the_spring_gap_is_not_ambiguous():
    in_gap = datetime(2024, 3, 10, 2, 30)
    assert is_nonexistent_local_time(NEW_YORK, in_gap) is True
    assert is_ambiguous_local_time(NEW_YORK, in_gap) is False
    assert is_ambiguous_local_time(NEW_YORK, datetime(2024, 11, 3, 1, 30)) is True


@pytest.mark.parametrize("check", [is_nonexistent_local_time, is_ambiguous_local_time])
def test_an_unknown_zone_is_the_module_error(check):
    with pytest.raises(DstBoundaryError, match="unknown timezone"):
        check("Mars/Olympus", datetime(2024, 1, 1))


def test_expected_fires_reports_an_unknown_zone_as_the_module_error():
    boundary = _boundary(Transition.FALL_BACK)
    boundary.tz_name = "Mars/Olympus"
    with pytest.raises(DstBoundaryError, match="unknown timezone"):
        expected_fires_around_boundary(boundary)


def test_spring_forward_skips_only_a_job_inside_the_gap():
    boundary = _boundary(Transition.SPRING_FORWARD)
    assert expected_fires_around_boundary(boundary, 2, 30) == []
    fires = expected_fires_around_boundary(boundary, 9, 0)
    assert [fire.moment_utc for fire in fires] == [datetime(2024, 3, 10, 13, 0, tzinfo=timezone.utc)]


def test_fall_back_doubles_only_a_job_inside_the_overlap():
    boundary = _boundary(Transition.FALL_BACK)
    twice = expected_fires_around_boundary(boundary, 1, 30)
    assert [fire.moment_utc for fire in twice] == [
        datetime(2024, 11, 3, 5, 30, tzinfo=timezone.utc),
        datetime(2024, 11, 3, 6, 30, tzinfo=timezone.utc),
    ]
    once = expected_fires_around_boundary(boundary)
    assert [fire.moment_utc for fire in once] == [datetime(2024, 11, 3, 7, 30, tzinfo=timezone.utc)]
