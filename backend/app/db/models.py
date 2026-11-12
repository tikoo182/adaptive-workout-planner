from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Database record for a planned workout.
class PlannedWorkoutRecord(Base):
    __tablename__ = "planned_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rotation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
    )
    uses_rings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

# Database record for a completed workout.
class CompletedWorkoutRecord(Base):
    __tablename__ = "completed_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_type: Mapped[str] = mapped_column(String(32), nullable=False)
    variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
    )