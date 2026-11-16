from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from ..db.repositories import (
    get_completed_workouts,
    get_google_calendar_connection,
    get_planned_workouts,
    save_planned_workout_calendar_events,
    save_skipped_workout,
)
from ..domain.completed_workout import CompletedWorkout
from ..domain.planned_workout import PlannedWorkout
from ..domain.skipped_workout import SkippedWorkout
from ..domain.schedule_rules import PLAN_HORIZON_DAYS
from ..schemas.completed_workout import (
    CompletedWorkoutResponse,
    LogCompletedWorkoutRequest,
)
from ..schemas.plan import PlannedWorkoutResponse
from ..services.google_calendar_service import (
    GOOGLE_CALENDAR_SCOPES,
    find_deleted_planned_workouts,
    get_busy_periods_for_all_calendars,
    sync_completed_workout_event,
    sync_planned_workout_events,
)
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


# Log a workout and sync the rebuilt plan with Google Calendar.
@router.post(
    "/completed-workouts",
    response_model=list[PlannedWorkoutResponse],
)
def log_workout(
    request: LogCompletedWorkoutRequest,
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
        # A workout logged now fulfils the slot instead of counting as a rest day.
        logged_deleted_event_ids = {
            workout.google_event_id
            for workout in deleted_workouts
            if request.rotation_type is not None
            and workout.rotation_type == request.rotation_type
        }
        for workout in deleted_workouts:
            if workout.google_event_id in logged_deleted_event_ids:
                continue
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
                or workout.google_event_id in logged_deleted_event_ids
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

    matching_planned_workout = None
    if request.rotation_type is not None:
        matching_planned_workout = next(
            (
                workout
                for workout in previous_workouts
                if workout.rotation_type == request.rotation_type
            ),
            None,
        )

    completed_workout = CompletedWorkout(
        workout_type=request.workout_type,
        completed_at=request.completed_at,
        variant=request.variant,
        rotation_type=request.rotation_type,
    )

    try:
        completed_event_id, completed_calendar_id = sync_completed_workout_event(
            encrypted_refresh_token=encrypted_refresh_token,
            scopes=GOOGLE_CALENDAR_SCOPES,
            target_calendar_id=target_calendar_id,
            workout=completed_workout,
            matching_planned_workout=matching_planned_workout,
        )
    except RefreshError as error:
        raise HTTPException(
            status_code=401,
            detail="Google Calendar access expired. Connect it again.",
        ) from error
    except HttpError as error:
        raise HTTPException(
            status_code=502,
            detail="Could not save the completed workout to Google Calendar.",
        ) from error

    completed_workout = CompletedWorkout(
        workout_type=request.workout_type,
        completed_at=request.completed_at,
        variant=request.variant,
        rotation_type=request.rotation_type,
        google_event_id=completed_event_id,
        google_calendar_id=completed_calendar_id,
    )

    previous_pending_workouts = [
        workout
        for workout in previous_workouts
        if workout is not matching_planned_workout
    ]
    calendar_events = [
        (event.starts_at, event.ends_at)
        for event in request.calendar_events
    ]
    calendar_events.extend(google_busy_periods)

    planned_workouts = log_completed_workout_and_rebuild_plan(
        session=session,
        completed_workout=completed_workout,
        first_candidate_start=request.first_candidate_start,
        calendar_events=calendar_events,
        push_uses_rings=request.push_uses_rings,
        previous_workouts=previous_pending_workouts,
    )

    try:
        sync_planned_workout_events(
            encrypted_refresh_token=encrypted_refresh_token,
            scopes=GOOGLE_CALENDAR_SCOPES,
            target_calendar_id=target_calendar_id,
            previous_workouts=previous_pending_workouts,
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
            detail="The workout was logged, but the pending plan could not be synced to Google Calendar.",
        ) from error

    save_planned_workout_calendar_events(session, planned_workouts)
    session.commit()
    return planned_workouts
