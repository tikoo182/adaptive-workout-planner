import os
import unittest
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import (
    CompletedWorkoutRecord,
    PlannedWorkoutRecord,
)
from backend.app.domain.completed_workout import CompletedWorkout
from backend.app.domain.workout_types import WorkoutType
from backend.app.services.schedule_service import (
    log_completed_workout_and_rebuild_plan,
)

# Database integration checks for schedule services.
DATABASE_ENVIRONMENT_IS_SET = all(
    os.environ.get(name)
    for name in (
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    )
)


@unittest.skipUnless(
    DATABASE_ENVIRONMENT_IS_SET,
    "PostgreSQL environment variables are not set",
)
class ScheduleServiceIntegrationTests(unittest.TestCase):
    # Check that an extra Run leaves the pending Push due.
    def test_extra_run_does_not_advance_pending_push(self):
        from backend.app.db.session import engine

        with engine.connect() as connection:
            outer_transaction = connection.begin()
            test_session_factory = sessionmaker(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )

            try:
                with test_session_factory() as session:
                    # Clear test rows inside a transaction that will be rolled back.
                    with session.begin():
                        session.execute(delete(CompletedWorkoutRecord))
                        session.execute(delete(PlannedWorkoutRecord))

                    plan_after_hiit = log_completed_workout_and_rebuild_plan(
                        session=session,
                        completed_workout=CompletedWorkout(
                            workout_type=WorkoutType.HIIT_LEGS,
                            completed_at=datetime(2026, 11, 5, 7, 0),
                            rotation_type=WorkoutType.HIIT_LEGS,
                        ),
                        first_candidate_start=datetime(2026, 11, 6, 7, 0),
                        calendar_events=[],
                    )

                    self.assertEqual(
                        plan_after_hiit[0].workout_type,
                        WorkoutType.PUSH,
                    )

                    plan_after_extra_run = (
                        log_completed_workout_and_rebuild_plan(
                            session=session,
                            completed_workout=CompletedWorkout(
                                workout_type=WorkoutType.RUN,
                                completed_at=datetime(2026, 11, 6, 8, 0),
                            ),
                            first_candidate_start=datetime(2026, 11, 7, 7, 0),
                            calendar_events=[],
                        )
                    )

                    self.assertEqual(
                        plan_after_extra_run[0].workout_type,
                        WorkoutType.PUSH,
                    )
            finally:
                outer_transaction.rollback()


if __name__ == "__main__":
    unittest.main()