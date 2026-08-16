from sqlalchemy import ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class MatchStatistics(Base):
    __tablename__ = "match_statistics"

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"),
        primary_key=True,
    )

    home_shots: Mapped[int | None] = mapped_column(SmallInteger)
    away_shots: Mapped[int | None] = mapped_column(SmallInteger)

    home_shots_on_target: Mapped[int | None] = mapped_column(SmallInteger)
    away_shots_on_target: Mapped[int | None] = mapped_column(SmallInteger)

    home_fouls: Mapped[int | None] = mapped_column(SmallInteger)
    away_fouls: Mapped[int | None] = mapped_column(SmallInteger)

    home_corners: Mapped[int | None] = mapped_column(SmallInteger)
    away_corners: Mapped[int | None] = mapped_column(SmallInteger)

    home_yellow_cards: Mapped[int | None] = mapped_column(SmallInteger)
    away_yellow_cards: Mapped[int | None] = mapped_column(SmallInteger)

    home_red_cards: Mapped[int | None] = mapped_column(SmallInteger)
    away_red_cards: Mapped[int | None] = mapped_column(SmallInteger)