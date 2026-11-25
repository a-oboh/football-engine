"""Pydantic v2 request and response schemas for the Football Engine Lab API v1."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ErrorResponse(BaseModel):
    """Standard error payload returned by FastAPI HTTPExceptions."""

    detail: str = Field(
        ...,
        description="Human-readable explanation of the error.",
        examples=["Historical match 99999 not found"],
    )


class HealthResponse(BaseModel):
    """Service health, database connectivity, and external provider status."""

    status: Literal["ok", "degraded"] = Field(
        ...,
        description=(
            "Overall service health ('ok' when database is reachable, "
            "'degraded' otherwise)."
        ),
        examples=["ok"],
    )
    database: Literal["connected", "unavailable"] = Field(
        ...,
        description="Connectivity status of the primary SQL database.",
        examples=["connected"],
    )
    model_version: str = Field(
        ...,
        description="Identifier of the active forecasting model.",
        examples=["sequential-poisson-v1"],
    )
    api_football_configured: bool = Field(
        ...,
        description=(
            "Whether an API_FOOTBALL_KEY environment variable is configured "
            "for live sync."
        ),
        examples=[True],
    )
    timestamp: datetime = Field(
        ...,
        description="UTC timestamp when the health check was evaluated.",
    )


class CompetitionItemResponse(BaseModel):
    """Summary of an ingested football competition and its available seasons."""

    code: str = Field(
        ...,
        description=(
            "Short competition code used across API requests (e.g. 'EPL' or 'E0')."
        ),
        examples=["EPL"],
    )
    name: str = Field(
        ...,
        description="Display name of the competition.",
        examples=["Premier League"],
    )
    seasons: list[str] = Field(
        ...,
        description="Chronologically ordered list of available season identifiers.",
        examples=[["2023-24", "2024-25", "2025-26"]],
    )
    match_count: int = Field(
        default=0,
        description="Total number of completed matches stored for this competition.",
        examples=[1140],
    )
    api_football_id: int | None = Field(
        default=None,
        description="Corresponding league ID on api-football.com (v3), if mapped.",
        examples=[39],
    )
    country: str | None = Field(
        default=None,
        description="Country or confederation hosting the competition.",
        examples=["England"],
    )
    logo_url: str | None = Field(
        default=None,
        description="Optional URL to the competition crest or logo.",
    )


class ModelMetadataResponse(BaseModel):
    """Specification, parameters, assumptions, and leakage policy of a model."""

    id: str = Field(
        ...,
        description="Unique slug identifying the model version.",
        examples=["sequential-poisson-v1"],
    )
    name: str = Field(
        ...,
        description="Human-readable model name.",
        examples=["Sequential Independent Poisson Baseline"],
    )
    version: str = Field(
        ...,
        description="Semantic version string of the model implementation.",
        examples=["1.0.0"],
    )
    family: str = Field(
        ...,
        description="Statistical model family.",
        examples=["Poisson / Venue-Conditioned Rate Multiplier"],
    )
    description: str = Field(
        ...,
        description=(
            "High-level summary of how the model estimates goal expectations."
        ),
    )
    parameters: dict[str, float | int] = Field(
        ...,
        description="Default model hyperparameters and prior baseline values.",
        examples=[
            {
                "initial_home_goals": 1.5,
                "initial_away_goals": 1.2,
                "default_max_goals": 10,
                "neutral_strength_multiplier": 1.0,
            }
        ],
    )
    assumptions: list[str] = Field(
        ...,
        description="Key statistical and structural assumptions made by the model.",
    )
    limitations: list[str] = Field(
        ...,
        description="Known modeling limitations and out-of-scope factors.",
    )
    data_leakage_policy: str = Field(
        ...,
        description=(
            "Guarantee describing how future data leakage is prevented "
            "during backtests."
        ),
    )


class OverviewResponse(BaseModel):
    """High-level summary of the ingested dataset corpus and active model."""

    total_matches: int = Field(
        ...,
        description=(
            "Total completed matches stored across all competitions and seasons."
        ),
        examples=[1140],
    )
    total_competitions: int = Field(
        ...,
        description="Number of distinct competitions in the database.",
        examples=[1],
    )
    total_seasons: int = Field(
        ...,
        description="Number of distinct competition-seasons in the database.",
        examples=[3],
    )
    total_teams: int = Field(
        ...,
        description="Number of canonical teams stored in the database.",
        examples=[24],
    )
    total_odds: int = Field(
        ...,
        description=(
            "Total bookmaker odds records stored across completed and "
            "scheduled matches."
        ),
        examples=[3420],
    )
    upcoming_fixtures: int = Field(
        ...,
        description=(
            "Number of scheduled unplayed fixtures synced from api-football.com."
        ),
        examples=[10],
    )
    earliest_match_date: str | None = Field(
        default=None,
        description=(
            "ISO date (YYYY-MM-DD) of the oldest completed match in the corpus."
        ),
        examples=["2023-08-11"],
    )
    latest_match_date: str | None = Field(
        default=None,
        description=(
            "ISO date (YYYY-MM-DD) of the most recent completed match in the corpus."
        ),
        examples=["2025-05-25"],
    )
    competitions: list[CompetitionItemResponse] = Field(
        ...,
        description=(
            "Per-competition breakdown of available seasons and match counts."
        ),
    )
    active_model: ModelMetadataResponse = Field(
        ...,
        description="Metadata for the default forecasting model.",
    )
    api_football_configured: bool = Field(
        ...,
        description=(
            "Whether live fixture/odds sync via api-football.com is configured."
        ),
        examples=[True],
    )


class TeamsResponse(BaseModel):
    """Canonical team names participating in the selected competition and seasons."""

    competition_code: str = Field(
        ...,
        description="Competition code queried.",
        examples=["EPL"],
    )
    seasons: list[str] = Field(
        ...,
        description="Season names included in the lookup.",
        examples=[["2024-25", "2025-26"]],
    )
    teams: list[str] = Field(
        ...,
        description="Alphabetically sorted list of canonical team names.",
        examples=[["Arsenal", "Chelsea", "Liverpool"]],
    )


class MatchSummaryResponse(BaseModel):
    """Compact summary of a completed historical match for paginated table views."""

    id: int = Field(
        ...,
        description="Internal database ID of the match.",
        examples=[42],
    )
    competition_code: str = Field(
        ...,
        description="Competition code.",
        examples=["EPL"],
    )
    competition_name: str = Field(
        ...,
        description="Competition display name.",
        examples=["Premier League"],
    )
    season_name: str = Field(
        ...,
        description="Season identifier.",
        examples=["2024-25"],
    )
    match_date: date = Field(
        ...,
        description="Match date (YYYY-MM-DD).",
        examples=["2024-09-01"],
    )
    kickoff_time: str | None = Field(
        default=None,
        description="Kickoff time formatted as HH:MM (24-hour), if available.",
        examples=["16:30"],
    )
    home_team: str = Field(
        ...,
        description="Canonical name of the home team.",
        examples=["Arsenal"],
    )
    away_team: str = Field(
        ...,
        description="Canonical name of the away team.",
        examples=["Chelsea"],
    )
    home_goals: int = Field(
        ...,
        description="Full-time goals scored by the home team (FTHG).",
        examples=[3],
    )
    away_goals: int = Field(
        ...,
        description="Full-time goals scored by the away team (FTAG).",
        examples=[1],
    )
    result: Literal["H", "D", "A"] = Field(
        ...,
        description=(
            "Full-time 1X2 outcome ('H' = home win, 'D' = draw, 'A' = away win)."
        ),
        examples=["H"],
    )
    home_half_time_goals: int | None = Field(
        default=None,
        description="Half-time goals scored by the home team (HTHG), if recorded.",
        examples=[2],
    )
    away_half_time_goals: int | None = Field(
        default=None,
        description="Half-time goals scored by the away team (HTAG), if recorded.",
        examples=[0],
    )
    half_time_result: str | None = Field(
        default=None,
        description="Half-time outcome ('H', 'D', or 'A'), if recorded.",
        examples=["H"],
    )
    referee_name: str | None = Field(
        default=None,
        description="Match referee name, if recorded.",
        examples=["Michael Oliver"],
    )
    has_statistics: bool = Field(
        ...,
        description=(
            "Whether team match statistics (shots, corners, cards) are available."
        ),
        examples=[True],
    )
    odds_count: int = Field(
        ...,
        description="Number of bookmaker odds entries stored for this match.",
        examples=[3],
    )


class PaginatedMatchesResponse(BaseModel):
    """Paginated list of completed historical matches."""

    items: list[MatchSummaryResponse] = Field(
        ...,
        description="Matches on the current page.",
    )
    total: int = Field(
        ...,
        description="Total matches matching the filter criteria.",
        examples=[380],
    )
    page: int = Field(
        ...,
        description="Current 1-based page number.",
        examples=[1],
    )
    page_size: int = Field(
        ...,
        description="Maximum number of items per page.",
        examples=[25],
    )
    total_pages: int = Field(
        ...,
        description="Total number of pages available.",
        examples=[16],
    )


class MatchStatisticsResponse(BaseModel):
    """Full-time team statistics for a completed match."""

    home_shots: int | None = Field(
        default=None,
        description="Total shots by the home team.",
    )
    away_shots: int | None = Field(
        default=None,
        description="Total shots by the away team.",
    )
    home_shots_on_target: int | None = Field(
        default=None,
        description="Shots on target by the home team.",
    )
    away_shots_on_target: int | None = Field(
        default=None,
        description="Shots on target by the away team.",
    )
    home_fouls: int | None = Field(
        default=None,
        description="Fouls committed by the home team.",
    )
    away_fouls: int | None = Field(
        default=None,
        description="Fouls committed by the away team.",
    )
    home_corners: int | None = Field(
        default=None,
        description="Corner kicks won by the home team.",
    )
    away_corners: int | None = Field(
        default=None,
        description="Corner kicks won by the away team.",
    )
    home_yellow_cards: int | None = Field(
        default=None,
        description="Yellow cards shown to the home team.",
    )
    away_yellow_cards: int | None = Field(
        default=None,
        description="Yellow cards shown to the away team.",
    )
    home_red_cards: int | None = Field(
        default=None,
        description="Red cards shown to the home team.",
    )
    away_red_cards: int | None = Field(
        default=None,
        description="Red cards shown to the away team.",
    )


class OddsEntryResponse(BaseModel):
    """Single bookmaker odds quote for a specific market selection."""

    source: str = Field(
        ...,
        description=(
            "Bookmaker or feed code (e.g. 'PS' for Pinnacle, 'B365' for Bet365)."
        ),
        examples=["PS"],
    )
    market: str = Field(
        ...,
        description="Betting market identifier (e.g. '1X2', 'OU2.5', 'BTTS').",
        examples=["1X2"],
    )
    selection: str = Field(
        ...,
        description=(
            "Outcome selection code within the market "
            "(e.g. 'H', 'D', 'A', 'OVER', 'UNDER')."
        ),
        examples=["H"],
    )
    line: float | None = Field(
        default=None,
        description="Goal line or handicap value for line-based markets (e.g. 2.5).",
        examples=[None],
    )
    phase: str = Field(
        ...,
        description="Quote timing phase ('opening', 'closing', or 'prematch').",
        examples=["closing"],
    )
    price: float = Field(
        ...,
        description="Decimal odds quote (e.g. 1.85).",
        examples=[1.75],
    )


class MatchDetailResponse(BaseModel):
    """Comprehensive match record including scoreline, statistics, and odds."""

    id: int = Field(
        ...,
        description="Internal database ID of the match.",
        examples=[42],
    )
    api_football_fixture_id: int | None = Field(
        default=None,
        description="External fixture ID from api-football.com, if linked.",
        examples=[1208021],
    )
    competition_code: str = Field(
        ...,
        description="Competition code.",
        examples=["EPL"],
    )
    competition_name: str = Field(
        ...,
        description="Competition display name.",
        examples=["Premier League"],
    )
    season_name: str = Field(
        ...,
        description="Season identifier.",
        examples=["2024-25"],
    )
    match_date: date = Field(
        ...,
        description="Match date (YYYY-MM-DD).",
        examples=["2024-09-01"],
    )
    kickoff_time: str | None = Field(
        default=None,
        description="Kickoff time (HH:MM), if available.",
        examples=["16:30"],
    )
    home_team: str = Field(
        ...,
        description="Canonical home team name.",
        examples=["Arsenal"],
    )
    away_team: str = Field(
        ...,
        description="Canonical away team name.",
        examples=["Chelsea"],
    )
    home_team_logo: str | None = Field(
        default=None,
        description="URL to the home team crest, if available.",
    )
    away_team_logo: str | None = Field(
        default=None,
        description="URL to the away team crest, if available.",
    )
    home_goals: int = Field(
        ...,
        description="Full-time home goals.",
        examples=[3],
    )
    away_goals: int = Field(
        ...,
        description="Full-time away goals.",
        examples=[1],
    )
    result: Literal["H", "D", "A"] = Field(
        ...,
        description="Full-time 1X2 outcome ('H', 'D', or 'A').",
        examples=["H"],
    )
    home_half_time_goals: int | None = Field(
        default=None,
        description="Half-time home goals, if available.",
        examples=[2],
    )
    away_half_time_goals: int | None = Field(
        default=None,
        description="Half-time away goals, if available.",
        examples=[0],
    )
    half_time_result: str | None = Field(
        default=None,
        description="Half-time 1X2 outcome, if available.",
        examples=["H"],
    )
    referee_name: str | None = Field(
        default=None,
        description="Match referee name, if available.",
    )
    statistics: MatchStatisticsResponse | None = Field(
        default=None,
        description=(
            "Team match statistics (shots, corners, fouls, cards), if recorded."
        ),
    )
    odds: list[OddsEntryResponse] = Field(
        default_factory=list,
        description="Bookmaker odds quotes attached to this match.",
    )


class ScheduledFixtureResponse(BaseModel):
    """Upcoming or recently scheduled fixture synced from api-football.com."""

    id: int = Field(
        ...,
        description="Internal scheduled fixture ID.",
        examples=[7],
    )
    api_football_fixture_id: int = Field(
        ...,
        description="External api-football.com fixture ID.",
        examples=[1208155],
    )
    competition_code: str = Field(
        ...,
        description="Competition code.",
        examples=["EPL"],
    )
    competition_name: str = Field(
        ...,
        description="Competition display name.",
        examples=["Premier League"],
    )
    season_name: str = Field(
        ...,
        description="Season identifier.",
        examples=["2025-26"],
    )
    home_team: str = Field(
        ...,
        description="Canonical home team name.",
        examples=["Arsenal"],
    )
    away_team: str = Field(
        ...,
        description="Canonical away team name.",
        examples=["Liverpool"],
    )
    home_team_logo: str | None = Field(
        default=None,
        description="URL to the home team crest, if available.",
    )
    away_team_logo: str | None = Field(
        default=None,
        description="URL to the away team crest, if available.",
    )
    match_date: date = Field(
        ...,
        description="Scheduled match date (YYYY-MM-DD).",
        examples=["2025-10-18"],
    )
    kickoff_time: str | None = Field(
        default=None,
        description="Scheduled kickoff time (HH:MM), if available.",
        examples=["17:30"],
    )
    venue_name: str | None = Field(
        default=None,
        description="Stadium or venue name.",
        examples=["Emirates Stadium"],
    )
    round_name: str | None = Field(
        default=None,
        description="Competition round or matchweek label.",
        examples=["Regular Season - 8"],
    )
    referee_name: str | None = Field(
        default=None,
        description="Assigned referee name, if announced.",
    )
    status_short: str = Field(
        ...,
        description=(
            "Short fixture status code from api-football.com (e.g. 'NS', 'TBD', 'FT')."
        ),
        examples=["NS"],
    )
    completed_match_id: int | None = Field(
        default=None,
        description=(
            "Linked completed match ID once the fixture finishes and is ingested."
        ),
    )
    last_synced_at: datetime = Field(
        ...,
        description="UTC timestamp when this fixture was last synchronized.",
    )
    odds_count: int = Field(
        default=0,
        description=(
            "Number of pre-match bookmaker odds quotes stored for this fixture."
        ),
        examples=[3],
    )


class PredictionRequest(BaseModel):
    """Parameters for generating an explainable Sequential Poisson fixture prediction.

    Supports three evaluation modes:
    - `hypothetical`: Forecast any custom home vs away matchup using all completed
      matches in `season_names` (optionally up to `as_of_date`).
    - `historical`: Replay a completed match by `match_id` (or teams + `as_of_date`)
      strictly using matches completed prior to that fixture, and attach the actual
      scoreline and closing bookmaker odds for comparison.
    - `upcoming`: Forecast a scheduled fixture by `fixture_id` (or teams) and attach
      pre-match bookmaker odds if synced.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "competition_code": "EPL",
                    "season_names": ["2024-25", "2025-26"],
                    "mode": "hypothetical",
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                    "max_goals": 10,
                    "save_snapshot": True,
                },
                {
                    "competition_code": "EPL",
                    "season_names": ["2024-25", "2025-26"],
                    "mode": "historical",
                    "match_id": 3,
                    "max_goals": 10,
                    "save_snapshot": True,
                },
            ]
        }
    )

    competition_code: str = Field(
        ...,
        min_length=1,
        description=(
            "Competition code to draw historical training matches from (e.g. 'EPL')."
        ),
        examples=["EPL"],
    )
    season_names: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Ordered list of season names to include in the chronological "
            "training window."
        ),
        examples=[["2024-25", "2025-26"]],
    )
    mode: Literal["hypothetical", "historical", "upcoming"] = Field(
        default="hypothetical",
        description=(
            "Prediction mode: 'hypothetical' (custom matchup), "
            "'historical' (walk-forward replay of a past match), or "
            "'upcoming' (scheduled fixture)."
        ),
        examples=["hypothetical"],
    )
    home_team: str | None = Field(
        default=None,
        description=(
            "Canonical home team name. Required for 'hypothetical' mode; "
            "automatically resolved when `match_id` or `fixture_id` is supplied."
        ),
        examples=["Arsenal"],
    )
    away_team: str | None = Field(
        default=None,
        description="Canonical away team name. Must differ from `home_team`.",
        examples=["Chelsea"],
    )
    match_id: int | None = Field(
        default=None,
        description=(
            "Completed match ID to replay in 'historical' mode. Automatically "
            "sets the walk-forward date cutoff and excludes the target match "
            "from training."
        ),
        examples=[None],
    )
    fixture_id: int | None = Field(
        default=None,
        description="Scheduled fixture ID to forecast in 'upcoming' mode.",
        examples=[None],
    )
    as_of_date: date | None = Field(
        default=None,
        description=(
            "Optional strict date cutoff (YYYY-MM-DD): only matches completed "
            "strictly before this date are used to estimate team strengths."
        ),
        examples=[None],
    )
    model_version: str = Field(
        default="sequential-poisson-v1",
        description="Forecasting model identifier to execute.",
        examples=["sequential-poisson-v1"],
    )
    max_goals: int = Field(
        default=10,
        ge=4,
        le=15,
        description=(
            "Maximum goals per team on the discrete score matrix grid [0..max_goals]."
        ),
        examples=[10],
    )
    save_snapshot: bool = Field(
        default=True,
        description=(
            "Whether to persist an immutable prediction snapshot with a "
            "shareable permalink `slug`."
        ),
        examples=[True],
    )

    @model_validator(mode="after")
    def validate_teams_or_ids(self) -> PredictionRequest:
        if self.mode == "historical" and self.match_id is None:
            if not self.home_team or not self.away_team:
                raise ValueError(
                    "historical mode requires either match_id or home_team + away_team"
                )
        if self.mode == "upcoming" and self.fixture_id is None:
            if not self.home_team or not self.away_team:
                raise ValueError(
                    "upcoming mode requires either fixture_id or home_team + away_team"
                )
        if self.mode == "hypothetical":
            if not self.home_team or not self.away_team:
                raise ValueError(
                    "hypothetical mode requires both home_team and away_team"
                )
        if (
            self.home_team
            and self.away_team
            and self.home_team.strip() == self.away_team.strip()
        ):
            raise ValueError("home_team and away_team must be different")
        return self


