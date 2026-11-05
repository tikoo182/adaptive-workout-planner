from dataclasses import dataclass
from datetime import datetime

from .workout_types import WorkoutType

# One workout placed in the plan, including whether it uses rings.
@dataclass
class PlannedWorkout:
    workout_type: WorkoutType
    starts_at: datetime
    uses_rings: bool = False