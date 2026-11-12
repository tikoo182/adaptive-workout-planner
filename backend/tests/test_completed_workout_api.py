import os
import unittest
from datetime import datetime

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
class CompletedWorkoutApiTests(unittest.TestCase):
    # Check that logging a workout updates history and rebuilds the plan.
    def test_logging_workout_returns_saved_plan_and_history(self):
        from fastapi.testclient import TestClient
        from sqlalchemy import delete
        from sqlalchemy.orm import sessionmaker

        from backend.app.api.plan import get_db_session
        from backend.app.db.models import (
            CompletedWorkoutRecord,
            PlannedWorkoutRecord,
        )
        from backend.app.db.session import engine
        from backend.app.main import app

        with engine.connect() as connection:
            outer_transaction = connection.begin()
            test_session_factory = sessionmaker(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )

            def override_db_session():
                with test_session_factory() as session:
                    yield session

            app.dependency_overrides[get_db_session] = override_db_session

            try:
                # Start with empty tables inside the transaction that will roll back.
                with test_session_factory() as session:
                    with session.begin():
                        session.execute(delete(CompletedWorkoutRecord))
                        session.execute(delete(PlannedWorkoutRecord))

                with TestClient(app) as client:
                    response = client.post(
                        "/completed-workouts",
                        json={
                            "workout_type": "hiit_legs",
                            "completed_at": "2026-11-12T07:00:00",
                            "rotation_type": "hiit_legs",
                            "first_candidate_start": "2026-11-13T07:00:00",
                            "calendar_events": [],
                            "push_uses_rings": False,
                        },
                    )

                    self.assertEqual(response.status_code, 200, response.text)
                    plan = response.json()
                    self.assertEqual(plan[0]["workout_type"], "push")

                    history_response = client.get("/completed-workouts")
                    self.assertEqual(history_response.status_code, 200)
                    self.assertEqual(
                        history_response.json()[0]["rotation_type"],
                        "hiit_legs",
                    )

                    saved_plan = client.get("/plan")
                    self.assertEqual(saved_plan.status_code, 200)
                    self.assertEqual(saved_plan.json(), plan)
            finally:
                app.dependency_overrides.pop(get_db_session, None)
                outer_transaction.rollback()


if __name__ == "__main__":
    unittest.main()