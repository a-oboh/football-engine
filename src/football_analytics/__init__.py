"""Command-line entry point for football analytics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from football_analytics.analytics import predict_fixture
from football_analytics.db.repository import FootballRepository
from football_analytics.db.session import SessionLocal
from football_analytics.ingestion.pipeline import ingest


def main() -> None:
    """Run the ingestion or fixture-prediction command."""
    parser = argparse.ArgumentParser(prog="football-analytics")
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subcommands.add_parser("ingest", help="Ingest completed matches")
    ingest_parser.add_argument("path", type=Path)
    _add_competition_arguments(ingest_parser, multiple_seasons=False)

    predict_parser = subcommands.add_parser(
        "predict",
        help="Predict an upcoming fixture",
    )
    _add_competition_arguments(predict_parser, multiple_seasons=True)
    predict_parser.add_argument("--home-team", required=True)
    predict_parser.add_argument("--away-team", required=True)
    predict_parser.add_argument("--max-goals", type=int, default=10)

    arguments = parser.parse_args()
    if arguments.command == "ingest":
        result = ingest(
            arguments.path,
            competition_name=arguments.competition_name,
            competition_code=arguments.competition_code,
            season_name=arguments.season,
        )
        print(
            json.dumps(
                {
                    "competition_code": result.competition_code,
                    "season_name": result.season_name,
                    "created_matches": result.created_matches,
                    "existing_matches": result.existing_matches,
                    "ignored_incomplete_matches": result.ignored_incomplete_matches,
                },
                indent=2,
            )
        )
        return

    with SessionLocal() as session:
        prediction = predict_fixture(
            FootballRepository(session),
            competition_code=arguments.competition_code,
            season_names=arguments.season,
            home_team=arguments.home_team,
            away_team=arguments.away_team,
            max_goals=arguments.max_goals,
        )
    print(
        json.dumps(
            {
                "competition_code": prediction.competition_code,
                "home_team": prediction.home_team,
                "away_team": prediction.away_team,
                "expected_home_goals": prediction.expected_goals.home,
                "expected_away_goals": prediction.expected_goals.away,
                "home_win_probability": prediction.outcomes.home_win,
                "draw_probability": prediction.outcomes.draw,
                "away_win_probability": prediction.outcomes.away_win,
                "probability_mass": prediction.outcomes.total_probability_mass,
            },
            indent=2,
        )
    )


def _add_competition_arguments(
    parser: argparse.ArgumentParser,
    *,
    multiple_seasons: bool,
) -> None:
    parser.add_argument("--competition-code", required=True)
    if multiple_seasons:
        parser.add_argument(
            "--season",
            action="append",
            required=True,
            help="Repeat for each historical season to include",
        )
    else:
        parser.add_argument("--season", required=True)
        parser.add_argument("--competition-name", required=True)
