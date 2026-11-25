"""FastAPI dependency providers for database sessions and viewer tier context."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Header
from sqlalchemy.orm import Session

from football_analytics.db.session import SessionLocal


def get_db_session() -> Generator[Session]:
    """Yield a transactional SQLAlchemy session per request."""
    with SessionLocal() as session:
        yield session


def get_viewer_tier(
    x_viewer_tier: str | None = Header(default=None),
) -> str:
    """Resolve the caller's subscription tier (defaults to 'free').

    Provides an explicit architectural seam for future Auth/Stripe gating.
    """
    if x_viewer_tier and x_viewer_tier.lower() in ("free", "pro", "admin"):
        return x_viewer_tier.lower()
    return "free"
