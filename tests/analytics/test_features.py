import pandas as pd
import pytest

from football_analytics.analytics.features import build_match_features


def test_build_match_features_uses_only_prior_matches() -> None:
    matches = pd.DataFrame(
        [
            {
                "Date": "01/08/2025",
                "HomeTeam": "A",
                "AwayTeam": "B",
                "FTHG": 2,
                "FTAG": 0,
                "FTR": "H",
            },
            {
                "Date": "08/08/2025",
                "HomeTeam": "B",
                "AwayTeam": "A",
                "FTHG": 1,
                "FTAG": 1,
                "FTR": "D",
            },
        ]
    )

    features = build_match_features(matches, form_window=5)

    first, second = features.to_dict("records")
    assert first["home_matches_played"] == 0
    assert first["away_points_per_match"] == 0.0
    assert second["home_matches_played"] == 1
    assert second["home_points_per_match"] == 0.0
    assert second["away_points_per_match"] == 3.0
    assert second["away_form_points"] == 3
    assert second["total_goals"] == 2


def test_build_match_features_sorts_by_date_stably() -> None:
    matches = pd.DataFrame(
        [
            {
                "Date": "08/08/2025",
                "HomeTeam": "B",
                "AwayTeam": "A",
                "FTHG": 0,
                "FTAG": 1,
                "FTR": "A",
            },
            {
                "Date": "01/08/2025",
                "HomeTeam": "A",
                "AwayTeam": "B",
                "FTHG": 2,
                "FTAG": 0,
                "FTR": "H",
            },
        ]
    )

    features = build_match_features(matches)

    assert features["match_date"].dt.day.tolist() == [1, 8]
    assert features.iloc[1]["away_points_per_match"] == 3.0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"form_window": 0}, "form_window"),
        ({}, "Missing required columns"),
    ],
)
def test_build_match_features_rejects_invalid_input(
    kwargs: dict[str, int],
    message: str,
) -> None:
    matches = pd.DataFrame(
        [
            {
                "Date": "01/08/2025",
                "HomeTeam": "A",
                "AwayTeam": "B",
                "FTHG": 2,
                "FTAG": 0,
                "FTR": "H",
            }
        ]
    )
    if not kwargs:
        matches = matches.drop(columns="FTR")

    with pytest.raises(ValueError, match=message):
        build_match_features(matches, **kwargs)