class ExpectedGoalsSchema(BaseModel):
    """Poisson goal rate parameters (λ_home, λ_away) for a fixture."""

    home: float = Field(
        ...,
        description="Expected goals (λ_home) for the home team.",
        examples=[1.82],
    )
    away: float = Field(
        ...,
        description="Expected goals (λ_away) for the away team.",
        examples=[1.14],
    )


class OutcomeProbabilitiesSchema(BaseModel):
    """1X2 match outcome probabilities summed over the [0..max_goals] score grid."""

    home_win: float = Field(
        ...,
        description="Probability that the home team wins (home_goals > away_goals).",
        examples=[0.542],
    )
    draw: float = Field(
        ...,
        description="Probability of a draw (home_goals == away_goals).",
        examples=[0.238],
    )
    away_win: float = Field(
        ...,
        description="Probability that the away team wins (home_goals < away_goals).",
        examples=[0.220],
    )


class PredictedScoreSchema(BaseModel):
    """Exact scoreline and its joint Poisson probability."""

    home_goals: int = Field(
        ...,
        description="Home team goal count.",
        examples=[2],
    )
    away_goals: int = Field(
        ...,
        description="Away team goal count.",
        examples=[1],
    )
    probability: float = Field(
        ...,
        description="Joint probability of this exact scoreline.",
        examples=[0.118],
    )


