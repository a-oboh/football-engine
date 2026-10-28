from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from football_analytics.db.base import Base
from football_analytics.db.repository import FootballRepository
from football_analytics.ingestion.bulk import (
    bulk_ingest_directory,
    season_name_from_path,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _write_matches(path: Path, *, home_team: str, away_team: str) -> None:
    pd.DataFrame(
        [
            {
                "Date": "01/08/2025",
                "HomeTeam": home_team,
                "AwayTeam": away_team,
                "FTHG": 2,
                "FTAG": 1,
                "FTR": "H",
            }
        ]
    ).to_csv(path, index=False)


def test_bulk_ingest_directory_creates_one_season_per_csv(
    session: Session,
    tmp_path: Path,
) -> None:
    _write_matches(tmp_path / "epl_2024_25.csv", home_team="A", away_team="B")
    _write_matches(tmp_path / "epl_2025_26.csv", home_team="C", away_team="D")

    result = bulk_ingest_directory(
        tmp_path,
        session=session,
        competition_name="Premier League",
        competition_code="EPL",
    )

    matches = FootballRepository(session).get_completed_matches(
        competition_code="EPL",
        season_names=["2024-25", "2025-26"],
    )
    assert [ingestion.season_name for _, ingestion in result.results] == [
        "2024-25",
        "2025-26",
    ]
    assert result.created_matches == 2
    assert {match.season_name for match in matches} == {"2024-25", "2025-26"}


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("epl_2025_26.csv", "2025-26"),
        ("epl-2024-25.csv", "2024-25"),
        ("epl_2023_2024.csv", "2023-24"),
    ],
)
def test_season_name_from_path_supports_common_filename_formats(
    filename: str,
    expected: str,
) -> None:
    assert season_name_from_path(Path(filename)) == expected


def test_bulk_ingest_rejects_filename_without_a_season(
    session: Session,
    tmp_path: Path,
) -> None:
    _write_matches(tmp_path / "latest.csv", home_team="A", away_team="B")

    with pytest.raises(ValueError, match="Could not determine season"):
        bulk_ingest_directory(
            tmp_path,
            session=session,
            competition_name="Premier League",
            competition_code="EPL",
        )
