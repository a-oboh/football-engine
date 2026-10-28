import pandas as pd

REQUIRED_COLUMNS = {
    "Date",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
}


def validate_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )


def validate_matches(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("Dataset contains no matches.")

    if df["HomeTeam"].eq(df["AwayTeam"]).any():
        raise ValueError(
            "Dataset contains matches where home and away teams are identical."
        )

    if not df["FTR"].isin({"H", "D", "A"}).all():
        raise ValueError("Invalid full-time result found.")

    home_goals = pd.to_numeric(df["FTHG"], errors="coerce")
    away_goals = pd.to_numeric(df["FTAG"], errors="coerce")
    if home_goals.isna().any() or away_goals.isna().any():
        raise ValueError("Missing or invalid final scores found.")
    if (home_goals < 0).any() or (away_goals < 0).any():
        raise ValueError("Negative goals found.")

def validate(df: pd.DataFrame) -> None:
    validate_columns(df)
    validate_matches(df)
