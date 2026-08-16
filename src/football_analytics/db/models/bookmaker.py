from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Bookmaker(Base):
    __tablename__ = "bookmakers"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )