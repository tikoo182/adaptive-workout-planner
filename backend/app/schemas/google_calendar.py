from pydantic import BaseModel

# Calendar details used by the planner.
class GoogleCalendarResponse(BaseModel):
    calendar_id: str
    name: str
    is_primary: bool
    access_role: str
    can_be_target: bool


# Calendar selected as the planner's workout destination.
class SetTargetCalendarRequest(BaseModel):
    calendar_id: str