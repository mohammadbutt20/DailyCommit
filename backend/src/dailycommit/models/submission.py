from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dailycommit.models.base import Base, utcnow


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    language: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(8))  # run (samples only) | submit (all tests)
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued | running | done
    verdict: Mapped[str | None] = mapped_column(String(4))  # AC WA TLE MLE RE CE IE
    passed: Mapped[int] = mapped_column(default=0)
    total: Mapped[int] = mapped_column(default=0)
    runtime_ms: Mapped[int | None]
    error: Mapped[str | None] = mapped_column(Text)  # compile error / runtime trace excerpt
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]


class SubmissionResult(Base):
    __tablename__ = "submission_results"

    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    verdict: Mapped[str] = mapped_column(String(8))  # AC WA TLE MLE RE skipped
    time_ms: Mapped[int | None]
    # Only filled for sample tests, so hidden inputs/outputs never reach the browser.
    actual: Mapped[Any | None] = mapped_column(JSONB)
    stdout: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
