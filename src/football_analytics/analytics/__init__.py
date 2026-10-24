"""Analysis utilities for football data."""

from .backtest import backtest_completed_matches, backtest_sequential_poisson
from .evaluation import OutcomeEvaluation, evaluate_outcome_probabilities
from .features import build_match_features

__all__ = [
    "backtest_completed_matches",
    "backtest_sequential_poisson",
    "build_match_features",
    "evaluate_outcome_probabilities",
    "OutcomeEvaluation",
]
