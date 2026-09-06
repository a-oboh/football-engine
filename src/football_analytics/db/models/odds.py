from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from football_analytics.db.base import Base


class Odds(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(primary_key=True)

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )

    bookmaker_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookmakers.id"),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    market: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    selection: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    line: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    phase: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )