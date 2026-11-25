"""Evaluation metrics, calibration bins, and baseline comparisons for 1X2 forecasts."""

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


@dataclass(frozen=True)
class CalibrationBin:
    """Reliability curve bucket comparing predicted probability to empirical rate."""

    bin_index: int
    bin_lower: float
    bin_upper: float
    sample_count: int
    mean_predicted_probability: float
    observed_frequency: float


@dataclass(frozen=True)
class OutcomeFrequencySummary:
    """Predicted vs. observed frequencies across Home Win, Draw, and Away Win."""

    predicted_home: float
    predicted_draw: float
    predicted_away: float
    observed_home: float
    observed_draw: float
    observed_away: float


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


def compute_calibration_curve(
    predictions: pd.DataFrame,
    *,
    num_bins: int = 10,
) -> tuple[CalibrationBin, ...]:
    """Pool normalized H/D/A probabilities across matches into reliability bins."""
    _validate_predictions(predictions)
    if num_bins < 2:
        raise ValueError("num_bins must be at least 2")

    pairs: list[tuple[float, float]] = []
    for prediction in predictions.itertuples(index=False):
        mass = float(prediction.probability_mass)
        probabilities = tuple(
            float(getattr(prediction, column)) / mass for column in _PROBABILITY_COLUMNS
        )
        actual_index = _OUTCOMES.index(prediction.result)
        for idx, prob in enumerate(probabilities):
            pairs.append((prob, 1.0 if idx == actual_index else 0.0))

    bins: list[CalibrationBin] = []
    for b in range(num_bins):
        lower = b / num_bins
        upper = (b + 1) / num_bins
        if b == num_bins - 1:
            bucket = [p for p in pairs if lower <= p[0] <= upper]
        else:
            bucket = [p for p in pairs if lower <= p[0] < upper]

        count = len(bucket)
        mean_pred = (
            sum(p[0] for p in bucket) / count if count > 0 else (lower + upper) / 2
        )
        obs_freq = sum(p[1] for p in bucket) / count if count > 0 else 0.0
        bins.append(
            CalibrationBin(
                bin_index=b,
                bin_lower=round(lower, 2),
                bin_upper=round(upper, 2),
                sample_count=count,
                mean_predicted_probability=mean_pred,
                observed_frequency=obs_freq,
            )
        )
    return tuple(bins)


def compute_outcome_frequencies(
    predictions: pd.DataFrame,
) -> OutcomeFrequencySummary:
    """Compare average predicted H/D/A probabilities with empirical frequencies."""
    _validate_predictions(predictions)
    n = len(predictions)
    pred_h = 0.0
    pred_d = 0.0
    pred_a = 0.0
    obs_h = 0
    obs_d = 0
    obs_a = 0

    for row in predictions.itertuples(index=False):
        mass = float(row.probability_mass)
        pred_h += float(row.home_win_probability) / mass
        pred_d += float(row.draw_probability) / mass
        pred_a += float(row.away_win_probability) / mass
        if row.result == "H":
            obs_h += 1
        elif row.result == "D":
            obs_d += 1
        else:
            obs_a += 1

    return OutcomeFrequencySummary(
        predicted_home=pred_h / n,
        predicted_draw=pred_d / n,
        predicted_away=pred_a / n,
        observed_home=obs_h / n,
        observed_draw=obs_d / n,
        observed_away=obs_a / n,
    )


def evaluate_naive_league_baseline(
    predictions: pd.DataFrame,
    *,
    prior_home_rate: float = 0.45,
    prior_draw_rate: float = 0.25,
    prior_away_rate: float = 0.30,
) -> OutcomeEvaluation:
    """Evaluate a sequential empirical H/D/A baseline on the same match set."""
    _validate_predictions(predictions)
    baseline_rows: list[dict[str, object]] = []
    h_count = 0
    d_count = 0
    a_count = 0
    total = 0

    for row in predictions.itertuples(index=False):
        if total == 0:
            p_h, p_d, p_a = prior_home_rate, prior_draw_rate, prior_away_rate
        else:
            # Laplace-smoothed running empirical frequencies
            p_h = (h_count + 1.5) / (total + 3.5)
            p_d = (d_count + 1.0) / (total + 3.5)
            p_a = (a_count + 1.0) / (total + 3.5)

        baseline_rows.append(
            {
                "result": row.result,
                "home_win_probability": p_h,
                "draw_probability": p_d,
                "away_win_probability": p_a,
                "probability_mass": p_h + p_d + p_a,
            }
        )
        total += 1
        if row.result == "H":
            h_count += 1
        elif row.result == "D":
            d_count += 1
        else:
            a_count += 1

    return evaluate_outcome_probabilities(pd.DataFrame(baseline_rows))


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