class HalfTimePredictionSchema(BaseModel):
    """Calibrated half-time expected goals and most likely half-time scoreline."""

    expected_goals: ExpectedGoalsSchema = Field(
        ...,
        description=(
            "Half-time expected goals scaled by the empirical pre-interval goal share."
        ),
    )
    score: PredictedScoreSchema = Field(
        ...,
        description="Most likely exact half-time scoreline (HTHG–HTAG).",
    )


class MarketSelectionSchema(BaseModel):
    """Model probability and margin-free fair decimal odds for a market selection."""

    probability: float = Field(
        ...,
        description="Model probability for this selection in [0, 1].",
        examples=[0.542],
    )
    fair_odds: float | None = Field(
        default=None,
        description=(
            "Margin-free fair decimal odds (`1 / probability`), "
            "or null if probability is 0."
        ),
        examples=[1.845],
    )


class BettingMarketsSchema(BaseModel):
    """Core derived betting markets (1X2, Over/Under 2.5 Goals, BTTS)."""

    home_win: MarketSelectionSchema = Field(
        ...,
        description="Full-time Home Win (1).",
    )
    draw: MarketSelectionSchema = Field(
        ...,
        description="Full-time Draw (X).",
    )
    away_win: MarketSelectionSchema = Field(
        ...,
        description="Full-time Away Win (2).",
    )
    over_2_5_goals: MarketSelectionSchema = Field(
        ...,
        description="Over 2.5 total full-time goals (FTHG + FTAG >= 3).",
    )
    under_2_5_goals: MarketSelectionSchema = Field(
        ...,
        description="Under 2.5 total full-time goals (FTHG + FTAG <= 2).",
    )
    btts_yes: MarketSelectionSchema = Field(
        ...,
        description="Both Teams To Score — Yes (FTHG >= 1 and FTAG >= 1).",
    )
    btts_no: MarketSelectionSchema = Field(
        ...,
        description="Both Teams To Score — No (FTHG == 0 or FTAG == 0).",
    )


