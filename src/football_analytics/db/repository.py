from sqlalchemy.orm import Session
from sqlalchemy import select

from .models.season import Season


class FootballRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_season(self, name: str) -> Season:
        stmt = select(Season).where(Season.name == name)

        season = self.session.scalar(stmt)

        if season is None:
            season = Season(name=name)
            self.session.add(season)
            self.session.flush()

        return season

    def 
