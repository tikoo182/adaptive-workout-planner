from dataclasses import dataclass, field

from .workout_types import WorkoutType

# Tracks where the rotation should continue.
@dataclass(frozen=True)
class SchedulerState:
    rotation_cursor: WorkoutType | str | None = None
    replacement_run_due: bool = False
    rotation_cursors: dict[str, WorkoutType | str] = field(default_factory=dict)
