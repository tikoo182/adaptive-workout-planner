from dataclasses import dataclass
from datetime import datetime

from .workout_types import WorkoutType, WorkoutVariant

# One workout placed in the plan, including whether it uses rings.
@dataclass
class PlannedWorkout:
    workout_type: WorkoutType
    starts_at: datetime
    uses_rings: bool = False
    variant: WorkoutVariant | None = None
    rotation_type: WorkoutType | None = None
    google_event_id: str | None = None
    google_calendar_id: str | None = None