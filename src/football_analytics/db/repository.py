from tracemalloc import Statistic
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import Season, Team, Referee, Match, MatchStatistics


class FootballRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_season(self, name: str) -> Season:
        stmt = select(Season).where(Season.name == name)

        season = self.session.scalar(stmt)

        if season is None:
            season = Season(name=name)
            self.session.add(season)
            self.session.flush()

        return season

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