class ScoreMatrixSchema(BaseModel):
    """2D joint probability grid `P(FTHG = i, FTAG = j)` on `[0..max_goals]`."""

    max_goals: int = Field(
        ...,
        description="Maximum goals per team on the grid.",
        examples=[10],
    )
    probabilities: list[list[float]] = Field(
        ...,
        description="2D matrix indexed by `[home_goals][away_goals]`.",
    )


class TeamVenueStrengthSchema(BaseModel):
    """Venue-specific historical sample and attack/defence multipliers for one team."""

    matches_played: int = Field(
        ...,
        description=(
            "Number of prior completed matches played by this team at this "
            "venue (home or away)."
        ),
        examples=[19],
    )
    goals_for: int = Field(
        ...,
        description="Total goals scored by this team at this venue.",
        examples=[42],
    )
    goals_against: int = Field(
        ...,
        description="Total goals conceded by this team at this venue.",
        examples=[16],
    )
    goals_for_per_match: float | None = Field(
        default=None,
        description=(
            "Average goals scored per match at this venue "
            "(`goals_for / matches_played`)."
        ),
        examples=[2.21],
    )
    goals_against_per_match: float | None = Field(
        default=None,
        description=(
            "Average goals conceded per match at this venue "
            "(`goals_against / matches_played`)."
        ),
        examples=[0.84],
    )
    attack_multiplier: float = Field(
        ...,
        description=(
            "Venue attack strength multiplier relative to the league venue average."
        ),
        examples=[1.41],
    )
    defence_multiplier: float = Field(
        ...,
        description=(
            "Venue defensive weakness multiplier relative to the league venue "
            "average (< 1.0 indicates a stronger-than-average defence)."
        ),
        examples=[0.68],
    )
    used_neutral_fallback: bool = Field(
        ...,
        description=(
            "True if the team had zero prior venue matches in the window and "
            "defaulted to neutral 1.0 multipliers."
        ),
        examples=[False],
    )


