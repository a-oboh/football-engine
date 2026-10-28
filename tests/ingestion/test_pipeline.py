import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from football_analytics.db.base import Base
from football_analytics.db.repository import FootballRepository
from football_analytics.ingestion.pipeline import ingest_dataframe


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _matches() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": "01/08/2025",
                "HomeTeam": "A",
                "AwayTeam": "B",
                "FTHG": 2,
                "FTAG": 1,
                "FTR": "H",
            },
            {
                "Date": "08/08/2025",
                "HomeTeam": "B",
                "AwayTeam": "A",
                "FTHG": 0,
                "FTAG": 2,
                "FTR": "A",
            },
        ]
    )


def test_ingest_dataframe_accepts_minimal_completed_match_data(
    session: Session,
) -> None:
    result = ingest_dataframe(
        _matches(),
        session=session,
        competition_name="Premier League",
        competition_code="EPL",
        season_name="2025-26",
    )

    stored_matches = FootballRepository(session).get_completed_matches(
        competition_code="EPL",
        season_names=["2025-26"],
    )
    assert result.created_matches == 2
    assert result.existing_matches == 0
    assert [(match.home_team, match.away_team) for match in stored_matches] == [
        ("A", "B"),
        ("B", "A"),
    ]


def test_ingest_dataframe_skips_matches_already_stored(session: Session) -> None:
    kwargs = {
        "session": session,
        "competition_name": "Premier League",
        "competition_code": "EPL",
        "season_name": "2025-26",
    }
    ingest_dataframe(_matches(), **kwargs)

    result = ingest_dataframe(_matches(), **kwargs)

    stored_matches = FootballRepository(session).get_completed_matches(
        competition_code="EPL",
        season_names=["2025-26"],
    )
    assert result.created_matches == 0
    assert result.existing_matches == 2
    assert len(stored_matches) == 2


def test_ingest_dataframe_ignores_unplayed_fixtures(session: Session) -> None:
    matches = pd.concat(
        [
            _matches(),
            pd.DataFrame(
                [
                    {
                        "Date": "15/08/2025",
                        "HomeTeam": "A",
                        "AwayTeam": "B",
                        "FTHG": None,
                        "FTAG": None,
                        "FTR": None,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    result = ingest_dataframe(
        matches,
        session=session,
        competition_name="Premier League",
        competition_code="EPL",
        season_name="2025-26",
    )

    assert result.created_matches == 2
    assert result.ignored_incomplete_matches == 1


def test_ingest_dataframe_requires_explicit_season_name(session: Session) -> None:
    with pytest.raises(ValueError, match="season_name"):
        ingest_dataframe(
            _matches(),
            session=session,
            competition_name="Premier League",
            competition_code="EPL",
            season_name="",
        )
