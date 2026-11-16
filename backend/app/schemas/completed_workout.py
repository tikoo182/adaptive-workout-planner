from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.workout_types import WorkoutType, WorkoutVariant
from .plan import CalendarEventInput, to_sonora_local_datetime

# Data sent when logging a workout and rebuilding the plan.
class LogCompletedWorkoutRequest(BaseModel):
    workout_type: WorkoutType
    completed_at: datetime
    variant: WorkoutVariant | None = None
    rotation_type: WorkoutType | None = None
    first_candidate_start: datetime
    calendar_events: list[CalendarEventInput] = Field(default_factory=list)
    push_uses_rings: bool = False

    @field_validator("completed_at", "first_candidate_start")
    @classmethod
    def use_sonora_local_time(cls, value: datetime) -> datetime:
        return to_sonora_local_datetime(value)


# A completed workout returned by the API.
class CompletedWorkoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workout_type: WorkoutType
    completed_at: datetime
    variant: WorkoutVariant | None = None
    rotation_type: WorkoutType | None = None
