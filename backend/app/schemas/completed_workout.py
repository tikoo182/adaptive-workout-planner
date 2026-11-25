from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.workout_types import WorkoutType, WorkoutVariant
from .plan import CalendarEventInput, to_sonora_local_datetime

# Data sent when logging a workout and rebuilding the plan.
class LogCompletedWorkoutRequest(BaseModel):
    workout_type: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    completed_at: datetime
    started_at: datetime | None = None
    variant: str | None = Field(default=None, max_length=50)
    rotation_type: str | None = None
    first_candidate_start: datetime
    calendar_events: list[CalendarEventInput] = Field(default_factory=list)
    push_uses_rings: bool = False
    healthkit_id: str | None = None
    source_activity: str | None = None
    muscles_trained: list[str] = Field(default_factory=list)
    custom_name: str | None = Field(default=None, max_length=80)

    @field_validator("completed_at", "started_at", "first_candidate_start")
    @classmethod
    def use_sonora_local_time(cls, value: datetime) -> datetime:
        return to_sonora_local_datetime(value)

# A completed workout returned by the API.
class CompletedWorkoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workout_type: str
    completed_at: datetime
    started_at: datetime | None = None
    variant: str | None = None
    rotation_type: str | None = None
    healthkit_id: str | None = None
    source_activity: str | None = None
    muscles_trained: list[str] = Field(default_factory=list)
    custom_name: str | None = None


# Workout details uploaded automatically by Apple Health.
class HealthKitWorkoutRequest(BaseModel):
    healthkit_id: str
    activity_type: str
    started_at: datetime
    ended_at: datetime
    source_name: str | None = None

    @field_validator("started_at", "ended_at")
    @classmethod
    def use_sonora_local_time(cls, value: datetime) -> datetime:
        return to_sonora_local_datetime(value)


# A correction to the workout's planner classification.
class CorrectCompletedWorkoutRequest(BaseModel):
    workout_type: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    variant: str | None = Field(default=None, max_length=50)
    rotation_type: str | None = None
    muscles_trained: list[str] = Field(default_factory=list)
    custom_name: str | None = Field(default=None, max_length=80)
