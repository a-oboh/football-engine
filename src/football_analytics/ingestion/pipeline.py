from football_analytics.ingestion.odds_transformer import transform_odds
from football_analytics.db.repository import FootballRepository
from football_analytics.db.session import SessionLocal
from pathlib import Path

from .cleaner import clean
from .profiler import profile
from .reader import read_csv
from .transformer import (
    extract_referees,
    extract_season,
    extract_teams,
    transform_match,
    transform_match_statistics,
)
from .validator import validate


def ingest(path: Path):
    df = read_csv(path)

    validate(df)
    profile(df)

    df = clean(df)

    season_name = extract_season(df)
    team_names = extract_teams(df)
    referee_names = extract_referees(df)

    matches = [transform_match(row) for _, row in df.iterrows()]

    statistics = [transform_match_statistics(row) for _, row in df.iterrows()]
    odds = [transform_odds(row) for _, row in df.iterrows()]

    with SessionLocal() as session:
        repository = FootballRepository(session)

        try:
            # Reference entities
            season = repository.get_or_create_season(season_name)

            teams = {name: repository.get_or_create_team(name) for name in team_names}

            referees = {
                name: repository.get_or_create_referee(name) for name in referee_names
            }

            # Matches + statistics
            for match_data, stats_data, match_odds in zip(matches, statistics, odds):
                home_team = teams[match_data["home_team_name"]]
                away_team = teams[match_data["away_team_name"]]

                referee = referees.get(match_data["referee_name"])

                match = repository.create_match(
                    season_id=season.id,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    referee_id=referee.id if referee else None,
                    **{
                        key: value
                        for key, value in match_data.items()
                        if key
                        not in {
                            "home_team_name",
                            "away_team_name",
                            "referee_name",
                        }
                    },
                )

                repository.create_match_statistics(
                    match_id=match.id,
                    **stats_data,
                )

            session.commit()

        except Exception:
            session.rollback()
            raise
