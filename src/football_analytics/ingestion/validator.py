import pandas as pd


REQUIRED_COLUMNS = {
    "Div",
    "Date",
    "Time",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "FTR",
    "HTHG",
    "HTAG",
    "HTR",
    "Referee",
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
        raise ValueError("Dataset contains matches where home and away teams are identical.")

    if not df["FTR"].isin({"H", "D", "A"}).all():
        raise ValueError("Invalid full-time result found.")

    if (df["FTHG"] < 0).any() or (df["FTAG"] < 0).any():
        raise ValueError("Negative goals found.")

def validate(df: pd.DataFrame) -> None:
    validate_columns(df)
    validate_matches(df)