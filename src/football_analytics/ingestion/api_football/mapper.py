"""Mapping helpers from API-Football v3 payloads into canonical domain structures."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC

from .schemas import (
    ApiFootballFixtureItem,
    ApiFootballOddsItem,
    ApiFootballTeamStatisticsItem,
)

COMPLETED_STATUSES = {"FT", "AET", "PEN"}
UPCOMING_OR_LIVE_STATUSES = {"NS", "TBD", "1H", "HT", "2H", "ET", "P", "PST"}


@dataclass(frozen=True)
class ApiFootballLeagueSpec:
    code: str
    name: str
    api_football_id: int
    country: str


DEFAULT_API_FOOTBALL_LEAGUES: dict[str, ApiFootballLeagueSpec] = {
    "EPL": ApiFootballLeagueSpec(
        code="EPL",
        name="Premier League",
        api_football_id=39,
        country="England",
    ),
    "ENG_CHAMP": ApiFootballLeagueSpec(
        code="ENG_CHAMP",
        name="Championship",
        api_football_id=40,
        country="England",
    ),
    "ITALY_SERIE_A": ApiFootballLeagueSpec(
        code="ITALY_SERIE_A",
        name="Serie A",
        api_football_id=135,
        country="Italy",
    ),
    "LA_LIGA": ApiFootballLeagueSpec(
        code="LA_LIGA",
        name="La Liga",
        api_football_id=140,
        country="Spain",
    ),
}

_BOOKMAKER_SOURCE_CODES: dict[str, str] = {
    "bet365": "B365",
    "pinnacle": "PS",
    "1xbet": "1XBET",
    "unibet": "UNIBET",
    "william hill": "WH",
    "bwin": "BW",
    "betfair": "BF",
}


def season_name_to_api_year(season_name: str) -> int:
    """Convert canonical season ('2025-26') to API-Football 4-digit year (2025)."""
    cleaned = season_name.strip()
    if len(cleaned) >= 4 and cleaned[:4].isdigit():
        return int(cleaned[:4])
    raise ValueError(
        f"Cannot derive 4-digit API-Football season year from '{season_name}'"
    )


def api_year_to_season_name(year: int) -> str:
    """Convert API-Football 4-digit year (2025) to canonical season ('2025-26')."""
    if year < 1900 or year > 2100:
        raise ValueError(f"Invalid season year: {year}")
    next_two = str(year + 1)[-2:]
    return f"{year}-{next_two}"


def compute_match_result(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "H"
    if home_goals == away_goals:
        return "D"
    return "A"


def extract_completed_match_fields(
    item: ApiFootballFixtureItem,
) -> dict[str, object]:
    """Transform a completed API-Football fixture item into `Match` creation fields."""
    if item.fixture.status.short not in COMPLETED_STATUSES:
        status_short = item.fixture.status.short
        raise ValueError(
            f"Fixture {item.fixture.id} is not completed (status={status_short})"
        )

    ft_home = (
        item.score.fulltime.home
        if item.score.fulltime.home is not None
        else item.goals.home
    )
    ft_away = (
        item.score.fulltime.away
        if item.score.fulltime.away is not None
        else item.goals.away
    )
    if ft_home is None or ft_away is None:
        raise ValueError(
            f"Completed fixture {item.fixture.id} is missing full-time goals"
        )

    ht_home = item.score.halftime.home
    ht_away = item.score.halftime.away
    ht_result = (
        compute_match_result(ht_home, ht_away)
        if ht_home is not None and ht_away is not None
        else None
    )

    dt_utc = item.fixture.date.astimezone(UTC)
    referee_clean = (
        item.fixture.referee.split(",")[0].strip() if item.fixture.referee else None
    )

    return {
        "api_football_fixture_id": item.fixture.id,
        "match_date": dt_utc.date(),
        "kickoff_time": dt_utc.time().replace(tzinfo=None),
        "home_goals": int(ft_home),
        "away_goals": int(ft_away),
        "result": compute_match_result(int(ft_home), int(ft_away)),
        "home_half_time_goals": int(ht_home) if ht_home is not None else None,
        "away_half_time_goals": int(ht_away) if ht_away is not None else None,
        "half_time_result": ht_result,
        "referee_name": referee_clean or None,
    }


def extract_scheduled_fixture_fields(
    item: ApiFootballFixtureItem,
) -> dict[str, object]:
    """Transform an API-Football fixture into `ScheduledFixture` upsert fields."""
    dt_utc = item.fixture.date.astimezone(UTC)
    referee_clean = (
        item.fixture.referee.split(",")[0].strip() if item.fixture.referee else None
    )
    return {
        "api_football_fixture_id": item.fixture.id,
        "match_date": dt_utc.date(),
        "kickoff_time": dt_utc.time().replace(tzinfo=None),
        "status_short": item.fixture.status.short,
        "referee_name": referee_clean or None,
        "venue_name": item.fixture.venue.name if item.fixture.venue else None,
        "round_name": item.league.round,
    }


def transform_api_football_statistics(
    items: Sequence[ApiFootballTeamStatisticsItem],
    *,
    home_api_team_id: int,
    away_api_team_id: int,
) -> dict[str, int | None] | None:
    """Convert `/fixtures/statistics` response into `MatchStatistics` columns."""
    by_team: dict[int, dict[str, int | None]] = {}
    for team_entry in items:
        stat_map: dict[str, int | None] = {}
        for pair in team_entry.statistics:
            stat_map[pair.type.strip().lower()] = _coerce_stat_int(pair.value)
        by_team[team_entry.team.id] = stat_map

    home_stats = by_team.get(home_api_team_id)
    away_stats = by_team.get(away_api_team_id)
    if not home_stats and not away_stats:
        return None

    home_stats = home_stats or {}
    away_stats = away_stats or {}

    return {
        "home_shots": home_stats.get("total shots"),
        "away_shots": away_stats.get("total shots"),
        "home_shots_on_target": home_stats.get("shots on goal"),
        "away_shots_on_target": away_stats.get("shots on goal"),
        "home_fouls": home_stats.get("fouls"),
        "away_fouls": away_stats.get("fouls"),
        "home_corners": home_stats.get("corner kicks"),
        "away_corners": away_stats.get("corner kicks"),
        "home_yellow_cards": home_stats.get("yellow cards"),
        "away_yellow_cards": away_stats.get("yellow cards"),
        "home_red_cards": home_stats.get("red cards"),
        "away_red_cards": away_stats.get("red cards"),
    }


def transform_api_football_odds(
    item: ApiFootballOddsItem,
) -> list[dict[str, object]]:
    """Extract normalized 1X2, Over/Under 2.5, and BTTS prices from an odds item."""
    extracted: list[dict[str, object]] = []
    for bookmaker in item.bookmakers:
        source_code = _BOOKMAKER_SOURCE_CODES.get(
            bookmaker.name.strip().lower(),
            bookmaker.name.strip().upper()[:20],
        )
        for bet in bookmaker.bets:
            bet_name = bet.name.strip().lower()
            # Market 1: Match Winner (1X2)
            if bet.id == 1 or bet_name == "match winner":
                for val in bet.values:
                    price = _coerce_positive_float(val.odd)
                    if price is None:
                        continue
                    v = val.value.strip().lower()
                    selection = (
                        "H"
                        if v == "home"
                        else ("D" if v == "draw" else ("A" if v == "away" else None))
                    )
                    if selection:
                        extracted.append(
                            {
                                "source": source_code,
                                "market": "1X2",
                                "selection": selection,
                                "line": None,
                                "phase": "prematch",
                                "price": price,
                            }
                        )
            # Market 5: Goals Over/Under (2.5)
            elif bet.id == 5 or "over/under" in bet_name:
                for val in bet.values:
                    price = _coerce_positive_float(val.odd)
                    if price is None:
                        continue
                    v = val.value.strip().lower()
                    if v == "over 2.5":
                        extracted.append(
                            {
                                "source": source_code,
                                "market": "OU",
                                "selection": "OVER",
                                "line": 2.5,
                                "phase": "prematch",
                                "price": price,
                            }
                        )
                    elif v == "under 2.5":
                        extracted.append(
                            {
                                "source": source_code,
                                "market": "OU",
                                "selection": "UNDER",
                                "line": 2.5,
                                "phase": "prematch",
                                "price": price,
                            }
                        )
            # Market 8: Both Teams Score (BTTS)
            elif bet.id == 8 or "both teams score" in bet_name:
                for val in bet.values:
                    price = _coerce_positive_float(val.odd)
                    if price is None:
                        continue
                    v = val.value.strip().lower()
                    if v in ("yes", "no"):
                        extracted.append(
                            {
                                "source": source_code,
                                "market": "BTTS",
                                "selection": v.upper(),
                                "line": None,
                                "phase": "prematch",
                                "price": price,
                            }
                        )
    return extracted


def _coerce_stat_int(value: int | float | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().rstrip("%")
    if not text or text.lower() == "none":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _coerce_positive_float(value: str) -> float | None:
    try:
        parsed = float(value)
        return parsed if parsed > 1.0 else None
    except ValueError:
        return None
