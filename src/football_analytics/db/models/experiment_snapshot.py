from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class SavedPrediction(Base):
    """Immutable snapshot of a generated prediction for permalink sharing."""

    __tablename__ = "saved_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(
        String(24),
        unique=True,
        index=True,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    competition_code: Mapped[str] = mapped_column(String(20), nullable=False)
    seasons_used: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    fixture_id: Mapped[int | None] = mapped_column(
        ForeignKey("scheduled_fixtures.id", ondelete="SET NULL"),
        nullable=True,
    )
    data_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class SavedEvaluation(Base):
    """Immutable snapshot of a walk-forward evaluation experiment for sharing."""

    __tablename__ = "saved_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(
        String(24),
        unique=True,
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="completed",
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    competition_code: Mapped[str] = mapped_column(String(20), nullable=False)
    warmup_seasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evaluation_seasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    data_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