class MatchupExplanationSchema(BaseModel):
    """Decomposition of expected goals into league baselines and team multipliers."""

    total_league_matches: int = Field(
        ...,
        description=(
            "Total prior completed league matches used to estimate baseline "
            "scoring rates."
        ),
        examples=[380],
    )
    league_home_goals: float = Field(
        ...,
        description="Average home goals per match across the training corpus.",
        examples=[1.57],
    )
    league_away_goals: float = Field(
        ...,
        description="Average away goals per match across the training corpus.",
        examples=[1.24],
    )
    used_initial_league_rates: bool = Field(
        ...,
        description=(
            "True if no prior league matches existed and prior fallback rates "
            "(1.5 / 1.2) were used."
        ),
        examples=[False],
    )
    home_team_home_strength: TeamVenueStrengthSchema = Field(
        ...,
        description=(
            "Home team's attacking and defensive strength estimated strictly "
            "from prior home matches."
        ),
    )
    away_team_away_strength: TeamVenueStrengthSchema = Field(
        ...,
        description=(
            "Away team's attacking and defensive strength estimated strictly "
            "from prior away matches."
        ),
    )


class HistoricalMatchContextSchema(BaseModel):
    """Actual scoreline and outcome attached when replaying a historical match."""

    match_id: int = Field(
        ...,
        description="Database ID of the historical match.",
        examples=[3],
    )
    match_date: date = Field(
        ...,
        description="Date the match was played.",
        examples=["2025-08-20"],
    )
    season_name: str = Field(
        ...,
        description="Season identifier.",
        examples=["2025-26"],
    )
    actual_home_goals: int = Field(
        ...,
        description="Actual full-time home goals.",
        examples=[2],
    )
    actual_away_goals: int = Field(
        ...,
        description="Actual full-time away goals.",
        examples=[2],
    )
    actual_result: Literal["H", "D", "A"] = Field(
        ...,
        description="Actual full-time 1X2 outcome.",
        examples=["D"],
    )
    actual_ht_home_goals: int | None = Field(
        default=None,
        description="Actual half-time home goals, if recorded.",
        examples=[1],
    )
    actual_ht_away_goals: int | None = Field(
        default=None,
        description="Actual half-time away goals, if recorded.",
        examples=[1],
    )


class Bookmaker1X2ComparisonSchema(BaseModel):
    """Bookmaker 1X2 decimal odds, overround, and normalized implied probabilities."""

    source: str = Field(
        ...,
        description="Bookmaker code (e.g. 'PS', 'B365').",
        examples=["B365"],
    )
    phase: str = Field(
        ...,
        description="Odds phase ('closing', 'opening', or 'prematch').",
        examples=["closing"],
    )
    home_price: float = Field(
        ...,
        description="Decimal odds for Home Win (1).",
        examples=[2.20],
    )
    draw_price: float = Field(
        ...,
        description="Decimal odds for Draw (X).",
        examples=[3.40],
    )
    away_price: float = Field(
        ...,
        description="Decimal odds for Away Win (2).",
        examples=[3.20],
    )
    overround: float = Field(
        ...,
        description="Bookmaker vigorish / overround (`(1/H + 1/D + 1/A) - 1`).",
        examples=[0.0612],
    )
    implied_home_win: float = Field(
        ...,
        description="Margin-normalized implied probability for Home Win.",
        examples=[0.4284],
    )
    implied_draw: float = Field(
        ...,
        description="Margin-normalized implied probability for Draw.",
        examples=[0.2772],
    )
    implied_away_win: float = Field(
        ...,
        description="Margin-normalized implied probability for Away Win.",
        examples=[0.2944],
    )


