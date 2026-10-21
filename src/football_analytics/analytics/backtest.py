"""Chronological evaluation helpers for the sequential Poisson model."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from football_analytics.db.repository import CompletedMatch

from .poisson import SequentialPoissonModel

_REQUIRED_COLUMNS = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"}
_RESULTS = {"H", "D", "A"}


def backtest_sequential_poisson(
    matches: pd.DataFrame,
    *,
    max_goals: int = 10,
    initial_home_goals: float = 1.5,
    initial_away_goals: float = 1.2,
) -> pd.DataFrame:
    """Return leakage-safe Poisson predictions for completed matches.

    Matches are ordered by date, preserving their original order for fixtures on
    the same day. Each prediction is produced before that row's result is
    recorded. Outcome probabilities are approximate because their finite score
    matrix is truncated at ``max_goals``.
    """
    _validate_matches(matches)

    work = matches.copy()
    work["_match_date"] = pd.to_datetime(
        work["Date"], format="%d/%m/%Y", errors="raise"
    )
    work["_input_order"] = range(len(work))
    work = work.sort_values(
        ["_match_date", "_input_order"], kind="mergesort"
    ).reset_index(drop=True)

    model = SequentialPoissonModel(
        initial_home_goals=initial_home_goals,
        initial_away_goals=initial_away_goals,
    )
    predictions: list[dict[str, object]] = []

    for _, match in work.iterrows():
        home_team = match["HomeTeam"]
        away_team = match["AwayTeam"]
        expected_goals = model.predict(home_team, away_team)
        outcomes = expected_goals.score_probability_matrix(
            max_goals=max_goals
        ).outcome_probabilities()

        predictions.append(
            {
                "match_date": match["_match_date"],
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": int(match["FTHG"]),
                "away_goals": int(match["FTAG"]),
                "result": match["FTR"],
                "expected_home_goals": expected_goals.home,
                "expected_away_goals": expected_goals.away,
                "home_win_probability": outcomes.home_win,
                "draw_probability": outcomes.draw,
                "away_win_probability": outcomes.away_win,
                "probability_mass": outcomes.total_probability_mass,
            }
        )

        model.record_result(
            home_team,
            away_team,
            home_goals=int(match["FTHG"]),
            away_goals=int(match["FTAG"]),
        )

    return pd.DataFrame(predictions)


def backtest_completed_matches(
    matches: Sequence[CompletedMatch],
    *,
    max_goals: int = 10,
    initial_home_goals: float = 1.5,
    initial_away_goals: float = 1.2,
) -> pd.DataFrame:
    """Backtest the sequential model using canonical database match records."""
    if not matches:
        raise ValueError("Cannot backtest an empty match history.")

    frame = pd.DataFrame(
        [
            {
                "Date": match.match_date.strftime("%d/%m/%Y"),
                "HomeTeam": match.home_team,
                "AwayTeam": match.away_team,
                "FTHG": match.home_goals,
                "FTAG": match.away_goals,
                "FTR": match.result,
            }
            for match in matches
        ]
    )
    return backtest_sequential_poisson(
        frame,
        max_goals=max_goals,
        initial_home_goals=initial_home_goals,
        initial_away_goals=initial_away_goals,
    )


def _validate_matches(matches: pd.DataFrame) -> None:
    missing = _REQUIRED_COLUMNS - set(matches.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if matches.empty:
        raise ValueError("Cannot backtest an empty dataset.")
    if matches["HomeTeam"].eq(matches["AwayTeam"]).any():
        raise ValueError("A match cannot have the same home and away team.")
    if not matches["FTR"].isin(_RESULTS).all():
        raise ValueError("FTR must contain only H, D, or A.")
