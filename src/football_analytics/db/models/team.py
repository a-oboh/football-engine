from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    api_football_id: Mapped[int | None] = mapped_column(
        Integer,
        unique=True,
        nullable=True,
    )

    short_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