class PredictionResponse(BaseModel):
    """Full fixture forecast with expected goals, markets, matrix, and explanation."""

    slug: str | None = Field(
        default=None,
        description=(
            "Shareable permalink slug if `save_snapshot=True` was requested "
            "(e.g. 'pred_a1b2c3d4e5')."
        ),
        examples=["pred_8f3a19c2b4"],
    )
    model_version: str = Field(
        ...,
        description="Identifier of the forecasting model used.",
        examples=["sequential-poisson-v1"],
    )
    data_snapshot_hash: str = Field(
        ...,
        description=(
            "SHA-256 fingerprint of the underlying competition/season training dataset."
        ),
        examples=["e3b0c44298fc1c14"],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the prediction was computed.",
    )
    mode: Literal["hypothetical", "historical", "upcoming"] = Field(
        ...,
        description="Prediction mode executed.",
        examples=["hypothetical"],
    )
    competition_code: str = Field(
        ...,
        description="Competition code.",
        examples=["EPL"],
    )
    seasons_used: list[str] = Field(
        ...,
        description="Seasons included in the training window.",
        examples=[["2024-25", "2025-26"]],
    )
    home_team: str = Field(
        ...,
        description="Canonical home team name.",
        examples=["Arsenal"],
    )
    away_team: str = Field(
        ...,
        description="Canonical away team name.",
        examples=["Chelsea"],
    )
    as_of_date: date | None = Field(
        default=None,
        description=(
            "Strict walk-forward cutoff date applied to training matches, if any."
        ),
    )
    expected_goals: ExpectedGoalsSchema = Field(
        ...,
        description="Full-time expected goals (λ_home, λ_away).",
    )
    outcome_probabilities: OutcomeProbabilitiesSchema = Field(
        ...,
        description="Full-time 1X2 outcome probabilities.",
    )
    probability_mass: float = Field(
        ...,
        description=(
            "Total probability mass retained within the `[0..max_goals]` "
            "score grid (typically > 0.999)."
        ),
        examples=[0.9998],
    )
    full_time_score: PredictedScoreSchema = Field(
        ...,
        description=(
            "Most likely exact full-time scoreline (mode of the score matrix)."
        ),
    )
    top_scores: list[PredictedScoreSchema] = Field(
        ...,
        description=(
            "Top-ranked exact full-time scorelines ordered by descending probability."
        ),
    )
    half_time: HalfTimePredictionSchema = Field(
        ...,
        description=(
            "Calibrated half-time expected goals and most likely half-time score."
        ),
    )
    markets: BettingMarketsSchema = Field(
        ...,
        description=(
            "Derived betting market probabilities and margin-free fair decimal odds."
        ),
    )
    score_matrix: ScoreMatrixSchema = Field(
        ...,
        description=(
            "Full 2D joint probability matrix over `[0..max_goals] x [0..max_goals]`."
        ),
    )
    explanation: MatchupExplanationSchema = Field(
        ...,
        description=(
            "Transparent decomposition of league baselines and "
            "venue-conditioned attack/defence multipliers."
        ),
    )
    historical_context: HistoricalMatchContextSchema | None = Field(
        default=None,
        description=(
            "Actual match outcome when replaying a completed fixture in "
            "'historical' mode."
        ),
    )
    bookmaker_comparison: Bookmaker1X2ComparisonSchema | None = Field(
        default=None,
        description=(
            "Closing or pre-match bookmaker 1X2 odds comparison when available."
        ),
    )


