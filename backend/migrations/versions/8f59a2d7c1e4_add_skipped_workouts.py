"""add skipped workouts for calendar rest days

Revision ID: 8f59a2d7c1e4
Revises: 72e8941cab36
Create Date: 2026-11-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f59a2d7c1e4"
down_revision: Union[str, Sequence[str], None] = "72e8941cab36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skipped_workouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workout_type", sa.String(length=32), nullable=False),
        sa.Column("rotation_type", sa.String(length=32), nullable=False),
        sa.Column("skipped_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("google_event_id", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_event_id"),
    )


def downgrade() -> None:
    op.drop_table("skipped_workouts")
