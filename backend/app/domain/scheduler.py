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
    RESCHEDULE_INTERVAL_MINUTES,
    PLAN_HORIZON_DAYS,
    MAX_CONSECUTIVE_WORKOUT_DAYS,
)
from .workout_types import WORKOUT_VARIANT_ROTATIONS, WorkoutType, WorkoutVariant
from .planned_workout import PlannedWorkout
from .completed_workout import CompletedWorkout
from .skipped_workout import SkippedWorkout
from .scheduler_state import SchedulerState

# Schedule the next workout in the rotation.
def schedule_next_workout(
    first_candidate_start: datetime,
    previous_workout_type: WorkoutType | None,
    calendar_events: list[tuple[datetime, datetime]],
    other_workouts: list[PlannedWorkout],
    uses_rings: bool = False,
    completed_workouts: list[CompletedWorkout] | None = None,
) -> PlannedWorkout | None:
    workout_type = get_next_workout_type(previous_workout_type)
    variant = get_next_workout_variant(
        workout_type,
        completed_workouts or [],
        [],
    )
    if workout_type == WorkoutType.PUSH and uses_rings:
        variant = WorkoutVariant.PUSH_DIPS
    workout_uses_rings = (
        uses_rings
        or workout_type == WorkoutType.PULL
        or variant == WorkoutVariant.PUSH_DIPS
    )
    other_workout_starts = [workout.starts_at for workout in other_workouts]

    available_start = find_next_available_start_in_plan(
        first_candidate_start,
        workout_type,
        calendar_events,
        other_workout_starts,
        workout_uses_rings,
    )

    if available_start is None:
        return None

    return PlannedWorkout(
        workout_type=workout_type,
        starts_at=available_start,
        uses_rings=workout_uses_rings,
        variant=variant,
    )


# The repeating order used to choose the next workout.
WORKOUT_ROTATION = (
    WorkoutType.HIIT_LEGS,
    WorkoutType.PUSH,
    WorkoutType.RUN,
    WorkoutType.LEGS,
    WorkoutType.HIIT_ABS,
    WorkoutType.PULL,
)


# Move to the next workout in the rotation.
def get_next_workout_type(
    current_workout_type: WorkoutType | None = None,
) -> WorkoutType:
    if current_workout_type is None:
        return WORKOUT_ROTATION[0]

    current_position = WORKOUT_ROTATION.index(current_workout_type)
    next_position = (current_position + 1) % len(WORKOUT_ROTATION)
    return WORKOUT_ROTATION[next_position]


# Pick the next variation after completed and already planned sessions.
def get_next_workout_variant(
    workout_type: WorkoutType,
    completed_workouts: list[CompletedWorkout],
    planned_workouts: list[PlannedWorkout],
) -> WorkoutVariant | None:
    variant_rotation = WORKOUT_VARIANT_ROTATIONS.get(workout_type)
    if variant_rotation is None:
        return None

    completed_count = sum(
        workout.workout_type == workout_type and workout.variant is not None
        for workout in completed_workouts
    )
    planned_count = sum(
        workout.workout_type == workout_type and workout.variant is not None
        for workout in planned_workouts
    )
    rotation_position = (completed_count + planned_count) % len(variant_rotation)
    return variant_rotation[rotation_position]



# Restore rotation progress from workouts that fulfilled planned slots.
def get_scheduler_state_from_history(
    completed_workouts: list[CompletedWorkout],
    skipped_workouts: list[SkippedWorkout] | None = None,
) -> SchedulerState:
    rotation_cursor = None
    replacement_run_due = False
    history = [
        (workout.completed_at, workout.rotation_type)
        for workout in completed_workouts
        if workout.rotation_type is not None
    ]
    history.extend(
        (workout.skipped_at, workout.rotation_type)
        for workout in (skipped_workouts or [])
    )

    for _, rotation_type in sorted(history, key=lambda item: item[0]):
        rotation_cursor = rotation_type

        if rotation_type == WorkoutType.RUN:
            replacement_run_due = True
        elif rotation_type == WorkoutType.HIIT_LEGS:
            replacement_run_due = False

    return SchedulerState(
        rotation_cursor=rotation_cursor,
        replacement_run_due=replacement_run_due,
    )





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


