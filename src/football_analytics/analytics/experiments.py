"""Season-based Poisson experiments backed by stored match history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from football_analytics.db.repository import CompletedMatch

from .backtest import backtest_completed_matches
from .evaluation import OutcomeEvaluation, evaluate_outcome_probabilities


class CompletedMatchRepository(Protocol):
    """Repository capability needed to run a competition experiment."""

    def get_completed_matches(
        self,
        *,
        competition_code: str,
        season_names: Sequence[str] | None = None,
    ) -> list[CompletedMatch]: ...


@dataclass(frozen=True)
class CompetitionExperiment:
    """Predictions and metrics for one competition's target seasons."""

    predictions: pd.DataFrame
    evaluation: OutcomeEvaluation


def run_poisson_experiment(
    repository: CompletedMatchRepository,
    *,
    competition_code: str,
    warmup_season_names: Sequence[str],
    evaluation_season_names: Sequence[str],
    max_goals: int = 10,
    initial_home_goals: float = 1.5,
    initial_away_goals: float = 1.2,
) -> CompetitionExperiment:
    """Warm up on prior seasons and score only separate target seasons.

    Match results from warm-up seasons are recorded by the sequential model but
    excluded from the reported metrics. This makes an experiment such as
    training on 2023-24 and 2024-25 before evaluating 2025-26 explicit.
    """
    warmup_seasons = _validate_season_names(
        warmup_season_names,
        label="warmup_season_names",
    )
    evaluation_seasons = _validate_season_names(
        evaluation_season_names,
        label="evaluation_season_names",
    )
    if set(warmup_seasons) & set(evaluation_seasons):
        raise ValueError("Warm-up and evaluation seasons must not overlap")

    matches = repository.get_completed_matches(
        competition_code=competition_code,
        season_names=warmup_seasons + evaluation_seasons,
    )
    if not matches:
        raise ValueError("No matches found for the selected competition and seasons")

    predictions = backtest_completed_matches(
        matches,
        max_goals=max_goals,
        initial_home_goals=initial_home_goals,
        initial_away_goals=initial_away_goals,
    )
    predictions = predictions.copy()
    predictions.insert(
        0,
        "competition_code",
        [match.competition_code for match in matches],
    )
    predictions.insert(1, "season_name", [match.season_name for match in matches])
    target_predictions = predictions.loc[
        predictions["season_name"].isin(evaluation_seasons)
    ].reset_index(drop=True)
    if target_predictions.empty:
        raise ValueError("No matches found for the evaluation seasons")

    return CompetitionExperiment(
        predictions=target_predictions,
        evaluation=evaluate_outcome_probabilities(target_predictions),
    )


def _validate_season_names(
    season_names: Sequence[str],
    *,
    label: str,
) -> tuple[str, ...]:
    if isinstance(season_names, str) or not season_names:
        raise ValueError(f"{label} must contain at least one season name")

    selected_seasons = tuple(season_names)
    if any(not season_name.strip() for season_name in selected_seasons):
        raise ValueError(f"{label} must not contain blank values")
    return selected_seasons
