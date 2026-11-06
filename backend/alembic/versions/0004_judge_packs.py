"""Judge packs: LeetCode problems judged in our sandbox

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Content hash of a LeetCode problem's judge pack (problems/leetcode/<slug>/). Kept apart
    # from content_hash (LeetCode's own data) so re-imports and pack syncs don't clobber each
    # other. NULL for local problems and for LeetCode problems without a pack.
    op.add_column("problems", sa.Column("judge_hash", sa.String(length=64), nullable=True))
    # 0003's importer stored an explicit None as JSON 'null'; make "no judge" a real SQL NULL
    # so `signature IS NULL` means "not judgeable here".
    for column in ("signature", "compare", "limits"):
        op.execute(f"UPDATE problems SET {column} = NULL WHERE {column} = 'null'::jsonb")


def downgrade() -> None:
    # Before 0004, LeetCode problems are never judged here: drop their judge data.
    op.execute(
        "DELETE FROM test_cases WHERE problem_id IN "
        "(SELECT id FROM problems WHERE source = 'leetcode')"
    )
    op.execute(
        "UPDATE problems SET signature = NULL, compare = NULL, limits = NULL "
        "WHERE source = 'leetcode'"
    )
    op.drop_column("problems", "judge_hash")
