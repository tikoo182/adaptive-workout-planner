"""add Google Calendar event references

Revision ID: 72e8941cab36
Revises: b640e8fa3c12
Create Date: 2026-11-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "72e8941cab36"
down_revision: Union[str, Sequence[str], None] = "b640e8fa3c12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "planned_workouts",
        sa.Column("google_calendar_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "completed_workouts",
        sa.Column("google_event_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "completed_workouts",
        sa.Column("google_calendar_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("completed_workouts", "google_calendar_id")
    op.drop_column("completed_workouts", "google_event_id")
    op.drop_column("planned_workouts", "google_calendar_id")
