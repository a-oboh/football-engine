from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from .models import (
    Bookmaker,
    Competition,
    Match,
    MatchStatistics,
    Odds,
    Referee,
    Season,
    Team,
)


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


class FootballRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_competition(self, *, name: str, code: str) -> Competition:
        competition = self.session.scalar(
            select(Competition).where(Competition.code == code)
        )

        if competition is not None:
            if competition.name != name:
                raise ValueError("Competition code already belongs to another name")
            return competition

        existing_name = self.session.scalar(
            select(Competition).where(Competition.name == name)
        )
        if existing_name is not None:
            raise ValueError("Competition name already belongs to another code")

        competition = Competition(name=name, code=code)
        self.session.add(competition)
        self.session.flush()
        return competition

    def get_or_create_season(
        self,
        *,
        competition: Competition,
        name: str,
    ) -> Season:
        stmt = select(Season).where(
            Season.competition_id == competition.id,
            Season.name == name,
        )

        season = self.session.scalar(stmt)

        if season is None:
            season = Season(competition=competition, name=name)
            self.session.add(season)
            self.session.flush()

        return season

    def get_completed_matches(
        self,
        *,
        competition_code: str,
        season_names: Sequence[str] | None = None,
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
                Competition.code.label("competition_code"),
                Season.name.label("season_name"),
                Match.match_date,
                Match.kickoff_time,
                home_team.name.label("home_team"),
                away_team.name.label("away_team"),
                Match.home_goals,
                Match.away_goals,
                Match.result,
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

        return [
            CompletedMatch(
                competition_code=row.competition_code,
                season_name=row.season_name,
                match_date=row.match_date,
                kickoff_time=row.kickoff_time,
                home_team=row.home_team,
                away_team=row.away_team,
                home_goals=row.home_goals,
                away_goals=row.away_goals,
                result=row.result,
            )
            for row in self.session.execute(statement).mappings()
        ]

    def get_or_create_team(self, name: str) -> Team:
        team = self.session.scalar(select(Team).where(Team.name == name))

        if team is None:
            team = Team(name=name)
            self.session.add(team)
            self.session.flush()

        return team

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
        match_date,
        kickoff_time,
        home_goals: int,
        away_goals: int,
        result: str,
        home_half_time_goals: int,
        away_half_time_goals: int,
        half_time_result: str,
    ) -> Match:
        match = Match(
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

    def create_match_statistics(
        self,
        *,
        match_id: int,
        home_shots: int,
        away_shots: int,
        home_shots_on_target: int,
        away_shots_on_target: int,
        home_fouls: int,
        away_fouls: int,
        home_corners: int,
        away_corners: int,
        home_yellow_cards: int,
        away_yellow_cards: int,
        home_red_cards: int,
        away_red_cards: int,
    ) -> MatchStatistics:
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
        bookmaker = self.session.query(Bookmaker).filter_by(name=name).one_or_none()

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
