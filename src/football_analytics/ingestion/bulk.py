"""Bulk ingestion of season CSV files from one competition directory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from football_analytics.db.session import SessionLocal

from .pipeline import IngestionResult, ingest_dataframe
from .reader import read_csv

_SEASON_PATTERN = re.compile(r"(?<!\d)(?P<start>\d{4})[-_](?P<end>\d{2}|\d{4})(?!\d)")


@dataclass(frozen=True)
class BulkIngestionResult:
    """Summary of a directory bulk-ingestion run."""

    results: tuple[tuple[Path, IngestionResult], ...]

    @property
    def created_matches(self) -> int:
        return sum(result.created_matches for _, result in self.results)

    @property
    def existing_matches(self) -> int:
        return sum(result.existing_matches for _, result in self.results)

    @property
    def ignored_incomplete_matches(self) -> int:
        return sum(result.ignored_incomplete_matches for _, result in self.results)


def bulk_ingest(
    directory: Path,
    *,
    competition_name: str,
    competition_code: str,
) -> BulkIngestionResult:
    """Atomically ingest all season CSV files in a competition directory."""
    with SessionLocal() as session:
        try:
            result = bulk_ingest_directory(
                directory,
                session=session,
                competition_name=competition_name,
                competition_code=competition_code,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
    return result


def bulk_ingest_directory(
    directory: Path,
    *,
    session: Session,
    competition_name: str,
    competition_code: str,
) -> BulkIngestionResult:
    """Ingest CSV files from one directory into a caller-owned transaction.

    Each filename must contain a season token such as ``2025_26``, ``2025-26``,
    or ``2025-2026``. The parsed season becomes ``2025-26``.
    """
    if not directory.is_dir():
        raise ValueError(f"Bulk ingestion directory does not exist: {directory}")

    paths = tuple(sorted(path for path in directory.glob("*.csv") if path.is_file()))
    if not paths:
        raise ValueError("Bulk ingestion directory contains no CSV files")

    results: list[tuple[Path, IngestionResult]] = []
    for path in paths:
        season_name = season_name_from_path(path)
        result = ingest_dataframe(
            read_csv(path),
            session=session,
            competition_name=competition_name,
            competition_code=competition_code,
            season_name=season_name,
        )
        results.append((path, result))

    return BulkIngestionResult(results=tuple(results))


def season_name_from_path(path: Path) -> str:
    """Return a normalized season name parsed from a CSV filename."""
    match = _SEASON_PATTERN.search(path.stem)
    if match is None:
        raise ValueError(
            f"Could not determine season from filename: {path.name}. "
            "Include a token such as 2025_26 or 2025-26."
        )

    start_year = match.group("start")
    end_year = match.group("end")
    return f"{start_year}-{end_year[-2:]}"
