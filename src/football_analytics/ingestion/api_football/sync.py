"""Transactional synchronization workflows for API-Football v3 (api-football.com)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from football_analytics.db.repository import FootballRepository

from .client import ApiFootballClient
from .mapper import (
    COMPLETED_STATUSES,
    DEFAULT_API_FOOTBALL_LEAGUES,
    extract_completed_match_fields,
    extract_scheduled_fixture_fields,
    season_name_to_api_year,
    transform_api_football_odds,
    transform_api_football_statistics,
)


@dataclass(frozen=True)
class ApiFootballSyncSummary:
    competition_code: str
    season_name: str
    api_football_league_id: int
    api_football_season_year: int
    created_completed_matches: int
    existing_completed_matches: int
    upserted_scheduled_fixtures: int
    synced_odds_records: int
    requests_remaining: int | None


def sync_competition_season(
    session: Session,
    client: ApiFootballClient,
    *,
    competition_code: str,
    season_name: str,
    competition_name: str | None = None,
    api_football_league_id: int | None = None,
    include_odds: bool = False,
    include_statistics_for_new: bool = False,
) -> ApiFootballSyncSummary:
    """Sync completed matches and scheduled fixtures for one league season."""
    code = competition_code.strip().upper()
    default_spec = DEFAULT_API_FOOTBALL_LEAGUES.get(code)
    resolved_league_id = api_football_league_id or (
        default_spec.api_football_id if default_spec else None
    )
    if resolved_league_id is None:
        raise ValueError(
            f"Unknown API-Football league ID for competition_code '{code}'. "
            "Pass api_football_league_id explicitly."
        )
    resolved_name = competition_name or (default_spec.name if default_spec else code)
    season_year = season_name_to_api_year(season_name)

    repository = FootballRepository(session)
    competition = repository.get_or_create_competition(
        name=resolved_name,
        code=code,
        api_football_id=resolved_league_id,
        country=default_spec.country if default_spec else None,
    )
    season = repository.get_or_create_season(
        competition=competition,
        name=season_name,
        api_football_year=season_year,
    )

    fixture_items, remaining = client.fetch_fixtures(
        league_id=resolved_league_id,
        season_year=season_year,
    )

    created_completed = 0
    existing_completed = 0
    upserted_scheduled = 0
    synced_odds = 0

    for item in fixture_items:
        if item.league.logo and not competition.logo_url:
            competition.logo_url = item.league.logo

        home_team = repository.get_or_create_team(
            item.teams.home.name,
            api_football_id=item.teams.home.id,
            logo_url=item.teams.home.logo,
            source="api_football",
        )
        away_team = repository.get_or_create_team(
            item.teams.away.name,
            api_football_id=item.teams.away.id,
            logo_url=item.teams.away.logo,
            source="api_football",
        )

        if item.fixture.status.short in COMPLETED_STATUSES and (
            item.score.fulltime.home is not None or item.goals.home is not None
        ):
            match_fields = extract_completed_match_fields(item)
            referee_name = match_fields.pop("referee_name")
            referee = (
                repository.get_or_create_referee(str(referee_name))
                if referee_name
                else None
            )
            match, created = repository.get_or_create_match(
                season_id=season.id,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                referee_id=referee.id if referee else None,
                **match_fields,  # type: ignore[arg-type]
            )
            if created:
                created_completed += 1
                if include_statistics_for_new:
                    stat_items, remaining = client.fetch_fixture_statistics(
                        fixture_id=item.fixture.id
                    )
                    mapped_stats = transform_api_football_statistics(
                        stat_items,
                        home_api_team_id=item.teams.home.id,
                        away_api_team_id=item.teams.away.id,
                    )
                    if mapped_stats is not None:
                        repository.create_match_statistics(
                            match_id=match.id,
                            **mapped_stats,
                        )
            else:
                existing_completed += 1

            # Also mark any corresponding scheduled fixture as completed
            sched_fields = extract_scheduled_fixture_fields(item)
            repository.upsert_scheduled_fixture(
                season_id=season.id,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                completed_match_id=match.id,
                **sched_fields,  # type: ignore[arg-type]
            )
        else:
            sched_fields = extract_scheduled_fixture_fields(item)
            repository.upsert_scheduled_fixture(
                season_id=season.id,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                **sched_fields,  # type: ignore[arg-type]
            )
            upserted_scheduled += 1

    if include_odds:
        odds_items, remaining = client.fetch_odds(
            league_id=resolved_league_id,
            season_year=season_year,
        )
        scheduled_by_api_id = {
            row.api_football_fixture_id: row.id
            for row in repository.list_scheduled_fixtures(
                competition_code=code,
                season_name=season_name,
                include_completed=True,
                limit=1000,
            )
        }
        for odds_item in odds_items:
            local_fixture_id = scheduled_by_api_id.get(odds_item.fixture.id)
            if local_fixture_id is None:
                continue
            normalized_odds = transform_api_football_odds(odds_item)
            if normalized_odds:
                synced_odds += repository.replace_fixture_odds(
                    fixture_id=local_fixture_id,
                    odds_items=normalized_odds,
                )

    repository.record_sync_log(
        endpoint="/fixtures",
        competition_code=code,
        season_name=season_name,
        status="success",
        requests_remaining=remaining,
        records_processed=len(fixture_items),
        details={
            "created_completed_matches": created_completed,
            "existing_completed_matches": existing_completed,
            "upserted_scheduled_fixtures": upserted_scheduled,
            "synced_odds_records": synced_odds,
        },
    )

    return ApiFootballSyncSummary(
        competition_code=code,
        season_name=season_name,
        api_football_league_id=resolved_league_id,
        api_football_season_year=season_year,
        created_completed_matches=created_completed,
        existing_completed_matches=existing_completed,
        upserted_scheduled_fixtures=upserted_scheduled,
        synced_odds_records=synced_odds,
        requests_remaining=remaining,
    )
