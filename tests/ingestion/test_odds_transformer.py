from pathlib import Path

from football_analytics.ingestion.reader import read_csv
from football_analytics.ingestion.odds_transformer import transform_odds


def test_transform_odds():
    path = Path("src/data/raw/epl/epl_2025_26.csv")

    df = read_csv(path)

    odds = transform_odds(df.iloc[0])

    assert len(odds) > 0

    for odd in odds:
        print(odd)