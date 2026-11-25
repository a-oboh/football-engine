from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class ScheduledFixture(Base):
    """Upcoming or in-play fixture synced from api-football.com before completion."""

    __tablename__ = "scheduled_fixtures"

    id: Mapped[int] = mapped_column(primary_key=True)
    api_football_fixture_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
    )
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"),
        nullable=False,
    )
    home_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )
    away_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )
    referee_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    round_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    kickoff_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    status_short: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="NS",
    )
    completed_match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "home_team_id <> away_team_id",
            name="chk_scheduled_different_teams",
        ),
    )


class FixtureOdds(Base):
    """Pre-match bookmaker odds synced for an upcoming scheduled fixture."""

    __tablename__ = "fixture_odds"

    id: Mapped[int] = mapped_column(primary_key=True)
    fixture_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_fixtures.id", ondelete="CASCADE"),
        nullable=False,
    )
    bookmaker_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookmakers.id"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(30), nullable=False)
    selection: Mapped[str] = mapped_column(String(20), nullable=False)
    line: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)


class ApiSyncLog(Base):
    """Audit log for api-football.com synchronization runs and quota tracking."""

    __tablename__ = "api_sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="api-football",
    )
    endpoint: Mapped[str] = mapped_column(String(120), nullable=False)
    competition_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    season_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    requests_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    details: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
