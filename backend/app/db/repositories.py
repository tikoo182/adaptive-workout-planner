from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..domain.completed_workout import CompletedWorkout
from ..domain.workout_types import WorkoutType, WorkoutVariant
from .models import CompletedWorkoutRecord

from ..domain.planned_workout import PlannedWorkout
from .models import PlannedWorkoutRecord

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
        )
        for record in records
    ]


# Clear the pending plan before saving its replacement.
def clear_planned_workouts(session: Session) -> None:
    session.execute(delete(PlannedWorkoutRecord))