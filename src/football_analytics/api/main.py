"""FastAPI application for the Football Engine Lab (/api/v1)."""

from __future__ import annotations

import math
import os
from datetime import UTC, date, datetime
from typing import Annotated, Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from football_analytics.analytics import (
    FixturePrediction,
    OutcomeEvaluation,
    compute_calibration_curve,
    compute_outcome_frequencies,
    evaluate_naive_league_baseline,
    evaluate_outcome_probabilities,
    predict_fixture,
    run_poisson_experiment,
)
from football_analytics.db.repository import FootballRepository, Match1X2Odds
from football_analytics.ingestion.api_football import (
    DEFAULT_API_FOOTBALL_LEAGUES,
    ApiFootballClient,
    ApiFootballError,
    sync_competition_season,
)

from .dependencies import get_db_session
from .schemas import (
    ApiFootballSyncRequest,
    ApiFootballSyncResponse,
    BettingMarketsSchema,
    Bookmaker1X2ComparisonSchema,
    BookmakerEvaluationBenchmarkSchema,
    CalibrationBinSchema,
    CompetitionItemResponse,
    ErrorResponse,
    EvaluatedMatchPredictionSchema,
    EvaluationRequest,
    EvaluationResponse,
    ExpectedGoalsSchema,
    HalfTimePredictionSchema,
    HealthResponse,
    HistoricalMatchContextSchema,
    MarketSelectionSchema,
    MatchDetailResponse,
    MatchSummaryResponse,
    MatchupExplanationSchema,
    ModelMetadataResponse,
    OutcomeFrequencySummarySchema,
    OutcomeMetricsSchema,
    OutcomeProbabilitiesSchema,
    OverviewResponse,
    PaginatedMatchesResponse,
    PredictedScoreSchema,
    PredictionRequest,
    PredictionResponse,
    ScheduledFixtureResponse,
    ScoreMatrixSchema,
    SeasonMetricsItemSchema,
    SyncLogItemSchema,
    SyncStatusResponse,
    TeamsResponse,
    TeamVenueStrengthSchema,
)

MODEL_ID = "sequential-poisson-v1"

# Defined at module scope so `from __future__ import annotations` can resolve
# `DbSessionDep` when FastAPI/Pydantic builds the OpenAPI schema for `/openapi.json`.
DbSessionDep = Annotated[Session, Depends(get_db_session)]

OPENAPI_TAGS = [
    {
        "name": "System",
        "description": (
            "Service health, database connectivity, and active model status."
        ),
    },
    {
        "name": "Catalogue",
        "description": (
            "Discover available forecasting models, dataset corpus summary, "
            "competitions, seasons, and canonical team lists."
        ),
    },
    {
        "name": "Explorer",
        "description": (
            "Browse and filter historical completed matches, full-time team "
            "statistics, bookmaker odds quotes, and upcoming scheduled fixtures."
        ),
    },
    {
        "name": "Predictions",
        "description": (
            "Generate and retrieve explainable Sequential Poisson match predictions "
            "across `hypothetical`, `historical` (walk-forward replay), and "
            "`upcoming` modes."
        ),
    },
    {
        "name": "Evaluations",
        "description": (
            "Run and retrieve chronological walk-forward backtest evaluations with "
            "log-loss, Brier score, 10-bin calibration curves, and bookmaker "
            "benchmarks."
        ),
    },
    {
        "name": "Live API Sync (api-football.com)",
        "description": (
            "Inspect live synchronization status, supported league mappings, and "
            "trigger fixture/odds ingestion from api-football.com (v3)."
        ),
    },
]


def get_active_model_metadata() -> ModelMetadataResponse:
    return ModelMetadataResponse(
        id=MODEL_ID,
        name="Sequential Independent Poisson Baseline",
        version="1.0.0",
        family="Poisson / Venue-Conditioned Rate Multiplier",
        description=(
            "Estimates full-time and calibrated half-time expected goals strictly "
            "from chronological prior match results, decomposing scoring rates into "
            "a dynamic league venue baseline, home/away attacking strength, and "
            "home/away defensive weakness."
        ),
        parameters={
            "initial_home_goals": 1.5,
            "initial_away_goals": 1.2,
            "default_max_goals": 10,
            "neutral_strength_multiplier": 1.0,
        },
        assumptions=[
            (
                "Full-time home and away goal counts follow independent Poisson "
                "distributions conditional on expected goals (λ_home, λ_away)."
            ),
            (
                "Venue context is preserved: home attack/defense is estimated "
                "strictly from prior home matches, and away attack/defense strictly "
                "from prior away matches."
            ),
            (
                "Teams without prior venue history in the selected window default "
                "to a neutral multiplier of 1.0 until their first venue result is "
                "recorded."
            ),
            (
                "Half-time expected goals scale full-time expectations by the "
                "empirically observed share of goals scored before half-time in the "
                "training corpus."
            ),
            (
                "Score matrices are evaluated on a finite grid [0..max_goals] "
                "without artificial tail renormalization; retained probability mass "
                "is explicitly reported."
            ),
        ],
        limitations=[
            (
                "Conditional independence under-represents low-score draws "
                "(0–0, 1–1) compared to bivariate extensions such as Dixon–Coles."
            ),
            (
                "All prior matches in the selected window receive equal weight "
                "(no exponential time-decay weighting yet)."
            ),
            (
                "Early-season predictions without warm-up seasons rely on small "
                "sample sizes and can exhibit higher variance."
            ),
            (
                "Does not incorporate player-level lineups, injuries, red-card "
                "suspensions, or shot-level xG."
            ),
            (
                "This model is a transparent statistical baseline for quantitative "
                "research, not a calibrated market-beating betting system."
            ),
        ],
        data_leakage_policy=(
            "Strict chronological ordering: when predicting a historical match or "
            "running a walk-forward evaluation, only matches completed strictly "
            "prior to the target fixture are recorded into the model state."
        ),
    )


