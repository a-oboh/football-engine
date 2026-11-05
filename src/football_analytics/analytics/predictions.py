"""Predictions for upcoming fixtures using stored completed match history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp
from typing import Protocol

from football_analytics.db.repository import CompletedMatch

from .poisson import (
    ExpectedGoals,
    OutcomeProbabilities,
    ScoreProbabilityMatrix,
    SequentialPoissonModel,
    poisson_probability,
)


class CompletedHistoryRepository(Protocol):
    """Repository capability needed to predict an upcoming fixture."""

    def get_completed_matches(
        self,
        *,
        competition_code: str,
        season_names: Sequence[str] | None = None,
    ) -> list[CompletedMatch]: ...


@dataclass(frozen=True)
class FixturePrediction:
    """Score and betting-market forecast for one upcoming fixture.

    Decimal prices are fair odds calculated directly from this model's
    probabilities. They intentionally do not include a bookmaker margin.
    """

    competition_code: str
    home_team: str
    away_team: str
    expected_goals: ExpectedGoals
    outcomes: OutcomeProbabilities
    score_probabilities: ScoreProbabilityMatrix
    full_time_score: PredictedScore
    half_time: HalfTimePrediction
    markets: BettingMarkets


@dataclass(frozen=True)
class PredictedScore:
    """The most likely exact score from a finite probability matrix."""

    home_goals: int
    away_goals: int
    probability: float


@dataclass(frozen=True)
class HalfTimePrediction:
    """Half-time forecast calibrated from observed half-time scoring rates."""

    expected_goals: ExpectedGoals
    score: PredictedScore


@dataclass(frozen=True)
class MarketSelection:
    """A model probability and its corresponding no-margin decimal price."""

    probability: float
    fair_odds: float | None


@dataclass(frozen=True)
class BettingMarkets:
    """Core full-time betting markets derived from independent Poisson goals."""

    home_win: MarketSelection
    draw: MarketSelection
    away_win: MarketSelection
    over_2_5_goals: MarketSelection
    under_2_5_goals: MarketSelection
    both_teams_to_score_yes: MarketSelection
    both_teams_to_score_no: MarketSelection


def predict_fixture(
    repository: CompletedHistoryRepository,
    *,
    competition_code: str,
    season_names: Sequence[str],
    home_team: str,
    away_team: str,
    max_goals: int = 10,
    initial_home_goals: float = 1.5,
    initial_away_goals: float = 1.2,
) -> FixturePrediction:
    """Predict an upcoming fixture from completed results in selected seasons."""
    _validate_fixture(home_team=home_team, away_team=away_team)
    selected_seasons = _validate_season_names(season_names)
    matches = repository.get_completed_matches(
        competition_code=competition_code,
        season_names=selected_seasons,
    )
    if not matches:
        raise ValueError("No completed matches found for the selected seasons")

    known_teams = {
        team
        for match in matches
        for team in (match.home_team, match.away_team)
    }
    unknown_teams = {home_team, away_team} - known_teams
    if unknown_teams:
        raise ValueError(
            "Fixture contains teams absent from match history: "
            f"{sorted(unknown_teams)}"
        )

    model = SequentialPoissonModel(
        initial_home_goals=initial_home_goals,
        initial_away_goals=initial_away_goals,
    )
    for match in matches:
        model.record_result(
            match.home_team,
            match.away_team,
            match.home_goals,
            match.away_goals,
        )

    expected_goals = model.predict(home_team, away_team)
    score_probabilities = expected_goals.score_probability_matrix(max_goals=max_goals)
    half_time_expected_goals = _half_time_expected_goals(
        matches,
        full_time_expected_goals=expected_goals,
    )
    half_time_scores = half_time_expected_goals.score_probability_matrix(
        max_goals=max_goals
    )
    outcomes = score_probabilities.outcome_probabilities()
    return FixturePrediction(
        competition_code=competition_code,
        home_team=home_team,
        away_team=away_team,
        expected_goals=expected_goals,
        outcomes=outcomes,
        score_probabilities=score_probabilities,
        full_time_score=_most_likely_score(score_probabilities),
        half_time=HalfTimePrediction(
            expected_goals=half_time_expected_goals,
            score=_most_likely_score(half_time_scores),
        ),
        markets=_build_markets(expected_goals, outcomes),
    )


def _validate_fixture(*, home_team: str, away_team: str) -> None:
    if not home_team.strip() or not away_team.strip():
        raise ValueError("Fixture teams must not be blank")
    if home_team == away_team:
        raise ValueError("A fixture cannot have the same home and away team")


def _validate_season_names(season_names: Sequence[str]) -> tuple[str, ...]:
    if isinstance(season_names, str) or not season_names:
        raise ValueError("season_names must contain at least one season name")

    selected_seasons = tuple(season_names)
    if any(not season_name.strip() for season_name in selected_seasons):
        raise ValueError("season_names must not contain blank values")
    return selected_seasons


def _half_time_expected_goals(
    matches: Sequence[CompletedMatch],
    *,
    full_time_expected_goals: ExpectedGoals,
) -> ExpectedGoals:
    """Scale full-time expectations by the historical scoring share at half-time."""
    half_time_matches = [
        match
        for match in matches
        if match.home_half_time_goals is not None
        and match.away_half_time_goals is not None
    ]
    if not half_time_matches:
        raise ValueError("No half-time results found for the selected seasons")

    home_half_time_goals = sum(
        match.home_half_time_goals for match in half_time_matches
    )
    away_half_time_goals = sum(
        match.away_half_time_goals for match in half_time_matches
    )
    home_full_time_goals = sum(match.home_goals for match in half_time_matches)
    away_full_time_goals = sum(match.away_goals for match in half_time_matches)

    return ExpectedGoals(
        home=full_time_expected_goals.home
        * _scoring_share(home_half_time_goals, home_full_time_goals),
        away=full_time_expected_goals.away
        * _scoring_share(away_half_time_goals, away_full_time_goals),
    )


def _scoring_share(half_time_goals: int, full_time_goals: int) -> float:
    if not full_time_goals:
        return 0.5
    return half_time_goals / full_time_goals


def _most_likely_score(matrix: ScoreProbabilityMatrix) -> PredictedScore:
    home_goals, away_goals, probability = max(
        (
            (home_goals, away_goals, probability)
            for home_goals, row in enumerate(matrix.probabilities)
            for away_goals, probability in enumerate(row)
        ),
        key=lambda score: score[2],
    )
    return PredictedScore(
        home_goals=home_goals,
        away_goals=away_goals,
        probability=probability,
    )


def _build_markets(
    expected_goals: ExpectedGoals,
    outcomes: OutcomeProbabilities,
) -> BettingMarkets:
    total_goals = expected_goals.home + expected_goals.away
    under_2_5 = sum(poisson_probability(goals, total_goals) for goals in range(3))
    both_teams_to_score_no = (
        exp(-expected_goals.home)
        + exp(-expected_goals.away)
        - exp(-total_goals)
    )

    return BettingMarkets(
        home_win=_selection(outcomes.home_win),
        draw=_selection(outcomes.draw),
        away_win=_selection(outcomes.away_win),
        over_2_5_goals=_selection(1 - under_2_5),
        under_2_5_goals=_selection(under_2_5),
        both_teams_to_score_yes=_selection(1 - both_teams_to_score_no),
        both_teams_to_score_no=_selection(both_teams_to_score_no),
    )


def _selection(probability: float) -> MarketSelection:
    return MarketSelection(
        probability=probability,
        fair_odds=(1 / probability if probability else None),
    )
