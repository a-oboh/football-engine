import pandas as pd


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="raise")

    if "Time" in df:
        df["Time"] = pd.to_datetime(
            df["Time"],
            format="%H:%M",
            errors="coerce",
        ).dt.time

    return df
