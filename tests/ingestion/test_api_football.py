from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from football_analytics.db.base import Base
from football_analytics.db.models import Match, Team, TeamAlias
from football_analytics.db.repository import FootballRepository
from football_analytics.ingestion.api_football import (
    ApiFootballClient,
    ApiFootballError,
    sync_competition_season,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _fake_transport_factory(
    routes: dict[str, dict[str, object]],
):
    def _transport(
        url: str,
        headers: Mapping[str, str],
    ) -> tuple[int, Mapping[str, str], bytes]:
        assert headers.get("x-apisports-key") == "test-api-key"
        for key, payload in routes.items():
            if key in url:
                return (
                    200,
                    {
                        "x-ratelimit-requests-remaining": "94",
                        "x-ratelimit-requests-limit": "100",
                    },
                    json.dumps(payload).encode("utf-8"),
                )
        raise AssertionError(f"Unexpected URL in fake transport: {url}")

    return _transport


def test_api_football_sync_reconciles_csv_team_aliases_and_separates_ft_from_ns(
    session: Session,
) -> None:
    repo = FootballRepository(session)
    comp = repo.get_or_create_competition(name="Premier League", code="EPL")
    season = repo.get_or_create_season(competition=comp, name="2025-26")

    # Pre-seed teams using football-data.co.uk CSV shorthand names
    man_utd_csv = repo.get_or_create_team("Man United")
    arsenal_csv = repo.get_or_create_team("Arsenal")
    chelsea_csv = repo.get_or_create_team("Chelsea")
    repo.create_match(
        season_id=season.id,
        home_team_id=man_utd_csv.id,
        away_team_id=arsenal_csv.id,
        referee_id=None,
        match_date=date(2025, 8, 10),
        kickoff_time=None,
        home_goals=1,
        away_goals=1,
        result="D",
        home_half_time_goals=0,
        away_half_time_goals=1,
        half_time_result="A",
    )
    session.flush()

    fixtures_envelope = {
        "get": "fixtures",
        "parameters": {"league": "39", "season": "2025"},
        "errors": [],
        "results": 2,
        "response": [
            {
                "fixture": {
                    "id": 120001,
                    "referee": "Michael Oliver, England",
                    "timezone": "UTC",
                    "date": "2025-08-17T15:30:00+00:00",
                    "venue": {"id": 556, "name": "Old Trafford", "city": "Manchester"},
                    "status": {"long": "Match Finished", "short": "FT", "elapsed": 90},
                },
                "league": {
                    "id": 39,
                    "name": "Premier League",
                    "country": "England",
                    "logo": "https://media.api-sports.io/football/leagues/39.png",
                    "season": 2025,
                    "round": "Regular Season - 2",
                },
                "teams": {
                    "home": {
                        "id": 33,
                        "name": "Manchester United",
                        "logo": "https://media.api-sports.io/football/teams/33.png",
                        "winner": True,
                    },
                    "away": {
                        "id": 49,
                        "name": "Chelsea",
                        "logo": "https://media.api-sports.io/football/teams/49.png",
                        "winner": False,
                    },
                },
                "goals": {"home": 2, "away": 0},
                "score": {
                    "halftime": {"home": 1, "away": 0},
                    "fulltime": {"home": 2, "away": 0},
                },
            },
            {
                "fixture": {
                    "id": 120002,
                    "referee": "Anthony Taylor",
                    "timezone": "UTC",
                    "date": "2025-08-24T16:30:00+00:00",
                    "venue": {"id": 494, "name": "Emirates Stadium", "city": "London"},
                    "status": {"long": "Not Started", "short": "NS", "elapsed": None},
                },
                "league": {
                    "id": 39,
                    "name": "Premier League",
                    "country": "England",
                    "season": 2025,
                    "round": "Regular Season - 3",
                },
                "teams": {
                    "home": {"id": 42, "name": "Arsenal", "logo": None, "winner": None},
                    "away": {
                        "id": 33,
                        "name": "Manchester United",
                        "logo": None,
                        "winner": None,
                    },
                },
                "goals": {"home": None, "away": None},
                "score": {
                    "halftime": {"home": None, "away": None},
                    "fulltime": {"home": None, "away": None},
                },
            },
        ],
    }

    odds_envelope = {
        "get": "odds",
        "errors": [],
        "results": 1,
        "response": [
            {
                "fixture": {"id": 120002},
                "bookmakers": [
                    {
                        "id": 8,
                        "name": "Bet365",
                        "bets": [
                            {
                                "id": 1,
                                "name": "Match Winner",
                                "values": [
                                    {"value": "Home", "odd": "1.80"},
                                    {"value": "Draw", "odd": "3.75"},
                                    {"value": "Away", "odd": "4.20"},
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    client = ApiFootballClient(
        api_key="test-api-key",
        transport=_fake_transport_factory(
            {
                "/fixtures": fixtures_envelope,
                "/odds": odds_envelope,
            }
        ),
    )

    summary = sync_competition_season(
        session,
        client,
        competition_code="EPL",
        season_name="2025-26",
        include_odds=True,
    )

    assert summary.created_completed_matches == 1
    assert summary.upserted_scheduled_fixtures == 1
    assert summary.synced_odds_records == 3
    assert summary.requests_remaining == 94

    # Verify "Manchester United" resolved to existing "Man United" team
    all_teams = session.scalars(select(Team)).all()
    assert len(all_teams) == 3
    refreshed_man_utd = session.get(Team, man_utd_csv.id)
    assert refreshed_man_utd is not None
    assert refreshed_man_utd.api_football_id == 33

    alias = session.scalar(
        select(TeamAlias).where(TeamAlias.alias == "Manchester United")
    )
    assert alias is not None
    assert alias.team_id == man_utd_csv.id

    # Verify FT match was persisted in `matches`
    ft_match = session.scalar(
        select(Match).where(Match.api_football_fixture_id == 120001)
    )
    assert ft_match is not None
    assert ft_match.home_team_id == man_utd_csv.id
    assert ft_match.away_team_id == chelsea_csv.id
    assert ft_match.home_goals == 2
    assert ft_match.away_goals == 0

    # Verify NS fixture was persisted in `scheduled_fixtures`
    upcoming = repo.list_scheduled_fixtures(
        competition_code="EPL",
        include_completed=False,
    )
    assert len(upcoming) == 1
    assert upcoming[0].api_football_fixture_id == 120002
    assert upcoming[0].home_team == "Arsenal"
    assert upcoming[0].away_team == "Man United"
    assert upcoming[0].odds_count == 3


def test_api_football_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    with pytest.raises(ApiFootballError, match="API_FOOTBALL_KEY"):
        ApiFootballClient(api_key="")
