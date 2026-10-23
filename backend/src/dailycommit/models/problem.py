from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dailycommit.models.base import Base


class Problem(Base):
    """Synced from problems/<slug>/ by `python -m dailycommit.problems sync`. Never edit in the DB."""

    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    difficulty: Mapped[str] = mapped_column(String(16))
    topics: Mapped[list[str]] = mapped_column(ARRAY(String(40)))
    statement_md: Mapped[str] = mapped_column(Text)
    # {"function": str, "params": [{"name", "type"}], "returns": str}
    signature: Mapped[dict[str, Any]] = mapped_column(JSONB)
    compare: Mapped[Any] = mapped_column(JSONB)
    limits: Mapped[dict[str, Any]] = mapped_column(JSONB)
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
