from dataclasses import dataclass
from datetime import datetime

from .workout_types import WorkoutType


# A planned workout deleted from Calendar and treated as a rest day.
@dataclass(frozen=True)
class SkippedWorkout:
    workout_type: WorkoutType | str
    rotation_type: WorkoutType | str
    skipped_at: datetime
    google_event_id: str
