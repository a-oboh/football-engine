from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )

    start_date: Mapped[Date | None] = mapped_column(Date)

    end_date: Mapped[Date | None] = mapped_column(Date)