from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .competition import Competition


class Season(Base):
    __tablename__ = "seasons"

    __table_args__ = (
        UniqueConstraint(
            "competition_id",
            "name",
            name="uq_seasons_competition_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    start_date: Mapped[Date | None] = mapped_column(Date)

    end_date: Mapped[Date | None] = mapped_column(Date)

    competition: Mapped[Competition] = relationship(back_populates="seasons")
