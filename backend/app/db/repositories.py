from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..domain.completed_workout import CompletedWorkout
from ..domain.workout_types import WorkoutType, WorkoutVariant
from .models import CompletedWorkoutRecord

from ..domain.planned_workout import PlannedWorkout
from ..domain.skipped_workout import SkippedWorkout
from .models import PlannedWorkoutRecord
from .models import GoogleCalendarConnectionRecord, SkippedWorkoutRecord

# Save and retrieve completed workout history.
# Save one completed workout without committing the whole transaction.
def save_completed_workout(
    session: Session,
    workout: CompletedWorkout,
) -> int:
    record = CompletedWorkoutRecord(
        workout_type=workout.workout_type.value,
        rotation_type=(
            workout.rotation_type.value
            if workout.rotation_type is not None
            else None
        ),
        variant=workout.variant.value if workout.variant is not None else None,
        completed_at=workout.completed_at,
        google_event_id=workout.google_event_id,
        google_calendar_id=workout.google_calendar_id,
    )
    session.add(record)
    session.flush()
    return record.id


# Return saved workouts as domain objects.
def get_completed_workouts(session: Session) -> list[CompletedWorkout]:
    records = session.scalars(
        select(CompletedWorkoutRecord).order_by(
            CompletedWorkoutRecord.completed_at,
            CompletedWorkoutRecord.id,
        )
    ).all()

    return [
        CompletedWorkout(
            workout_type=WorkoutType(record.workout_type),
            rotation_type=(
                WorkoutType(record.rotation_type)
                if record.rotation_type is not None
                else None
            ),
            completed_at=record.completed_at,
            variant=(
                WorkoutVariant(record.variant)
                if record.variant is not None
                else None
            ),
            google_event_id=record.google_event_id,
            google_calendar_id=record.google_calendar_id,
        )
        for record in records
    ]

# Save one planned workout without committing the whole transaction.
def save_planned_workout(
    session: Session,
    workout: PlannedWorkout,
) -> int:
    record = PlannedWorkoutRecord(
        workout_type=workout.workout_type.value,
        rotation_type=(
            workout.rotation_type or workout.workout_type
        ).value,
        variant=workout.variant.value if workout.variant is not None else None,
        starts_at=workout.starts_at,
        uses_rings=workout.uses_rings,
        google_event_id=workout.google_event_id,
        google_calendar_id=workout.google_calendar_id,
    )
    session.add(record)
    session.flush()
    return record.id


# Return saved plans as domain objects.
def get_planned_workouts(session: Session) -> list[PlannedWorkout]:
    records = session.scalars(
        select(PlannedWorkoutRecord).order_by(
            PlannedWorkoutRecord.starts_at,
            PlannedWorkoutRecord.id,
        )
    ).all()

    return [
        PlannedWorkout(
            workout_type=WorkoutType(record.workout_type),
            starts_at=record.starts_at,
            uses_rings=record.uses_rings,
            variant=(
                WorkoutVariant(record.variant)
                if record.variant is not None
                else None
            ),
            rotation_type=WorkoutType(record.rotation_type),
            google_event_id=record.google_event_id,
            google_calendar_id=record.google_calendar_id,
        )
        for record in records
    ]


# Clear the pending plan before saving its replacement.
def clear_planned_workouts(session: Session) -> None:
    session.execute(delete(PlannedWorkoutRecord))


# Save or update the one Google Calendar connection for this single-user version.
def save_google_calendar_connection(
    session: Session,
    encrypted_refresh_token: str,
) -> GoogleCalendarConnectionRecord:
    connection = session.get(GoogleCalendarConnectionRecord, 1)

    if connection is None:
        connection = GoogleCalendarConnectionRecord(
            id=1,
            refresh_token_encrypted=encrypted_refresh_token,
        )
        session.add(connection)
    else:
        connection.refresh_token_encrypted = encrypted_refresh_token

    session.flush()
    return connection


# Return the saved Google Calendar connection, if one exists.
def get_google_calendar_connection(
    session: Session,
) -> GoogleCalendarConnectionRecord | None:
    return session.get(GoogleCalendarConnectionRecord, 1)


# Save the selected workout calendar.
def set_google_calendar_target(
    session: Session,
    calendar_id: str,
) -> GoogleCalendarConnectionRecord | None:
    connection = get_google_calendar_connection(session)
    if connection is None:
        return None

    connection.target_calendar_id = calendar_id
    session.flush()
    return connection

# Update Google event references after synchronizing the pending plan.
def save_planned_workout_calendar_events(
    session: Session,
    workouts: list[PlannedWorkout],
) -> None:
    records = session.scalars(select(PlannedWorkoutRecord)).all()
    records_by_start = {record.starts_at: record for record in records}

    for workout in workouts:
        record = records_by_start.get(workout.starts_at)
        if record is not None:
            record.google_event_id = workout.google_event_id
            record.google_calendar_id = workout.google_calendar_id

    session.flush()


# Return rest-day skips recorded from deleted Google Calendar events.
def get_skipped_workouts(session: Session) -> list[SkippedWorkout]:
    records = session.scalars(
        select(SkippedWorkoutRecord).order_by(
            SkippedWorkoutRecord.skipped_at,
            SkippedWorkoutRecord.id,
        )
    ).all()
    return [
        SkippedWorkout(
            workout_type=WorkoutType(record.workout_type),
            rotation_type=WorkoutType(record.rotation_type),
            skipped_at=record.skipped_at,
            google_event_id=record.google_event_id,
        )
        for record in records
    ]


# Save a deleted planned event as a rest day once.
def save_skipped_workout(
    session: Session,
    workout: SkippedWorkout,
) -> None:
    existing = session.scalar(
        select(SkippedWorkoutRecord).where(
            SkippedWorkoutRecord.google_event_id == workout.google_event_id
        )
    )
    if existing is not None:
        return

    session.add(
        SkippedWorkoutRecord(
            workout_type=workout.workout_type.value,
            rotation_type=workout.rotation_type.value,
            skipped_at=workout.skipped_at,
            google_event_id=workout.google_event_id,
        )
    )
    session.flush()