def create_app() -> FastAPI:
    """Create the FastAPI application serving /api/v1 endpoints."""
    app = FastAPI(
        title="Football Engine Lab API",
        version="1.0.0",
        summary=(
            "Quantitative football match analytics, explainable Poisson "
            "forecasting, and walk-forward backtesting API."
        ),
        description=(
            "REST API (`/api/v1`) for exploring historical football match data, "
            "generating explainable **Sequential Independent Poisson** predictions, "
            "running chronological walk-forward backtests against bookmaker "
            "benchmarks, and synchronizing live fixtures and odds from "
            "`api-football.com`."
        ),
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    cors_origins_env = os.getenv("CORS_ORIGINS", "")
    allowed_origins = (
        [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
        if cors_origins_env
        else [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(
        "/api/v1/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Check service and database health",
        response_description=(
            "Current health status of the API server and database connection."
        ),
    )
    def health(session: DbSessionDep) -> HealthResponse:
        """Verify API liveness, SQL database connectivity, and provider setup."""
        db_status: Literal["connected", "unavailable"] = "connected"
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db_status = "unavailable"
        return HealthResponse(
            status="ok" if db_status == "connected" else "degraded",
            database=db_status,
            model_version=MODEL_ID,
            api_football_configured=bool(os.getenv("API_FOOTBALL_KEY", "").strip()),
            timestamp=datetime.now(UTC),
        )

    @app.get(
        "/api/v1/models",
        response_model=list[ModelMetadataResponse],
        tags=["Catalogue"],
        summary="List available forecasting models",
        response_description=(
            "List of registered forecasting models and their specifications."
        ),
    )
    def list_models() -> list[ModelMetadataResponse]:
        """Return metadata, hyperparameters, assumptions, limitations, and
        data-leakage policy for all registered forecasting models.
        """
        return [get_active_model_metadata()]

    @app.get(
        "/api/v1/overview",
        response_model=OverviewResponse,
        tags=["Catalogue"],
        summary="Get dataset corpus overview and active model metadata",
        response_description=(
            "Aggregate counts across matches, competitions, seasons, teams, and odds."
        ),
        responses={
            503: {
                "model": ErrorResponse,
                "description": "Database is temporarily unavailable.",
            }
        },
    )
    def overview(session: DbSessionDep) -> OverviewResponse:
        """Return summary statistics of the ingested match database,
        available competitions/seasons, and active model specification.
        """
        try:
            stats = FootballRepository(session).get_overview_stats()
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=503,
                detail="Database is temporarily unavailable",
            ) from error

        return OverviewResponse(
            total_matches=int(stats["total_matches"]),  # type: ignore[arg-type]
            total_competitions=int(stats["total_competitions"]),  # type: ignore[arg-type]
            total_seasons=int(stats["total_seasons"]),  # type: ignore[arg-type]
            total_teams=int(stats["total_teams"]),  # type: ignore[arg-type]
            total_odds=int(stats["total_odds"]),  # type: ignore[arg-type]
            upcoming_fixtures=int(stats["upcoming_fixtures"]),  # type: ignore[arg-type]
            earliest_match_date=stats["earliest_match_date"],  # type: ignore[arg-type]
            latest_match_date=stats["latest_match_date"],  # type: ignore[arg-type]
            competitions=[
                CompetitionItemResponse.model_validate(comp)
                for comp in stats["competitions"]  # type: ignore[union-attr]
            ],
            active_model=get_active_model_metadata(),
            api_football_configured=bool(os.getenv("API_FOOTBALL_KEY", "").strip()),
        )

    @app.get(
        "/api/v1/competitions",
        response_model=list[CompetitionItemResponse],
        tags=["Catalogue"],
        summary="List competitions and seasons available for prediction",
        response_description=(
            "Catalogue of competitions with their ingested seasons and match counts."
        ),
        responses={
            503: {
                "model": ErrorResponse,
                "description": "Prediction catalogue is temporarily unavailable.",
            }
        },
    )
    def list_competitions(
        session: DbSessionDep,
    ) -> list[CompetitionItemResponse]:
        """List all competitions in the database along with their available
        season identifiers, completed match counts, and league mappings.
        """
        try:
            catalogue = FootballRepository(session).get_prediction_competitions()
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=503,
                detail="Prediction catalogue is temporarily unavailable",
            ) from error

        return [
            CompetitionItemResponse(
                code=item.code,
                name=item.name,
                seasons=list(item.seasons),
                match_count=item.match_count,
                api_football_id=item.api_football_id,
                country=item.country,
                logo_url=item.logo_url,
            )
            for item in catalogue
        ]

    @app.get(
        "/api/v1/teams",
        response_model=TeamsResponse,
        tags=["Catalogue"],
        summary="List teams in a competition and season window",
        response_description="Alphabetically sorted list of canonical team names.",
        responses={
            400: {
                "model": ErrorResponse,
                "description": "Invalid competition code or season names.",
            }
        },
    )
    def list_teams(
        competition_code: Annotated[
            str,
            Query(
                min_length=1,
                description="Competition code to query (e.g. 'EPL').",
                examples=["EPL"],
            ),
        ],
        season: Annotated[
            list[str],
            Query(
                min_length=1,
                description=(
                    "One or more season identifiers to collect teams from "
                    "(repeat `season=...` for multiple seasons)."
                ),
                examples=[["2024-25", "2025-26"]],
            ),
        ],
        session: DbSessionDep,
    ) -> TeamsResponse:
        """Return all canonical team names that have appeared in completed
        matches for the given `competition_code` and `season` window.
        """
        try:
            teams = FootballRepository(session).get_team_names(
                competition_code=competition_code,
                season_names=season,
            )
        except (SQLAlchemyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        return TeamsResponse(
            competition_code=competition_code,
            seasons=season,
            teams=teams,
        )

    @app.get(
        "/api/v1/matches",
        response_model=PaginatedMatchesResponse,
        tags=["Explorer"],
        summary="Search and paginate historical completed matches",
        response_description=(
            "Paginated list of completed historical matches matching the filters."
        ),
    )
    def list_matches(
        session: DbSessionDep,
        competition_code: Annotated[
            str | None,
            Query(
                description="Optional competition code filter (e.g. 'EPL').",
                examples=["EPL"],
            ),
        ] = None,
        season: Annotated[
            str | None,
            Query(
                description="Optional season name filter (e.g. '2024-25').",
                examples=["2024-25"],
            ),
        ] = None,
        team: Annotated[
            str | None,
            Query(
                description=(
                    "Optional substring or canonical team name filter "
                    "(matches either home or away team)."
                ),
                examples=["Arsenal"],
            ),
        ] = None,
        result: Annotated[
            Literal["H", "D", "A"] | None,
            Query(
                description=(
                    "Optional full-time 1X2 outcome filter "
                    "('H' = home win, 'D' = draw, 'A' = away win)."
                ),
            ),
        ] = None,
        date_from: Annotated[
            date | None,
            Query(
                description="Inclusive start date filter (YYYY-MM-DD).",
            ),
        ] = None,
        date_to: Annotated[
            date | None,
            Query(
                description="Inclusive end date filter (YYYY-MM-DD).",
            ),
        ] = None,
        page: Annotated[
            int,
            Query(
                ge=1,
                description="1-based page number.",
            ),
        ] = 1,
        page_size: Annotated[
            int,
            Query(
                ge=5,
                le=100,
                description="Number of matches per page (5 to 100).",
            ),
        ] = 25,
    ) -> PaginatedMatchesResponse:
        """Search completed matches with optional filters for competition,
        season, team name, full-time outcome, and date range.
        """
        offset = (page - 1) * page_size
        rows, total = FootballRepository(session).search_matches(
            competition_code=competition_code,
            season_name=season,
            team_name=team,
            result=result,
            date_from=date_from,
            date_to=date_to,
            limit=page_size,
            offset=offset,
        )
        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        return PaginatedMatchesResponse(
            items=[
                MatchSummaryResponse(
                    id=r.id,
                    competition_code=r.competition_code,
                    competition_name=r.competition_name,
                    season_name=r.season_name,
                    match_date=r.match_date,
                    kickoff_time=(
                        r.kickoff_time.strftime("%H:%M") if r.kickoff_time else None
                    ),
                    home_team=r.home_team,
                    away_team=r.away_team,
                    home_goals=r.home_goals,
                    away_goals=r.away_goals,
                    result=r.result,  # type: ignore[arg-type]
                    home_half_time_goals=r.home_half_time_goals,
                    away_half_time_goals=r.away_half_time_goals,
                    half_time_result=r.half_time_result,
                    referee_name=r.referee_name,
                    has_statistics=r.has_statistics,
                    odds_count=r.odds_count,
                )
                for r in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @app.get(
        "/api/v1/matches/{match_id}",
        response_model=MatchDetailResponse,
        tags=["Explorer"],
        summary="Get full match details, team statistics, and bookmaker odds",
        response_description=(
            "Detailed match record with optional team statistics and bookmaker odds."
        ),
        responses={
            404: {
                "model": ErrorResponse,
                "description": "Match with the specified ID was not found.",
            }
        },
    )
    def get_match(
        match_id: Annotated[
            int,
            Path(
                description="Internal database ID of the completed match.",
                examples=[1],
            ),
        ],
        session: DbSessionDep,
    ) -> MatchDetailResponse:
        """Retrieve a single completed match by ID, including half-time and
        full-time scorelines, referee, match statistics, and bookmaker odds.
        """
        detail = FootballRepository(session).get_match_detail(match_id)
        if detail is None:
            raise HTTPException(
                status_code=404,
                detail=f"Match {match_id} not found",
            )
        kickoff = detail.get("kickoff_time")
        detail["kickoff_time"] = (
            kickoff.strftime("%H:%M") if hasattr(kickoff, "strftime") else None
        )
        return MatchDetailResponse.model_validate(detail)

    @app.get(
        "/api/v1/fixtures/upcoming",
        response_model=list[ScheduledFixtureResponse],
        tags=["Explorer"],
        summary="List upcoming scheduled fixtures",
        response_description="Chronological list of upcoming unplayed fixtures.",
    )
    def list_upcoming_fixtures(
        session: DbSessionDep,
        competition_code: Annotated[
            str | None,
            Query(
                description="Optional competition code filter (e.g. 'EPL').",
                examples=["EPL"],
            ),
        ] = None,
        season: Annotated[
            str | None,
            Query(
                description="Optional season identifier filter (e.g. '2025-26').",
                examples=["2025-26"],
            ),
        ] = None,
        limit: Annotated[
            int,
            Query(
                ge=1,
                le=200,
                description=(
                    "Maximum number of scheduled fixtures to return (1 to 200)."
                ),
            ),
        ] = 50,
    ) -> list[ScheduledFixtureResponse]:
        """List upcoming unplayed fixtures synchronized from `api-football.com`,
        ordered by scheduled kickoff date.
        """
        rows = FootballRepository(session).list_scheduled_fixtures(
            competition_code=competition_code,
            season_name=season,
            include_completed=False,
            limit=limit,
        )
        return [
            ScheduledFixtureResponse(
                id=r.id,
                api_football_fixture_id=r.api_football_fixture_id,
                competition_code=r.competition_code,
                competition_name=r.competition_name,
                season_name=r.season_name,
                home_team=r.home_team,
                away_team=r.away_team,
                home_team_logo=r.home_team_logo,
                away_team_logo=r.away_team_logo,
                match_date=r.match_date,
                kickoff_time=(
                    r.kickoff_time.strftime("%H:%M") if r.kickoff_time else None
                ),
                venue_name=r.venue_name,
                round_name=r.round_name,
                referee_name=r.referee_name,
                status_short=r.status_short,
                completed_match_id=r.completed_match_id,
                last_synced_at=r.last_synced_at,
                odds_count=r.odds_count,
            )
            for r in rows
        ]

    @app.post(
        "/api/v1/predictions",
        response_model=PredictionResponse,
        tags=["Predictions"],
        summary="Generate an explainable Sequential Poisson fixture prediction",
        response_description=(
            "Full fixture forecast with expected goals, score matrix, fair odds, "
            "and strength decomposition."
        ),
        responses={
            400: {
                "model": ErrorResponse,
                "description": (
                    "Invalid model version, competition/season parameters, or "
                    "insufficient team history."
                ),
            },
            404: {
                "model": ErrorResponse,
                "description": (
                    "Referenced historical `match_id` or upcoming `fixture_id` "
                    "was not found."
                ),
            },
        },
    )
    def create_prediction(
        request: PredictionRequest,
        session: DbSessionDep,
    ) -> PredictionResponse:
        """Compute a fixture prediction using the Sequential Independent Poisson model.

        - **`hypothetical` mode**: Forecasts any `home_team` vs `away_team` matchup
          using all completed matches in `season_names` (or strictly prior to
          `as_of_date`).
        - **`historical` mode**: Replays a completed match (`match_id`) using only
          matches completed strictly prior to that fixture, returning the actual
          scoreline and closing bookmaker 1X2 odds alongside the forecast.
        - **`upcoming` mode**: Forecasts a scheduled fixture (`fixture_id`) and
          attaches pre-match bookmaker 1X2 odds when available.
        """
        if request.model_version != MODEL_ID:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported model_version '{request.model_version}'. "
                    f"Active model: {MODEL_ID}"
                ),
            )

        repo = FootballRepository(session)
        home_team = request.home_team
        away_team = request.away_team
        as_of_date = request.as_of_date
        historical_context: HistoricalMatchContextSchema | None = None
        bookmaker_comparison: Bookmaker1X2ComparisonSchema | None = None

        if request.mode == "historical" and request.match_id is not None:
            match_detail = repo.get_match_detail(request.match_id)
            if match_detail is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Historical match {request.match_id} not found",
                )
            home_team = str(match_detail["home_team"])
            away_team = str(match_detail["away_team"])
            as_of_date = match_detail["match_date"]  # type: ignore[assignment]
            historical_context = HistoricalMatchContextSchema(
                match_id=int(match_detail["id"]),  # type: ignore[arg-type]
                match_date=match_detail["match_date"],  # type: ignore[arg-type]
                season_name=str(match_detail["season_name"]),
                actual_home_goals=int(match_detail["home_goals"]),  # type: ignore[arg-type]
                actual_away_goals=int(match_detail["away_goals"]),  # type: ignore[arg-type]
                actual_result=str(match_detail["result"]),  # type: ignore[arg-type]
                actual_ht_home_goals=match_detail["home_half_time_goals"],  # type: ignore[arg-type]
                actual_ht_away_goals=match_detail["away_half_time_goals"],  # type: ignore[arg-type]
            )
            odds_map = repo.get_match_1x2_odds_map([request.match_id])
            if request.match_id in odds_map:
                bookmaker_comparison = _format_bookmaker_1x2(odds_map[request.match_id])

        elif request.mode == "upcoming" and request.fixture_id is not None:
            fixture_detail = repo.get_scheduled_fixture_detail(request.fixture_id)
            if fixture_detail is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Scheduled fixture {request.fixture_id} not found",
                )
            home_team = str(fixture_detail["home_team"])
            away_team = str(fixture_detail["away_team"])
            fixture_odds = fixture_detail.get("odds", [])
            if isinstance(fixture_odds, list):
                bm_1x2 = _extract_1x2_from_odds_list(fixture_odds)
                if bm_1x2 is not None:
                    bookmaker_comparison = _format_bookmaker_1x2(bm_1x2)

        assert home_team is not None and away_team is not None

        try:
            forecast = predict_fixture(
                repo,
                competition_code=request.competition_code,
                season_names=request.season_names,
                home_team=home_team,
                away_team=away_team,
                max_goals=request.max_goals,
                as_of_date=as_of_date,
                exclude_match_id=request.match_id,
                allow_neutral_teams=(request.mode in ("historical", "upcoming")),
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        snapshot_hash = repo.compute_data_snapshot_hash(
            competition_code=request.competition_code,
            season_names=request.season_names,
        )
        now = datetime.now(UTC)
        response_payload = _serialize_prediction_response(
            forecast=forecast,
            mode=request.mode,
            seasons_used=request.season_names,
            as_of_date=as_of_date,
            snapshot_hash=snapshot_hash,
            created_at=now,
            historical_context=historical_context,
            bookmaker_comparison=bookmaker_comparison,
        )

        if request.save_snapshot:
            saved = repo.save_prediction_snapshot(
                model_version=MODEL_ID,
                mode=request.mode,
                competition_code=request.competition_code,
                seasons_used=request.season_names,
                home_team=home_team,
                away_team=away_team,
                as_of_date=as_of_date,
                match_id=request.match_id,
                fixture_id=request.fixture_id,
                data_snapshot_hash=snapshot_hash,
                payload=response_payload.model_dump(mode="json"),
            )
            session.commit()
            response_payload.slug = saved.slug

        return response_payload

    @app.get(
        "/api/v1/predictions/{slug}",
        response_model=PredictionResponse,
        tags=["Predictions"],
        summary="Retrieve a saved prediction snapshot by permalink slug",
        response_description="Stored immutable prediction snapshot.",
        responses={
            404: {
                "model": ErrorResponse,
                "description": "Saved prediction slug was not found.",
            }
        },
    )
    def get_prediction_by_slug(
        slug: Annotated[
            str,
            Path(
                description=(
                    "Unique permalink slug returned when a prediction was "
                    "created with `save_snapshot=True`."
                ),
                examples=["pred_8f3a19c2b4"],
            ),
        ],
        session: DbSessionDep,
    ) -> PredictionResponse:
        """Load a previously persisted prediction snapshot by its permalink `slug`."""
        saved = FootballRepository(session).get_saved_prediction(slug)
        if saved is None:
            raise HTTPException(
                status_code=404,
                detail=f"Saved prediction '{slug}' not found",
            )
        payload = dict(saved.payload)
        payload["slug"] = saved.slug
        return PredictionResponse.model_validate(payload)

    @app.post(
        "/api/v1/evaluations",
        response_model=EvaluationResponse,
        tags=["Evaluations"],
        summary="Run a chronological walk-forward backtest evaluation",
        response_description=(
            "Complete walk-forward evaluation metrics, calibration curve, "
            "bookmaker benchmark, and match predictions."
        ),
        responses={
            400: {
                "model": ErrorResponse,
                "description": (
                    "Invalid model version, overlapping warmup/evaluation "
                    "seasons, or missing season data."
                ),
            }
        },
    )
    def create_evaluation(
        request: EvaluationRequest,
        session: DbSessionDep,
    ) -> EvaluationResponse:
        """Execute a strict chronological walk-forward backtest across
        `evaluation_seasons` after warming up on `warmup_seasons`.

        Computes log-loss, Brier score, top-1 accuracy, a 10-bin calibration curve,
        a naive rolling league baseline, and a head-to-head benchmark against
        bookmaker implied probabilities on all evaluated matches with 1X2 odds.
        """
        if request.model_version != MODEL_ID:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported model_version '{request.model_version}'. "
                    f"Active model: {MODEL_ID}"
                ),
            )

        repo = FootballRepository(session)
        try:
            experiment = run_poisson_experiment(
                repo,
                competition_code=request.competition_code,
                warmup_season_names=request.warmup_seasons,
                evaluation_season_names=request.evaluation_seasons,
                max_goals=request.max_goals,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        preds_df = experiment.predictions
        model_metrics = _to_metrics_schema(experiment.evaluation)
        baseline_eval = evaluate_naive_league_baseline(preds_df)
        baseline_metrics = _to_metrics_schema(baseline_eval)
        frequencies = compute_outcome_frequencies(preds_df)
        calibration = compute_calibration_curve(preds_df, num_bins=10)

        # Per-season breakdown
        season_breakdown: list[SeasonMetricsItemSchema] = []
        for season_name in request.evaluation_seasons:
            season_slice = preds_df.loc[preds_df["season_name"] == season_name]
            if not season_slice.empty:
                season_eval = evaluate_outcome_probabilities(season_slice)
                season_breakdown.append(
                    SeasonMetricsItemSchema(
                        season_name=season_name,
                        metrics=_to_metrics_schema(season_eval),
                    )
                )

        # Bookmaker odds benchmark on the exact same evaluated matches
        match_ids = [
            int(mid)
            for mid in preds_df["match_id"].dropna().tolist()
            if mid is not None
        ]
        odds_map = repo.get_match_1x2_odds_map(match_ids)
        bookmaker_benchmark = _build_bookmaker_benchmark(preds_df, odds_map)

        # Build match-level prediction list
        match_predictions: list[EvaluatedMatchPredictionSchema] = []
        for row in preds_df.itertuples(index=False):
            mass = float(row.probability_mass)
            p_h = float(row.home_win_probability) / mass
            p_d = float(row.draw_probability) / mass
            p_a = float(row.away_win_probability) / mass
            outcomes: tuple[Literal["H", "D", "A"], ...] = ("H", "D", "A")
            probs = (p_h, p_d, p_a)
            pred_res = outcomes[probs.index(max(probs))]
            mid = (
                int(row.match_id)
                if getattr(row, "match_id", None) is not None
                and not pd.isna(row.match_id)
                else None
            )
            bm = odds_map.get(mid) if mid is not None else None
            bm_probs = bm.implied_probabilities if bm is not None else None
            match_date_str = (
                row.match_date.strftime("%Y-%m-%d")
                if hasattr(row.match_date, "strftime")
                else str(row.match_date)[:10]
            )
            match_predictions.append(
                EvaluatedMatchPredictionSchema(
                    match_id=mid,
                    season_name=str(row.season_name),
                    match_date=match_date_str,
                    home_team=str(row.home_team),
                    away_team=str(row.away_team),
                    home_goals=int(row.home_goals),
                    away_goals=int(row.away_goals),
                    actual_result=str(row.result),  # type: ignore[arg-type]
                    expected_home_goals=float(row.expected_home_goals),
                    expected_away_goals=float(row.expected_away_goals),
                    home_win_probability=p_h,
                    draw_probability=p_d,
                    away_win_probability=p_a,
                    predicted_result=pred_res,
                    correct=(pred_res == str(row.result)),
                    bookmaker_source=bm.source if bm else None,
                    bookmaker_home_prob=bm_probs[0] if bm_probs else None,
                    bookmaker_draw_prob=bm_probs[1] if bm_probs else None,
                    bookmaker_away_prob=bm_probs[2] if bm_probs else None,
                )
            )

        all_seasons = list(request.warmup_seasons) + list(request.evaluation_seasons)
        snapshot_hash = repo.compute_data_snapshot_hash(
            competition_code=request.competition_code,
            season_names=all_seasons,
        )
        now = datetime.now(UTC)

        eval_response = EvaluationResponse(
            slug=None,
            status="completed",
            model_version=MODEL_ID,
            data_snapshot_hash=snapshot_hash,
            created_at=now,
            competition_code=request.competition_code,
            warmup_seasons=request.warmup_seasons,
            evaluation_seasons=request.evaluation_seasons,
            model_metrics=model_metrics,
            league_baseline_metrics=baseline_metrics,
            bookmaker_benchmark=bookmaker_benchmark,
            outcome_frequencies=OutcomeFrequencySummarySchema(
                predicted_home=frequencies.predicted_home,
                predicted_draw=frequencies.predicted_draw,
                predicted_away=frequencies.predicted_away,
                observed_home=frequencies.observed_home,
                observed_draw=frequencies.observed_draw,
                observed_away=frequencies.observed_away,
            ),
            calibration_curve=[
                CalibrationBinSchema(
                    bin_index=b.bin_index,
                    bin_lower=b.bin_lower,
                    bin_upper=b.bin_upper,
                    sample_count=b.sample_count,
                    mean_predicted_probability=b.mean_predicted_probability,
                    observed_frequency=b.observed_frequency,
                )
                for b in calibration
            ],
            season_breakdown=season_breakdown,
            predictions=match_predictions,
        )

        if request.save_snapshot:
            saved = repo.save_evaluation_snapshot(
                model_version=MODEL_ID,
                competition_code=request.competition_code,
                warmup_seasons=request.warmup_seasons,
                evaluation_seasons=request.evaluation_seasons,
                data_snapshot_hash=snapshot_hash,
                payload=eval_response.model_dump(mode="json"),
            )
            session.commit()
            eval_response.slug = saved.slug

        return eval_response

    @app.get(
        "/api/v1/evaluations/{slug}",
        response_model=EvaluationResponse,
        tags=["Evaluations"],
        summary="Retrieve a saved evaluation snapshot by permalink slug",
        response_description="Stored immutable walk-forward evaluation snapshot.",
        responses={
            404: {
                "model": ErrorResponse,
                "description": "Saved evaluation slug was not found.",
            }
        },
    )
    def get_evaluation_by_slug(
        slug: Annotated[
            str,
            Path(
                description=(
                    "Unique permalink slug returned when an evaluation was "
                    "created with `save_snapshot=True`."
                ),
                examples=["eval_9c4e12a8f0"],
            ),
        ],
        session: DbSessionDep,
    ) -> EvaluationResponse:
        """Load a previously persisted walk-forward evaluation report by `slug`."""
        saved = FootballRepository(session).get_saved_evaluation(slug)
        if saved is None:
            raise HTTPException(
                status_code=404,
                detail=f"Saved evaluation '{slug}' not found",
            )
        payload = dict(saved.payload)
        payload["slug"] = saved.slug
        return EvaluationResponse.model_validate(payload)

    @app.get(
        "/api/v1/sync/status",
        response_model=SyncStatusResponse,
        tags=["Live API Sync (api-football.com)"],
        summary=(
            "Get live sync configuration status, supported leagues, and audit logs"
        ),
        response_description=(
            "Configuration status, supported league mappings, and 10 most "
            "recent sync audit logs."
        ),
    )
    def get_sync_status(
        session: DbSessionDep,
    ) -> SyncStatusResponse:
        """Inspect whether `API_FOOTBALL_KEY` is configured, list built-in
        league ID mappings, and view recent synchronization audit logs.
        """
        logs = FootballRepository(session).list_sync_logs(limit=10)
        return SyncStatusResponse(
            api_football_configured=bool(os.getenv("API_FOOTBALL_KEY", "").strip()),
            supported_leagues=[
                {
                    "code": spec.code,
                    "name": spec.name,
                    "api_football_id": spec.api_football_id,
                    "country": spec.country,
                }
                for spec in DEFAULT_API_FOOTBALL_LEAGUES.values()
            ],
            recent_logs=[
                SyncLogItemSchema(
                    id=log.id,
                    provider=log.provider,
                    endpoint=log.endpoint,
                    competition_code=log.competition_code,
                    season_name=log.season_name,
                    status=log.status,
                    requests_remaining=log.requests_remaining,
                    records_processed=log.records_processed,
                    created_at=log.created_at,
                )
                for log in logs
            ],
        )

    @app.post(
        "/api/v1/sync/api-football",
        response_model=ApiFootballSyncResponse,
        tags=["Live API Sync (api-football.com)"],
        summary=(
            "Trigger live fixture, statistics, and odds synchronization from "
            "api-football.com"
        ),
        response_description=(
            "Summary of newly ingested completed matches, updated scheduled "
            "fixtures, and remaining API quota."
        ),
        responses={
            400: {
                "model": ErrorResponse,
                "description": (
                    "Missing `API_FOOTBALL_KEY`, unmapped competition code, or "
                    "upstream provider error."
                ),
            }
        },
    )
    def trigger_api_football_sync(
        request: ApiFootballSyncRequest,
        session: DbSessionDep,
    ) -> ApiFootballSyncResponse:
        """Synchronize completed matches (`FT`), upcoming scheduled fixtures
        (`NS`/`TBD`), and optional match statistics or pre-match bookmaker
        1X2 odds from `api-football.com` (v3).
        """
        try:
            client = ApiFootballClient()
            summary = sync_competition_season(
                session,
                client,
                competition_code=request.competition_code,
                season_name=request.season_name,
                include_odds=request.include_odds,
                include_statistics_for_new=request.include_statistics_for_new,
            )
            session.commit()
        except (ApiFootballError, ValueError) as error:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(error)) from error

        return ApiFootballSyncResponse(
            competition_code=summary.competition_code,
            season_name=summary.season_name,
            api_football_league_id=summary.api_football_league_id,
            api_football_season_year=summary.api_football_season_year,
            created_completed_matches=summary.created_completed_matches,
            existing_completed_matches=summary.existing_completed_matches,
            upserted_scheduled_fixtures=summary.upserted_scheduled_fixtures,
            synced_odds_records=summary.synced_odds_records,
            requests_remaining=summary.requests_remaining,
        )

    return app


