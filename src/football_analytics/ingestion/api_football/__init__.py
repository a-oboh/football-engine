"""API-Football v3 (api-football.com) live ingestion package."""

from .client import ApiFootballClient, ApiFootballError
from .mapper import (
    DEFAULT_API_FOOTBALL_LEAGUES,
    ApiFootballLeagueSpec,
    api_year_to_season_name,
    extract_completed_match_fields,
    extract_scheduled_fixture_fields,
    season_name_to_api_year,
    transform_api_football_odds,
    transform_api_football_statistics,
)
from .sync import ApiFootballSyncSummary, sync_competition_season

__all__ = [
    "ApiFootballClient",
    "ApiFootballError",
    "ApiFootballLeagueSpec",
    "ApiFootballSyncSummary",
    "DEFAULT_API_FOOTBALL_LEAGUES",
    "api_year_to_season_name",
    "extract_completed_match_fields",
    "extract_scheduled_fixture_fields",
    "season_name_to_api_year",
    "sync_competition_season",
    "transform_api_football_odds",
    "transform_api_football_statistics",
]
