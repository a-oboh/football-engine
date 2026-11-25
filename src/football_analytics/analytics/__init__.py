"""Analytics utilities for feature engineering and match outcome baselines."""

from .backtest import backtest_completed_matches, backtest_sequential_poisson
from .evaluation import (
    CalibrationBin,
    OutcomeEvaluation,
    OutcomeFrequencySummary,
    compute_calibration_curve,
    compute_outcome_frequencies,
    evaluate_naive_league_baseline,
    evaluate_outcome_probabilities,
)
from .experiments import CompetitionExperiment, run_poisson_experiment
from .features import build_match_features
from .poisson import (
    ExpectedGoals,
    MatchupExplanation,
    OutcomeProbabilities,
    ScoreProbabilityMatrix,
    SequentialPoissonModel,
    TeamVenueStrength,
    poisson_probability,
)
from .predictions import (
    BettingMarkets,
    FixturePrediction,
    HalfTimePrediction,
    MarketSelection,
    PredictedScore,
    predict_fixture,
)

__all__ = [
    "BettingMarkets",
    "CalibrationBin",
    "CompetitionExperiment",
    "ExpectedGoals",
    "FixturePrediction",
    "HalfTimePrediction",
    "MarketSelection",
    "MatchupExplanation",
    "OutcomeEvaluation",
    "OutcomeFrequencySummary",
    "OutcomeProbabilities",
    "PredictedScore",
    "ScoreProbabilityMatrix",
    "SequentialPoissonModel",
    "TeamVenueStrength",
    "backtest_completed_matches",
    "backtest_sequential_poisson",
    "build_match_features",
    "compute_calibration_curve",
    "compute_outcome_frequencies",
    "evaluate_naive_league_baseline",
    "evaluate_outcome_probabilities",
    "poisson_probability",
    "predict_fixture",
    "run_poisson_experiment",
]
