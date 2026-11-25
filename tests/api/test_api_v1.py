from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from football_analytics.api.main import create_app
from football_analytics.api.schemas import (
    EvaluationRequest,
    PredictionRequest,
)
from football_analytics.db.base import Base
from football_analytics.db.repository import FootballRepository


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = FootballRepository(session)
        comp = repo.get_or_create_competition(
            name="Premier League",
            code="EPL",
            api_football_id=39,
            country="England",
        )
        s24 = repo.get_or_create_season(competition=comp, name="2024-25")
        s25 = repo.get_or_create_season(competition=comp, name="2025-26")

        arsenal = repo.get_or_create_team("Arsenal")
        chelsea = repo.get_or_create_team("Chelsea")
        liverpool = repo.get_or_create_team("Liverpool")

        m1 = repo.create_match(
            season_id=s24.id,
            home_team_id=arsenal.id,
            away_team_id=chelsea.id,
            referee_id=None,
            match_date=date(2024, 9, 1),
            kickoff_time=None,
            home_goals=3,
            away_goals=1,
            result="H",
            home_half_time_goals=2,
            away_half_time_goals=0,
            half_time_result="H",
        )
        repo.create_odds(m1.id, "PS", "1X2", "H", None, "closing", 1.75)
        repo.create_odds(m1.id, "PS", "1X2", "D", None, "closing", 3.80)
        repo.create_odds(m1.id, "PS", "1X2", "A", None, "closing", 4.60)

        repo.create_match(
            season_id=s24.id,
            home_team_id=chelsea.id,
            away_team_id=liverpool.id,
            referee_id=None,
            match_date=date(2024, 10, 1),
            kickoff_time=None,
            home_goals=1,
            away_goals=2,
            result="A",
            home_half_time_goals=1,
            away_half_time_goals=1,
            half_time_result="D",
        )

        m3 = repo.create_match(
            season_id=s25.id,
            home_team_id=liverpool.id,
            away_team_id=arsenal.id,
            referee_id=None,
            match_date=date(2025, 8, 20),
            kickoff_time=None,
            home_goals=2,
            away_goals=2,
            result="D",
            home_half_time_goals=1,
            away_half_time_goals=1,
            half_time_result="D",
        )
        repo.create_odds(m3.id, "B365", "1X2", "H", None, "closing", 2.20)
        repo.create_odds(m3.id, "B365", "1X2", "D", None, "closing", 3.40)
        repo.create_odds(m3.id, "B365", "1X2", "A", None, "closing", 3.20)

        m4 = repo.create_match(
            season_id=s25.id,
            home_team_id=chelsea.id,
            away_team_id=arsenal.id,
            referee_id=None,
            match_date=date(2025, 9, 15),
            kickoff_time=None,
            home_goals=0,
            away_goals=2,
            result="A",
            home_half_time_goals=0,
            away_half_time_goals=1,
            half_time_result="A",
        )
        repo.create_match_statistics(
            match_id=m4.id,
            home_shots=10,
            away_shots=15,
            home_shots_on_target=3,
            away_shots_on_target=7,
            home_fouls=12,
            away_fouls=9,
            home_corners=4,
            away_corners=8,
            home_yellow_cards=2,
            away_yellow_cards=1,
            home_red_cards=0,
            away_red_cards=0,
        )
        session.commit()
        yield session


def _find_endpoint(app, path: str, method: str):
    for route in app.routes:
        if getattr(route, "path", None) == path and method.upper() in getattr(
            route, "methods", set()
        ):
            return route.endpoint
    raise AssertionError(f"Route {method} {path} not found")


def test_overview_and_catalogue_endpoints(session: Session) -> None:
    app = create_app()
    overview_fn = _find_endpoint(app, "/api/v1/overview", "GET")
    teams_fn = _find_endpoint(app, "/api/v1/teams", "GET")

    overview = overview_fn(session=session)
    assert overview.total_matches == 4
    assert overview.total_competitions == 1
    assert overview.total_seasons == 2
    assert overview.total_teams == 3
    assert overview.competitions[0].code == "EPL"
    assert overview.active_model.id == "sequential-poisson-v1"

    teams = teams_fn(
        competition_code="EPL",
        season=["2024-25", "2025-26"],
        session=session,
    )
    assert teams.teams == ["Arsenal", "Chelsea", "Liverpool"]


