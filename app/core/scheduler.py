"""SM-2 spaced-repetition scheduling.

Deterministic core logic: given a card's current scheduling state and a
recall-quality grade (0-5, SuperMemo convention), compute the next review
interval, easiness factor and due date. Pure functions, fully unit-testable
without any AI component or persistence.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


MIN_EASINESS_FACTOR = 1.3


@dataclass
class SchedulerState:
    easiness_factor: float
    interval_days: int
    repetitions: int


@dataclass
class SchedulerResult:
    state: SchedulerState
    due_at: datetime


def review(state: SchedulerState, grade: int, now: datetime | None = None) -> SchedulerResult:
    """Apply one SM-2 review step.

    grade: 0-5, where >=3 counts as a correct/successful recall.
    Raises ValueError for out-of-range grades so bad input fails loudly
    instead of silently corrupting scheduling state.
    """
    if not isinstance(grade, int) or not (0 <= grade <= 5):
        raise ValueError(f"grade must be an integer in [0, 5], got {grade!r}")

    now = now or datetime.now(timezone.utc)

    ef = state.easiness_factor
    reps = state.repetitions
    interval = state.interval_days

    if grade < 3:
        # Failed recall: restart repetitions, review again soon, but keep
        # (and still adjust) the easiness factor per the original SM-2 spec.
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        reps += 1

    ef = ef + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    ef = max(MIN_EASINESS_FACTOR, ef)

    new_state = SchedulerState(easiness_factor=round(ef, 3), interval_days=interval, repetitions=reps)
    due_at = now + timedelta(days=interval)
    return SchedulerResult(state=new_state, due_at=due_at)
