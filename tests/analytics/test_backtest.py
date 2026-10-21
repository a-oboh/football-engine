from datetime import date

import pandas as pd
import pytest

from football_analytics.analytics.backtest import (
    backtest_completed_matches,
    backtest_sequential_poisson,
)
from football_analytics.db.repository import CompletedMatch


def _matches() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": "08/08/2025",
                "HomeTeam": "B",
                "AwayTeam": "A",
                "FTHG": 0,
                "FTAG": 2,
                "FTR": "A",
            },
            {
                "Date": "01/08/2025",
                "HomeTeam": "A",
                "AwayTeam": "B",
                "FTHG": 2,
                "FTAG": 1,
                "FTR": "H",
            },
        ]
    )


def test_backtest_orders_matches_and_predicts_before_recording_result() -> None:
    predictions = backtest_sequential_poisson(_matches(), max_goals=10)

    first, second = predictions.to_dict("records")
    assert predictions["match_date"].dt.day.tolist() == [1, 8]
    assert first["expected_home_goals"] == 1.5
    assert first["expected_away_goals"] == 1.2
    assert second["expected_home_goals"] == 2.0
    assert second["expected_away_goals"] == 1.0
    assert first["result"] == "H"
    assert second["result"] == "A"


def test_backtest_returns_outcome_probabilities_and_retained_mass() -> None:
    predictions = backtest_sequential_poisson(_matches(), max_goals=1)

    first = predictions.iloc[0]
    probability_sum = (
        first["home_win_probability"]
        + first["draw_probability"]
        + first["away_win_probability"]
    )
    assert probability_sum == pytest.approx(first["probability_mass"])
    assert 0 < first["probability_mass"] < 1


def test_backtest_completed_matches_uses_canonical_database_records() -> None:
    matches = [
        CompletedMatch(
            competition_code="EPL",
            season_name="2025-26",
            match_date=date(2025, 8, 1),
            kickoff_time=None,
            home_team="A",
            away_team="B",
            home_goals=2,
            away_goals=1,
            result="H",
        ),
        CompletedMatch(
            competition_code="EPL",
            season_name="2025-26",
            match_date=date(2025, 8, 8),
            kickoff_time=None,
            home_team="B",
            away_team="A",
            home_goals=0,
            away_goals=2,
            result="A",
        ),
    ]

    predictions = backtest_completed_matches(matches)

    assert predictions["expected_home_goals"].tolist() == [1.5, 2.0]
    assert predictions["expected_away_goals"].tolist() == [1.2, 1.0]


def test_backtest_completed_matches_rejects_empty_history() -> None:
    with pytest.raises(ValueError, match="empty match history"):
        backtest_completed_matches([])


@pytest.mark.parametrize(
    ("matches", "message"),
    [
        (pd.DataFrame(), "Missing required columns"),
        (_matches().drop(columns="FTR"), "Missing required columns"),
        (
            _matches().assign(HomeTeam="A", AwayTeam="A"),
            "same home and away team",
        ),
        (_matches().assign(FTR="X"), "FTR must contain"),
    ],
)
def test_backtest_rejects_invalid_match_data(
    matches: pd.DataFrame,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        backtest_sequential_poisson(matches)
