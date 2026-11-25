from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class TeamAlias(Base):
    """Maps alternative team names (e.g. CSV vs API-Football) to canonical Team IDs."""

    __tablename__ = "team_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="api_football",
    )
