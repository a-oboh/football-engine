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
        raise ValueError(f"Missing required columns: {missing}")