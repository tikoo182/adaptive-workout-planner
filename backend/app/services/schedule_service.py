from datetime import datetime

from sqlalchemy.orm import Session

from ..db.repositories import (
    clear_planned_workouts,
    get_completed_workouts,
    get_skipped_workouts,
    save_planned_workout,
)
from ..domain.planned_workout import PlannedWorkout
from ..domain.scheduler import (
    build_rolling_plan_with_state,
    get_scheduler_state_from_history,
)

from ..db.repositories import save_completed_workout
from ..domain.completed_workout import CompletedWorkout

# Coordinates plan rebuilding and database storage.


# Carry old Google event references forward so rebuilds can update those events.
def _carry_forward_calendar_event_ids(
    planned_workouts: list[PlannedWorkout],
    previous_workouts: list[PlannedWorkout] | None,
) -> None:
    previous_events = [
        workout
        for workout in (previous_workouts or [])
        if workout.google_event_id is not None
    ]
    for index, workout in enumerate(planned_workouts):
        if index >= len(previous_events):
            break
        workout.google_event_id = previous_events[index].google_event_id
        workout.google_calendar_id = previous_events[index].google_calendar_id


# Rebuild the pending plan and save it as one transaction.
def rebuild_and_save_plan(
    session: Session,
    first_candidate_start: datetime,
    calendar_events: list[tuple[datetime, datetime]],
    push_uses_rings: bool = False,
    previous_workouts: list[PlannedWorkout] | None = None,
) -> list[PlannedWorkout]:
    with session.begin():
        completed_workouts = get_completed_workouts(session)
        skipped_workouts = get_skipped_workouts(session)
        historical_skips = [
            workout
            for workout in skipped_workouts
            if workout.skipped_at.date() < first_candidate_start.date()
        ]
        upcoming_skips = [
            workout
            for workout in skipped_workouts
            if workout.skipped_at.date() >= first_candidate_start.date()
        ]
        state = get_scheduler_state_from_history(
            completed_workouts,
            historical_skips,
        )

        planned_workouts, _ = build_rolling_plan_with_state(
            first_candidate_start=first_candidate_start,
            calendar_events=calendar_events,
            existing_workouts=[],
            state=state,
            push_uses_rings=push_uses_rings,
            completed_workouts=completed_workouts,
            skipped_workouts=upcoming_skips,
        )

        _carry_forward_calendar_event_ids(planned_workouts, previous_workouts)
        clear_planned_workouts(session)
        for workout in planned_workouts:
            save_planned_workout(session, workout)

    return planned_workouts


# Record a workout and rebuild the remaining plan atomically.
def log_completed_workout_and_rebuild_plan(
    session: Session,
    completed_workout: CompletedWorkout,
    first_candidate_start: datetime,
    calendar_events: list[tuple[datetime, datetime]],
    push_uses_rings: bool = False,
    previous_workouts: list[PlannedWorkout] | None = None,
) -> list[PlannedWorkout]:
    with session.begin():
        save_completed_workout(session, completed_workout)

        completed_workouts = get_completed_workouts(session)
        skipped_workouts = get_skipped_workouts(session)
        historical_skips = [
            workout
            for workout in skipped_workouts
            if workout.skipped_at.date() < first_candidate_start.date()
        ]
        upcoming_skips = [
            workout
            for workout in skipped_workouts
            if workout.skipped_at.date() >= first_candidate_start.date()
        ]
        state = get_scheduler_state_from_history(
            completed_workouts,
            historical_skips,
        )

        planned_workouts, _ = build_rolling_plan_with_state(
            first_candidate_start=first_candidate_start,
            calendar_events=calendar_events,
            existing_workouts=[],
            state=state,
            push_uses_rings=push_uses_rings,
            completed_workouts=completed_workouts,
            skipped_workouts=upcoming_skips,
        )

        _carry_forward_calendar_event_ids(planned_workouts, previous_workouts)
        clear_planned_workouts(session)
        for workout in planned_workouts:
            save_planned_workout(session, workout)

    return planned_workouts