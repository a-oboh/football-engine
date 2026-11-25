from __future__ import annotations

import hashlib
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import func, or_, select, union
from sqlalchemy.orm import Session, aliased

from .models import (
    ApiSyncLog,
    Bookmaker,
    Competition,
    FixtureOdds,
    Match,
    MatchStatistics,
    Odds,
    Referee,
    SavedEvaluation,
    SavedPrediction,
    ScheduledFixture,
    Season,
    Team,
    TeamAlias,
)

# Common cross-source aliases between football-data.co.uk CSVs and api-football.com v3
_CROSS_SOURCE_TEAM_EQUIVALENTS: dict[str, tuple[str, ...]] = {
    "Manchester United": ("Man United", "Manchester Utd"),
    "Man United": ("Manchester United", "Manchester Utd"),
    "Manchester City": ("Man City",),
    "Man City": ("Manchester City",),
    "Nottingham Forest": ("Nott'm Forest", "Nottingham"),
    "Nott'm Forest": ("Nottingham Forest", "Nottingham"),
    "Tottenham": ("Spurs", "Tottenham Hotspur"),
    "Spurs": ("Tottenham", "Tottenham Hotspur"),
    "Newcastle": ("Newcastle United", "Newcastle Utd"),
    "Newcastle United": ("Newcastle", "Newcastle Utd"),
    "Wolverhampton Wanderers": ("Wolves", "Wolverhampton"),
    "Wolves": ("Wolverhampton Wanderers", "Wolverhampton"),
    "Brighton": ("Brighton & Hove Albion", "Brighton and Hove Albion"),
    "West Ham": ("West Ham United",),
    "West Ham United": ("West Ham",),
    "Leicester": ("Leicester City",),
    "Leicester City": ("Leicester",),
    "Leeds": ("Leeds United",),
    "Leeds United": ("Leeds",),
    "Sheffield United": ("Sheffield Utd",),
    "Sheffield Utd": ("Sheffield United",),
    "Sheffield Wednesday": ("Sheffield Weds",),
    "Sheffield Weds": ("Sheffield Wednesday",),
    "West Bromwich Albion": ("West Brom",),
    "West Brom": ("West Bromwich Albion",),
    "Queens Park Rangers": ("QPR",),
    "QPR": ("Queens Park Rangers",),
    "Blackburn Rovers": ("Blackburn",),
    "Blackburn": ("Blackburn Rovers",),
    "Preston North End": ("Preston",),
    "Preston": ("Preston North End",),
    "Oxford United": ("Oxford",),
    "Oxford": ("Oxford United",),
    "Atletico Madrid": ("Ath Madrid", "Atlético Madrid"),
    "Ath Madrid": ("Atletico Madrid", "Atlético Madrid"),
    "Athletic Club": ("Ath Bilbao", "Athletic Bilbao"),
    "Ath Bilbao": ("Athletic Club", "Athletic Bilbao"),
    "Real Sociedad": ("Sociedad",),
    "Sociedad": ("Real Sociedad",),
    "Real Betis": ("Betis",),
    "Betis": ("Real Betis",),
    "Celta Vigo": ("Celta",),
    "Celta": ("Celta Vigo",),
    "Espanyol": ("RCD Espanyol",),
    "Alaves": ("Deportivo Alaves", "Alavés"),
    "Sporting Gijon": ("Sp Gijon",),
    "Sp Gijon": ("Sporting Gijon",),
    "Inter": ("Internazionale", "Inter Milan"),
    "AC Milan": ("Milan",),
    "Milan": ("AC Milan",),
    "Hellas Verona": ("Verona",),
    "Verona": ("Hellas Verona",),
    "SPAL": ("Spal",),
}


@dataclass(frozen=True)
class CompletedMatch:
    """A completed match in the shape required by analytics consumers."""

    competition_code: str
    season_name: str
    match_date: date
    kickoff_time: time | None
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    result: str
    home_half_time_goals: int | None = None
    away_half_time_goals: int | None = None
    match_id: int | None = None


@dataclass(frozen=True)
class CompetitionSummary:
    """A competition exposed by the public prediction catalogue."""

    code: str
    name: str
    seasons: tuple[str, ...]
    api_football_id: int | None = None
    country: str | None = None
    logo_url: str | None = None
    match_count: int = 0


@dataclass(frozen=True)
class MatchSummaryRow:
    """Compact historical match row for the corpus explorer."""

    id: int
    competition_code: str
    competition_name: str
    season_name: str
    match_date: date
    kickoff_time: time | None
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    result: str
    home_half_time_goals: int | None
    away_half_time_goals: int | None
    half_time_result: str | None
    referee_name: str | None
    has_statistics: bool
    odds_count: int


@dataclass(frozen=True)
class Match1X2Odds:
    """Representative pre-match/closing 1X2 decimal prices for a match."""

    source: str
    phase: str
    home_price: float
    draw_price: float
    away_price: float

    @property
    def overround(self) -> float:
        return (
            (1.0 / self.home_price) + (1.0 / self.draw_price) + (1.0 / self.away_price)
        )

    @property
    def implied_probabilities(self) -> tuple[float, float, float]:
        total = self.overround
        if total <= 0:
            return (1 / 3, 1 / 3, 1 / 3)
        return (
            (1.0 / self.home_price) / total,
            (1.0 / self.draw_price) / total,
            (1.0 / self.away_price) / total,
        )


