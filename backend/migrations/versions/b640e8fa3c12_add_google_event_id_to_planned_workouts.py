"""add Google event ID to planned workouts

Revision ID: b640e8fa3c12
Revises: a7794a44df66
Create Date: 2026-11-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b640e8fa3c12"
down_revision: Union[str, Sequence[str], None] = "a7794a44df66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "planned_workouts",
        sa.Column("google_event_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("planned_workouts", "google_event_id")
