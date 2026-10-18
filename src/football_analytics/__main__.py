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
    ingest(
        Path("src/data/raw/epl/epl_2025_26.csv"),
        competition_name="Premier League",
        competition_code="EPL",
    )


if __name__ == "__main__":
    main()
