from sqlalchemy.orm import Session


class FootballRepository:
    def __init__(self, session: Session):
        self.session = session