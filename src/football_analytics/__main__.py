from pathlib import Path

from football_analytics.ingestion.pipeline import ingest


DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "data"
    / "raw"
    / "epl"
    / "epl_2025_26.csv"
)


def main() -> None:
    df = ingest(DATA_PATH)

    print(df.head())
    print(df.shape)
    print(df.columns.tolist())


if __name__ == "__main__":
    main()
