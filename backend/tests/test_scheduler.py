import unittest
from unittest.mock import patch

from datetime import datetime, timedelta

from backend.app.domain.planned_workout import PlannedWorkout
from backend.app.domain.completed_workout import CompletedWorkout
from backend.app.domain.scheduler import (
    build_rolling_plan,
    build_rolling_plan_with_state,
    get_next_workout_variant,
)
from backend.app.domain.workout_types import WorkoutType
from backend.app.domain.workout_types import WorkoutVariant
from backend.app.domain.scheduler_state import SchedulerState


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

    # Keep the repeated Dips session in the Push variant rotation.
    def test_push_variants_follow_the_expected_rotation(self):
        planned_push_workouts = []
        actual_variants = []

        for day_offset in range(5):
            variant = get_next_workout_variant(
                workout_type=WorkoutType.PUSH,
                completed_workouts=[],
                planned_workouts=planned_push_workouts,
            )
            actual_variants.append(variant)
            planned_push_workouts.append(
                PlannedWorkout(
                    workout_type=WorkoutType.PUSH,
                    starts_at=datetime(2026, 11, 5 + day_offset, 7, 0),
                    variant=variant,
                )
            )

        self.assertEqual(
            actual_variants,
            [
                WorkoutVariant.PUSH_DIPS,
                WorkoutVariant.PUSH_PIKE_RUSSIAN,
                WorkoutVariant.PUSH_DIPS,
                WorkoutVariant.PUSH_PIKE_WEIGHTED,
                WorkoutVariant.PUSH_PIKE_ARCHER,
            ],
        )

    # Continue the Push rotation from the last completed variation.
    def test_completed_push_history_advances_the_variant_rotation(self):
        completed_workouts = [
            CompletedWorkout(
                workout_type=WorkoutType.PUSH,
                completed_at=datetime(2026, 11, 4, 7, 0),
                variant=WorkoutVariant.PUSH_DIPS,
            )
        ]

        next_variant = get_next_workout_variant(
            workout_type=WorkoutType.PUSH,
            completed_workouts=completed_workouts,
            planned_workouts=[],
        )

        self.assertEqual(next_variant, WorkoutVariant.PUSH_PIKE_RUSSIAN)

    # Alternate between the two Pull workout variations.
    def test_pull_variants_follow_the_expected_rotation(self):
        planned_pull_workouts = []
        actual_variants = []

        for day_offset in range(2):
            variant = get_next_workout_variant(
                workout_type=WorkoutType.PULL,
                completed_workouts=[],
                planned_workouts=planned_pull_workouts,
            )
            actual_variants.append(variant)
            planned_pull_workouts.append(
                PlannedWorkout(
                    workout_type=WorkoutType.PULL,
                    starts_at=datetime(2026, 11, 5 + day_offset, 7, 0),
                    variant=variant,
                )
            )

        self.assertEqual(
            actual_variants,
            [
                WorkoutVariant.PULL_CHINUPS_AND_PULLUPS,
                WorkoutVariant.PULL_DEAD_HANGS_AND_ABS,
            ],
        )

    # Alternate between the two Legs workout variations.
    def test_legs_variants_follow_the_expected_rotation(self):
        planned_leg_workouts = []
        actual_variants = []

        for day_offset in range(2):
            variant = get_next_workout_variant(
                workout_type=WorkoutType.LEGS,
                completed_workouts=[],
                planned_workouts=planned_leg_workouts,
            )
            actual_variants.append(variant)
            planned_leg_workouts.append(
                PlannedWorkout(
                    workout_type=WorkoutType.LEGS,
                    starts_at=datetime(2026, 11, 5 + day_offset, 7, 0),
                    variant=variant,
                )
            )

        self.assertEqual(
            actual_variants,
            [
                WorkoutVariant.LEGS_LUNGES,
                WorkoutVariant.LEGS_WEIGHTED_SITUPS,
            ],
        )

    # Start a Run at the end of an event, without adding a buffer afterward.
    def test_starts_run_when_calendar_event_ends(self):
        plan_start = datetime(2026, 11, 5, 7, 0)
        calendar_events = [
            (datetime(2026, 11, 5, 8, 0), datetime(2026, 11, 5, 10, 0))
        ]

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=calendar_events,
            existing_workouts=[],
            previous_workout_type=WorkoutType.PUSH,
        )

        first_workout = planned_workouts[0]
        self.assertEqual(first_workout.workout_type, WorkoutType.RUN)
        self.assertEqual(first_workout.starts_at, datetime(2026, 11, 5, 10, 0))

    # Leave an hour between the Run and a later calendar event.
    def test_leaves_buffer_before_calendar_event(self):
        plan_start = datetime(2026, 11, 5, 7, 0)
        calendar_events = [
            (datetime(2026, 11, 5, 8, 30), datetime(2026, 11, 5, 9, 30))
        ]

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=calendar_events,
            existing_workouts=[],
            previous_workout_type=WorkoutType.PUSH,
        )

        first_workout = planned_workouts[0]
        self.assertEqual(first_workout.workout_type, WorkoutType.RUN)
        self.assertEqual(first_workout.starts_at, datetime(2026, 11, 5, 10, 0))

    # Keep the next rotation workout off a day that is already occupied.
    def test_skips_day_with_existing_workout(self):
        plan_start = datetime(2026, 11, 5, 7, 0)
        existing_workouts = [
            PlannedWorkout(
                workout_type=WorkoutType.HIIT_LEGS,
                starts_at=datetime(2026, 11, 5, 7, 0),
            )
        ]

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=[],
            existing_workouts=existing_workouts,
            previous_workout_type=WorkoutType.HIIT_LEGS,
        )

        first_workout = planned_workouts[0]
        self.assertEqual(first_workout.workout_type, WorkoutType.PUSH)
        self.assertEqual(first_workout.starts_at, datetime(2026, 11, 6, 7, 0))

    # Keep Pull workouts out of the daytime window.
    def test_schedules_pull_in_the_evening(self):
        plan_start = datetime(2026, 11, 5, 10, 0)

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=[],
            existing_workouts=[],
            previous_workout_type=WorkoutType.HIIT_ABS,
        )

        first_workout = planned_workouts[0]
        self.assertEqual(first_workout.workout_type, WorkoutType.PULL)
        self.assertEqual(first_workout.starts_at, datetime(2026, 11, 5, 18, 0))


    # Move HIIT Legs to the next morning when the search starts too late.
    def test_moves_hiit_legs_to_next_morning_after_cutoff(self):
        plan_start = datetime(2026, 11, 5, 10, 0)

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=[],
            existing_workouts=[],
        )

        first_workout = planned_workouts[0]
        self.assertEqual(first_workout.workout_type, WorkoutType.HIIT_LEGS)
        self.assertEqual(first_workout.starts_at, datetime(2026, 11, 6, 7, 0))


    # Allow a non-ring Push workout at the latest morning start time.
    def test_allows_push_at_latest_morning_start(self):
        plan_start = datetime(2026, 11, 5, 11, 0)
        completed_workouts = [
            CompletedWorkout(
                workout_type=WorkoutType.PUSH,
                completed_at=datetime(2026, 11, 4, 7, 0),
                variant=WorkoutVariant.PUSH_DIPS,
            )
        ]

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=[],
            existing_workouts=[],
            previous_workout_type=WorkoutType.HIIT_LEGS,
            completed_workouts=completed_workouts,
        )

        first_workout = planned_workouts[0]
        self.assertEqual(first_workout.workout_type, WorkoutType.PUSH)
        self.assertEqual(
            first_workout.variant,
            WorkoutVariant.PUSH_PIKE_RUSSIAN,
        )
        self.assertEqual(first_workout.starts_at, datetime(2026, 11, 5, 11, 0))


    # Schedule a ring-based Push workout in the evening when searched from 10 a.m.
    def test_schedules_ring_push_in_the_evening(self):
        plan_start = datetime(2026, 11, 5, 10, 0)

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=[],
            existing_workouts=[],
            previous_workout_type=WorkoutType.HIIT_LEGS,
            push_uses_rings=True,
        )

        first_workout = planned_workouts[0]
        self.assertEqual(first_workout.workout_type, WorkoutType.PUSH)
        self.assertTrue(first_workout.uses_rings)
        self.assertEqual(first_workout.starts_at, datetime(2026, 11, 5, 18, 0))


    # Allow ring-based Push at its latest morning start time.
    def test_allows_ring_push_at_latest_morning_start(self):
        plan_start = datetime(2026, 11, 5, 9, 0)

        planned_workouts = build_rolling_plan(
            first_candidate_start=plan_start,
            calendar_events=[],
            existing_workouts=[],
            previous_workout_type=WorkoutType.HIIT_LEGS,
            push_uses_rings=True,
        )

        first_workout = planned_workouts[0]
        self.assertEqual(first_workout.workout_type, WorkoutType.PUSH)
        self.assertTrue(first_workout.uses_rings)
        self.assertEqual(first_workout.starts_at, datetime(2026, 11, 5, 9, 0))

        # Resume after a normal Run and keep its replacement due.
    def test_resumes_replacement_run_after_rotation_run(self):
        first_start = datetime(2026, 11, 5, 7, 0)

        with patch("backend.app.domain.scheduler.PLAN_HORIZON_DAYS", 1):
            first_plan, state = build_rolling_plan_with_state(
                first_candidate_start=first_start,
                calendar_events=[],
                existing_workouts=[],
                state=SchedulerState(rotation_cursor=WorkoutType.PUSH),
            )

        self.assertEqual(first_plan[0].workout_type, WorkoutType.RUN)
        self.assertEqual(first_plan[0].rotation_type, WorkoutType.RUN)
        self.assertTrue(state.replacement_run_due)

        with patch("backend.app.domain.scheduler.PLAN_HORIZON_DAYS", 10):
            resumed_plan, _ = build_rolling_plan_with_state(
                first_candidate_start=datetime(2026, 11, 6, 7, 0),
                calendar_events=[],
                existing_workouts=first_plan,
                state=state,
            )

        replacement_run = next(
            workout
            for workout in resumed_plan
            if workout.rotation_type == WorkoutType.HIIT_LEGS
        )
        self.assertEqual(replacement_run.workout_type, WorkoutType.RUN)

    # Resuming in two windows should produce the same schedule as one window.
    def test_resumed_plan_matches_uninterrupted_plan(self):
        plan_start = datetime(2026, 11, 5, 7, 0)

        with patch("backend.app.domain.scheduler.PLAN_HORIZON_DAYS", 10):
            full_plan, _ = build_rolling_plan_with_state(
                first_candidate_start=plan_start,
                calendar_events=[],
                existing_workouts=[],
                state=SchedulerState(),
            )

        with patch("backend.app.domain.scheduler.PLAN_HORIZON_DAYS", 5):
            first_part, state = build_rolling_plan_with_state(
                first_candidate_start=plan_start,
                calendar_events=[],
                existing_workouts=[],
                state=SchedulerState(),
            )
            second_part, _ = build_rolling_plan_with_state(
                first_candidate_start=plan_start + timedelta(days=5),
                calendar_events=[],
                existing_workouts=first_part,
                state=state,
            )

        def schedule_details(workouts):
            return [
                (
                    workout.starts_at,
                    workout.workout_type,
                    workout.variant,
                    workout.rotation_type,
                )
                for workout in workouts
            ]

        self.assertEqual(
            schedule_details(first_part + second_part),
            schedule_details(full_plan),
        )


if __name__ == "__main__":
    unittest.main()
