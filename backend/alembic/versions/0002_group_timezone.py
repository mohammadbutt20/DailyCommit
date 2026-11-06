"""per-group timezone

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from dailycommit.config import settings

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing groups keep the zone they were implicitly using (the old app-wide setting).
    op.add_column(
        "groups",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default=settings.day_timezone,
        ),
    )
    op.alter_column("groups", "timezone", server_default=None)


def downgrade() -> None:
    op.drop_column("groups", "timezone")
