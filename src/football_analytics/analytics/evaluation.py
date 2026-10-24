"""Evaluation metrics for three-way football outcome probabilities."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite, log

import pandas as pd

_REQUIRED_COLUMNS = {
    "result",
    "home_win_probability",
    "draw_probability",
    "away_win_probability",
    "probability_mass",
}
_OUTCOMES = ("H", "D", "A")
_PROBABILITY_COLUMNS = (
    "home_win_probability",
    "draw_probability",
    "away_win_probability",
)


@dataclass(frozen=True)
class OutcomeEvaluation:
    """Aggregate quality metrics for a set of H/D/A predictions."""

    matches: int
    log_loss: float
    brier_score: float
    accuracy: float
    mean_probability_mass: float


def evaluate_outcome_probabilities(predictions: pd.DataFrame) -> OutcomeEvaluation:
    """Evaluate finite-matrix H/D/A predictions against completed results.

    Score matrices are intentionally truncated, so their three outcome
    probabilities can sum to less than one. Metrics normalize each row by its
    retained ``probability_mass`` and therefore evaluate the implied three-way
    distribution. ``mean_probability_mass`` reports how much original mass was
    retained before that normalization.
    """
    _validate_predictions(predictions)

    log_loss = 0.0
    brier_score = 0.0
    correct_predictions = 0
    total_probability_mass = 0.0

    for prediction in predictions.itertuples(index=False):
        probabilities = tuple(
            float(getattr(prediction, column)) / float(prediction.probability_mass)
            for column in _PROBABILITY_COLUMNS
        )
        actual_index = _OUTCOMES.index(prediction.result)
        actual_probability = probabilities[actual_index]
        log_loss -= log(actual_probability)
        brier_score += sum(
            (probability - float(index == actual_index)) ** 2
            for index, probability in enumerate(probabilities)
        )
        predicted_index = probabilities.index(max(probabilities))
        correct_predictions += int(predicted_index == actual_index)
        total_probability_mass += float(prediction.probability_mass)

    matches = len(predictions)
    return OutcomeEvaluation(
        matches=matches,
        log_loss=log_loss / matches,
        brier_score=brier_score / matches,
        accuracy=correct_predictions / matches,
        mean_probability_mass=total_probability_mass / matches,
    )


def _validate_predictions(predictions: pd.DataFrame) -> None:
    missing = _REQUIRED_COLUMNS - set(predictions.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if predictions.empty:
        raise ValueError("Cannot evaluate an empty prediction set.")
    if not predictions["result"].isin(_OUTCOMES).all():
        raise ValueError("result must contain only H, D, or A.")

    for prediction in predictions.itertuples(index=False):
        probabilities = tuple(
            float(getattr(prediction, column)) for column in _PROBABILITY_COLUMNS
        )
        probability_mass = float(prediction.probability_mass)
        if not isfinite(probability_mass) or not 0 < probability_mass <= 1:
            raise ValueError("probability_mass must be between 0 and 1")
        has_invalid_probability = any(
            not isfinite(probability) or probability < 0
            for probability in probabilities
        )
        if has_invalid_probability:
            raise ValueError("Outcome probabilities must be finite and non-negative")
        if not isclose(sum(probabilities), probability_mass, rel_tol=1e-9):
            raise ValueError("Outcome probabilities must sum to probability_mass")
        if probabilities[_OUTCOMES.index(prediction.result)] == 0:
            raise ValueError("Actual outcome must have positive probability")
