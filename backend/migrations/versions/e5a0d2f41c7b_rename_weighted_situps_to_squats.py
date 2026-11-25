"""rename weighted sit-ups variant to squats

Revision ID: e5a0d2f41c7b
Revises: d71f4ad8c2e1
Create Date: 2026-11-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5a0d2f41c7b"
down_revision: Union[str, Sequence[str], None] = "d71f4ad8c2e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_VARIANT = "legs_weighted_situps"
NEW_VARIANT = "legs_squats"
SQUAT_MUSCLES = ["quadriceps", "glutes", "hamstrings", "core"]


def _rename_saved_settings(rename_to_squats: bool) -> None:
    settings_table = sa.table(
        "planner_settings",
        sa.column("id", sa.Integer),
        sa.column("settings", sa.JSON),
    )
    connection = op.get_bind()

    for row in connection.execute(
        sa.select(settings_table.c.id, settings_table.c.settings)
    ).mappings():
        settings = row["settings"]
        changed = False

        for workout in settings.get("workouts", []):
            variants = workout.get("variants", [])
            variant_muscles = workout.get("variant_muscles", {})

            if rename_to_squats:
                if OLD_VARIANT in variants:
                    workout["variants"] = [
                        NEW_VARIANT if item == OLD_VARIANT else item
                        for item in variants
                    ]
                    changed = True
                if OLD_VARIANT in variant_muscles:
                    variant_muscles.pop(OLD_VARIANT)
                    variant_muscles[NEW_VARIANT] = SQUAT_MUSCLES
                    changed = True
            else:
                if NEW_VARIANT in variants:
                    workout["variants"] = [
                        OLD_VARIANT if item == NEW_VARIANT else item
                        for item in variants
                    ]
                    changed = True
                if NEW_VARIANT in variant_muscles:
                    variant_muscles.pop(NEW_VARIANT)
                    variant_muscles[OLD_VARIANT] = ["core"]
                    changed = True

        if changed:
            connection.execute(
                sa.update(settings_table)
                .where(settings_table.c.id == row["id"])
                .values(settings=settings)
            )


def upgrade() -> None:
    _rename_saved_settings(rename_to_squats=True)

    op.execute(
        sa.text(
            "UPDATE planned_workouts "
            "SET variant = :new_variant "
            "WHERE variant = :old_variant"
        ).bindparams(new_variant=NEW_VARIANT, old_variant=OLD_VARIANT)
    )

    completed_workouts = sa.table(
        "completed_workouts",
        sa.column("variant", sa.String(50)),
        sa.column("muscles_trained", sa.JSON),
    )
    op.get_bind().execute(
        sa.update(completed_workouts)
        .where(completed_workouts.c.variant == OLD_VARIANT)
        .values(variant=NEW_VARIANT, muscles_trained=SQUAT_MUSCLES)
    )


def downgrade() -> None:
    _rename_saved_settings(rename_to_squats=False)

    op.execute(
        sa.text(
            "UPDATE planned_workouts "
            "SET variant = :old_variant "
            "WHERE variant = :new_variant"
        ).bindparams(new_variant=NEW_VARIANT, old_variant=OLD_VARIANT)
    )

    completed_workouts = sa.table(
        "completed_workouts",
        sa.column("variant", sa.String(50)),
        sa.column("muscles_trained", sa.JSON),
    )
    op.get_bind().execute(
        sa.update(completed_workouts)
        .where(completed_workouts.c.variant == NEW_VARIANT)
        .values(variant=OLD_VARIANT, muscles_trained=["core"])
    )
