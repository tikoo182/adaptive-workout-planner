from datetime import datetime

from sqlalchemy.orm import Session

from ..db.repositories import (
    clear_planned_workouts,
    get_completed_workouts,
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


# Rebuild the pending plan and save it as one transaction.
def rebuild_and_save_plan(
    session: Session,
    first_candidate_start: datetime,
    calendar_events: list[tuple[datetime, datetime]],
    push_uses_rings: bool = False,
) -> list[PlannedWorkout]:
    with session.begin():
        completed_workouts = get_completed_workouts(session)
        state = get_scheduler_state_from_history(completed_workouts)

        planned_workouts, _ = build_rolling_plan_with_state(
            first_candidate_start=first_candidate_start,
            calendar_events=calendar_events,
            existing_workouts=[],
            state=state,
            push_uses_rings=push_uses_rings,
            completed_workouts=completed_workouts,
        )

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
) -> list[PlannedWorkout]:
    with session.begin():
        save_completed_workout(session, completed_workout)

        completed_workouts = get_completed_workouts(session)
        state = get_scheduler_state_from_history(completed_workouts)

        planned_workouts, _ = build_rolling_plan_with_state(
            first_candidate_start=first_candidate_start,
            calendar_events=calendar_events,
            existing_workouts=[],
            state=state,
            push_uses_rings=push_uses_rings,
            completed_workouts=completed_workouts,
        )

        clear_planned_workouts(session)
        for workout in planned_workouts:
            save_planned_workout(session, workout)

    return planned_workouts