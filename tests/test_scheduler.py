from datetime import datetime, timezone

import pytest

from app.core.scheduler import SchedulerState, review


def make_state():
    return SchedulerState(easiness_factor=2.5, interval_days=0, repetitions=0)


def test_first_successful_review_sets_interval_to_one_day():
    result = review(make_state(), grade=4)
    assert result.state.interval_days == 1
    assert result.state.repetitions == 1


def test_second_successful_review_sets_interval_to_six_days():
    state = make_state()
    r1 = review(state, grade=4)
    r2 = review(r1.state, grade=4)
    assert r2.state.interval_days == 6
    assert r2.state.repetitions == 2


def test_third_successful_review_multiplies_interval_by_easiness_factor():
    state = make_state()
    r1 = review(state, grade=4)
    r2 = review(r1.state, grade=4)
    r3 = review(r2.state, grade=4)
    assert r3.state.interval_days == round(6 * r2.state.easiness_factor)


def test_failed_recall_resets_repetitions_and_interval():
    state = SchedulerState(easiness_factor=2.5, interval_days=30, repetitions=5)
    result = review(state, grade=1)
    assert result.state.repetitions == 0
    assert result.state.interval_days == 1


def test_easiness_factor_never_drops_below_minimum():
    state = SchedulerState(easiness_factor=1.3, interval_days=1, repetitions=1)
    for _ in range(10):
        result = review(state, grade=0)
        state = result.state
    assert state.easiness_factor >= 1.3


def test_due_at_is_now_plus_interval_days():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = review(make_state(), grade=5, now=now)
    assert (result.due_at - now).days == result.state.interval_days


@pytest.mark.parametrize("bad_grade", [-1, 6, 3.5, "3", None])
def test_invalid_grade_raises(bad_grade):
    with pytest.raises(ValueError):
        review(make_state(), grade=bad_grade)  # type: ignore[arg-type]
