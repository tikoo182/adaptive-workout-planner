from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db.models import PlannerSettingsRecord
from ..schemas.settings import DEFAULT_SETTINGS, MUSCLE_GROUPS, PlannerSettings, PlannerSettingsResponse
from .plan import get_db_session

router = APIRouter()


def _get_or_create_settings(session: Session) -> PlannerSettingsRecord:
    record = session.get(PlannerSettingsRecord, 1)
    if record is None:
        record = PlannerSettingsRecord(
            id=1,
            settings=DEFAULT_SETTINGS.model_dump(mode="json"),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
    return record


# Return the saved workout catalogue and scheduling preferences.
@router.get("/settings", response_model=PlannerSettingsResponse)
def read_settings(session: Session = Depends(get_db_session)) -> PlannerSettingsResponse:
    settings = PlannerSettings.model_validate(_get_or_create_settings(session).settings)
    return PlannerSettingsResponse(**settings.model_dump(), muscle_groups=MUSCLE_GROUPS)


# Save the user's editable workouts, rotation, and time constraints.
@router.put("/settings", response_model=PlannerSettingsResponse)
def save_settings(
    request: PlannerSettings,
    session: Session = Depends(get_db_session),
) -> PlannerSettingsResponse:
    record = _get_or_create_settings(session)
    record.settings = request.model_dump(mode="json")
    session.commit()
    session.refresh(record)
    return PlannerSettingsResponse(**request.model_dump(), muscle_groups=MUSCLE_GROUPS)
