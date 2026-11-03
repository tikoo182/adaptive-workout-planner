from datetime import time

from .schedule_rules import EARLIEST_WORKOUT_START, LATEST_WORKOUT_START


def is_allowed_start_time(start_time: time) -> bool:
    return EARLIEST_WORKOUT_START <= start_time <= LATEST_WORKOUT_START