def test_prediction_hypothetical_and_historical_modes_and_permalink(
    session: Session,
) -> None:
    app = create_app()
    create_pred_fn = _find_endpoint(app, "/api/v1/predictions", "POST")
    get_pred_fn = _find_endpoint(app, "/api/v1/predictions/{slug}", "GET")

    # 1. Hypothetical prediction
    hyp_req = PredictionRequest(
        competition_code="EPL",
        season_names=["2024-25", "2025-26"],
        mode="hypothetical",
        home_team="Arsenal",
        away_team="Chelsea",
        max_goals=8,
        save_snapshot=True,
    )
    hyp_resp = create_pred_fn(request=hyp_req, session=session)
    assert hyp_resp.slug is not None
    assert hyp_resp.slug.startswith("pred_")
    assert hyp_resp.explanation.total_league_matches == 4
    assert hyp_resp.score_matrix.max_goals == 8
    assert len(hyp_resp.top_scores) == 6

    # Retrieve by slug
    loaded = get_pred_fn(slug=hyp_resp.slug, session=session)
    assert loaded.slug == hyp_resp.slug
    assert loaded.expected_goals.home == pytest.approx(hyp_resp.expected_goals.home)

    # 2. Historical prediction on match_id=3 (2025-08-20) uses only prior matches
    hist_req = PredictionRequest(
        competition_code="EPL",
        season_names=["2024-25", "2025-26"],
        mode="historical",
        match_id=3,
        max_goals=8,
        save_snapshot=True,
    )
    hist_resp = create_pred_fn(request=hist_req, session=session)
    assert hist_resp.explanation.total_league_matches == 2
    assert hist_resp.historical_context is not None
    assert hist_resp.historical_context.actual_result == "D"
    assert hist_resp.bookmaker_comparison is not None
    assert hist_resp.bookmaker_comparison.source == "B365"


def test_walk_forward_evaluation_endpoint_and_bookmaker_benchmark(
    session: Session,
) -> None:
    app = create_app()
    create_eval_fn = _find_endpoint(app, "/api/v1/evaluations", "POST")
    get_eval_fn = _find_endpoint(app, "/api/v1/evaluations/{slug}", "GET")

    req = EvaluationRequest(
        competition_code="EPL",
        warmup_seasons=["2024-25"],
        evaluation_seasons=["2025-26"],
        max_goals=8,
        save_snapshot=True,
    )
    resp = create_eval_fn(request=req, session=session)
    assert resp.slug is not None
    assert resp.slug.startswith("eval_")
    assert resp.model_metrics.matches == 2
    assert resp.league_baseline_metrics.matches == 2
    assert resp.bookmaker_benchmark is not None
    assert resp.bookmaker_benchmark.evaluated_matches_with_odds == 1
    assert len(resp.calibration_curve) == 10
    assert len(resp.predictions) == 2

    loaded = get_eval_fn(slug=resp.slug, session=session)
    assert loaded.slug == resp.slug
    assert loaded.model_metrics.log_loss == pytest.approx(resp.model_metrics.log_loss)


def test_openapi_schema_generation_and_swagger_metadata() -> None:
    app = create_app()
    schema = app.openapi()

    assert schema["info"]["title"] == "Football Engine Lab API"
    assert schema["info"]["version"] == "1.0.0"

    tag_names = [tag["name"] for tag in schema.get("tags", [])]
    assert tag_names == [
        "System",
        "Catalogue",
        "Explorer",
        "Predictions",
        "Evaluations",
        "Live API Sync (api-football.com)",
    ]

    expected_paths = {
        "/api/v1/health",
        "/api/v1/models",
        "/api/v1/overview",
        "/api/v1/competitions",
        "/api/v1/teams",
        "/api/v1/matches",
        "/api/v1/matches/{match_id}",
        "/api/v1/fixtures/upcoming",
        "/api/v1/predictions",
        "/api/v1/predictions/{slug}",
        "/api/v1/evaluations",
        "/api/v1/evaluations/{slug}",
        "/api/v1/sync/status",
        "/api/v1/sync/api-football",
    }
    assert set(schema["paths"].keys()) == expected_paths

    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            assert operation.get("summary"), f"Missing summary on {method} {path}"
            assert operation.get("description"), (
                f"Missing description on {method} {path}"
            )
            assert operation.get("tags"), f"Missing tags on {method} {path}"

    components = schema["components"]["schemas"]
    assert "PredictionRequest" in components
    assert "PredictionResponse" in components
    assert "EvaluationRequest" in components
    assert "EvaluationResponse" in components
    assert "ErrorResponse" in components
