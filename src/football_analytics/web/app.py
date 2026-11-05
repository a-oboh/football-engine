"""FastAPI application exposing a narrow public prediction surface."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from football_analytics.analytics import FixturePrediction, predict_fixture
from football_analytics.db.repository import FootballRepository
from football_analytics.db.session import SessionLocal

_STATIC_DIRECTORY = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create the dashboard app without exposing engine implementation details."""
    app = FastAPI(title="Football Quant", docs_url=None, redoc_url=None)
    app.mount("/assets", StaticFiles(directory=_STATIC_DIRECTORY), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIRECTORY / "index.html")

    @app.get("/api/competitions")
    def competitions() -> list[dict[str, object]]:
        try:
            with SessionLocal() as session:
                catalogue = FootballRepository(session).get_prediction_competitions()
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=503,
                detail="Prediction data is temporarily unavailable",
            ) from error

        return [
            {"code": item.code, "name": item.name, "seasons": item.seasons}
            for item in catalogue
        ]

    @app.get("/api/teams")
    def teams(
        competition_code: str,
        season: list[str] = Query(min_length=1),
    ) -> dict[str, object]:
        try:
            with SessionLocal() as session:
                team_names = FootballRepository(session).get_team_names(
                    competition_code=competition_code,
                    season_names=season,
                )
        except (SQLAlchemyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"teams": team_names}

    @app.get("/api/prediction")
    def prediction(
        competition_code: str,
        season: list[str] = Query(min_length=1),
        home_team: str = "",
        away_team: str = "",
    ) -> dict[str, object]:
        try:
            with SessionLocal() as session:
                forecast = predict_fixture(
                    FootballRepository(session),
                    competition_code=competition_code,
                    season_names=season,
                    home_team=home_team,
                    away_team=away_team,
                )
        except (SQLAlchemyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return prediction_json(forecast)

    return app


def prediction_json(prediction: FixturePrediction) -> dict[str, object]:
    """Return only presentation-ready forecast data for the public dashboard."""
    return {
        "fixture": {
            "competition_code": prediction.competition_code,
            "home_team": prediction.home_team,
            "away_team": prediction.away_team,
        },
        "expected_goals": {
            "home": prediction.expected_goals.home,
            "away": prediction.expected_goals.away,
        },
        "full_time": _score_json(prediction.full_time_score.home_goals,
                                  prediction.full_time_score.away_goals,
                                  prediction.full_time_score.probability),
        "half_time": {
            **_score_json(
                prediction.half_time.score.home_goals,
                prediction.half_time.score.away_goals,
                prediction.half_time.score.probability,
            ),
            "expected_home_goals": prediction.half_time.expected_goals.home,
            "expected_away_goals": prediction.half_time.expected_goals.away,
        },
        "markets": {
            "home_win": _market_json(prediction.markets.home_win),
            "draw": _market_json(prediction.markets.draw),
            "away_win": _market_json(prediction.markets.away_win),
            "over_2_5_goals": _market_json(prediction.markets.over_2_5_goals),
            "under_2_5_goals": _market_json(prediction.markets.under_2_5_goals),
            "btts_yes": _market_json(prediction.markets.both_teams_to_score_yes),
            "btts_no": _market_json(prediction.markets.both_teams_to_score_no),
        },
        "probability_mass": prediction.outcomes.total_probability_mass,
    }


def _score_json(home_goals: int, away_goals: int, probability: float) -> dict[str, object]:
    return {
        "home_goals": home_goals,
        "away_goals": away_goals,
        "probability": probability,
    }


def _market_json(market) -> dict[str, float | None]:
    return {"probability": market.probability, "fair_odds": market.fair_odds}
