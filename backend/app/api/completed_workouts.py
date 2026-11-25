from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from ..db.models import CompletedWorkoutRecord
from ..db.models import PlannerSettingsRecord
from ..db.repositories import (
    get_completed_workouts,
    get_completed_workout_by_healthkit_id,
    get_google_calendar_connection,
    get_planned_workouts,
    save_planned_workout_calendar_events,
    save_skipped_workout,
)
from ..domain.completed_workout import CompletedWorkout
from ..domain.planned_workout import PlannedWorkout
from ..domain.skipped_workout import SkippedWorkout
from ..domain.workout_types import WorkoutType
from ..domain.schedule_rules import PLAN_HORIZON_DAYS
from ..schemas.completed_workout import (
    CompletedWorkoutResponse,
    CorrectCompletedWorkoutRequest,
    LogCompletedWorkoutRequest,
    HealthKitWorkoutRequest,
)
from ..schemas.plan import PlannedWorkoutResponse
from ..schemas.settings import DEFAULT_SETTINGS, PlannerSettings
from ..services.google_calendar_service import (
    GOOGLE_CALENDAR_SCOPES,
    find_deleted_planned_workouts,
    get_busy_periods_for_all_calendars,
    sync_completed_workout_event,
    sync_planned_workout_events,
)
from ..services.schedule_service import (
    log_completed_workout_and_rebuild_plan,
    rebuild_and_save_plan,
)
from .plan import get_db_session

router = APIRouter()


def _muscles_for_workout(
    session: Session,
    workout_type: str | WorkoutType,
    variant: str | None = None,
) -> tuple[str, ...]:
    record = session.get(PlannerSettingsRecord, 1)
    settings = PlannerSettings.model_validate(record.settings) if record else DEFAULT_SETTINGS
    workout_id = workout_type.value if isinstance(workout_type, WorkoutType) else workout_type
    definition = next((item for item in settings.workouts if item.id == workout_id), None)
    if definition is None:
        return ()
    return tuple(definition.variant_muscles.get(variant, definition.muscles))


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
        started_at=request.started_at,
        variant=request.variant,
        rotation_type=request.rotation_type,
        healthkit_id=request.healthkit_id,
        source_activity=request.source_activity,
        muscles_trained=tuple(request.muscles_trained) or _muscles_for_workout(session, request.workout_type, request.variant),
        custom_name=request.custom_name,
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
        started_at=request.started_at,
        variant=request.variant,
        rotation_type=request.rotation_type,
        google_event_id=completed_event_id,
        google_calendar_id=completed_calendar_id,
        healthkit_id=request.healthkit_id,
        source_activity=request.source_activity,
        muscles_trained=tuple(request.muscles_trained) or _muscles_for_workout(session, request.workout_type, request.variant),
        custom_name=request.custom_name,
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