def _serialize_prediction_response(
    *,
    forecast: FixturePrediction,
    mode: Literal["hypothetical", "historical", "upcoming"],
    seasons_used: list[str],
    as_of_date: date | None,
    snapshot_hash: str,
    created_at: datetime,
    historical_context: HistoricalMatchContextSchema | None,
    bookmaker_comparison: Bookmaker1X2ComparisonSchema | None,
) -> PredictionResponse:
    assert forecast.explanation is not None
    exp = forecast.explanation
    h_str = exp.home_team_home_strength
    a_str = exp.away_team_away_strength

    return PredictionResponse(
        slug=None,
        model_version=MODEL_ID,
        data_snapshot_hash=snapshot_hash,
        created_at=created_at,
        mode=mode,
        competition_code=forecast.competition_code,
        seasons_used=seasons_used,
        home_team=forecast.home_team,
        away_team=forecast.away_team,
        as_of_date=as_of_date,
        expected_goals=ExpectedGoalsSchema(
            home=forecast.expected_goals.home,
            away=forecast.expected_goals.away,
        ),
        outcome_probabilities=OutcomeProbabilitiesSchema(
            home_win=forecast.outcomes.home_win,
            draw=forecast.outcomes.draw,
            away_win=forecast.outcomes.away_win,
        ),
        probability_mass=forecast.outcomes.total_probability_mass,
        full_time_score=PredictedScoreSchema(
            home_goals=forecast.full_time_score.home_goals,
            away_goals=forecast.full_time_score.away_goals,
            probability=forecast.full_time_score.probability,
        ),
        top_scores=[
            PredictedScoreSchema(
                home_goals=s.home_goals,
                away_goals=s.away_goals,
                probability=s.probability,
            )
            for s in forecast.top_scores
        ],
        half_time=HalfTimePredictionSchema(
            expected_goals=ExpectedGoalsSchema(
                home=forecast.half_time.expected_goals.home,
                away=forecast.half_time.expected_goals.away,
            ),
            score=PredictedScoreSchema(
                home_goals=forecast.half_time.score.home_goals,
                away_goals=forecast.half_time.score.away_goals,
                probability=forecast.half_time.score.probability,
            ),
        ),
        markets=BettingMarketsSchema(
            home_win=MarketSelectionSchema(
                probability=forecast.markets.home_win.probability,
                fair_odds=forecast.markets.home_win.fair_odds,
            ),
            draw=MarketSelectionSchema(
                probability=forecast.markets.draw.probability,
                fair_odds=forecast.markets.draw.fair_odds,
            ),
            away_win=MarketSelectionSchema(
                probability=forecast.markets.away_win.probability,
                fair_odds=forecast.markets.away_win.fair_odds,
            ),
            over_2_5_goals=MarketSelectionSchema(
                probability=forecast.markets.over_2_5_goals.probability,
                fair_odds=forecast.markets.over_2_5_goals.fair_odds,
            ),
            under_2_5_goals=MarketSelectionSchema(
                probability=forecast.markets.under_2_5_goals.probability,
                fair_odds=forecast.markets.under_2_5_goals.fair_odds,
            ),
            btts_yes=MarketSelectionSchema(
                probability=forecast.markets.both_teams_to_score_yes.probability,
                fair_odds=forecast.markets.both_teams_to_score_yes.fair_odds,
            ),
            btts_no=MarketSelectionSchema(
                probability=forecast.markets.both_teams_to_score_no.probability,
                fair_odds=forecast.markets.both_teams_to_score_no.fair_odds,
            ),
        ),
        score_matrix=ScoreMatrixSchema(
            max_goals=forecast.score_probabilities.max_goals,
            probabilities=[
                list(row) for row in forecast.score_probabilities.probabilities
            ],
        ),
        explanation=MatchupExplanationSchema(
            total_league_matches=exp.total_league_matches,
            league_home_goals=exp.league_home_goals,
            league_away_goals=exp.league_away_goals,
            used_initial_league_rates=exp.used_initial_league_rates,
            home_team_home_strength=TeamVenueStrengthSchema(
                matches_played=h_str.matches_played,
                goals_for=h_str.goals_for,
                goals_against=h_str.goals_against,
                goals_for_per_match=h_str.goals_for_per_match,
                goals_against_per_match=h_str.goals_against_per_match,
                attack_multiplier=h_str.attack_multiplier,
                defence_multiplier=h_str.defence_multiplier,
                used_neutral_fallback=h_str.used_neutral_fallback,
            ),
            away_team_away_strength=TeamVenueStrengthSchema(
                matches_played=a_str.matches_played,
                goals_for=a_str.goals_for,
                goals_against=a_str.goals_against,
                goals_for_per_match=a_str.goals_for_per_match,
                goals_against_per_match=a_str.goals_against_per_match,
                attack_multiplier=a_str.attack_multiplier,
                defence_multiplier=a_str.defence_multiplier,
                used_neutral_fallback=a_str.used_neutral_fallback,
            ),
        ),
        historical_context=historical_context,
        bookmaker_comparison=bookmaker_comparison,
    )


