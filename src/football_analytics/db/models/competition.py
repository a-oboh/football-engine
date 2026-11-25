from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .season import Season


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    api_football_id: Mapped[int | None] = mapped_column(
        Integer,
        unique=True,
        nullable=True,
    )
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    seasons: Mapped[list[Season]] = relationship(back_populates="competition")
