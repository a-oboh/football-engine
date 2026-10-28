"""Ingest completed football results into the canonical database."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from football_analytics.db.repository import FootballRepository
from football_analytics.db.session import SessionLocal

from .cleaner import clean
from .odds_transformer import transform_odds
from .reader import read_csv
from .transformer import (
    extract_referees,
    extract_teams,
    transform_match,
    transform_match_statistics,
)
from .validator import validate, validate_columns

_STATISTIC_COLUMNS = {
    "HS",
    "AS",
    "HST",
    "AST",
    "HF",
    "AF",
    "HC",
    "AC",
    "HY",
    "AY",
    "HR",
    "AR",
}


@dataclass(frozen=True)
class IngestionResult:
    competition_code: str
    season_name: str
    created_matches: int
    existing_matches: int
    ignored_incomplete_matches: int


def ingest(
    path: Path,
    *,
    competition_name: str,
    competition_code: str,
    season_name: str,
) -> IngestionResult:
    """Read a completed-match CSV and persist its results."""
    dataframe = read_csv(path)
    with SessionLocal() as session:
        try:
            result = ingest_dataframe(
                dataframe,
                session=session,
                competition_name=competition_name,
                competition_code=competition_code,
                season_name=season_name,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
    return result


def ingest_dataframe(
    dataframe: pd.DataFrame,
    *,
    session: Session,
    competition_name: str,
    competition_code: str,
    season_name: str,
) -> IngestionResult:
    """Persist completed matches from a DataFrame into an existing session.

    The caller owns the transaction. Re-ingesting an existing match leaves it
    unchanged, allowing a refreshed current-season CSV to add only new results.
    """
    _validate_context(
        competition_name=competition_name,
        competition_code=competition_code,
        season_name=season_name,
    )
    validate_columns(dataframe)
    completed_frame = dataframe.dropna(subset=["FTHG", "FTAG", "FTR"])
    if completed_frame.empty:
        raise ValueError("Dataset contains no completed matches.")
    validate(completed_frame)
    matches_frame = clean(completed_frame)

    repository = FootballRepository(session)
    competition = repository.get_or_create_competition(
        name=competition_name,
        code=competition_code,
    )
    season = repository.get_or_create_season(
        competition=competition,
        name=season_name,
    )
    teams = {
        name: repository.get_or_create_team(name)
        for name in extract_teams(matches_frame)
    }
    referees = {
        name: repository.get_or_create_referee(name)
        for name in extract_referees(matches_frame)
    }
    has_statistics = _STATISTIC_COLUMNS.issubset(matches_frame.columns)
    created_matches = 0
    existing_matches = 0

    for _, row in matches_frame.iterrows():
        match_data = transform_match(row)
        home_team = teams[match_data.pop("home_team_name")]
        away_team = teams[match_data.pop("away_team_name")]
        referee_name = match_data.pop("referee_name")
        referee = referees.get(referee_name)
        match, created = repository.get_or_create_match(
            season_id=season.id,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            referee_id=referee.id if referee is not None else None,
            **match_data,
        )
        if not created:
            existing_matches += 1
            continue

        created_matches += 1
        if has_statistics:
            repository.create_match_statistics(
                match_id=match.id,
                **transform_match_statistics(row),
            )
        for odd in transform_odds(row):
            repository.create_odds(match_id=match.id, **odd)

    return IngestionResult(
        competition_code=competition.code,
        season_name=season.name,
        created_matches=created_matches,
        existing_matches=existing_matches,
        ignored_incomplete_matches=len(dataframe) - len(completed_frame),
    )


def _validate_context(
    *,
    competition_name: str,
    competition_code: str,
    season_name: str,
) -> None:
    if not competition_name.strip():
        raise ValueError("competition_name must not be blank")
    if not competition_code.strip():
        raise ValueError("competition_code must not be blank")
    if not season_name.strip():
        raise ValueError("season_name must not be blank")
