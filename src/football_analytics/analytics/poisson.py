"""A small, sequential Poisson baseline for football scores."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, factorial, isfinite
from numbers import Integral, Real


def poisson_probability(goals: int, expected_goals: float) -> float:
    """Return the probability of scoring exactly ``goals``."""
    if not isinstance(goals, Integral) or isinstance(goals, bool):
        raise ValueError("goals must be an integer")
    if goals < 0:
        raise ValueError("goals must not be negative")
    if not _is_finite_number(expected_goals):
        raise ValueError("expected_goals must be a finite number")
    if expected_goals < 0:
        raise ValueError("expected_goals must not be negative")

    return exp(-expected_goals) * expected_goals**goals / factorial(goals)


@dataclass(frozen=True)
class ExpectedGoals:
    home: float
    away: float

    def __post_init__(self) -> None:
        if not _is_finite_number(self.home) or not _is_finite_number(self.away):
            raise ValueError("Expected goals must be finite numbers")
        if self.home < 0 or self.away < 0:
            raise ValueError("Expected goals must not be negative")

    def score_probability_matrix(
        self,
        *,
        max_goals: int = 10,
    ) -> ScoreProbabilityMatrix:
        """Return finite independent Poisson score probabilities.

        The matrix is truncated at ``max_goals`` for both teams and is not
        renormalized, so outcome probabilities are approximate. Use
        ``total_probability_mass`` to inspect how much probability the finite
        grid retained.
        """
        return ScoreProbabilityMatrix.from_expected_goals(self, max_goals=max_goals)


@dataclass(frozen=True)
class OutcomeProbabilities:
    """Home/draw/away probabilities summed over a finite score matrix."""

    home_win: float
    draw: float
    away_win: float
    total_probability_mass: float


@dataclass(frozen=True)
class ScoreProbabilityMatrix:
    """Finite, truncated joint score probabilities for one match.

    ``probabilities[home_goals][away_goals]`` stores the independent Poisson
    probability for that exact score. Because the matrix only includes scores
    from 0 through ``max_goals``, values are approximate and intentionally not
    normalized to sum to 1.0.
    """

    max_goals: int
    probabilities: tuple[tuple[float, ...], ...]

    @classmethod
    def from_expected_goals(
        cls,
        expected_goals: ExpectedGoals,
        *,
        max_goals: int = 10,
    ) -> ScoreProbabilityMatrix:
        """Build a finite joint score matrix from expected goals."""
        _validate_max_goals(max_goals)

        home_probabilities = tuple(
            poisson_probability(goals, expected_goals.home)
            for goals in range(max_goals + 1)
        )
        away_probabilities = tuple(
            poisson_probability(goals, expected_goals.away)
            for goals in range(max_goals + 1)
        )

        return cls(
            max_goals=max_goals,
            probabilities=tuple(
                tuple(
                    home_probability * away_probability
                    for away_probability in away_probabilities
                )
                for home_probability in home_probabilities
            ),
        )

    @property
    def shape(self) -> tuple[int, int]:
        size = self.max_goals + 1
        return (size, size)

    @property
    def total_probability_mass(self) -> float:
        """Return the unnormalized probability mass retained by the finite grid."""
        return sum(sum(row) for row in self.probabilities)

    def probability(self, home_goals: int, away_goals: int) -> float:
        """Return the finite-matrix probability for one exact score."""
        _validate_score_index(home_goals, self.max_goals, label="home_goals")
        _validate_score_index(away_goals, self.max_goals, label="away_goals")
        return self.probabilities[home_goals][away_goals]

    def outcome_probabilities(self) -> OutcomeProbabilities:
        """Aggregate the finite score matrix into home/draw/away probabilities."""
        home_win = 0.0
        draw = 0.0
        away_win = 0.0

        for home_goals, row in enumerate(self.probabilities):
            for away_goals, probability in enumerate(row):
                if home_goals > away_goals:
                    home_win += probability
                elif home_goals == away_goals:
                    draw += probability
                else:
                    away_win += probability

        return OutcomeProbabilities(
            home_win=home_win,
            draw=draw,
            away_win=away_win,
            total_probability_mass=home_win + draw + away_win,
        )


@dataclass
class _VenueRecord:
    # Track one team's results in a single venue context: home or away.
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
    # Keep home and away form separate because football scoring rates are
    # strongly venue-dependent.
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

        # Predictions are based only on league and team history already recorded,
        # so the match being predicted cannot leak into its own expectation.
        league_home_goals = self._league_home_goals
        league_away_goals = self._league_away_goals
        home = self._team_record(home_team)
        away = self._team_record(away_team)

        # Convert each team's venue-specific scoring profile into a multiplier
        # around the current league average. Missing history stays neutral.
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
            # Standard independent Poisson baseline: league rate adjusted by the
            # attacking team's strength and the opponent's defensive weakness.
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

        # Store the same match from both perspectives, preserving venue context
        # for later home-vs-away predictions.
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
        # Teams without relevant venue history use a neutral strength multiplier.
        if rate is None or league_rate == 0:
            return 1.0
        return rate / league_rate

    @staticmethod
    def _validate_teams(home_team: str, away_team: str) -> None:
        if home_team == away_team:
            raise ValueError("A match cannot have the same home and away team")


def _validate_max_goals(max_goals: int) -> None:
    if not isinstance(max_goals, Integral) or isinstance(max_goals, bool):
        raise ValueError("max_goals must be an integer")
    if max_goals < 0:
        raise ValueError("max_goals must not be negative")


def _validate_score_index(goals: int, max_goals: int, *, label: str) -> None:
    if not isinstance(goals, Integral) or isinstance(goals, bool):
        raise ValueError(f"{label} must be an integer")
    if goals < 0:
        raise ValueError(f"{label} must not be negative")
    if goals > max_goals:
        raise ValueError(f"{label} must be within the finite score matrix")


def _is_finite_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and isfinite(value)
