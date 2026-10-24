from math import log

import pandas as pd
import pytest

from football_analytics.analytics.evaluation import evaluate_outcome_probabilities


def _prediction(
    *,
    result: str = "H",
    home: float = 0.5,
    draw: float = 0.3,
    away: float = 0.2,
    mass: float = 1.0,
) -> dict[str, float | str]:
    return {
        "result": result,
        "home_win_probability": home,
        "draw_probability": draw,
        "away_win_probability": away,
        "probability_mass": mass,
    }


def test_evaluation_calculates_multiclass_metrics() -> None:
    predictions = pd.DataFrame(
        [
            _prediction(result="H", home=0.7, draw=0.2, away=0.1),
            _prediction(result="A", home=0.2, draw=0.2, away=0.6),
        ]
    )

    evaluation = evaluate_outcome_probabilities(predictions)

    assert evaluation.matches == 2
    assert evaluation.log_loss == pytest.approx((-log(0.7) - log(0.6)) / 2)
    assert evaluation.brier_score == pytest.approx((0.14 + 0.24) / 2)
    assert evaluation.accuracy == 1.0
    assert evaluation.mean_probability_mass == 1.0


def test_evaluation_normalizes_truncated_probability_mass() -> None:
    predictions = pd.DataFrame(
        [_prediction(result="H", home=0.4, draw=0.2, away=0.2, mass=0.8)]
    )

    evaluation = evaluate_outcome_probabilities(predictions)

    assert evaluation.log_loss == pytest.approx(-log(0.5))
    assert evaluation.brier_score == pytest.approx(0.375)
    assert evaluation.mean_probability_mass == 0.8


@pytest.mark.parametrize(
    ("predictions", "message"),
    [
        (pd.DataFrame(), "Missing required columns"),
        (pd.DataFrame([_prediction(result="X")]), "result must contain"),
        (
            pd.DataFrame([_prediction(home=0.4, draw=0.2, away=0.2, mass=0.7)]),
            "sum to probability_mass",
        ),
        (
            pd.DataFrame([_prediction(result="H", home=0.0, draw=0.5, away=0.5)]),
            "Actual outcome",
        ),
    ],
)
def test_evaluation_rejects_invalid_predictions(
    predictions: pd.DataFrame,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        evaluate_outcome_probabilities(predictions)