class EvaluationRequest(BaseModel):
    """Parameters for running a chronological walk-forward backtest evaluation.

    The model is warmed up on `warmup_seasons` and then evaluates every match in
    `evaluation_seasons` strictly in chronological order, updating team and league
    state after each match is scored.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "competition_code": "EPL",
                    "warmup_seasons": ["2024-25"],
                    "evaluation_seasons": ["2025-26"],
                    "model_version": "sequential-poisson-v1",
                    "max_goals": 10,
                    "save_snapshot": True,
                }
            ]
        }
    )

    competition_code: str = Field(
        ...,
        min_length=1,
        description="Competition code to evaluate (e.g. 'EPL').",
        examples=["EPL"],
    )
    warmup_seasons: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Initial season(s) used strictly to warm up team attack/defence "
            "multipliers before scoring begins. Must not overlap with "
            "`evaluation_seasons`."
        ),
        examples=[["2024-25"]],
    )
    evaluation_seasons: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "Target out-of-sample season(s) evaluated walk-forward match by "
            "match. Must be disjoint from `warmup_seasons`."
        ),
        examples=[["2025-26"]],
    )
    model_version: str = Field(
        default="sequential-poisson-v1",
        description="Forecasting model identifier to backtest.",
        examples=["sequential-poisson-v1"],
    )
    max_goals: int = Field(
        default=10,
        ge=4,
        le=15,
        description=(
            "Maximum goals per team on the discrete score matrix grid [0..max_goals]."
        ),
        examples=[10],
    )
    save_snapshot: bool = Field(
        default=True,
        description=(
            "Whether to persist an immutable evaluation snapshot with a "
            "shareable permalink `slug`."
        ),
        examples=[True],
    )

    @model_validator(mode="after")
    def validate_disjoint_seasons(self) -> EvaluationRequest:
        overlap = set(self.warmup_seasons) & set(self.evaluation_seasons)
        if overlap:
            msg = (
                "warmup_seasons and evaluation_seasons must not overlap: "
                f"{sorted(overlap)}"
            )
            raise ValueError(msg)
        return self


class OutcomeMetricsSchema(BaseModel):
    """Proper scoring rules and classification accuracy over evaluated 1X2 forecasts."""

    matches: int = Field(
        ...,
        description="Number of evaluated matches.",
        examples=[380],
    )
    log_loss: float = Field(
        ...,
        description=(
            "Multi-class logarithmic loss (cross-entropy) on 1X2 outcome "
            "probabilities (lower is better)."
        ),
        examples=[1.012],
    )
    brier_score: float = Field(
        ...,
        description=(
            "Multi-class Brier score (mean squared error across H/D/A "
            "probability vectors; lower is better)."
        ),
        examples=[0.598],
    )
    accuracy: float = Field(
        ...,
        description=(
            "Top-1 classification accuracy (share of matches where the "
            "highest-probability 1X2 outcome occurred)."
        ),
        examples=[0.534],
    )
    mean_probability_mass: float = Field(
        ...,
        description=(
            "Mean probability mass retained on the `[0..max_goals]` score "
            "grid across evaluated matches."
        ),
        examples=[0.9997],
    )


class BookmakerEvaluationBenchmarkSchema(BaseModel):
    """Head-to-head comparison between bookmaker implied probabilities and the model."""

    evaluated_matches_with_odds: int = Field(
        ...,
        description=(
            "Number of evaluated matches that have complete 1X2 bookmaker odds."
        ),
        examples=[380],
    )
    source_summary: str = Field(
        ...,
        description=(
            "Summary of bookmaker sources and phases used in the benchmark "
            "(e.g. 'PS (closing), B365 (closing)')."
        ),
        examples=["PS (closing), B365 (closing)"],
    )
    bookmaker_metrics: OutcomeMetricsSchema = Field(
        ...,
        description=(
            "Scoring metrics achieved by margin-normalized bookmaker implied "
            "probabilities."
        ),
    )
    model_metrics_on_same_matches: OutcomeMetricsSchema = Field(
        ...,
        description=(
            "Scoring metrics achieved by the Sequential Poisson model on the "
            "exact same odds-covered matches."
        ),
    )


class CalibrationBinSchema(BaseModel):
    """Single probability decile bin on the reliability / calibration curve."""

    bin_index: int = Field(
        ...,
        description="0-based bin index.",
        examples=[5],
    )
    bin_lower: float = Field(
        ...,
        description="Inclusive lower probability bound of the bin.",
        examples=[0.5],
    )
    bin_upper: float = Field(
        ...,
        description="Upper probability bound of the bin.",
        examples=[0.6],
    )
    sample_count: int = Field(
        ...,
        description=(
            "Number of outcome predictions falling inside this probability bin."
        ),
        examples=[142],
    )
    mean_predicted_probability: float = Field(
        ...,
        description="Average predicted probability of samples inside this bin.",
        examples=[0.548],
    )
    observed_frequency: float = Field(
        ...,
        description=(
            "Empirical frequency with which outcomes in this bin actually occurred."
        ),
        examples=[0.535],
    )


class OutcomeFrequencySummarySchema(BaseModel):
    """Comparison between mean predicted 1X2 probabilities and empirical base rates."""

    predicted_home: float = Field(
        ...,
        description="Mean predicted Home Win probability across evaluated matches.",
        examples=[0.452],
    )
    predicted_draw: float = Field(
        ...,
        description="Mean predicted Draw probability across evaluated matches.",
        examples=[0.241],
    )
    predicted_away: float = Field(
        ...,
        description="Mean predicted Away Win probability across evaluated matches.",
        examples=[0.307],
    )
    observed_home: float = Field(
        ...,
        description="Observed fraction of Home Wins across evaluated matches.",
        examples=[0.447],
    )
    observed_draw: float = Field(
        ...,
        description="Observed fraction of Draws across evaluated matches.",
        examples=[0.258],
    )
    observed_away: float = Field(
        ...,
        description="Observed fraction of Away Wins across evaluated matches.",
        examples=[0.295],
    )


class SeasonMetricsItemSchema(BaseModel):
    """Evaluation scoring metrics isolated to a single evaluation season."""

    season_name: str = Field(
        ...,
        description="Season identifier.",
        examples=["2025-26"],
    )
    metrics: OutcomeMetricsSchema = Field(
        ...,
        description="Scoring metrics on matches played within this season.",
    )


class EvaluatedMatchPredictionSchema(BaseModel):
    """Walk-forward prediction and actual result for a single evaluated match."""

    match_id: int | None = Field(
        default=None,
        description="Database ID of the evaluated match.",
        examples=[70],
    )
    season_name: str = Field(
        ...,
        description="Season identifier.",
        examples=["2025-26"],
    )
    match_date: str = Field(
        ...,
        description="Match date formatted as YYYY-MM-DD.",
        examples=["2025-08-20"],
    )
    home_team: str = Field(
        ...,
        description="Canonical home team name.",
        examples=["Liverpool"],
    )
    away_team: str = Field(
        ...,
        description="Canonical away team name.",
        examples=["Arsenal"],
    )
    home_goals: int = Field(
        ...,
        description="Actual full-time home goals.",
        examples=[2],
    )
    away_goals: int = Field(
        ...,
        description="Actual full-time away goals.",
        examples=[2],
    )
    actual_result: Literal["H", "D", "A"] = Field(
        ...,
        description="Actual full-time 1X2 outcome.",
        examples=["D"],
    )
    expected_home_goals: float = Field(
        ...,
        description="Walk-forward predicted home expected goals (λ_home).",
        examples=[1.68],
    )
    expected_away_goals: float = Field(
        ...,
        description="Walk-forward predicted away expected goals (λ_away).",
        examples=[1.31],
    )
    home_win_probability: float = Field(
        ...,
        description="Normalized walk-forward Home Win probability.",
        examples=[0.465],
    )
    draw_probability: float = Field(
        ...,
        description="Normalized walk-forward Draw probability.",
        examples=[0.248],
    )
    away_win_probability: float = Field(
        ...,
        description="Normalized walk-forward Away Win probability.",
        examples=[0.287],
    )
    predicted_result: Literal["H", "D", "A"] = Field(
        ...,
        description="Highest-probability 1X2 outcome predicted by the model.",
        examples=["H"],
    )
    correct: bool = Field(
        ...,
        description="Whether `predicted_result == actual_result`.",
        examples=[False],
    )
    bookmaker_source: str | None = Field(
        default=None,
        description="Bookmaker code if 1X2 odds were available.",
        examples=["B365"],
    )
    bookmaker_home_prob: float | None = Field(
        default=None,
        description="Bookmaker implied Home Win probability, if available.",
        examples=[0.428],
    )
    bookmaker_draw_prob: float | None = Field(
        default=None,
        description="Bookmaker implied Draw probability, if available.",
        examples=[0.277],
    )
    bookmaker_away_prob: float | None = Field(
        default=None,
        description="Bookmaker implied Away Win probability, if available.",
        examples=[0.295],
    )


class EvaluationResponse(BaseModel):
    """Complete walk-forward backtest report with metrics, calibration, and matches."""

    slug: str | None = Field(
        default=None,
        description=(
            "Shareable permalink slug if `save_snapshot=True` was requested "
            "(e.g. 'eval_9c4e12a8f0')."
        ),
        examples=["eval_9c4e12a8f0"],
    )
    status: Literal["queued", "running", "completed", "failed"] = Field(
        default="completed",
        description="Execution status of the evaluation run.",
        examples=["completed"],
    )
    model_version: str = Field(
        ...,
        description="Evaluated forecasting model identifier.",
        examples=["sequential-poisson-v1"],
    )
    data_snapshot_hash: str = Field(
        ...,
        description=(
            "SHA-256 fingerprint of the underlying warmup + evaluation dataset."
        ),
        examples=["7f83b1657ff1fc53"],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the evaluation completed.",
    )
    competition_code: str = Field(
        ...,
        description="Evaluated competition code.",
        examples=["EPL"],
    )
    warmup_seasons: list[str] = Field(
        ...,
        description="Seasons used strictly for initial model warm-up.",
        examples=[["2024-25"]],
    )
    evaluation_seasons: list[str] = Field(
        ...,
        description="Out-of-sample seasons evaluated walk-forward.",
        examples=[["2025-26"]],
    )
    model_metrics: OutcomeMetricsSchema = Field(
        ...,
        description=(
            "Overall scoring metrics achieved by the Sequential Poisson model."
        ),
    )
    league_baseline_metrics: OutcomeMetricsSchema = Field(
        ...,
        description=(
            "Scoring metrics of a naive rolling historical league outcome "
            "frequency baseline."
        ),
    )
    bookmaker_benchmark: BookmakerEvaluationBenchmarkSchema | None = Field(
        default=None,
        description=(
            "Comparison against margin-normalized bookmaker implied "
            "probabilities on matches with 1X2 odds."
        ),
    )
    outcome_frequencies: OutcomeFrequencySummarySchema = Field(
        ...,
        description="Predicted vs observed 1X2 outcome frequency summary.",
    )
    calibration_curve: list[CalibrationBinSchema] = Field(
        ...,
        description=(
            "10-bin reliability / calibration curve across all 1X2 probability "
            "predictions."
        ),
    )
    season_breakdown: list[SeasonMetricsItemSchema] = Field(
        ...,
        description="Per-season breakdown of model scoring metrics.",
    )
    predictions: list[EvaluatedMatchPredictionSchema] = Field(
        ...,
        description=(
            "Chronological list of walk-forward match predictions and actual outcomes."
        ),
    )


class ApiFootballSyncRequest(BaseModel):
    """Parameters for triggering a live synchronization from api-football.com (v3)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "competition_code": "EPL",
                    "season_name": "2025-26",
                    "include_odds": True,
                    "include_statistics_for_new": False,
                }
            ]
        }
    )

    competition_code: str = Field(
        ...,
        min_length=1,
        description=(
            "Competition code to synchronize (must map to a configured "
            "api-football.com league ID, e.g. 'EPL' or 'E0')."
        ),
        examples=["EPL"],
    )
    season_name: str = Field(
        ...,
        min_length=4,
        description=(
            "Season name (e.g. '2024-25' or '2025-26'). The starting 4-digit "
            "year is sent to api-football.com."
        ),
        examples=["2025-26"],
    )
    include_odds: bool = Field(
        default=False,
        description=(
            "Whether to fetch and upsert pre-match bookmaker 1X2 odds for "
            "upcoming scheduled fixtures."
        ),
        examples=[True],
    )
    include_statistics_for_new: bool = Field(
        default=False,
        description=(
            "Whether to fetch team match statistics (shots, corners, cards) "
            "for newly ingested completed matches."
        ),
        examples=[False],
    )


