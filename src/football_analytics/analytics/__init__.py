"""Analysis utilities for football data."""

from .backtest import backtest_sequential_poisson
from .features import build_match_features

__all__ = ["backtest_sequential_poisson", "build_match_features"]
