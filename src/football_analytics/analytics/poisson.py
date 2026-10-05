"""A small, sequential Poisson baseline for football scores."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, factorial


def poisson_probability(goals: int, expected_goals: float) -> float:
    """Return the probability of scoring exactly ``goals``."""
    if goals < 0:
        raise ValueError("goals must not be negative")
    if expected_goals < 0:
        raise ValueError("expected_goals must not be negative")

    return exp(-expected_goals) * expected_goals**goals / factorial(goals)


@dataclass(frozen=True)
class ExpectedGoals:
    home: float
    away: float


@dataclass
class _VenueRecord:
    matches: int = 0
    goals_for: int = 0
    goals_against: int = 0

    def record(self, goals_for: int, goals_against: int) -> None:
        self.matches += 1
        self.goals_for += goals_for
        self.goals_against += goals_against

    def goals_for_per_match(self) -> float | None:
        if not self.matches:
            return None
        return self.goals_for / self.matches

    def goals_against_per_match(self) -> float | None:
        if not self.matches:
            return None
        return self.goals_against / self.matches


@dataclass
class _TeamRecord:
    home: _VenueRecord = field(default_factory=_VenueRecord)
    away: _VenueRecord = field(default_factory=_VenueRecord)


class SequentialPoissonModel:
    """Estimate score expectations using only results recorded so far.

    The caller must predict a match before recording its result. New teams use
    neutral strengths of 1.0 until they have venue-specific history.
    """

    def __init__(
        self,
        *,
        initial_home_goals: float = 1.5,
        initial_away_goals: float = 1.2,
    ) -> None:
        if initial_home_goals <= 0 or initial_away_goals <= 0:
            raise ValueError("Initial league goal rates must be positive")

        self._initial_home_goals = initial_home_goals
        self._initial_away_goals = initial_away_goals
        self._teams: dict[str, _TeamRecord] = {}
        self._matches = 0
        self._home_goals = 0
        self._away_goals = 0

    def predict(self, home_team: str, away_team: str) -> ExpectedGoals:
        """Return expected goals from the state before this match."""
        self._validate_teams(home_team, away_team)

        league_home_goals = self._league_home_goals
        league_away_goals = self._league_away_goals
        home = self._team_record(home_team)
        away = self._team_record(away_team)

        home_attack = self._relative_rate(
            home.home.goals_for_per_match(), league_home_goals
        )
        away_defence = self._relative_rate(
            away.away.goals_against_per_match(), league_home_goals
        )
        away_attack = self._relative_rate(
            away.away.goals_for_per_match(), league_away_goals
        )
        home_defence = self._relative_rate(
            home.home.goals_against_per_match(), league_away_goals
        )

        return ExpectedGoals(
            home=league_home_goals * home_attack * away_defence,
            away=league_away_goals * away_attack * home_defence,
        )

    def record_result(
        self,
        home_team: str,
        away_team: str,
        home_goals: int,
        away_goals: int,
    ) -> None:
        """Update state after a completed match."""
        self._validate_teams(home_team, away_team)
        if home_goals < 0 or away_goals < 0:
            raise ValueError("Goals must not be negative")

        self._team_record(home_team).home.record(home_goals, away_goals)
        self._team_record(away_team).away.record(away_goals, home_goals)
        self._matches += 1
        self._home_goals += home_goals
        self._away_goals += away_goals

    @property
    def _league_home_goals(self) -> float:
        if not self._matches:
            return self._initial_home_goals
        return self._home_goals / self._matches

    @property
    def _league_away_goals(self) -> float:
        if not self._matches:
            return self._initial_away_goals
        return self._away_goals / self._matches

    def _team_record(self, team: str) -> _TeamRecord:
        if team not in self._teams:
            self._teams[team] = _TeamRecord()
        return self._teams[team]

    @staticmethod
    def _relative_rate(rate: float | None, league_rate: float) -> float:
        if rate is None or league_rate == 0:
            return 1.0
        return rate / league_rate

    @staticmethod
    def _validate_teams(home_team: str, away_team: str) -> None:
        if home_team == away_team:
            raise ValueError("A match cannot have the same home and away team")
