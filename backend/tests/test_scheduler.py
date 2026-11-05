import unittest
from datetime import datetime

from backend.app.domain.scheduler import build_rolling_plan
from backend.app.domain.workout_types import WorkoutType


class BuildRollingPlanTests(unittest.TestCase):
    # Check the rotation, rest days, and Run replacement with no other conflicts.
    def test_builds_expected_plan_without_calendar_conflicts(self):
        plan_start = datetime(2026, 11, 5, 7, 0)

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=[],
            existing_workouts=[],
        )

        actual_schedule = [
            (workout.starts_at, workout.workout_type)
            for workout in planned_workouts
        ]
        expected_schedule = [
            (datetime(2026, 11, 5, 7, 0), WorkoutType.HIIT_LEGS),
            (datetime(2026, 11, 6, 7, 0), WorkoutType.PUSH),
            (datetime(2026, 11, 7, 7, 0), WorkoutType.RUN),
            (datetime(2026, 11, 9, 7, 0), WorkoutType.LEGS),
            (datetime(2026, 11, 10, 7, 0), WorkoutType.HIIT_ABS),
            (datetime(2026, 11, 11, 7, 0), WorkoutType.PULL),
            (datetime(2026, 11, 13, 7, 0), WorkoutType.RUN),
            (datetime(2026, 11, 14, 7, 0), WorkoutType.PUSH),
        ]

        self.assertEqual(actual_schedule, expected_schedule)


if __name__ == "__main__":
    unittest.main()
