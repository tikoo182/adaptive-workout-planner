from collections.abc import Iterator
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from ..db.repositories import (
    get_google_calendar_connection,
    get_planned_workouts,
    save_planned_workout_calendar_events,
    save_skipped_workout,
)
from ..db.session import SessionLocal
from ..domain.planned_workout import PlannedWorkout
from ..domain.skipped_workout import SkippedWorkout
from ..domain.schedule_rules import PLAN_HORIZON_DAYS
from ..schemas.plan import PlannedWorkoutResponse, RebuildPlanRequest
from ..services.google_calendar_service import (
    GOOGLE_CALENDAR_SCOPES,
    find_deleted_planned_workouts,
    get_busy_periods_for_all_calendars,
    sync_planned_workout_events,
)
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


# Rebuild the plan and sync its events to the selected Google Calendar.
@router.post("/plan/rebuild", response_model=list[PlannedWorkoutResponse])
def rebuild_plan(
    request: RebuildPlanRequest,
    session: Session = Depends(get_db_session),
) -> list[PlannedWorkout]:
    connection = get_google_calendar_connection(session)
    if connection is None or connection.target_calendar_id is None:
        raise HTTPException(
            status_code=409,
            detail="Connect Google Calendar and choose a target calendar first.",
        )

    encrypted_refresh_token = connection.refresh_token_encrypted
    target_calendar_id = connection.target_calendar_id
    previous_workouts = get_planned_workouts(session)
    session.rollback()

    plan_end_date = (
        request.first_candidate_start.date()
        + timedelta(days=PLAN_HORIZON_DAYS)
    )
    calendar_start = datetime.combine(
        request.first_candidate_start.date(),
        time.min,
    )
    calendar_end = datetime.combine(plan_end_date, time.min)

    try:
        deleted_workouts = find_deleted_planned_workouts(
            encrypted_refresh_token=encrypted_refresh_token,
            scopes=GOOGLE_CALENDAR_SCOPES,
            planned_workouts=previous_workouts,
        )
        for workout in deleted_workouts:
            save_skipped_workout(
                session,
                SkippedWorkout(
                    workout_type=workout.workout_type,
                    rotation_type=workout.rotation_type or workout.workout_type,
                    skipped_at=workout.starts_at,
                    google_event_id=workout.google_event_id,
                ),
            )
        if deleted_workouts:
            session.commit()
            deleted_event_ids = {
                workout.google_event_id for workout in deleted_workouts
            }
            previous_workouts = [
                workout
                for workout in previous_workouts
                if workout.google_event_id not in deleted_event_ids
            ]

        google_busy_periods = get_busy_periods_for_all_calendars(
            encrypted_refresh_token=encrypted_refresh_token,
            scopes=GOOGLE_CALENDAR_SCOPES,
            starts_at=calendar_start,
            ends_at=calendar_end,
            managed_calendar_id=target_calendar_id,
        )
    except RefreshError as error:
        raise HTTPException(
            status_code=401,
            detail="Google Calendar access expired. Connect it again.",
        ) from error
    except (HttpError, RuntimeError) as error:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve Busy times from Google Calendar.",
        ) from error

    calendar_events = [
        (event.starts_at, event.ends_at)
        for event in request.calendar_events
    ]
    calendar_events.extend(google_busy_periods)

    planned_workouts = rebuild_and_save_plan(
        session=session,
        first_candidate_start=request.first_candidate_start,
        calendar_events=calendar_events,
        push_uses_rings=request.push_uses_rings,
        previous_workouts=previous_workouts,
    )

    try:
        sync_planned_workout_events(
            encrypted_refresh_token=encrypted_refresh_token,
            scopes=GOOGLE_CALENDAR_SCOPES,
            target_calendar_id=target_calendar_id,
            previous_workouts=previous_workouts,
            planned_workouts=planned_workouts,
        )
    except RefreshError as error:
        raise HTTPException(
            status_code=401,
            detail="Google Calendar access expired. Connect it again.",
        ) from error
    except (HttpError, RuntimeError) as error:
        raise HTTPException(
            status_code=502,
            detail="The plan was saved, but Google Calendar events could not be synced.",
        ) from error

    save_planned_workout_calendar_events(session, planned_workouts)
    session.commit()
    return planned_workouts
