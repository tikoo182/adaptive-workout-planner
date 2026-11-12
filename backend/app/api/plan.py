from collections.abc import Iterator

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db.repositories import get_planned_workouts
from ..db.session import SessionLocal
from ..domain.planned_workout import PlannedWorkout
from ..schemas.plan import PlannedWorkoutResponse, RebuildPlanRequest
from ..services.schedule_service import rebuild_and_save_plan

router = APIRouter()

# Provide a database session for one request.
def get_db_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


# Return the currently saved plan.
@router.get("/plan", response_model=list[PlannedWorkoutResponse])
def read_plan(session: Session = Depends(get_db_session)) -> list[PlannedWorkout]:
    return get_planned_workouts(session)


# Rebuild and save the pending plan.
@router.post("/plan/rebuild", response_model=list[PlannedWorkoutResponse])
def rebuild_plan(
    request: RebuildPlanRequest,
    session: Session = Depends(get_db_session),
) -> list[PlannedWorkout]:
    calendar_events = [
        (event.starts_at, event.ends_at)
        for event in request.calendar_events
    ]

    return rebuild_and_save_plan(
        session=session,
        first_candidate_start=request.first_candidate_start,
        calendar_events=calendar_events,
        push_uses_rings=request.push_uses_rings,
    )