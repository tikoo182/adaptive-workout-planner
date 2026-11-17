import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..domain.completed_workout import CompletedWorkout
from ..domain.planned_workout import PlannedWorkout
from ..domain.schedule_rules import WORKOUT_DURATION_MINUTES
from .google_token_encryption import decrypt_refresh_token

SONORA_TIMEZONE = ZoneInfo("America/Hermosillo")
GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
    "https://www.googleapis.com/auth/calendar.events.owned",
]


# Build an authorized Google Calendar API client.
def build_google_calendar_service(
    encrypted_refresh_token: str,
    scopes: list[str],
) -> Any:
    credentials = Credentials(
        token=None,
        refresh_token=decrypt_refresh_token(encrypted_refresh_token),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=scopes,
    )

    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


# Convert a local datetime to the format Google Calendar expects.
def _as_google_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=SONORA_TIMEZONE)
    else:
        value = value.astimezone(SONORA_TIMEZONE)

    return value.isoformat()


# Convert Google's time to a local, timezone-naive datetime.
def _as_local_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed

    return parsed.astimezone(SONORA_TIMEZONE).replace(tzinfo=None)


# Read Busy periods while excluding this app's own events on the target calendar.
def get_busy_periods_for_all_calendars(
    encrypted_refresh_token: str,
    scopes: list[str],
    starts_at: datetime,
    ends_at: datetime,
    managed_calendar_id: str | None = None,
) -> list[tuple[datetime, datetime]]:
    calendar_api = build_google_calendar_service(
        encrypted_refresh_token,
        scopes,
    )

    calendar_ids: list[str] = []
    page_token = None

    # Get every calendar ID, following Google's pagination.
    while True:
        parameters: dict[str, Any] = {
            "maxResults": 250,
            "fields": "nextPageToken,items(id)",
        }
        if page_token is not None:
            parameters["pageToken"] = page_token

        result = (
            calendar_api.calendarList()
            .list(**parameters)
            .execute()
        )

        calendar_ids.extend(
            item["id"] for item in result.get("items", [])
        )
        page_token = result.get("nextPageToken")

        if page_token is None:
            break

    busy_periods: list[tuple[datetime, datetime]] = []
    other_calendar_ids = [
        calendar_id
        for calendar_id in calendar_ids
        if calendar_id != managed_calendar_id
    ]

    # Google allows up to 50 calendars in one FreeBusy request.
    for index in range(0, len(other_calendar_ids), 50):
        calendar_batch = other_calendar_ids[index:index + 50]
        result = (
            calendar_api.freebusy()
            .query(
                body={
                    "timeMin": _as_google_datetime(starts_at),
                    "timeMax": _as_google_datetime(ends_at),
                    "timeZone": "America/Hermosillo",
                    "items": [
                        {"id": calendar_id}
                        for calendar_id in calendar_batch
                    ],
                }
            )
            .execute()
        )

        for calendar in result.get("calendars", {}).values():
            if calendar.get("errors"):
                raise RuntimeError("Google could not read a calendar's Busy times.")
            for period in calendar.get("busy", []):
                busy_periods.append(
                    (
                        _as_local_datetime(period["start"]),
                        _as_local_datetime(period["end"]),
                    )
                )

    if managed_calendar_id is not None:
        page_token = None
        while True:
            parameters = {
                "calendarId": managed_calendar_id,
                "timeMin": _as_google_datetime(starts_at),
                "timeMax": _as_google_datetime(ends_at),
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": 2500,
            }
            if page_token is not None:
                parameters["pageToken"] = page_token

            result = calendar_api.events().list(**parameters).execute()
            for event in result.get("items", []):
                if event.get("status") == "cancelled":
                    continue
                if event.get("transparency") == "transparent":
                    continue
                marker = (
                    event.get("extendedProperties", {})
                    .get("private", {})
                    .get("adaptiveWorkoutPlanner")
                )
                if marker in {"planned", "completed"}:
                    continue

                event_start = event.get("start", {})
                event_end = event.get("end", {})
                start_value = event_start.get("dateTime") or event_start.get("date")
                end_value = event_end.get("dateTime") or event_end.get("date")
                if start_value and end_value:
                    busy_periods.append(
                        (
                            _as_local_datetime(start_value),
                            _as_local_datetime(end_value),
                        )
                    )

            page_token = result.get("nextPageToken")
            if page_token is None:
                break

    return busy_periods


