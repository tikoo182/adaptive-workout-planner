from dataclasses import dataclass
from datetime import datetime, timedelta

from .workout_types import WorkoutType, WorkoutVariant

# One workout recorded after it has been completed.
@dataclass(frozen=True)
class CompletedWorkout:
    workout_type: WorkoutType | str
    completed_at: datetime
    variant: WorkoutVariant | str | None = None
    rotation_type: WorkoutType | str | None = None
    google_event_id: str | None = None
    google_calendar_id: str | None = None
    started_at: datetime | None = None
    id: int | None = None
    muscles_trained: tuple[str, ...] = ()
    custom_name: str | None = None