# Combine the time, calendar, and consecutive-day checks.
def can_schedule_workout(
    workout_start: datetime,
    workout_type: WorkoutType,
    calendar_events: list[tuple[datetime, datetime]],
    other_workout_starts: list[datetime],
    uses_rings: bool = False,
) -> bool:
    return (
        is_allowed_start_time(workout_start.time(), workout_type, uses_rings)
        and fits_around_calendar_events(workout_start, calendar_events)
        and fits_consecutive_workout_day_limit(workout_start, other_workout_starts)
    )


# Find the first valid start time from the candidates for that day.
def find_next_available_start(
    first_candidate_start: datetime,
    workout_type: WorkoutType,
    calendar_events: list[tuple[datetime, datetime]],
    other_workout_starts: list[datetime],
    uses_rings: bool = False,
) -> datetime | None:
    candidate_start = first_candidate_start

    while candidate_start.time() <= LATEST_WORKOUT_START:
        if can_schedule_workout(
            workout_start=candidate_start,
            workout_type=workout_type,
            calendar_events=calendar_events,
            other_workout_starts=other_workout_starts,
            uses_rings=uses_rings,
        ):
            return candidate_start

        candidate_start += timedelta(minutes=RESCHEDULE_INTERVAL_MINUTES)

    return None


# Search each day in the rolling plan for the next available time.
def find_next_available_start_in_plan(
    first_candidate_start: datetime,
    workout_type: WorkoutType,
    calendar_events: list[tuple[datetime, datetime]],
    other_workout_starts: list[datetime],
    uses_rings: bool = False,
) -> datetime | None:
    search_start = first_candidate_start
    plan_end_date = first_candidate_start.date() + timedelta(days=PLAN_HORIZON_DAYS)

    while search_start.date() < plan_end_date:
        available_start = find_next_available_start(
            search_start,
            workout_type,
            calendar_events,
            other_workout_starts,
            uses_rings,
        )

        if available_start is not None:
            return available_start

        search_start = (
            search_start.replace(
                hour=EARLIEST_WORKOUT_START.hour,
                minute=EARLIEST_WORKOUT_START.minute,
                second=0,
                microsecond=0,
            )
            + timedelta(days=1)
        )

    return None


# Check that this workout does not create a long streak.
def fits_consecutive_workout_day_limit(
    candidate_start: datetime,
    other_workout_starts: list[datetime],
) -> bool:
    workout_days = {workout.date() for workout in other_workout_starts}
    candidate_day = candidate_start.date()
    workout_days.add(candidate_day)

    consecutive_days = 1

    day_before = candidate_day - timedelta(days=1)
    while day_before in workout_days:
        consecutive_days += 1
        day_before -= timedelta(days=1)

    day_after = candidate_day + timedelta(days=1)
    while day_after in workout_days:
        consecutive_days += 1
        day_after += timedelta(days=1)

    return consecutive_days <= MAX_CONSECUTIVE_WORKOUT_DAYS


# Keep the original list-returning interface for existing callers.
def build_rolling_plan(
    first_candidate_start: datetime,
    calendar_events: list[tuple[datetime, datetime]],
    existing_workouts: list[PlannedWorkout],
    previous_workout_type: WorkoutType | None = None,
    push_uses_rings: bool = False,
    completed_workouts: list[CompletedWorkout] | None = None,
) -> list[PlannedWorkout]:
    planned_workouts, _ = build_rolling_plan_with_state(
        first_candidate_start=first_candidate_start,
        calendar_events=calendar_events,
        existing_workouts=existing_workouts,
        state=SchedulerState(rotation_cursor=previous_workout_type),
        push_uses_rings=push_uses_rings,
        completed_workouts=completed_workouts,
    )
    return planned_workouts


