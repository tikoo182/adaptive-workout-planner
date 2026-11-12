from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..domain.workout_types import WorkoutType, WorkoutVariant

# A calendar event received by the API.
class CalendarEventInput(BaseModel):
    starts_at: datetime
    ends_at: datetime


# Inputs accepted when rebuilding a plan.
class RebuildPlanRequest(BaseModel):
    first_candidate_start: datetime
    calendar_events: list[CalendarEventInput] = Field(default_factory=list)
    push_uses_rings: bool = False


# One planned workout returned by the API.
class PlannedWorkoutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workout_type: WorkoutType
    rotation_type: WorkoutType
    variant: WorkoutVariant | None = None
    starts_at: datetime
    uses_rings: bool