def _format_label(value: str) -> str:
    return " ".join(
        "HIIT" if word == "hiit" else word.capitalize()
        for word in value.split("_")
    )


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _build_workout_event(
    workout: PlannedWorkout | CompletedWorkout,
    completed: bool,
) -> dict[str, Any]:
    workout_type = _enum_value(workout.workout_type)
    variant = _enum_value(workout.variant) if workout.variant is not None else None
    label = getattr(workout, "custom_name", None) or _format_label(variant or workout_type)
    if completed:
        starts_at = workout.started_at or (
            workout.completed_at - timedelta(minutes=WORKOUT_DURATION_MINUTES)
        )
        ends_at = workout.completed_at
    else:
        starts_at = workout.starts_at
        ends_at = starts_at + timedelta(
            minutes=getattr(workout, "duration_minutes", WORKOUT_DURATION_MINUTES)
        )
    title_prefix = "Completed workout" if completed else "Workout"
    description = "Logged by Adaptive Workout Planner." if completed else (
        "Scheduled by Adaptive Workout Planner.\n"
        f"Rotation item: {_format_label(_enum_value(workout.rotation_type or workout.workout_type))}.\n"
        + ("Gymnastic rings required." if workout.uses_rings else "")
    )

    event: dict[str, Any] = {
        "summary": f"{title_prefix}: {label}",
        "description": description,
        "start": {
            "dateTime": _as_google_datetime(starts_at),
            "timeZone": "America/Hermosillo",
        },
        "end": {
            "dateTime": _as_google_datetime(ends_at),
            "timeZone": "America/Hermosillo",
        },
        "extendedProperties": {
            "private": {
                "adaptiveWorkoutPlanner": "completed" if completed else "planned",
            }
        },
    }

    if completed:
        event["reminders"] = {"useDefault": False, "overrides": []}
    else:
        event["reminders"] = {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 15},
                {"method": "popup", "minutes": 0},
            ],
        }

    return event


def _delete_calendar_event(
    calendar_api: Any,
    calendar_id: str,
    event_id: str,
) -> None:
    try:
        calendar_api.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
        ).execute()
    except HttpError as error:
        if getattr(error.resp, "status", None) != 404:
            raise


def _upsert_calendar_event(
    calendar_api: Any,
    target_calendar_id: str,
    body: dict[str, Any],
    old_event_id: str | None = None,
    old_calendar_id: str | None = None,
) -> str:
    if old_event_id and old_calendar_id == target_calendar_id:
        try:
            result = calendar_api.events().update(
                calendarId=target_calendar_id,
                eventId=old_event_id,
                body=body,
            ).execute()
            return result["id"]
        except HttpError as error:
            if getattr(error.resp, "status", None) != 404:
                raise

    result = calendar_api.events().insert(
        calendarId=target_calendar_id,
        body=body,
    ).execute()
    new_event_id = result["id"]

    if old_event_id and old_calendar_id:
        _delete_calendar_event(calendar_api, old_calendar_id, old_event_id)

    return new_event_id


# Update or create planned events, then remove events no longer in the plan.
def sync_planned_workout_events(
    encrypted_refresh_token: str,
    scopes: list[str],
    target_calendar_id: str,
    previous_workouts: list[PlannedWorkout],
    planned_workouts: list[PlannedWorkout],
) -> None:
    calendar_api = build_google_calendar_service(
        encrypted_refresh_token,
        scopes,
    )
    previous_events = [
        workout
        for workout in previous_workouts
        if workout.google_event_id is not None
    ]

    for index, workout in enumerate(planned_workouts):
        previous = previous_events[index] if index < len(previous_events) else None
        workout.google_event_id = _upsert_calendar_event(
            calendar_api=calendar_api,
            target_calendar_id=target_calendar_id,
            body=_build_workout_event(workout, completed=False),
            old_event_id=previous.google_event_id if previous else None,
            old_calendar_id=previous.google_calendar_id if previous else None,
        )
        workout.google_calendar_id = target_calendar_id

    # Remove surplus old planned events after the replacements are in place.
    for previous in previous_events[len(planned_workouts):]:
        if previous.google_calendar_id is not None:
            _delete_calendar_event(
                calendar_api,
                previous.google_calendar_id,
                previous.google_event_id,
            )


# Keep a completed workout in Calendar, reusing its planned event when possible.
def sync_completed_workout_event(
    encrypted_refresh_token: str,
    scopes: list[str],
    target_calendar_id: str,
    workout: CompletedWorkout,
    matching_planned_workout: PlannedWorkout | None,
) -> tuple[str, str]:
    calendar_api = build_google_calendar_service(
        encrypted_refresh_token,
        scopes,
    )
    event_id = _upsert_calendar_event(
        calendar_api=calendar_api,
        target_calendar_id=target_calendar_id,
        body=_build_workout_event(workout, completed=True),
        old_event_id=(
            matching_planned_workout.google_event_id
            if matching_planned_workout
            else None
        ),
        old_calendar_id=(
            matching_planned_workout.google_calendar_id
            if matching_planned_workout
            else None
        ),
    )
    return event_id, target_calendar_id


# Find app-planned events that the user deleted directly from Google Calendar.
def find_deleted_planned_workouts(
    encrypted_refresh_token: str,
    scopes: list[str],
    planned_workouts: list[PlannedWorkout],
) -> list[PlannedWorkout]:
    calendar_api = build_google_calendar_service(
        encrypted_refresh_token,
        scopes,
    )
    deleted: list[PlannedWorkout] = []

    for workout in planned_workouts:
        if workout.google_event_id is None or workout.google_calendar_id is None:
            continue
        try:
            event = calendar_api.events().get(
                calendarId=workout.google_calendar_id,
                eventId=workout.google_event_id,
            ).execute()
            if event.get("status") == "cancelled":
                deleted.append(workout)
        except HttpError as error:
            if getattr(error.resp, "status", None) in {404, 410}:
                deleted.append(workout)
            else:
                raise

    return deleted
