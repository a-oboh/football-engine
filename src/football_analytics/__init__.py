"""Command-line entry point for football analytics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from football_analytics.analytics import predict_fixture
from football_analytics.db.repository import FootballRepository
from football_analytics.db.session import SessionLocal
from football_analytics.ingestion.bulk import bulk_ingest
from football_analytics.ingestion.pipeline import ingest


def main() -> None:
    """Run the ingestion or fixture-prediction command."""
    parser = argparse.ArgumentParser(prog="football-analytics")
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subcommands.add_parser("ingest", help="Ingest completed matches")
    ingest_parser.add_argument("path", type=Path)
    _add_competition_arguments(ingest_parser, multiple_seasons=False)

    bulk_ingest_parser = subcommands.add_parser(
        "bulk-ingest",
        help="Ingest every season CSV in one directory",
    )
    bulk_ingest_parser.add_argument("directory", type=Path)
    bulk_ingest_parser.add_argument("--competition-name", required=True)
    bulk_ingest_parser.add_argument("--competition-code", required=True)

    predict_parser = subcommands.add_parser(
        "predict",
        help="Predict an upcoming fixture",
    )
    _add_competition_arguments(predict_parser, multiple_seasons=True)
    predict_parser.add_argument("--home-team", required=True)
    predict_parser.add_argument("--away-team", required=True)
    predict_parser.add_argument("--max-goals", type=int, default=10)

    serve_parser = subcommands.add_parser(
        "serve",
        help="Run the local prediction dashboard",
    )
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

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

    if arguments.command == "bulk-ingest":
        result = bulk_ingest(
            arguments.directory,
            competition_name=arguments.competition_name,
            competition_code=arguments.competition_code,
        )
        print(
            json.dumps(
                {
                    "created_matches": result.created_matches,
                    "existing_matches": result.existing_matches,
                    "ignored_incomplete_matches": result.ignored_incomplete_matches,
                    "files": [
                        {
                            "path": str(path),
                            "season_name": ingestion.season_name,
                            "created_matches": ingestion.created_matches,
                            "existing_matches": ingestion.existing_matches,
                        }
                        for path, ingestion in result.results
                    ],
                },
                indent=2,
            )
        )
        return

    if arguments.command == "serve":
        import uvicorn

        uvicorn.run(
            "football_analytics.web.app:create_app",
            factory=True,
            host=arguments.host,
            port=arguments.port,
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
                "predicted_full_time_score": {
                    "FTHG": prediction.full_time_score.home_goals,
                    "FTAG": prediction.full_time_score.away_goals,
                    "probability": prediction.full_time_score.probability,
                },
                "predicted_half_time_score": {
                    "HTHG": prediction.half_time.score.home_goals,
                    "HTAG": prediction.half_time.score.away_goals,
                    "expected_home_goals": prediction.half_time.expected_goals.home,
                    "expected_away_goals": prediction.half_time.expected_goals.away,
                    "probability": prediction.half_time.score.probability,
                },
                "home_win_probability": prediction.outcomes.home_win,
                "draw_probability": prediction.outcomes.draw,
                "away_win_probability": prediction.outcomes.away_win,
                "probability_mass": prediction.outcomes.total_probability_mass,
                "markets": {
                    "home_win": _market_json(prediction.markets.home_win),
                    "draw": _market_json(prediction.markets.draw),
                    "away_win": _market_json(prediction.markets.away_win),
                    "over_2_5_goals": _market_json(
                        prediction.markets.over_2_5_goals
                    ),
                    "under_2_5_goals": _market_json(
                        prediction.markets.under_2_5_goals
                    ),
                    "both_teams_to_score_yes": _market_json(
                        prediction.markets.both_teams_to_score_yes
                    ),
                    "both_teams_to_score_no": _market_json(
                        prediction.markets.both_teams_to_score_no
                    ),
                },
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


def _market_json(market) -> dict[str, float | None]:
    return {
        "probability": market.probability,
        "fair_odds": market.fair_odds,
    }