@dataclass(frozen=True)
class ScheduledFixtureRow:
    """Upcoming or in-play fixture synced from api-football.com."""

    id: int
    api_football_fixture_id: int
    competition_code: str
    competition_name: str
    season_name: str
    home_team: str
    away_team: str
    home_team_logo: str | None
    away_team_logo: str | None
    match_date: date
    kickoff_time: time | None
    venue_name: str | None
    round_name: str | None
    referee_name: str | None
    status_short: str
    completed_match_id: int | None
    last_synced_at: datetime
    odds_count: int = 0


class FootballRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_competition(
        self,
        *,
        name: str,
        code: str,
        api_football_id: int | None = None,
        country: str | None = None,
        logo_url: str | None = None,
    ) -> Competition:
        competition = self.session.scalar(
            select(Competition).where(Competition.code == code)
        )

        if competition is not None:
            if competition.name != name:
                raise ValueError("Competition code already belongs to another name")
            if api_football_id is not None and competition.api_football_id is None:
                competition.api_football_id = api_football_id
            if country is not None and competition.country is None:
                competition.country = country
            if logo_url is not None and competition.logo_url is None:
                competition.logo_url = logo_url
            self.session.flush()
            return competition

        existing_name = self.session.scalar(
            select(Competition).where(Competition.name == name)
        )
        if existing_name is not None:
            raise ValueError("Competition name already belongs to another code")

        competition = Competition(
            name=name,
            code=code,
            api_football_id=api_football_id,
            country=country,
            logo_url=logo_url,
        )
        self.session.add(competition)
        self.session.flush()
        return competition

    def get_or_create_season(
        self,
        *,
        competition: Competition,
        name: str,
        api_football_year: int | None = None,
        is_current: bool | None = None,
    ) -> Season:
        stmt = select(Season).where(
            Season.competition_id == competition.id,
            Season.name == name,
        )

        season = self.session.scalar(stmt)

        if season is None:
            season = Season(
                competition=competition,
                name=name,
                api_football_year=api_football_year,
                is_current=bool(is_current) if is_current is not None else False,
            )
            self.session.add(season)
            self.session.flush()
        else:
            if api_football_year is not None and season.api_football_year is None:
                season.api_football_year = api_football_year
            if is_current is not None:
                season.is_current = is_current
            self.session.flush()

        return season

    def get_completed_matches(
        self,
        *,
        competition_code: str,
        season_names: Sequence[str] | None = None,
        before_date: date | None = None,
        exclude_match_id: int | None = None,
    ) -> list[CompletedMatch]:
        """Return completed matches for a competition in chronological order.

        Passing ``season_names`` restricts the history to those seasons. Omit it
        to retrieve every stored season for the selected competition.
        """
        if not competition_code.strip():
            raise ValueError("competition_code must not be blank")
        if isinstance(season_names, str):
            raise ValueError("season_names must be a sequence of season names")

        selected_seasons = tuple(season_names) if season_names is not None else ()
        if any(not season_name.strip() for season_name in selected_seasons):
            raise ValueError("season_names must not contain blank values")

        home_team = aliased(Team)
        away_team = aliased(Team)
        statement = (
            select(
                Match.id.label("match_id"),
                Competition.code.label("competition_code"),
                Season.name.label("season_name"),
                Match.match_date,
                Match.kickoff_time,
                home_team.name.label("home_team"),
                away_team.name.label("away_team"),
                Match.home_goals,
                Match.away_goals,
                Match.result,
                Match.home_half_time_goals,
                Match.away_half_time_goals,
            )
            .select_from(Match)
            .join(Season, Match.season_id == Season.id)
            .join(Competition, Season.competition_id == Competition.id)
            .join(home_team, Match.home_team_id == home_team.id)
            .join(away_team, Match.away_team_id == away_team.id)
            .where(Competition.code == competition_code)
            .order_by(Match.match_date, Match.id)
        )
        if selected_seasons:
            statement = statement.where(Season.name.in_(selected_seasons))
        if before_date is not None:
            statement = statement.where(Match.match_date < before_date)
        if exclude_match_id is not None:
            statement = statement.where(Match.id != exclude_match_id)

        return [
            CompletedMatch(
                match_id=row.match_id,
                competition_code=row.competition_code,
                season_name=row.season_name,
                match_date=row.match_date,
                kickoff_time=row.kickoff_time,
                home_team=row.home_team,
                away_team=row.away_team,
                home_goals=row.home_goals,
                away_goals=row.away_goals,
                result=row.result,
                home_half_time_goals=row.home_half_time_goals,
                away_half_time_goals=row.away_half_time_goals,
            )
            for row in self.session.execute(statement).mappings()
        ]

    def get_prediction_competitions(self) -> list[CompetitionSummary]:
        """Return competitions and stored seasons available for forecasts."""
        rows = self.session.execute(
            select(
                Competition.id,
                Competition.code,
                Competition.name,
                Competition.api_football_id,
                Competition.country,
                Competition.logo_url,
                Season.name.label("season_name"),
            )
            .join(Season, Season.competition_id == Competition.id)
            .order_by(Competition.name, Season.name)
        ).all()

        match_counts = dict(
            self.session.execute(
                select(Competition.code, func.count(Match.id))
                .select_from(Match)
                .join(Season, Match.season_id == Season.id)
                .join(Competition, Season.competition_id == Competition.id)
                .group_by(Competition.code)
            ).all()
        )

        competitions: dict[str, dict[str, object]] = {}
        for row in rows:
            entry = competitions.setdefault(
                row.code,
                {
                    "code": row.code,
                    "name": row.name,
                    "api_football_id": row.api_football_id,
                    "country": row.country,
                    "logo_url": row.logo_url,
                    "seasons": [],
                },
            )
            seasons_list = entry["seasons"]
            assert isinstance(seasons_list, list)
            seasons_list.append(row.season_name)

        return [
            CompetitionSummary(
                code=str(item["code"]),
                name=str(item["name"]),
                seasons=tuple(item["seasons"]),  # type: ignore[arg-type]
                api_football_id=item["api_football_id"],  # type: ignore[arg-type]
                country=item["country"],  # type: ignore[arg-type]
                logo_url=item["logo_url"],  # type: ignore[arg-type]
                match_count=int(match_counts.get(str(item["code"]), 0)),
            )
            for item in competitions.values()
        ]

    def get_team_names(
        self,
        *,
        competition_code: str,
        season_names: Sequence[str],
    ) -> list[str]:
        """Return teams with completed matches in the selected competition history."""
        if not competition_code.strip():
            raise ValueError("competition_code must not be blank")
        if isinstance(season_names, str) or not season_names:
            raise ValueError("season_names must contain at least one season name")

        selected_seasons = tuple(season_names)
        if any(not season_name.strip() for season_name in selected_seasons):
            raise ValueError("season_names must not contain blank values")

        home_team = aliased(Team)
        away_team = aliased(Team)
        base = (
            select(Match)
            .join(Season, Match.season_id == Season.id)
            .join(Competition, Season.competition_id == Competition.id)
            .where(
                Competition.code == competition_code,
                Season.name.in_(selected_seasons),
            )
        )
        team_names = union(
            base.with_only_columns(home_team.name).join(
                home_team, Match.home_team_id == home_team.id
            ),
            base.with_only_columns(away_team.name).join(
                away_team, Match.away_team_id == away_team.id
            ),
        ).subquery()
        return list(
            self.session.scalars(select(team_names.c.name).order_by(team_names.c.name))
        )

    def get_or_create_team(
        self,
        name: str,
        *,
        api_football_id: int | None = None,
        short_code: str | None = None,
        logo_url: str | None = None,
        source: str = "csv",
    ) -> Team:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Team name must not be blank")

        team: Team | None = None
        if api_football_id is not None:
            team = self.session.scalar(
                select(Team).where(Team.api_football_id == api_football_id)
            )

        if team is None:
            team = self.session.scalar(select(Team).where(Team.name == cleaned_name))

        if team is None:
            alias_row = self.session.scalar(
                select(TeamAlias).where(TeamAlias.alias == cleaned_name)
            )
            if alias_row is not None:
                team = self.session.get(Team, alias_row.team_id)

        if team is None:
            equivalents = _CROSS_SOURCE_TEAM_EQUIVALENTS.get(cleaned_name, ())
            for candidate in equivalents:
                team = self.session.scalar(select(Team).where(Team.name == candidate))
                if team is not None:
                    self._ensure_team_alias(team.id, cleaned_name, source=source)
                    break

        if team is None:
            team = Team(
                name=cleaned_name,
                api_football_id=api_football_id,
                short_code=short_code,
                logo_url=logo_url,
            )
            self.session.add(team)
            self.session.flush()
        else:
            if api_football_id is not None and team.api_football_id is None:
                team.api_football_id = api_football_id
            if short_code is not None and team.short_code is None:
                team.short_code = short_code
            if logo_url is not None and team.logo_url is None:
                team.logo_url = logo_url
            if team.name != cleaned_name:
                self._ensure_team_alias(team.id, cleaned_name, source=source)
            self.session.flush()

        return team

    def _ensure_team_alias(self, team_id: int, alias: str, *, source: str) -> None:
        existing = self.session.scalar(
            select(TeamAlias).where(TeamAlias.alias == alias)
        )
        if existing is None:
            self.session.add(TeamAlias(team_id=team_id, alias=alias, source=source))
            self.session.flush()

    def get_or_create_referee(self, name: str) -> Referee:
        referee = self.session.scalar(select(Referee).where(Referee.name == name))

        if referee is None:
            referee = Referee(name=name)
            self.session.add(referee)
            self.session.flush()

        return referee

    def create_match(
        self,
        *,
        season_id: int,
        home_team_id: int,
        away_team_id: int,
        referee_id: int | None,
        match_date: date,
        kickoff_time: time | None,
        home_goals: int,
        away_goals: int,
        result: str,
        home_half_time_goals: int | None,
        away_half_time_goals: int | None,
        half_time_result: str | None,
        api_football_fixture_id: int | None = None,
    ) -> Match:
        match = Match(
            api_football_fixture_id=api_football_fixture_id,
            season_id=season_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            referee_id=referee_id,
            match_date=match_date,
            kickoff_time=kickoff_time,
            home_goals=home_goals,
            away_goals=away_goals,
            result=result,
            home_half_time_goals=home_half_time_goals,
            away_half_time_goals=away_half_time_goals,
            half_time_result=half_time_result,
        )

        self.session.add(match)
        self.session.flush()

        return match

    def get_or_create_match(
        self,
        *,
        season_id: int,
        home_team_id: int,
        away_team_id: int,
        referee_id: int | None,
        match_date: date,
        kickoff_time: time | None,
        home_goals: int,
        away_goals: int,
        result: str,
        home_half_time_goals: int | None,
        away_half_time_goals: int | None,
        half_time_result: str | None,
        api_football_fixture_id: int | None = None,
    ) -> tuple[Match, bool]:
        """Return an existing match or create it from a completed result."""
        match: Match | None = None
        if api_football_fixture_id is not None:
            match = self.session.scalar(
                select(Match).where(
                    Match.api_football_fixture_id == api_football_fixture_id
                )
            )
        if match is None:
            match = self.session.scalar(
                select(Match).where(
                    Match.season_id == season_id,
                    Match.home_team_id == home_team_id,
                    Match.away_team_id == away_team_id,
                    Match.match_date == match_date,
                )
            )
        if match is not None:
            if (
                api_football_fixture_id is not None
                and match.api_football_fixture_id is None
            ):
                match.api_football_fixture_id = api_football_fixture_id
                self.session.flush()
            return match, False

        return (
            self.create_match(
                season_id=season_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                referee_id=referee_id,
                match_date=match_date,
                kickoff_time=kickoff_time,
                home_goals=home_goals,
                away_goals=away_goals,
                result=result,
                home_half_time_goals=home_half_time_goals,
                away_half_time_goals=away_half_time_goals,
                half_time_result=half_time_result,
                api_football_fixture_id=api_football_fixture_id,
            ),
            True,
        )

    def create_match_statistics(
        self,
        *,
        match_id: int,
        home_shots: int | None,
        away_shots: int | None,
        home_shots_on_target: int | None,
        away_shots_on_target: int | None,
        home_fouls: int | None,
        away_fouls: int | None,
        home_corners: int | None,
        away_corners: int | None,
        home_yellow_cards: int | None,
        away_yellow_cards: int | None,
        home_red_cards: int | None,
        away_red_cards: int | None,
    ) -> MatchStatistics:
        existing = self.session.get(MatchStatistics, match_id)
        if existing is not None:
            return existing

        statistics = MatchStatistics(
            match_id=match_id,
            home_shots=home_shots,
            away_shots=away_shots,
            home_shots_on_target=home_shots_on_target,
            away_shots_on_target=away_shots_on_target,
            home_fouls=home_fouls,
            away_fouls=away_fouls,
            home_corners=home_corners,
            away_corners=away_corners,
            home_yellow_cards=home_yellow_cards,
            away_yellow_cards=away_yellow_cards,
            home_red_cards=home_red_cards,
            away_red_cards=away_red_cards,
        )

        self.session.add(statistics)
        self.session.flush()

        return statistics

    def get_or_create_bookmaker(self, name: str) -> Bookmaker:
        bookmaker = self.session.scalar(select(Bookmaker).where(Bookmaker.name == name))

        if bookmaker is None:
            bookmaker = Bookmaker(name=name)
            self.session.add(bookmaker)
            self.session.flush()

        return bookmaker

    def create_odds(
        self,
        match_id: int,
        source: str,
        market: str,
        selection: str,
        line: float | None,
        phase: str,
        price: float,
    ) -> Odds:
        bookmaker = self.get_or_create_bookmaker(source)

        odds = Odds(
            match_id=match_id,
            bookmaker_id=bookmaker.id,
            source=source.upper(),
            market=market,
            selection=selection,
            line=Decimal(str(line)) if line is not None else None,
            price=Decimal(str(price)),
            phase=phase,
        )

        self.session.add(odds)
        self.session.flush()

        return odds

    # ------------------------------------------------------------------
    # Explorer, Odds Lookup, Scheduled Fixtures & Snapshot Persistence
    # ------------------------------------------------------------------

    def get_overview_stats(self) -> dict[str, object]:
        """Return corpus statistics for the Overview dashboard."""
        total_matches = int(self.session.scalar(select(func.count(Match.id))) or 0)
        total_competitions = int(
            self.session.scalar(select(func.count(Competition.id))) or 0
        )
        total_seasons = int(self.session.scalar(select(func.count(Season.id))) or 0)
        total_teams = int(self.session.scalar(select(func.count(Team.id))) or 0)
        total_odds = int(self.session.scalar(select(func.count(Odds.id))) or 0)
        upcoming_fixtures = int(
            self.session.scalar(
                select(func.count(ScheduledFixture.id)).where(
                    ScheduledFixture.completed_match_id.is_(None)
                )
            )
            or 0
        )
        min_date, max_date = self.session.execute(
            select(func.min(Match.match_date), func.max(Match.match_date))
        ).one()

        return {
            "total_matches": total_matches,
            "total_competitions": total_competitions,
            "total_seasons": total_seasons,
            "total_teams": total_teams,
            "total_odds": total_odds,
            "upcoming_fixtures": upcoming_fixtures,
            "earliest_match_date": min_date.isoformat() if min_date else None,
            "latest_match_date": max_date.isoformat() if max_date else None,
            "competitions": [
                {
                    "code": comp.code,
                    "name": comp.name,
                    "seasons": list(comp.seasons),
                    "match_count": comp.match_count,
                    "api_football_id": comp.api_football_id,
                    "country": comp.country,
                    "logo_url": comp.logo_url,
                }
                for comp in self.get_prediction_competitions()
            ],
        }

    def search_matches(
        self,
        *,
        competition_code: str | None = None,
        season_name: str | None = None,
        team_name: str | None = None,
        result: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[MatchSummaryRow], int]:
        """Search historical matches with pagination and metadata indicators."""
        home_team = aliased(Team)
        away_team = aliased(Team)

        filters = []
        if competition_code:
            filters.append(Competition.code == competition_code)
        if season_name:
            filters.append(Season.name == season_name)
        if team_name:
            pattern = f"%{team_name.strip()}%"
            filters.append(
                or_(
                    home_team.name.ilike(pattern),
                    away_team.name.ilike(pattern),
                )
            )
        if result in ("H", "D", "A"):
            filters.append(Match.result == result)
        if date_from is not None:
            filters.append(Match.match_date >= date_from)
        if date_to is not None:
            filters.append(Match.match_date <= date_to)

        count_stmt = (
            select(func.count(Match.id))
            .select_from(Match)
            .join(Season, Match.season_id == Season.id)
            .join(Competition, Season.competition_id == Competition.id)
            .join(home_team, Match.home_team_id == home_team.id)
            .join(away_team, Match.away_team_id == away_team.id)
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = int(self.session.scalar(count_stmt) or 0)

        odds_subq = (
            select(Odds.match_id, func.count(Odds.id).label("odds_count"))
            .group_by(Odds.match_id)
            .subquery()
        )

        stmt = (
            select(
                Match.id,
                Competition.code.label("competition_code"),
                Competition.name.label("competition_name"),
                Season.name.label("season_name"),
                Match.match_date,
                Match.kickoff_time,
                home_team.name.label("home_team"),
                away_team.name.label("away_team"),
                Match.home_goals,
                Match.away_goals,
                Match.result,
                Match.home_half_time_goals,
                Match.away_half_time_goals,
                Match.half_time_result,
                Referee.name.label("referee_name"),
                MatchStatistics.match_id.label("stats_match_id"),
                func.coalesce(odds_subq.c.odds_count, 0).label("odds_count"),
            )
            .select_from(Match)
            .join(Season, Match.season_id == Season.id)
            .join(Competition, Season.competition_id == Competition.id)
            .join(home_team, Match.home_team_id == home_team.id)
            .join(away_team, Match.away_team_id == away_team.id)
            .outerjoin(Referee, Match.referee_id == Referee.id)
            .outerjoin(MatchStatistics, MatchStatistics.match_id == Match.id)
            .outerjoin(odds_subq, odds_subq.c.match_id == Match.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = (
            stmt.order_by(Match.match_date.desc(), Match.id.desc())
            .limit(limit)
            .offset(offset)
        )

        rows = [
            MatchSummaryRow(
                id=row.id,
                competition_code=row.competition_code,
                competition_name=row.competition_name,
                season_name=row.season_name,
                match_date=row.match_date,
                kickoff_time=row.kickoff_time,
                home_team=row.home_team,
                away_team=row.away_team,
                home_goals=row.home_goals,
                away_goals=row.away_goals,
                result=row.result,
                home_half_time_goals=row.home_half_time_goals,
                away_half_time_goals=row.away_half_time_goals,
                half_time_result=row.half_time_result,
                referee_name=row.referee_name,
                has_statistics=row.stats_match_id is not None,
                odds_count=int(row.odds_count),
            )
            for row in self.session.execute(stmt).mappings()
        ]
        return rows, total

    def get_match_detail(self, match_id: int) -> dict[str, object] | None:
        """Return full match detail including statistics and all bookmaker odds."""
        home_team = aliased(Team)
        away_team = aliased(Team)
        row = (
            self.session.execute(
                select(
                    Match.id,
                    Match.api_football_fixture_id,
                    Competition.code.label("competition_code"),
                    Competition.name.label("competition_name"),
                    Season.name.label("season_name"),
                    Match.match_date,
                    Match.kickoff_time,
                    home_team.name.label("home_team"),
                    away_team.name.label("away_team"),
                    home_team.logo_url.label("home_team_logo"),
                    away_team.logo_url.label("away_team_logo"),
                    Match.home_goals,
                    Match.away_goals,
                    Match.result,
                    Match.home_half_time_goals,
                    Match.away_half_time_goals,
                    Match.half_time_result,
                    Referee.name.label("referee_name"),
                )
                .select_from(Match)
                .join(Season, Match.season_id == Season.id)
                .join(Competition, Season.competition_id == Competition.id)
                .join(home_team, Match.home_team_id == home_team.id)
                .join(away_team, Match.away_team_id == away_team.id)
                .outerjoin(Referee, Match.referee_id == Referee.id)
                .where(Match.id == match_id)
            )
            .mappings()
            .first()
        )

        if row is None:
            return None

        stats = self.session.get(MatchStatistics, match_id)
        odds_rows = self.session.scalars(
            select(Odds)
            .where(Odds.match_id == match_id)
            .order_by(Odds.market, Odds.source, Odds.phase, Odds.selection)
        ).all()

        return {
            "id": row.id,
            "api_football_fixture_id": row.api_football_fixture_id,
            "competition_code": row.competition_code,
            "competition_name": row.competition_name,
            "season_name": row.season_name,
            "match_date": row.match_date,
            "kickoff_time": row.kickoff_time,
            "home_team": row.home_team,
            "away_team": row.away_team,
            "home_team_logo": row.home_team_logo,
            "away_team_logo": row.away_team_logo,
            "home_goals": row.home_goals,
            "away_goals": row.away_goals,
            "result": row.result,
            "home_half_time_goals": row.home_half_time_goals,
            "away_half_time_goals": row.away_half_time_goals,
            "half_time_result": row.half_time_result,
            "referee_name": row.referee_name,
            "statistics": (
                {
                    "home_shots": stats.home_shots,
                    "away_shots": stats.away_shots,
                    "home_shots_on_target": stats.home_shots_on_target,
                    "away_shots_on_target": stats.away_shots_on_target,
                    "home_fouls": stats.home_fouls,
                    "away_fouls": stats.away_fouls,
                    "home_corners": stats.home_corners,
                    "away_corners": stats.away_corners,
                    "home_yellow_cards": stats.home_yellow_cards,
                    "away_yellow_cards": stats.away_yellow_cards,
                    "home_red_cards": stats.home_red_cards,
                    "away_red_cards": stats.away_red_cards,
                }
                if stats is not None
                else None
            ),
            "odds": [
                {
                    "source": odd.source,
                    "market": odd.market,
                    "selection": odd.selection,
                    "line": float(odd.line) if odd.line is not None else None,
                    "phase": odd.phase,
                    "price": float(odd.price),
                }
                for odd in odds_rows
            ],
        }

    def get_match_1x2_odds_map(
        self,
        match_ids: Sequence[int],
    ) -> dict[int, Match1X2Odds]:
        """Return representative 1X2 odds per match for bookmaker benchmarking.

        Prioritizes sharp/consensus sources in order: PS (Pinnacle), AVG, B365,
        and prefers closing prices when available.
        """
        if not match_ids:
            return {}

        rows = self.session.scalars(
            select(Odds).where(
                Odds.match_id.in_(tuple(match_ids)),
                Odds.market == "1X2",
                Odds.selection.in_(("H", "D", "A", "HOME", "DRAW", "AWAY")),
            )
        ).all()

        grouped: dict[int, dict[tuple[str, str], dict[str, float]]] = {}
        for odd in rows:
            sel = odd.selection.upper()
            normalized_sel = (
                "H" if sel in ("H", "HOME") else ("D" if sel in ("D", "DRAW") else "A")
            )
            key = (odd.source.upper(), odd.phase.lower())
            grouped.setdefault(odd.match_id, {}).setdefault(key, {})[normalized_sel] = (
                float(odd.price)
            )

        priority_sources = ("PS", "PINNACLE", "AVG", "B365", "BET365", "MAX")
        priority_phases = ("closing", "opening", "prematch")

        result: dict[int, Match1X2Odds] = {}
        for match_id, candidates in grouped.items():
            complete = [
                (source, phase, prices)
                for (source, phase), prices in candidates.items()
                if {"H", "D", "A"}.issubset(prices.keys())
                and all(prices[k] > 1.0 for k in ("H", "D", "A"))
            ]
            if not complete:
                continue

            def _rank(item: tuple[str, str, dict[str, float]]) -> tuple[int, int]:
                src, phs, _ = item
                src_rank = (
                    priority_sources.index(src)
                    if src in priority_sources
                    else len(priority_sources)
                )
                phs_rank = (
                    priority_phases.index(phs)
                    if phs in priority_phases
                    else len(priority_phases)
                )
                return (src_rank, phs_rank)

            best_src, best_phase, best_prices = min(complete, key=_rank)
            result[match_id] = Match1X2Odds(
                source=best_src,
                phase=best_phase,
                home_price=best_prices["H"],
                draw_price=best_prices["D"],
                away_price=best_prices["A"],
            )

        return result

    def upsert_scheduled_fixture(
        self,
        *,
        api_football_fixture_id: int,
        season_id: int,
        home_team_id: int,
        away_team_id: int,
        match_date: date,
        kickoff_time: time | None,
        status_short: str,
        referee_name: str | None = None,
        venue_name: str | None = None,
        round_name: str | None = None,
        completed_match_id: int | None = None,
        synced_at: datetime | None = None,
    ) -> ScheduledFixture:
        now = synced_at or datetime.now(UTC)
        fixture = self.session.scalar(
            select(ScheduledFixture).where(
                ScheduledFixture.api_football_fixture_id == api_football_fixture_id
            )
        )
        if fixture is None:
            fixture = ScheduledFixture(
                api_football_fixture_id=api_football_fixture_id,
                season_id=season_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_date=match_date,
                kickoff_time=kickoff_time,
                status_short=status_short,
                referee_name=referee_name,
                venue_name=venue_name,
                round_name=round_name,
                completed_match_id=completed_match_id,
                last_synced_at=now,
            )
            self.session.add(fixture)
        else:
            fixture.season_id = season_id
            fixture.home_team_id = home_team_id
            fixture.away_team_id = away_team_id
            fixture.match_date = match_date
            fixture.kickoff_time = kickoff_time
            fixture.status_short = status_short
            fixture.referee_name = referee_name
            fixture.venue_name = venue_name
            fixture.round_name = round_name
            if completed_match_id is not None:
                fixture.completed_match_id = completed_match_id
            fixture.last_synced_at = now

        self.session.flush()
        return fixture

    def replace_fixture_odds(
        self,
        *,
        fixture_id: int,
        odds_items: Sequence[dict[str, object]],
    ) -> int:
        existing = self.session.scalars(
            select(FixtureOdds).where(FixtureOdds.fixture_id == fixture_id)
        ).all()
        for row in existing:
            self.session.delete(row)
        self.session.flush()

        count = 0
        for item in odds_items:
            source = str(item["source"])
            bookmaker = self.get_or_create_bookmaker(source)
            line_val = item.get("line")
            self.session.add(
                FixtureOdds(
                    fixture_id=fixture_id,
                    bookmaker_id=bookmaker.id,
                    source=source.upper(),
                    market=str(item["market"]),
                    selection=str(item["selection"]),
                    line=Decimal(str(line_val)) if line_val is not None else None,
                    price=Decimal(str(item["price"])),
                )
            )
            count += 1
        self.session.flush()
        return count

    def list_scheduled_fixtures(
        self,
        *,
        competition_code: str | None = None,
        season_name: str | None = None,
        include_completed: bool = False,
        limit: int = 50,
    ) -> list[ScheduledFixtureRow]:
        home_team = aliased(Team)
        away_team = aliased(Team)
        odds_subq = (
            select(
                FixtureOdds.fixture_id,
                func.count(FixtureOdds.id).label("odds_count"),
            )
            .group_by(FixtureOdds.fixture_id)
            .subquery()
        )

        stmt = (
            select(
                ScheduledFixture.id,
                ScheduledFixture.api_football_fixture_id,
                Competition.code.label("competition_code"),
                Competition.name.label("competition_name"),
                Season.name.label("season_name"),
                home_team.name.label("home_team"),
                away_team.name.label("away_team"),
                home_team.logo_url.label("home_team_logo"),
                away_team.logo_url.label("away_team_logo"),
                ScheduledFixture.match_date,
                ScheduledFixture.kickoff_time,
                ScheduledFixture.venue_name,
                ScheduledFixture.round_name,
                ScheduledFixture.referee_name,
                ScheduledFixture.status_short,
                ScheduledFixture.completed_match_id,
                ScheduledFixture.last_synced_at,
                func.coalesce(odds_subq.c.odds_count, 0).label("odds_count"),
            )
            .select_from(ScheduledFixture)
            .join(Season, ScheduledFixture.season_id == Season.id)
            .join(Competition, Season.competition_id == Competition.id)
            .join(home_team, ScheduledFixture.home_team_id == home_team.id)
            .join(away_team, ScheduledFixture.away_team_id == away_team.id)
            .outerjoin(odds_subq, odds_subq.c.fixture_id == ScheduledFixture.id)
        )
        if competition_code:
            stmt = stmt.where(Competition.code == competition_code)
        if season_name:
            stmt = stmt.where(Season.name == season_name)
        if not include_completed:
            stmt = stmt.where(ScheduledFixture.completed_match_id.is_(None))

        stmt = stmt.order_by(
            ScheduledFixture.match_date.asc(),
            ScheduledFixture.kickoff_time.asc(),
            ScheduledFixture.id.asc(),
        ).limit(limit)

        return [
            ScheduledFixtureRow(
                id=row.id,
                api_football_fixture_id=row.api_football_fixture_id,
                competition_code=row.competition_code,
                competition_name=row.competition_name,
                season_name=row.season_name,
                home_team=row.home_team,
                away_team=row.away_team,
                home_team_logo=row.home_team_logo,
                away_team_logo=row.away_team_logo,
                match_date=row.match_date,
                kickoff_time=row.kickoff_time,
                venue_name=row.venue_name,
                round_name=row.round_name,
                referee_name=row.referee_name,
                status_short=row.status_short,
                completed_match_id=row.completed_match_id,
                last_synced_at=row.last_synced_at,
                odds_count=int(row.odds_count),
            )
            for row in self.session.execute(stmt).mappings()
        ]

    def get_scheduled_fixture_detail(
        self,
        fixture_id: int,
    ) -> dict[str, object] | None:
        home_team = aliased(Team)
        away_team = aliased(Team)
        row = (
            self.session.execute(
                select(
                    ScheduledFixture.id,
                    ScheduledFixture.api_football_fixture_id,
                    Competition.code.label("competition_code"),
                    Competition.name.label("competition_name"),
                    Season.name.label("season_name"),
                    home_team.name.label("home_team"),
                    away_team.name.label("away_team"),
                    home_team.logo_url.label("home_team_logo"),
                    away_team.logo_url.label("away_team_logo"),
                    ScheduledFixture.match_date,
                    ScheduledFixture.kickoff_time,
                    ScheduledFixture.venue_name,
                    ScheduledFixture.round_name,
                    ScheduledFixture.referee_name,
                    ScheduledFixture.status_short,
                    ScheduledFixture.completed_match_id,
                    ScheduledFixture.last_synced_at,
                )
                .select_from(ScheduledFixture)
                .join(Season, ScheduledFixture.season_id == Season.id)
                .join(Competition, Season.competition_id == Competition.id)
                .join(home_team, ScheduledFixture.home_team_id == home_team.id)
                .join(away_team, ScheduledFixture.away_team_id == away_team.id)
                .where(ScheduledFixture.id == fixture_id)
            )
            .mappings()
            .first()
        )

        if row is None:
            return None

        odds_rows = self.session.scalars(
            select(FixtureOdds).where(FixtureOdds.fixture_id == fixture_id)
        ).all()

        return {
            **dict(row),
            "odds": [
                {
                    "source": odd.source,
                    "market": odd.market,
                    "selection": odd.selection,
                    "line": float(odd.line) if odd.line is not None else None,
                    "phase": "prematch",
                    "price": float(odd.price),
                }
                for odd in odds_rows
            ],
        }

    def record_sync_log(
        self,
        *,
        endpoint: str,
        status: str,
        competition_code: str | None = None,
        season_name: str | None = None,
        requests_remaining: int | None = None,
        records_processed: int = 0,
        details: dict[str, object] | None = None,
    ) -> ApiSyncLog:
        log = ApiSyncLog(
            provider="api-football",
            endpoint=endpoint,
            competition_code=competition_code,
            season_name=season_name,
            status=status,
            requests_remaining=requests_remaining,
            records_processed=records_processed,
            details=details,
            created_at=datetime.now(UTC),
        )
        self.session.add(log)
        self.session.flush()
        return log

    def list_sync_logs(self, *, limit: int = 10) -> list[ApiSyncLog]:
        return list(
            self.session.scalars(
                select(ApiSyncLog)
                .order_by(ApiSyncLog.created_at.desc(), ApiSyncLog.id.desc())
                .limit(limit)
            )
        )

    def compute_data_snapshot_hash(
        self,
        *,
        competition_code: str,
        season_names: Sequence[str],
    ) -> str:
        stmt = (
            select(
                func.count(Match.id),
                func.min(Match.match_date),
                func.max(Match.match_date),
                func.sum(Match.home_goals),
                func.sum(Match.away_goals),
            )
            .select_from(Match)
            .join(Season, Match.season_id == Season.id)
            .join(Competition, Season.competition_id == Competition.id)
            .where(
                Competition.code == competition_code,
                Season.name.in_(tuple(season_names)),
            )
        )
        count, min_d, max_d, sum_hg, sum_ag = self.session.execute(stmt).one()
        raw = (
            f"{competition_code}|{'-'.join(sorted(season_names))}|"
            f"{count}|{min_d}|{max_d}|{sum_hg}|{sum_ag}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def save_prediction_snapshot(
        self,
        *,
        model_version: str,
        mode: str,
        competition_code: str,
        seasons_used: Sequence[str],
        home_team: str,
        away_team: str,
        data_snapshot_hash: str,
        payload: dict[str, object],
        as_of_date: date | None = None,
        match_id: int | None = None,
        fixture_id: int | None = None,
    ) -> SavedPrediction:
        slug = f"pred_{secrets.token_urlsafe(6).replace('-', '').replace('_', '')[:8]}"
        record = SavedPrediction(
            slug=slug,
            model_version=model_version,
            mode=mode,
            competition_code=competition_code,
            seasons_used=list(seasons_used),
            home_team=home_team,
            away_team=away_team,
            as_of_date=as_of_date,
            match_id=match_id,
            fixture_id=fixture_id,
            data_snapshot_hash=data_snapshot_hash,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_saved_prediction(self, slug: str) -> SavedPrediction | None:
        return self.session.scalar(
            select(SavedPrediction).where(SavedPrediction.slug == slug)
        )

    def save_evaluation_snapshot(
        self,
        *,
        model_version: str,
        competition_code: str,
        warmup_seasons: Sequence[str],
        evaluation_seasons: Sequence[str],
        data_snapshot_hash: str,
        payload: dict[str, object],
        status: str = "completed",
        error_message: str | None = None,
    ) -> SavedEvaluation:
        slug = f"eval_{secrets.token_urlsafe(6).replace('-', '').replace('_', '')[:8]}"
        record = SavedEvaluation(
            slug=slug,
            status=status,
            model_version=model_version,
            competition_code=competition_code,
            warmup_seasons=list(warmup_seasons),
            evaluation_seasons=list(evaluation_seasons),
            data_snapshot_hash=data_snapshot_hash,
            payload=payload,
            error_message=error_message,
            created_at=datetime.now(UTC),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_saved_evaluation(self, slug: str) -> SavedEvaluation | None:
        return self.session.scalar(
            select(SavedEvaluation).where(SavedEvaluation.slug == slug)
        )

    def list_saved_evaluations(
        self,
        *,
        competition_code: str | None = None,
        limit: int = 10,
    ) -> list[SavedEvaluation]:
        stmt = select(SavedEvaluation).order_by(
            SavedEvaluation.created_at.desc(), SavedEvaluation.id.desc()
        )
        if competition_code:
            stmt = stmt.where(SavedEvaluation.competition_code == competition_code)
        return list(self.session.scalars(stmt.limit(limit)))
