from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
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
    google_event_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    google_calendar_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

# Database record for a completed workout.
class CompletedWorkoutRecord(Base):
    __tablename__ = "completed_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rotation_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
    )
    google_event_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    google_calendar_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

# Database record for a workout cancelled from Google Calendar.
class SkippedWorkoutRecord(Base):
    __tablename__ = "skipped_workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rotation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    skipped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
    )
    google_event_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )


# Store the connected Google account's calendar settings.
class GoogleCalendarConnectionRecord(Base):
    __tablename__ = "google_calendar_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    target_calendar_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )