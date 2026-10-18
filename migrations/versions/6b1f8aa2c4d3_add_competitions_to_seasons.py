"""add competitions to seasons

Revision ID: 6b1f8aa2c4d3
Revises: 64de8147bd69
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6b1f8aa2c4d3"
down_revision: str | Sequence[str] | None = "64de8147bd69"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add competitions and scope seasons to their competition."""
    op.create_table(
        "competitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.add_column("seasons", sa.Column("competition_id", sa.Integer(), nullable=True))

    # Historical seasons lack league metadata, so retain them under an explicit
    # placeholder instead of making an unverified assumption about their league.
    op.execute(
        "INSERT INTO competitions (name, code) "
        "VALUES ('Unspecified competition', 'UNSPECIFIED')"
    )
    op.execute(
        "UPDATE seasons SET competition_id = ("
        "SELECT id FROM competitions WHERE code = 'UNSPECIFIED'"
        ")"
    )

    op.alter_column("seasons", "competition_id", nullable=False)
    op.create_foreign_key(
        "fk_seasons_competition_id",
        "seasons",
        "competitions",
        ["competition_id"],
        ["id"],
    )
    op.drop_constraint("seasons_name_key", "seasons", type_="unique")
    op.create_unique_constraint(
        "uq_seasons_competition_name",
        "seasons",
        ["competition_id", "name"],
    )


def downgrade() -> None:
    """Restore globally unique season names."""
    op.drop_constraint("uq_seasons_competition_name", "seasons", type_="unique")
    op.create_unique_constraint("seasons_name_key", "seasons", ["name"])
    op.drop_constraint("fk_seasons_competition_id", "seasons", type_="foreignkey")
    op.drop_column("seasons", "competition_id")
    op.drop_table("competitions")
