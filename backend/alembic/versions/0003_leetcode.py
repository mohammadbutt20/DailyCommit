"""LeetCode problems, linked LeetCode accounts, and solves verified on LeetCode

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Problems: 'local' (problems/ folder, judged in our sandbox) or 'leetcode' (imported,
    # solved on leetcode.com). LeetCode problems have no signature/compare/limits.
    op.add_column(
        "problems",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="local"),
    )
    op.alter_column("problems", "source", server_default=None)
    op.add_column("problems", sa.Column("source_url", sa.String(length=300), nullable=True))
    op.add_column("problems", sa.Column("frontend_id", sa.String(length=16), nullable=True))
    op.add_column("problems", sa.Column("statement_html", sa.Text(), nullable=True))
    for column in ("signature", "compare", "limits"):
        op.alter_column("problems", column, nullable=True)

    # Linked LeetCode account. `leetcode_username` is set only after the ownership check.
    op.add_column("users", sa.Column("leetcode_username", sa.String(length=64), nullable=True))
    op.add_column(
        "users", sa.Column("leetcode_pending_username", sa.String(length=64), nullable=True)
    )
    op.add_column("users", sa.Column("leetcode_verify_code", sa.String(length=32), nullable=True))
    op.create_index(
        "uq_users_leetcode_username",
        "users",
        [sa.text("lower(leetcode_username)")],
        unique=True,
    )

    # A solve comes from our own judge (submission_id) or from LeetCode (external_ref).
    op.alter_column("group_day_solves", "submission_id", nullable=True)
    op.add_column(
        "group_day_solves", sa.Column("external_ref", sa.String(length=64), nullable=True)
    )
    op.create_check_constraint(
        "ck_group_day_solves_has_source",
        "group_day_solves",
        "submission_id IS NOT NULL OR external_ref IS NOT NULL",
    )


def downgrade() -> None:
    op.execute("DELETE FROM group_day_solves WHERE submission_id IS NULL")
    op.drop_constraint("ck_group_day_solves_has_source", "group_day_solves")
    op.drop_column("group_day_solves", "external_ref")
    op.alter_column("group_day_solves", "submission_id", nullable=False)
    op.drop_index("uq_users_leetcode_username", "users")
    for column in ("leetcode_verify_code", "leetcode_pending_username", "leetcode_username"):
        op.drop_column("users", column)
    # LeetCode problems can't satisfy the old NOT NULLs; they (and their history) go.
    op.execute("DELETE FROM problems WHERE source = 'leetcode'")
    for column in ("signature", "compare", "limits"):
        op.alter_column("problems", column, nullable=False)
    for column in ("statement_html", "frontend_id", "source_url", "source"):
        op.drop_column("problems", column)
