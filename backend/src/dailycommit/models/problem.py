from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dailycommit.models.base import Base


class Problem(Base):
    """Either `local` (synced from problems/<slug>/ by `python -m dailycommit.problems sync`,
    judged in our sandbox) or `leetcode` (imported by `python -m dailycommit.leetcode`, solved
    on leetcode.com and verified there). Never edit in the DB."""

    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    difficulty: Mapped[str] = mapped_column(String(16))
    topics: Mapped[list[str]] = mapped_column(ARRAY(String(40)))
    statement_md: Mapped[str] = mapped_column(Text)  # local problems; "" for LeetCode
    source: Mapped[str] = mapped_column(String(16), default="local")  # local | leetcode
    source_url: Mapped[str | None] = mapped_column(String(300))  # the problem on leetcode.com
    frontend_id: Mapped[str | None] = mapped_column(String(16))  # LeetCode's problem number
    statement_html: Mapped[str | None] = mapped_column(Text)  # LeetCode's, sanitized on import
    # Local problems only (NULL for LeetCode):
    # {"function": str, "params": [{"name", "type"}], "returns": str}
    signature: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    compare: Mapped[Any] = mapped_column(JSONB, nullable=True)
    limits: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    retired: Mapped[bool] = mapped_column(default=False)


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("problem_id", "ordinal"),)
    __test__ = False  # not a pytest class

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    ordinal: Mapped[int]
    is_sample: Mapped[bool]
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    expected: Mapped[Any] = mapped_column(JSONB)
