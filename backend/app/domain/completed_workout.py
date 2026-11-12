from dataclasses import dataclass
from datetime import datetime

from .workout_types import WorkoutType, WorkoutVariant

# One workout recorded after it has been completed.
@dataclass(frozen=True)
class CompletedWorkout:
    workout_type: WorkoutType
    completed_at: datetime
    variant: WorkoutVariant | None = None
    rotation_type: WorkoutType | None = None