# Receive Watch workouts automatically and match them against today's plan.
@router.post(
    "/completed-workouts/healthkit",
    response_model=list[PlannedWorkoutResponse],
)
def receive_healthkit_workout(
    payload: HealthKitWorkoutRequest,
    session: Session = Depends(get_db_session),
) -> list[PlannedWorkout]:
    existing = get_completed_workout_by_healthkit_id(session, payload.healthkit_id)
    if existing is not None:
        plan = get_planned_workouts(session)
        session.rollback()
        return plan
    plan = get_planned_workouts(session)
    session.rollback()

    scheduled_today = next(
        (workout for workout in plan if workout.starts_at.date() == payload.ended_at.date()),
        None,
    )
    activity = payload.activity_type.lower().replace("_", " ")
    rotation_type = None
    variant = None

    is_running = "run" in activity
    is_hiit = "hiit" in activity or "high intensity" in activity
    is_strength = any(
        word in activity
        for word in ("strength", "gymnastic", "cross training")
    )
    workout_type = (
        WorkoutType.RUN if is_running
        else WorkoutType.HIIT_LEGS if is_hiit
        else WorkoutType.PUSH
    )

    if scheduled_today is not None:
        planned_type = scheduled_today.rotation_type or scheduled_today.workout_type
        if is_running and planned_type in (WorkoutType.RUN, WorkoutType.HIIT_LEGS):
            workout_type = WorkoutType.RUN
            rotation_type = planned_type
        elif is_hiit and planned_type in (WorkoutType.HIIT_LEGS, WorkoutType.HIIT_ABS):
            workout_type = scheduled_today.workout_type
            rotation_type = planned_type
        elif is_strength and planned_type in (WorkoutType.PUSH, WorkoutType.PULL, WorkoutType.LEGS):
            workout_type = scheduled_today.workout_type
            rotation_type = planned_type
            variant = scheduled_today.variant
        elif not (is_running or is_hiit or is_strength):
            workout_type = scheduled_today.workout_type
            rotation_type = planned_type
            variant = scheduled_today.variant
    elif is_running:
        workout_type = WorkoutType.RUN
    elif is_hiit:
        workout_type = WorkoutType.HIIT_LEGS

    request = LogCompletedWorkoutRequest(
        workout_type=workout_type,
        completed_at=payload.ended_at,
        started_at=payload.started_at,
        variant=variant,
        rotation_type=rotation_type,
        first_candidate_start=(
            payload.ended_at.replace(hour=7, minute=0, second=0, microsecond=0)
            if payload.ended_at.hour < 7
            else payload.ended_at.replace(
                hour=7, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
        ),
        calendar_events=[],
        push_uses_rings=False,
        healthkit_id=payload.healthkit_id,
        source_activity=f"{payload.activity_type} · {payload.source_name or 'Apple Health'}"[:80],
    )
    return log_workout(request, session)


# Correct an automatic match and rebuild the pending plan and calendar.
@router.patch(
    "/completed-workouts/{workout_id}",
    response_model=CompletedWorkoutResponse,
)
def correct_completed_workout(
    workout_id: int,
    request: CorrectCompletedWorkoutRequest,
    session: Session = Depends(get_db_session),
) -> CompletedWorkout:
    record = session.get(CompletedWorkoutRecord, workout_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Completed workout not found.")

    record.workout_type = request.workout_type
    record.variant = request.variant
    record.rotation_type = request.rotation_type
    record.muscles_trained = request.muscles_trained
    record.custom_name = request.custom_name
    session.commit()

    connection = get_google_calendar_connection(session)
    encrypted_refresh_token = (
        connection.refresh_token_encrypted if connection is not None else None
    )
    target_calendar_id = (
        connection.target_calendar_id if connection is not None else None
    )
    previous_workouts = get_planned_workouts(session)
    session.rollback()
    calendar_events: list[tuple[datetime, datetime]] = []
    if encrypted_refresh_token and target_calendar_id:
        now_local = datetime.now(ZoneInfo("America/Hermosillo"))
        first_candidate_start = now_local.replace(
            hour=7, minute=0, second=0, microsecond=0, tzinfo=None
        )
        if now_local.hour >= 7:
            first_candidate_start += timedelta(days=1)
        plan_end_date = first_candidate_start.date() + timedelta(days=PLAN_HORIZON_DAYS)
        try:
            calendar_events = get_busy_periods_for_all_calendars(
                encrypted_refresh_token=encrypted_refresh_token,
                scopes=GOOGLE_CALENDAR_SCOPES,
                starts_at=datetime.combine(first_candidate_start.date(), time.min),
                ends_at=datetime.combine(plan_end_date, time.min),
                managed_calendar_id=target_calendar_id,
            )
        except RefreshError as error:
            raise HTTPException(status_code=401, detail="Google Calendar access expired. Connect it again.") from error
        except (HttpError, RuntimeError) as error:
            raise HTTPException(status_code=502, detail="Could not retrieve Busy times from Google Calendar.") from error
    else:
        now_local = datetime.now(ZoneInfo("America/Hermosillo"))
        first_candidate_start = now_local.replace(
            hour=7, minute=0, second=0, microsecond=0, tzinfo=None
        )
        if now_local.hour >= 7:
            first_candidate_start += timedelta(days=1)

    updated_plan = rebuild_and_save_plan(
        session=session,
        first_candidate_start=first_candidate_start,
        calendar_events=calendar_events,
        previous_workouts=previous_workouts,
    )

    if encrypted_refresh_token and target_calendar_id:
        completed = CompletedWorkout(
            workout_type=request.workout_type,
            completed_at=record.completed_at,
            started_at=record.started_at,
            variant=request.variant,
            rotation_type=request.rotation_type,
            google_event_id=record.google_event_id,
            google_calendar_id=record.google_calendar_id,
            healthkit_id=record.healthkit_id,
            source_activity=record.source_activity,
            id=record.id,
            muscles_trained=tuple(record.muscles_trained or []),
            custom_name=record.custom_name,
        )
        previous_event = PlannedWorkout(
            workout_type=request.workout_type,
            starts_at=record.started_at,
            google_event_id=record.google_event_id,
            google_calendar_id=record.google_calendar_id,
        ) if record.google_event_id else None
        try:
            event_id, calendar_id = sync_completed_workout_event(
                encrypted_refresh_token=encrypted_refresh_token,
                scopes=GOOGLE_CALENDAR_SCOPES,
                target_calendar_id=target_calendar_id,
                workout=completed,
                matching_planned_workout=previous_event,
            )
            record.google_event_id = event_id
            record.google_calendar_id = calendar_id
            sync_planned_workout_events(
                encrypted_refresh_token=encrypted_refresh_token,
                scopes=GOOGLE_CALENDAR_SCOPES,
                target_calendar_id=target_calendar_id,
                previous_workouts=previous_workouts,
                planned_workouts=updated_plan,
            )
            save_planned_workout_calendar_events(session, updated_plan)
            session.commit()
        except RefreshError as error:
            raise HTTPException(status_code=401, detail="Google Calendar access expired. Connect it again.") from error
        except (HttpError, RuntimeError) as error:
            raise HTTPException(status_code=502, detail="The correction was saved, but Calendar could not be updated.") from error

    session.refresh(record)
    return CompletedWorkout(
        workout_type=record.workout_type,
        completed_at=record.completed_at,
        started_at=record.started_at,
        variant=record.variant,
        rotation_type=record.rotation_type,
        google_event_id=record.google_event_id,
        google_calendar_id=record.google_calendar_id,
        healthkit_id=record.healthkit_id,
        source_activity=record.source_activity,
        id=record.id,
        muscles_trained=tuple(record.muscles_trained or []),
        custom_name=record.custom_name,
    )
