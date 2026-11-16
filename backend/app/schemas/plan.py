from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.workout_types import WorkoutType, WorkoutVariant

SONORA_TIMEZONE = ZoneInfo("America/Hermosillo")


# Convert an incoming datetime to the local, timezone-naive format the scheduler uses.
def to_sonora_local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value

    return value.astimezone(SONORA_TIMEZONE).replace(tzinfo=None)


# A calendar event received by the API.
class CalendarEventInput(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def use_sonora_local_time(cls, value: datetime) -> datetime:
        return to_sonora_local_datetime(value)


# Inputs accepted when rebuilding a plan.
class RebuildPlanRequest(BaseModel):
    first_candidate_start: datetime
    calendar_events: list[CalendarEventInput] = Field(default_factory=list)
    push_uses_rings: bool = False

    @field_validator("first_candidate_start")
    @classmethod
    def use_sonora_local_time(cls, value: datetime) -> datetime:
        return to_sonora_local_datetime(value)


# One planned workout returned by the API.
class PlannedWorkoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workout_type: WorkoutType
    rotation_type: WorkoutType
    variant: WorkoutVariant | None = None
    starts_at: datetime
    uses_rings: bool
