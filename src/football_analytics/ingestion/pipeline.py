from pathlib import Path

from .cleaner import clean
from .profiler import profile
from .reader import read_csv
from .transformer import (
    extract_referees,
    extract_season,
    extract_teams,
    transform_match,
    transform_match_statistics,
)
from .validator import validate


def ingest(path: Path):
    df = read_csv(path)

    validate(df)
    profile(df)

    df = clean(df)

    season = extract_season(df)
    teams = extract_teams(df)
    referees = extract_referees(df)

    matches = [
        transform_match(row)
        for _, row in df.iterrows()
    ]

    statistics = [
        transform_match_statistics(row)
        for _, row in df.iterrows()
    ]

    return {
        "season": season,
        "teams": teams,
        "referees": referees,
        "matches": matches,
        "statistics": statistics,
    }