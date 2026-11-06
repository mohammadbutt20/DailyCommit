"""Submissions remember their group; `practice` submissions

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The group a submission was made from (the daily page or a past problem). Kept when the
    # group's deleted as NULL. `submissions.kind` (String(8)) now also takes 'practice': judged
    # on every test like 'submit', but never credited to a streak or a day.
    op.add_column(
        "submissions",
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # Older submissions: the group their solve was credited to, where there was one.
    op.execute(
        """
        UPDATE submissions s SET group_id = d.group_id
        FROM (
            SELECT submission_id, min(group_id) AS group_id
            FROM group_day_solves WHERE submission_id IS NOT NULL GROUP BY submission_id
        ) d
        WHERE d.submission_id = s.id
        """
    )
    # "My history": a user's submissions, newest first, paged by id.
    op.create_index("ix_submissions_user_id_id", "submissions", ["user_id", sa.text("id DESC")])


def downgrade() -> None:
    op.execute("DELETE FROM submissions WHERE kind = 'practice'")
    op.drop_index("ix_submissions_user_id_id", table_name="submissions")
    op.drop_column("submissions", "group_id")
