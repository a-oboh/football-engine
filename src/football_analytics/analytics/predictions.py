"""Predictions for upcoming fixtures using stored completed match history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from football_analytics.db.repository import CompletedMatch

from .poisson import (
    ExpectedGoals,
    OutcomeProbabilities,
    ScoreProbabilityMatrix,
    SequentialPoissonModel,
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
    """Independent-Poisson probabilities for one upcoming fixture."""

    competition_code: str
    home_team: str
    away_team: str
    expected_goals: ExpectedGoals
    outcomes: OutcomeProbabilities
    score_probabilities: ScoreProbabilityMatrix


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
    return FixturePrediction(
        competition_code=competition_code,
        home_team=home_team,
        away_team=away_team,
        expected_goals=expected_goals,
        outcomes=score_probabilities.outcome_probabilities(),
        score_probabilities=score_probabilities,
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