def _to_metrics_schema(evaluation: OutcomeEvaluation) -> OutcomeMetricsSchema:
    return OutcomeMetricsSchema(
        matches=evaluation.matches,
        log_loss=evaluation.log_loss,
        brier_score=evaluation.brier_score,
        accuracy=evaluation.accuracy,
        mean_probability_mass=evaluation.mean_probability_mass,
    )


def _format_bookmaker_1x2(odds: Match1X2Odds) -> Bookmaker1X2ComparisonSchema:
    imp_h, imp_d, imp_a = odds.implied_probabilities
    return Bookmaker1X2ComparisonSchema(
        source=odds.source,
        phase=odds.phase,
        home_price=odds.home_price,
        draw_price=odds.draw_price,
        away_price=odds.away_price,
        overround=odds.overround,
        implied_home_win=imp_h,
        implied_draw=imp_d,
        implied_away_win=imp_a,
    )


def _extract_1x2_from_odds_list(
    odds_list: list[dict[str, object]],
) -> Match1X2Odds | None:
    by_source: dict[str, dict[str, float]] = {}
    for item in odds_list:
        if item.get("market") != "1X2":
            continue
        src = str(item.get("source", "BOOKMAKER")).upper()
        sel = str(item.get("selection", "")).upper()
        price = float(item.get("price", 0.0))  # type: ignore[arg-type]
        if sel in ("H", "D", "A") and price > 1.0:
            by_source.setdefault(src, {})[sel] = price
    for src, prices in by_source.items():
        if {"H", "D", "A"}.issubset(prices.keys()):
            return Match1X2Odds(
                source=src,
                phase="prematch",
                home_price=prices["H"],
                draw_price=prices["D"],
                away_price=prices["A"],
            )
    return None


