"""Build leakage-safe, match-level features from historical results."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "Date",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
}

_RESULT_POINTS = {"H": (3, 0), "D": (1, 1), "A": (0, 3)}


@dataclass
class _TeamHistory:
    matches: int = 0
    points: int = 0
    goals_for: int = 0
    goals_against: int = 0
    recent_points: deque[int] = field(default_factory=deque)
    recent_goal_differences: deque[int] = field(default_factory=deque)

    def snapshot(self) -> dict[str, float | int]:
        matches = self.matches
        recent_matches = len(self.recent_points)

        return {
            "matches_played": matches,
            "points_per_match": self.points / matches if matches else 0.0,
            "goals_for_per_match": self.goals_for / matches if matches else 0.0,
            "goals_against_per_match": (
                self.goals_against / matches if matches else 0.0
            ),
            "form_points": sum(self.recent_points),
            "form_points_per_match": (
                sum(self.recent_points) / recent_matches if recent_matches else 0.0
            ),
            "form_goal_difference": sum(self.recent_goal_differences),
        }

    def record(self, points: int, goals_for: int, goals_against: int) -> None:
        self.matches += 1
        self.points += points
        self.goals_for += goals_for
        self.goals_against += goals_against
        self.recent_points.append(points)
        self.recent_goal_differences.append(goals_for - goals_against)


def _validate_input(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if df.empty:
        raise ValueError("Cannot build features from an empty dataset.")

    if df["HomeTeam"].eq(df["AwayTeam"]).any():
        raise ValueError("A match cannot have the same home and away team.")

    if not df["FTR"].isin(_RESULT_POINTS).all():
        raise ValueError("FTR must contain only H, D, or A.")


def build_match_features(
    df: pd.DataFrame,
    *,
    form_window: int = 5,
) -> pd.DataFrame:
    """Return one leakage-safe feature row per match.

    Features are calculated from matches that occurred before the current row.
    The current match's result and score are included as target columns, so the
    returned frame can be passed directly to analysis or model-training code.
    """
    _validate_input(df)
    if form_window < 1:
        raise ValueError("form_window must be at least 1.")

    work = df.copy()
    work["_match_date"] = pd.to_datetime(work["Date"], errors="raise")
    work["_input_order"] = range(len(work))
    work = work.sort_values(
        ["_match_date", "_input_order"], kind="mergesort"
    ).reset_index(drop=True)

    histories: dict[str, _TeamHistory] = {}
    rows: list[dict[str, Any]] = []

    def history_for(team: str) -> _TeamHistory:
        if team not in histories:
            histories[team] = _TeamHistory(
                recent_points=deque(maxlen=form_window),
                recent_goal_differences=deque(maxlen=form_window),
            )
        return histories[team]

    for _, match in work.iterrows():
        home_team = match["HomeTeam"]
        away_team = match["AwayTeam"]
        home_history = history_for(home_team)
        away_history = history_for(away_team)

        home_snapshot = home_history.snapshot()
        away_snapshot = away_history.snapshot()
        row: dict[str, Any] = {
            "match_date": match["_match_date"],
            "home_team": home_team,
            "away_team": away_team,
            "home_goals": int(match["FTHG"]),
            "away_goals": int(match["FTAG"]),
            "result": match["FTR"],
            "total_goals": int(match["FTHG"]) + int(match["FTAG"]),
            "goal_difference": int(match["FTHG"]) - int(match["FTAG"]),
        }

        for name, value in home_snapshot.items():
            row[f"home_{name}"] = value
        for name, value in away_snapshot.items():
            row[f"away_{name}"] = value

        rows.append(row)

        home_points, away_points = _RESULT_POINTS[match["FTR"]]
        home_history.record(
            home_points,
            int(match["FTHG"]),
            int(match["FTAG"]),
        )
        away_history.record(
            away_points,
            int(match["FTAG"]),
            int(match["FTHG"]),
        )

    return pd.DataFrame(rows)
