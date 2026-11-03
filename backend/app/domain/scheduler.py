from datetime import datetime, time, timedelta

from .schedule_rules import (
    EARLIEST_WORKOUT_START,
    EVENING_START_TIME,
    EVENT_BUFFER_MINUTES,
    LATEST_HIIT_START,
    LATEST_NON_RING_WORKOUT_MORNING_START,
    LATEST_RING_WORKOUT_MORNING_START,
    LATEST_WORKOUT_START,
    WORKOUT_DURATION_MINUTES,
)
from .workout_types import WorkoutType

# Check workout times against the planner rules.


# Check the time limits for this workout type.
def is_allowed_start_time(
    start_time: time,
    workout_type: WorkoutType,
    uses_rings: bool = False,
) -> bool:
    if not EARLIEST_WORKOUT_START <= start_time <= LATEST_WORKOUT_START:
        return False

    if workout_type in (WorkoutType.HIIT_LEGS, WorkoutType.HIIT_ABS):
        return start_time <= LATEST_HIIT_START

    if workout_type == WorkoutType.PULL or uses_rings:
        return (
            start_time <= LATEST_RING_WORKOUT_MORNING_START
            or start_time >= EVENING_START_TIME
        )

    if workout_type in (WorkoutType.PUSH, WorkoutType.LEGS):
        return (
            start_time <= LATEST_NON_RING_WORKOUT_MORNING_START
            or start_time >= EVENING_START_TIME
        )

    return True


# Check whether a workout overlaps one calendar event.
def overlaps_calendar_event(
    workout_start: datetime,
    calendar_event_start: datetime,
    calendar_event_end: datetime,
) -> bool:
    workout_end = workout_start + timedelta(minutes=WORKOUT_DURATION_MINUTES)

    return (
        workout_start < calendar_event_end
        and workout_end > calendar_event_start
    )


# Check whether the workout fits around one event and its buffer.
def fits_around_calendar_event(
    workout_start: datetime,
    calendar_event_start: datetime,
    calendar_event_end: datetime,
) -> bool:
    workout_end = workout_start + timedelta(minutes=WORKOUT_DURATION_MINUTES)

    if overlaps_calendar_event(
        workout_start,
        calendar_event_start,
        calendar_event_end,
    ):
        return False

    if calendar_event_start >= workout_end:
        workout_and_buffer_end = workout_end + timedelta(
            minutes=EVENT_BUFFER_MINUTES
        )
        return workout_and_buffer_end <= calendar_event_start

    return True


# Check every calendar event against the proposed workout time.
def fits_around_calendar_events(
    workout_start: datetime,
    calendar_events: list[tuple[datetime, datetime]],
) -> bool:
    return all(
        fits_around_calendar_event(
            workout_start,
            calendar_event_start,
            calendar_event_end,
        )
        for calendar_event_start, calendar_event_end in calendar_events
    )


# Combine the time limits and calendar checks.
def can_schedule_workout(
    workout_start: datetime,
    workout_type: WorkoutType,
    calendar_events: list[tuple[datetime, datetime]],
    uses_rings: bool = False,
) -> bool:
    return (
        is_allowed_start_time(workout_start.time(), workout_type, uses_rings)
        and fits_around_calendar_events(workout_start, calendar_events)
    )
