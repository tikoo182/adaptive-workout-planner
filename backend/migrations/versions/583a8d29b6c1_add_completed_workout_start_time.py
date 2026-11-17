"""add completed workout start time

Revision ID: 583a8d29b6c1
Revises: a7794a44df66
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "583a8d29b6c1"
down_revision: Union[str, Sequence[str], None] = "8f59a2d7c1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "completed_workouts",
        sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.execute(
        "UPDATE completed_workouts "
        "SET started_at = completed_at - INTERVAL '30 minutes' "
        "WHERE started_at IS NULL"
    )
    op.alter_column("completed_workouts", "started_at", nullable=False)


def downgrade() -> None:
    op.drop_column("completed_workouts", "started_at")
