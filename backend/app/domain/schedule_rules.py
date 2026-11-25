from datetime import time

# Shared workout limits and timing rules.

WORKOUT_DURATION_MINUTES = 60
PLAN_HORIZON_DAYS = 10

MAX_CONSECUTIVE_WORKOUT_DAYS = 3

EARLIEST_WORKOUT_START = time(7, 0)
LATEST_WORKOUT_START = time(20, 0)
LATEST_HIIT_START = time(9, 0)
EVENING_START_TIME = time(17, 30)

LATEST_RING_WORKOUT_MORNING_START = time(9, 0)
LATEST_NON_RING_WORKOUT_MORNING_START = time(11, 0)

# Leave an hour between a workout and a later calendar event.
EVENT_BUFFER_MINUTES = 60

RESCHEDULE_INTERVAL_MINUTES = 60
from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduleRules:
    earliest_workout_start: time = EARLIEST_WORKOUT_START
    latest_workout_start: time = LATEST_WORKOUT_START
    latest_hiit_start: time = LATEST_HIIT_START
    evening_start_time: time = EVENING_START_TIME
    latest_ring_workout_morning_start: time = LATEST_RING_WORKOUT_MORNING_START
    latest_non_ring_workout_morning_start: time = LATEST_NON_RING_WORKOUT_MORNING_START
    workout_duration_minutes: int = WORKOUT_DURATION_MINUTES
    event_buffer_minutes: int = EVENT_BUFFER_MINUTES
    plan_horizon_days: int = PLAN_HORIZON_DAYS
    max_consecutive_workout_days: int = MAX_CONSECUTIVE_WORKOUT_DAYS
    reschedule_interval_minutes: int = RESCHEDULE_INTERVAL_MINUTES
    prefer_sunday_runs: bool = False

    @classmethod
    def from_settings(cls, values: dict) -> "ScheduleRules":
        return cls(
            earliest_workout_start=time.fromisoformat(values["earliest_start"]),
            latest_workout_start=time.fromisoformat(values["latest_start"]),
            latest_hiit_start=time.fromisoformat(values["latest_hiit_start"]),
            evening_start_time=time.fromisoformat(values["evening_start"]),
            latest_ring_workout_morning_start=time.fromisoformat(values["latest_ring_morning_start"]),
            latest_non_ring_workout_morning_start=time.fromisoformat(values["latest_non_ring_morning_start"]),
            workout_duration_minutes=values["workout_duration_minutes"],
            event_buffer_minutes=values["calendar_buffer_minutes"],
            max_consecutive_workout_days=values["max_consecutive_workout_days"],
            prefer_sunday_runs=values.get("prefer_sunday_runs", False),
        )
