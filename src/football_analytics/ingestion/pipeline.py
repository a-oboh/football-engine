from pathlib import Path

from .reader import read_csv
from .validator import validate_columns


def ingest(path: Path):
    df = read_csv(path)

    validate_columns(df)

    return df