def _build_bookmaker_benchmark(
    predictions_df: pd.DataFrame,
    odds_map: dict[int, Match1X2Odds],
) -> BookmakerEvaluationBenchmarkSchema | None:
    if not odds_map:
        return None

    bm_rows: list[dict[str, object]] = []
    model_subset_rows: list[dict[str, object]] = []
    sources_used: set[str] = set()

    for row in predictions_df.itertuples(index=False):
        mid = (
            int(row.match_id)
            if getattr(row, "match_id", None) is not None and not pd.isna(row.match_id)
            else None
        )
        if mid is None or mid not in odds_map:
            continue
        odds = odds_map[mid]
        sources_used.add(f"{odds.source} ({odds.phase})")
        imp_h, imp_d, imp_a = odds.implied_probabilities
        bm_rows.append(
            {
                "result": row.result,
                "home_win_probability": imp_h,
                "draw_probability": imp_d,
                "away_win_probability": imp_a,
                "probability_mass": imp_h + imp_d + imp_a,
            }
        )
        model_subset_rows.append(
            {
                "result": row.result,
                "home_win_probability": float(row.home_win_probability),
                "draw_probability": float(row.draw_probability),
                "away_win_probability": float(row.away_win_probability),
                "probability_mass": float(row.probability_mass),
            }
        )

    if not bm_rows:
        return None

    bm_eval = evaluate_outcome_probabilities(pd.DataFrame(bm_rows))
    model_sub_eval = evaluate_outcome_probabilities(pd.DataFrame(model_subset_rows))
    return BookmakerEvaluationBenchmarkSchema(
        evaluated_matches_with_odds=len(bm_rows),
        source_summary=", ".join(sorted(sources_used)),
        bookmaker_metrics=_to_metrics_schema(bm_eval),
        model_metrics_on_same_matches=_to_metrics_schema(model_sub_eval),
    )
