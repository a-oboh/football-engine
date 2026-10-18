import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from football_analytics.db.base import Base
from football_analytics.db.models import Competition, Season
from football_analytics.db.repository import FootballRepository


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_repository_creates_and_retrieves_competitions(session: Session) -> None:
    repository = FootballRepository(session)

    created = repository.get_or_create_competition(
        name="Premier League",
        code="EPL",
    )
    retrieved = repository.get_or_create_competition(
        name="Premier League",
        code="EPL",
    )

    assert created.id == retrieved.id
    assert retrieved.code == "EPL"


def test_same_season_name_can_exist_in_different_competitions(session: Session) -> None:
    repository = FootballRepository(session)
    premier_league = repository.get_or_create_competition(
        name="Premier League",
        code="EPL",
    )
    la_liga = repository.get_or_create_competition(name="La Liga", code="LL")

    premier_league_season = repository.get_or_create_season(
        competition=premier_league,
        name="2025-26",
    )
    la_liga_season = repository.get_or_create_season(
        competition=la_liga,
        name="2025-26",
    )

    assert premier_league_season.id != la_liga_season.id
    assert premier_league_season.competition.code == "EPL"
    assert la_liga_season.competition.code == "LL"


def test_duplicate_season_name_is_rejected_within_one_competition(
    session: Session,
) -> None:
    competition = Competition(name="Premier League", code="EPL")
    session.add(competition)
    session.flush()
    session.add_all(
        [
            Season(competition=competition, name="2025-26"),
            Season(competition=competition, name="2025-26"),
        ]
    )

    with pytest.raises(IntegrityError):
        session.flush()
