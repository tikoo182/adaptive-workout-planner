"""store configurable workouts and completed-workout muscles

Revision ID: d71f4ad8c2e1
Revises: 583a8d29b6c1
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d71f4ad8c2e1"
down_revision: Union[str, Sequence[str], None] = "583a8d29b6c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "planned_workouts",
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
    )
    op.add_column(
        "completed_workouts",
        sa.Column("muscles_trained", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("completed_workouts", sa.Column("custom_name", sa.String(length=80), nullable=True))
    op.create_table(
        "planner_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("planner_settings")
    op.drop_column("completed_workouts", "custom_name")
    op.drop_column("completed_workouts", "muscles_trained")
    op.drop_column("planned_workouts", "duration_minutes")
