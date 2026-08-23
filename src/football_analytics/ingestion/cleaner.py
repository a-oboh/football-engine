import pandas as pd


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["Date"] = pd.to_datetime(
        df["Date"],
        format="%d/%m/%Y",
    )

    df["Time"] = pd.to_datetime(
        df["Time"],
        format="%H:%M",
    ).dt.time

    return df