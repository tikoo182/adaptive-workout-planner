from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db.repositories import get_completed_workouts
from ..domain.completed_workout import CompletedWorkout
from ..domain.planned_workout import PlannedWorkout
from ..schemas.completed_workout import (
    CompletedWorkoutResponse,
    LogCompletedWorkoutRequest,
)
from ..schemas.plan import PlannedWorkoutResponse
from ..services.schedule_service import (
    log_completed_workout_and_rebuild_plan,
)
from .plan import get_db_session

router = APIRouter()

# Return saved completed-workout history.
@router.get(
    "/completed-workouts",
    response_model=list[CompletedWorkoutResponse],
)
def read_completed_workouts(
    session: Session = Depends(get_db_session),
) -> list[CompletedWorkout]:
    return get_completed_workouts(session)


# Log a workout and return the rebuilt pending plan.
@router.post(
    "/completed-workouts",
    response_model=list[PlannedWorkoutResponse],
)
def log_workout(
    request: LogCompletedWorkoutRequest,
    session: Session = Depends(get_db_session),
) -> list[PlannedWorkout]:
    completed_workout = CompletedWorkout(
        workout_type=request.workout_type,
        completed_at=request.completed_at,
        variant=request.variant,
        rotation_type=request.rotation_type,
    )
    calendar_events = [
        (event.starts_at, event.ends_at)
        for event in request.calendar_events
    ]

    return log_completed_workout_and_rebuild_plan(
        session=session,
        completed_workout=completed_workout,
        first_candidate_start=request.first_candidate_start,
        calendar_events=calendar_events,
        push_uses_rings=request.push_uses_rings,
    )