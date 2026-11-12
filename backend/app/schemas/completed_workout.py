from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..domain.workout_types import WorkoutType, WorkoutVariant
from .plan import CalendarEventInput

# Data sent when logging a workout and rebuilding the plan.
class LogCompletedWorkoutRequest(BaseModel):
    workout_type: WorkoutType
    completed_at: datetime
    variant: WorkoutVariant | None = None
    rotation_type: WorkoutType | None = None
    first_candidate_start: datetime
    calendar_events: list[CalendarEventInput] = Field(default_factory=list)
    push_uses_rings: bool = False


# A completed workout returned by the API.
class CompletedWorkoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workout_type: WorkoutType
    completed_at: datetime
    variant: WorkoutVariant | None = None
    rotation_type: WorkoutType | None = None