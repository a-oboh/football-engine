"""Analysis utilities for football data."""

from .backtest import backtest_completed_matches, backtest_sequential_poisson
from .evaluation import OutcomeEvaluation, evaluate_outcome_probabilities
from .experiments import CompetitionExperiment, run_poisson_experiment
from .features import build_match_features

__all__ = [
    "backtest_completed_matches",
    "backtest_sequential_poisson",
    "build_match_features",
    "CompetitionExperiment",
    "evaluate_outcome_probabilities",
    "OutcomeEvaluation",
    "run_poisson_experiment",
]
