import pandas as pd


def extract_season(df: pd.DataFrame) -> str:
    start_year = df["Date"].min().year
    end_year = df["Date"].max().year

    return f"{start_year}-{str(end_year)[-2:]}"


def extract_teams(df: pd.DataFrame) -> set[str]:
    home_teams = set(df["HomeTeam"])
    away_teams = set(df["AwayTeam"])

    return home_teams | away_teams


def extract_referees(df: pd.DataFrame) -> set[str]:
    return set(df["Referee"].dropna())

def transform_match(row: pd.Series) -> dict:
    return {
        "home_team_name": row["HomeTeam"],
        "away_team_name": row["AwayTeam"],
        "referee_name": row["Referee"],
        "match_date": row["Date"].date(),
        "kickoff_time": row["Time"],
        "home_goals": int(row["FTHG"]),
        "away_goals": int(row["FTAG"]),
        "result": row["FTR"],
        "home_half_time_goals": int(row["HTHG"]),
        "away_half_time_goals": int(row["HTAG"]),
        "half_time_result": row["HTR"],
    }

def transform_match_statistics(row: pd.Series) -> dict:
    return {
        "home_shots": int(row["HS"]),
        "away_shots": int(row["AS"]),
        "home_shots_on_target": int(row["HST"]),
        "away_shots_on_target": int(row["AST"]),
        "home_fouls": int(row["HF"]),
        "away_fouls": int(row["AF"]),
        "home_corners": int(row["HC"]),
        "away_corners": int(row["AC"]),
        "home_yellow_cards": int(row["HY"]),
        "away_yellow_cards": int(row["AY"]),
        "home_red_cards": int(row["HR"]),
        "away_red_cards": int(row["AR"]),
    }