class ApiFootballSyncResponse(BaseModel):
    """Summary of records created and updated during an api-football.com sync run."""

    competition_code: str = Field(
        ...,
        description="Synchronized competition code.",
        examples=["EPL"],
    )
    season_name: str = Field(
        ...,
        description="Synchronized season name.",
        examples=["2025-26"],
    )
    api_football_league_id: int = Field(
        ...,
        description="External api-football.com league ID queried.",
        examples=[39],
    )
    api_football_season_year: int = Field(
        ...,
        description="4-digit season start year sent to api-football.com.",
        examples=[2025],
    )
    created_completed_matches: int = Field(
        ...,
        description="Number of newly completed matches inserted into the database.",
        examples=[10],
    )
    existing_completed_matches: int = Field(
        ...,
        description="Number of already-stored completed matches skipped.",
        examples=[270],
    )
    upserted_scheduled_fixtures: int = Field(
        ...,
        description="Number of upcoming scheduled fixtures inserted or updated.",
        examples=[100],
    )
    synced_odds_records: int = Field(
        ...,
        description="Number of pre-match bookmaker odds records synchronized.",
        examples=[30],
    )
    requests_remaining: int | None = Field(
        default=None,
        description=(
            "Remaining daily API quota reported by api-football.com response headers."
        ),
        examples=[85],
    )


class SyncLogItemSchema(BaseModel):
    """Audit log entry recording a past external API synchronization call."""

    id: int = Field(
        ...,
        description="Internal sync log ID.",
        examples=[1],
    )
    provider: str = Field(
        ...,
        description="External data provider identifier.",
        examples=["api-football"],
    )
    endpoint: str = Field(
        ...,
        description="Provider endpoint or operation invoked.",
        examples=["/fixtures"],
    )
    competition_code: str | None = Field(
        default=None,
        description="Competition code targeted by the sync.",
        examples=["EPL"],
    )
    season_name: str | None = Field(
        default=None,
        description="Season targeted by the sync.",
        examples=["2025-26"],
    )
    status: str = Field(
        ...,
        description="Outcome status of the sync operation ('success' or 'error').",
        examples=["success"],
    )
    requests_remaining: int | None = Field(
        default=None,
        description="Remaining daily API quota after this request.",
        examples=[94],
    )
    records_processed: int = Field(
        ...,
        description="Number of fixture or odds records processed.",
        examples=[380],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the sync operation was logged.",
    )


class SyncStatusResponse(BaseModel):
    """Configuration status, supported leagues, and recent sync audit logs."""

    api_football_configured: bool = Field(
        ...,
        description="Whether an API_FOOTBALL_KEY environment variable is configured.",
        examples=[True],
    )
    supported_leagues: list[dict[str, object]] = Field(
        ...,
        description=(
            "Built-in competition codes and their mapped api-football.com league IDs."
        ),
    )
    recent_logs: list[SyncLogItemSchema] = Field(
        ...,
        description="Most recent 10 synchronization audit log entries.",
    )
