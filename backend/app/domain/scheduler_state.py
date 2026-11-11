from dataclasses import dataclass

from .workout_types import WorkoutType

# Tracks where the rotation should continue.
@dataclass(frozen=True)
class SchedulerState:
    rotation_cursor: WorkoutType | None = None
    replacement_run_due: bool = False