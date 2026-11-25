from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, UniqueConstraint
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
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
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
    __table_args__ = (
        UniqueConstraint("healthkit_id", name="uq_completed_workouts_healthkit_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rotation_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    variant: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
    )
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
    healthkit_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    source_activity: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )
    muscles_trained: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    custom_name: Mapped[str | None] = mapped_column(String(80), nullable=True)


# Store the editable workout catalogue and scheduling preferences for this planner.
class PlannerSettingsRecord(Base):
    __tablename__ = "planner_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False)

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
