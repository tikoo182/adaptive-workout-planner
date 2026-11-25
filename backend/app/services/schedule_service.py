from datetime import datetime

from sqlalchemy.orm import Session

from ..db.repositories import (
    clear_planned_workouts,
    get_completed_workouts,
    get_skipped_workouts,
    save_planned_workout,
)
from ..domain.planned_workout import PlannedWorkout
from ..domain.scheduler import (
    build_rolling_plan_with_state,
    get_scheduler_state_from_history,
)

from ..db.repositories import save_completed_workout
from ..domain.completed_workout import CompletedWorkout
from ..db.models import PlannerSettingsRecord
from ..domain.schedule_rules import ScheduleRules
from ..domain.workout_types import WorkoutType
from ..schemas.settings import DEFAULT_SETTINGS, PlannerSettings

# Coordinates plan rebuilding and database storage.


def _scheduler_preferences(session: Session):
    record = session.get(PlannerSettingsRecord, 1)
    settings = PlannerSettings.model_validate(record.settings) if record else DEFAULT_SETTINGS
    valid_types = {item.value for item in WorkoutType if item != WorkoutType.CUSTOM}
    enabled_ids = {item.id for item in settings.workouts if item.enabled}
    rotation = tuple(
        WorkoutType(item) if item in valid_types else item
        for item in settings.rotation
        if item in enabled_ids
    )
    return (
        ScheduleRules.from_settings(settings.timing.model_dump()),
        rotation,
        {item.id: item.muscles for item in settings.workouts},
        settings.timing.muscle_recovery_days,
        {item.id: item.variants for item in settings.workouts},
        {item.id: item.category for item in settings.workouts},
        {item.id: item.variant_muscles for item in settings.workouts},
        {item.id: item.uses_rings for item in settings.workouts},
        {item.id: item.variant_uses_rings for item in settings.workouts},
        {item.id: item.is_hiit for item in settings.workouts},
        {item.id: item.category == "strength" for item in settings.workouts},
    )


# Carry old Google event references forward so rebuilds can update those events.
def _carry_forward_calendar_event_ids(
    planned_workouts: list[PlannedWorkout],
    previous_workouts: list[PlannedWorkout] | None,
) -> None:
    previous_events = [
        workout
        for workout in (previous_workouts or [])
        if workout.google_event_id is not None
    ]
    for index, workout in enumerate(planned_workouts):
        if index >= len(previous_events):
            break
        workout.google_event_id = previous_events[index].google_event_id
        workout.google_calendar_id = previous_events[index].google_calendar_id


# Rebuild the pending plan and save it as one transaction.
def rebuild_and_save_plan(
    session: Session,
    first_candidate_start: datetime,
    calendar_events: list[tuple[datetime, datetime]],
    push_uses_rings: bool = False,
    previous_workouts: list[PlannedWorkout] | None = None,
) -> list[PlannedWorkout]:
    with session.begin():
        rules, workout_rotation, muscles_by_workout, muscle_recovery_days, variants_by_workout, category_by_workout, variant_muscles_by_workout, uses_rings_by_workout, variant_uses_rings_by_workout, hiit_by_workout, strength_by_workout = _scheduler_preferences(session)
        completed_workouts = get_completed_workouts(session)
        skipped_workouts = get_skipped_workouts(session)
        historical_skips = [
            workout
            for workout in skipped_workouts
            if workout.skipped_at.date() < first_candidate_start.date()
        ]
        upcoming_skips = [
            workout
            for workout in skipped_workouts
            if workout.skipped_at.date() >= first_candidate_start.date()
        ]
        state = get_scheduler_state_from_history(
            completed_workouts,
            historical_skips,
            category_by_workout,
        )

        planned_workouts, _ = build_rolling_plan_with_state(
            first_candidate_start=first_candidate_start,
            calendar_events=calendar_events,
            existing_workouts=[],
            state=state,
            push_uses_rings=push_uses_rings,
            completed_workouts=completed_workouts,
            skipped_workouts=upcoming_skips,
            rules=rules,
            workout_rotation=workout_rotation,
            muscles_by_workout=muscles_by_workout,
            muscle_recovery_days=muscle_recovery_days,
            variants_by_workout=variants_by_workout,
            category_by_workout=category_by_workout,
            variant_muscles_by_workout=variant_muscles_by_workout,
            uses_rings_by_workout=uses_rings_by_workout,
            variant_uses_rings_by_workout=variant_uses_rings_by_workout,
            hiit_by_workout=hiit_by_workout,
            strength_by_workout=strength_by_workout,
        )

        _carry_forward_calendar_event_ids(planned_workouts, previous_workouts)
        clear_planned_workouts(session)
        for workout in planned_workouts:
            save_planned_workout(session, workout)

    return planned_workouts


# Record a workout and rebuild the remaining plan atomically.
def log_completed_workout_and_rebuild_plan(
    session: Session,
    completed_workout: CompletedWorkout,
    first_candidate_start: datetime,
    calendar_events: list[tuple[datetime, datetime]],
    push_uses_rings: bool = False,
    previous_workouts: list[PlannedWorkout] | None = None,
) -> list[PlannedWorkout]:
    with session.begin():
        save_completed_workout(session, completed_workout)
        rules, workout_rotation, muscles_by_workout, muscle_recovery_days, variants_by_workout, category_by_workout, variant_muscles_by_workout, uses_rings_by_workout, variant_uses_rings_by_workout, hiit_by_workout, strength_by_workout = _scheduler_preferences(session)

        completed_workouts = get_completed_workouts(session)
        skipped_workouts = get_skipped_workouts(session)
        historical_skips = [
            workout
            for workout in skipped_workouts
            if workout.skipped_at.date() < first_candidate_start.date()
        ]
        upcoming_skips = [
            workout
            for workout in skipped_workouts
            if workout.skipped_at.date() >= first_candidate_start.date()
        ]
        state = get_scheduler_state_from_history(
            completed_workouts,
            historical_skips,
            category_by_workout,
        )

        planned_workouts, _ = build_rolling_plan_with_state(
            first_candidate_start=first_candidate_start,
            calendar_events=calendar_events,
            existing_workouts=[],
            state=state,
            push_uses_rings=push_uses_rings,
            completed_workouts=completed_workouts,
            skipped_workouts=upcoming_skips,
            rules=rules,
            workout_rotation=workout_rotation,
            muscles_by_workout=muscles_by_workout,
            muscle_recovery_days=muscle_recovery_days,
            variants_by_workout=variants_by_workout,
            category_by_workout=category_by_workout,
            variant_muscles_by_workout=variant_muscles_by_workout,
            uses_rings_by_workout=uses_rings_by_workout,
            variant_uses_rings_by_workout=variant_uses_rings_by_workout,
            hiit_by_workout=hiit_by_workout,
            strength_by_workout=strength_by_workout,
        )

        _carry_forward_calendar_event_ids(planned_workouts, previous_workouts)
        clear_planned_workouts(session)
        for workout in planned_workouts:
            save_planned_workout(session, workout)

    return planned_workouts
