from pandas import pd


def profile(df: pd.DataFrame) -> None:
    print("\n--- SHAPE ---")
    print(df.shape)

    print("\n--- DATA TYPES ---")
    print(df.dtypes)

    print("\n--- MISSING VALUES ---")
    print(df.isna().sum())

    print("\n--- DUPLICATES ---")
    print(df.duplicated().sum())

    print("\n--- RESULT DISTRIBUTION ---")
    print(df["FTR"].value_counts())

    print("\n--- HOME TEAMS ---")
    print(df["HomeTeam"].nunique())

    print("\n--- AWAY TEAMS ---")
    print(df["AwayTeam"].nunique())
