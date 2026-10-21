from datetime import date

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


def test_get_completed_matches_filters_seasons_and_orders_chronologically(
    session: Session,
) -> None:
    repository = FootballRepository(session)
    premier_league = repository.get_or_create_competition(
        name="Premier League",
        code="EPL",
    )
    la_liga = repository.get_or_create_competition(name="La Liga", code="LL")
    premier_league_2024 = repository.get_or_create_season(
        competition=premier_league,
        name="2024-25",
    )
    premier_league_2025 = repository.get_or_create_season(
        competition=premier_league,
        name="2025-26",
    )
    la_liga_2025 = repository.get_or_create_season(
        competition=la_liga,
        name="2025-26",
    )

    _create_match(
        repository,
        season_id=premier_league_2025.id,
        match_date=date(2025, 8, 8),
        home_team="B",
        away_team="A",
        home_goals=0,
        away_goals=2,
        result="A",
    )
    _create_match(
        repository,
        season_id=premier_league_2024.id,
        match_date=date(2024, 8, 16),
        home_team="A",
        away_team="B",
        home_goals=2,
        away_goals=1,
        result="H",
    )
    _create_match(
        repository,
        season_id=la_liga_2025.id,
        match_date=date(2025, 8, 1),
        home_team="C",
        away_team="D",
        home_goals=1,
        away_goals=1,
        result="D",
    )

    matches = repository.get_completed_matches(
        competition_code="EPL",
        season_names=["2024-25", "2025-26"],
    )

    assert [(match.season_name, match.match_date) for match in matches] == [
        ("2024-25", date(2024, 8, 16)),
        ("2025-26", date(2025, 8, 8)),
    ]
    assert matches[0].home_team == "A"
    assert matches[0].away_team == "B"
    assert matches[0].home_goals == 2
    assert matches[0].result == "H"


@pytest.mark.parametrize(
    ("competition_code", "season_names", "message"),
    [
        ("", None, "competition_code"),
        ("EPL", "2025-26", "season_names must be a sequence"),
        ("EPL", [""], "season_names must not contain blank"),
    ],
)
def test_get_completed_matches_validates_filters(
    session: Session,
    competition_code: str,
    season_names: object,
    message: str,
) -> None:
    repository = FootballRepository(session)

    with pytest.raises(ValueError, match=message):
        repository.get_completed_matches(
            competition_code=competition_code,
            season_names=season_names,
        )  # type: ignore[arg-type]


def _create_match(
    repository: FootballRepository,
    *,
    season_id: int,
    match_date: date,
    home_team: str,
    away_team: str,
    home_goals: int,
    away_goals: int,
    result: str,
) -> None:
    home = repository.get_or_create_team(home_team)
    away = repository.get_or_create_team(away_team)
    repository.create_match(
        season_id=season_id,
        home_team_id=home.id,
        away_team_id=away.id,
        referee_id=None,
        match_date=match_date,
        kickoff_time=None,
        home_goals=home_goals,
        away_goals=away_goals,
        result=result,
        home_half_time_goals=None,
        away_half_time_goals=None,
        half_time_result=None,
    )
