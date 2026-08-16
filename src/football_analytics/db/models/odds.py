from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Odds(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(primary_key=True)

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )

    bookmaker_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookmakers.id"),
    )

    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    source_name: Mapped[str] = mapped_column(
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
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )

    snapshot: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CLOSE",
    )