# Build a plan and return the state needed to continue it later.
def build_rolling_plan_with_state(
    first_candidate_start: datetime,
    calendar_events: list[tuple[datetime, datetime]],
    existing_workouts: list[PlannedWorkout],
    state: SchedulerState = SchedulerState(),
    push_uses_rings: bool = False,
    completed_workouts: list[CompletedWorkout] | None = None,
    skipped_workouts: list[SkippedWorkout] | None = None,
) -> tuple[list[PlannedWorkout], SchedulerState]:
    plan_end_date = (
        first_candidate_start.date() + timedelta(days=PLAN_HORIZON_DAYS)
    )
    planned_workouts: list[PlannedWorkout] = []
    workouts_to_check = list(existing_workouts)
    completed_workouts = completed_workouts or []
    skipped_workouts = sorted(skipped_workouts or [], key=lambda item: item.skipped_at)
    candidate_start = first_candidate_start
    rotation_cursor = state.rotation_cursor
    replacement_run_due = state.replacement_run_due

    while candidate_start.date() < plan_end_date:
        skipped_today = next(
            (
                item
                for item in skipped_workouts
                if item.skipped_at.date() == candidate_start.date()
            ),
            None,
        )
        if skipped_today is not None:
            rotation_cursor = skipped_today.rotation_type
            if rotation_cursor == WorkoutType.RUN:
                replacement_run_due = True
            elif rotation_cursor == WorkoutType.HIIT_LEGS:
                replacement_run_due = False
            skipped_workouts.remove(skipped_today)
            candidate_start = skipped_today.skipped_at.replace(
                hour=EARLIEST_WORKOUT_START.hour,
                minute=EARLIEST_WORKOUT_START.minute,
                second=0,
                microsecond=0,
            ) + timedelta(days=1)
            continue

        rotation_type = get_next_workout_type(rotation_cursor)
        is_replacement_run = (
            rotation_type == WorkoutType.HIIT_LEGS
            and replacement_run_due
        )
        scheduled_type = (
            WorkoutType.RUN if is_replacement_run else rotation_type
        )
        variant = get_next_workout_variant(
            scheduled_type,
            completed_workouts,
            workouts_to_check,
        )
        if scheduled_type == WorkoutType.PUSH and push_uses_rings:
            variant = WorkoutVariant.PUSH_DIPS
        workout_uses_rings = (
            scheduled_type == WorkoutType.PULL
            or variant == WorkoutVariant.PUSH_DIPS
        )

        other_workout_starts = [
            workout.starts_at for workout in workouts_to_check
        ]
        available_start = find_next_available_start_in_plan(
            candidate_start,
            scheduled_type,
            calendar_events,
            other_workout_starts,
            workout_uses_rings,
        )

        if available_start is None or available_start.date() >= plan_end_date:
            break

        skipped_before_available = next(
            (
                item
                for item in skipped_workouts
                if candidate_start.date() < item.skipped_at.date() <= available_start.date()
            ),
            None,
        )
        if skipped_before_available is not None:
            rotation_cursor = skipped_before_available.rotation_type
            if rotation_cursor == WorkoutType.RUN:
                replacement_run_due = True
            elif rotation_cursor == WorkoutType.HIIT_LEGS:
                replacement_run_due = False
            skipped_workouts.remove(skipped_before_available)
            candidate_start = skipped_before_available.skipped_at.replace(
                hour=EARLIEST_WORKOUT_START.hour,
                minute=EARLIEST_WORKOUT_START.minute,
                second=0,
                microsecond=0,
            ) + timedelta(days=1)
            continue

        if any(
            workout.starts_at.date() == available_start.date()
            for workout in workouts_to_check
        ):
            candidate_start = available_start.replace(
                hour=EARLIEST_WORKOUT_START.hour,
                minute=EARLIEST_WORKOUT_START.minute,
                second=0,
                microsecond=0,
            ) + timedelta(days=1)
            continue

        workout = PlannedWorkout(
            workout_type=scheduled_type,
            starts_at=available_start,
            uses_rings=workout_uses_rings,
            variant=variant,
            rotation_type=rotation_type,
        )
        planned_workouts.append(workout)
        workouts_to_check.append(workout)

        if is_replacement_run:
            replacement_run_due = False
        elif rotation_type == WorkoutType.RUN:
            replacement_run_due = True

        rotation_cursor = rotation_type
        candidate_start = available_start.replace(
            hour=EARLIEST_WORKOUT_START.hour,
            minute=EARLIEST_WORKOUT_START.minute,
            second=0,
            microsecond=0,
        ) + timedelta(days=1)

    updated_state = SchedulerState(
        rotation_cursor=rotation_cursor,
        replacement_run_due=replacement_run_due,
    )
    return planned_workouts, updated_state