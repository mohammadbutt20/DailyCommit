"""Request/response models. These define the OpenAPI contract the web app's types come from."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict, Field


class BaseModel(_BaseModel):
    # Lets routes return ORM rows directly where the fields line up.
    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: int
    display_name: str
    avatar_url: str | None = None


class DevLoginIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)


class ProblemSummary(BaseModel):
    slug: str
    title: str
    difficulty: str
    topics: list[str]


class GroupSummary(BaseModel):
    id: int
    name: str
    role: str
    member_count: int
    current_streak: int
    best_streak: int
    today_problem: ProblemSummary | None
    solved_today: bool


class MeOut(BaseModel):
    user: UserOut
    groups: list[GroupSummary]


class GroupCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class GroupJoinIn(BaseModel):
    invite_code: str = Field(min_length=4, max_length=16)


class GroupRef(BaseModel):
    id: int


class MemberOut(BaseModel):
    user_id: int
    display_name: str
    avatar_url: str | None
    role: str
    paused: bool
    eligible_today: bool
    solved_today: bool
    solved_at: datetime | None


class StreakDayOut(BaseModel):
    day: date
    kept: bool | None
    eligible_count: int
    solved_count: int


class GroupDetail(BaseModel):
    id: int
    name: str
    invite_code: str
    my_role: str
    current_streak: int
    best_streak: int
    today: date
    day_ends_at: datetime
    today_problem: ProblemSummary | None
    tomorrow_problem: ProblemSummary | None  # only shown to leaders
    members: list[MemberOut]
    recent_days: list[StreakDayOut]


class MemberUpdateIn(BaseModel):
    paused: bool


class DailyOverrideIn(BaseModel):
    problem_slug: str


class InviteOut(BaseModel):
    invite_code: str


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    display_name: str
    solved: int
    seconds: int


class LeaderboardOut(BaseModel):
    period: Literal["day", "week"]
    day: date
    entries: list[LeaderboardEntry]


class ParamOut(BaseModel):
    name: str
    type: str


class LanguageOut(BaseModel):
    id: str
    name: str
    monaco: str


class SampleOut(BaseModel):
    input: dict[str, Any]
    expected: Any


class ProblemDetail(ProblemSummary):
    statement_md: str
    function: str
    params: list[ParamOut]
    returns: str
    time_limit_ms: int
    memory_limit_mb: int
    samples: list[SampleOut]
    languages: list[LanguageOut]
    starter_code: dict[str, str]


class SubmissionIn(BaseModel):
    problem_slug: str
    language: str
    kind: Literal["run", "submit"]
    code: str


class SubmissionResultOut(BaseModel):
    ordinal: int
    verdict: str
    time_ms: int | None
    sample: bool
    # Filled for sample tests only.
    input: dict[str, Any] | None = None
    expected: Any = None
    actual: Any = None
    stdout: str | None = None
    error: str | None = None


class SubmissionOut(BaseModel):
    id: int
    problem_slug: str
    language: str
    kind: str
    status: str
    verdict: str | None
    passed: int
    total: int
    runtime_ms: int | None
    error: str | None
    created_at: datetime
    finished_at: datetime | None
    results: list[SubmissionResultOut]
