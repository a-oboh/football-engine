"""add api football and lab tables

Revision ID: 8c3e12f9a1b2
Revises: 6b1f8aa2c4d3
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c3e12f9a1b2"
down_revision: str | Sequence[str] | None = "6b1f8aa2c4d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add API-Football v3 metadata columns, scheduled fixtures, aliases, and lab snapshots."""
    op.add_column(
        "competitions",
        sa.Column("api_football_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "competitions",
        sa.Column("country", sa.String(length=60), nullable=True),
    )
    op.add_column(
        "competitions",
        sa.Column("logo_url", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_competitions_api_football_id",
        "competitions",
        ["api_football_id"],
    )

    op.add_column(
        "seasons",
        sa.Column("api_football_year", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "seasons",
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )

    op.add_column(
        "teams",
        sa.Column("api_football_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("short_code", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("logo_url", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_teams_api_football_id",
        "teams",
        ["api_football_id"],
    )

    op.add_column(
        "matches",
        sa.Column("api_football_fixture_id", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_matches_api_football_fixture_id",
        "matches",
        ["api_football_fixture_id"],
    )

    op.create_table(
        "team_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias", name="uq_team_aliases_alias"),
    )

    op.create_table(
        "scheduled_fixtures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("api_football_fixture_id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("referee_name", sa.String(length=100), nullable=True),
        sa.Column("venue_name", sa.String(length=150), nullable=True),
        sa.Column("round_name", sa.String(length=80), nullable=True),
        sa.Column("match_date", sa.Date(), nullable=False),
        sa.Column("kickoff_time", sa.Time(), nullable=True),
        sa.Column("status_short", sa.String(length=16), nullable=False),
        sa.Column("completed_match_id", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "home_team_id <> away_team_id",
            name="chk_scheduled_different_teams",
        ),
        sa.ForeignKeyConstraint(
            ["away_team_id"],
            ["teams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["completed_match_id"],
            ["matches.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["home_team_id"],
            ["teams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["season_id"],
            ["seasons.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "api_football_fixture_id",
            name="uq_scheduled_fixtures_api_id",
        ),
    )

    op.create_table(
        "fixture_odds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fixture_id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=30), nullable=False),
        sa.Column("selection", sa.String(length=20), nullable=False),
        sa.Column("line", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"]),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["scheduled_fixtures.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "api_sync_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
        sa.Column("competition_code", sa.String(length=20), nullable=True),
        sa.Column("season_name", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requests_remaining", sa.Integer(), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "saved_predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=24), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("competition_code", sa.String(length=20), nullable=False),
        sa.Column("seasons_used", sa.JSON(), nullable=False),
        sa.Column("home_team", sa.String(length=100), nullable=False),
        sa.Column("away_team", sa.String(length=100), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("match_id", sa.Integer(), nullable=True),
        sa.Column("fixture_id", sa.Integer(), nullable=True),
        sa.Column("data_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["scheduled_fixtures.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_saved_predictions_slug"),
    )
    op.create_index(
        "ix_saved_predictions_slug",
        "saved_predictions",
        ["slug"],
        unique=True,
    )

    op.create_table(
        "saved_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("competition_code", sa.String(length=20), nullable=False),
        sa.Column("warmup_seasons", sa.JSON(), nullable=False),
        sa.Column("evaluation_seasons", sa.JSON(), nullable=False),
        sa.Column("data_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_saved_evaluations_slug"),
    )
    op.create_index(
        "ix_saved_evaluations_slug",
        "saved_evaluations",
        ["slug"],
        unique=True,
    )


def downgrade() -> None:
    """Remove lab and API-Football extensions."""
    op.drop_index("ix_saved_evaluations_slug", table_name="saved_evaluations")
    op.drop_table("saved_evaluations")
    op.drop_index("ix_saved_predictions_slug", table_name="saved_predictions")
    op.drop_table("saved_predictions")
    op.drop_table("api_sync_logs")
    op.drop_table("fixture_odds")
    op.drop_table("scheduled_fixtures")
    op.drop_table("team_aliases")
    op.drop_constraint(
        "uq_matches_api_football_fixture_id",
        "matches",
        type_="unique",
    )
    op.drop_column("matches", "api_football_fixture_id")
    op.drop_constraint("uq_teams_api_football_id", "teams", type_="unique")
    op.drop_column("teams", "logo_url")
    op.drop_column("teams", "short_code")
    op.drop_column("teams", "api_football_id")
    op.drop_column("seasons", "is_current")
    op.drop_column("seasons", "api_football_year")
    op.drop_constraint(
        "uq_competitions_api_football_id",
        "competitions",
        type_="unique",
    )
    op.drop_column("competitions", "logo_url")
    op.drop_column("competitions", "country")
    op.drop_column("competitions", "api_football_id")
