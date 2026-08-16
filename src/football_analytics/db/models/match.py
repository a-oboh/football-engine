from datetime import date, time

from sqlalchemy import CheckConstraint, Date, ForeignKey, SmallInteger, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)

    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id"),
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

    referee_id: Mapped[int | None] = mapped_column(
        ForeignKey("referees.id"),
    )

    match_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    kickoff_time: Mapped[time | None] = mapped_column(Time)

    home_goals: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    away_goals: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    result: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
    )

    home_half_time_goals: Mapped[int | None] = mapped_column(
        SmallInteger,
    )

    away_half_time_goals: Mapped[int | None] = mapped_column(
        SmallInteger,
    )

    half_time_result: Mapped[str | None] = mapped_column(
        String(1),
    )

    __table_args__ = (
        CheckConstraint(
            "home_team_id <> away_team_id",
            name="chk_different_teams",
        ),
        CheckConstraint(
            "result IN ('H', 'D', 'A')",
            name="chk_result",
        ),
        CheckConstraint(
            "home_goals >= 0 AND away_goals >= 0",
            name="chk_goals_non_negative",
        ),
    )