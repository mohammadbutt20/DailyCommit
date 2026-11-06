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


class AuthProvidersOut(BaseModel):
    discord: bool
    dev: bool


class DevLoginIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)


class ProblemSummary(BaseModel):
    slug: str
    title: str
    difficulty: str
    topics: list[str]
    source: Literal["local", "leetcode"] = "local"
    source_url: str | None = None  # leetcode.com problem page (LeetCode problems)
    frontend_id: str | None = None  # LeetCode's problem number
    # Submittable to our judge: every local problem, and LeetCode problems with a judge pack.
    # LeetCode problems without one are solved on leetcode.com.
    judgeable: bool = False


class LeetCodeAccountOut(BaseModel):
    username: str | None  # verified and linked
    pending_username: str | None  # waiting for the verify code to appear in its profile
    verify_code: str | None


class LeetCodeLinkIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class LeetCodeCheckOut(BaseModel):
    credited: int  # groups where a new solve was recorded


class GroupSummary(BaseModel):
    id: int
    name: str
    timezone: str  # IANA zone that defines the group's day
    timezone_label: str  # how to show it, e.g. "Eastern (ET)"
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
    # IANA zone (e.g. "Europe/London"); defaults to the server's DAY_TIMEZONE.
    timezone: str | None = Field(default=None, max_length=64)


class TimezoneOption(BaseModel):
    id: str  # IANA zone, stored on the group
    label: str  # e.g. "Eastern (ET)"


class TimezonesOut(BaseModel):
    default: str
    zones: list[TimezoneOption]


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


class ActivityOut(BaseModel):
    """One entry of a group's activity feed. Live `solve`/`join` events on `group:{id}` carry
    the same `id`, so the browser can merge history and live events without duplicates."""

    id: str
    kind: Literal["solve", "join"]
    user_id: int
    display_name: str
    at: datetime
    problem_slug: str | None  # solves only


class GroupDetail(BaseModel):
    id: int
    name: str
    invite_code: str
    timezone: str
    timezone_label: str
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
    # A problem slug, or a leetcode.com problem URL (imported on the spot if needed).
    problem_slug: str = Field(min_length=1, max_length=300)


class InviteOut(BaseModel):
    invite_code: str


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    display_name: str
    solved: int  # week: days solved
    seconds: int  # time-to-solve from the day's start (week: summed); the ranking tie-break
    solved_at: datetime | None = None  # day: when they solved it (shown in the group's zone)


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
    statement_html: str | None  # LeetCode problems: sanitized HTML, safe to render as-is
    # Judge fields: set when `judgeable` (null/empty otherwise).
    function: str | None
    params: list[ParamOut]
    returns: str | None
    time_limit_ms: int | None
    memory_limit_mb: int | None
    samples: list[SampleOut]
    languages: list[LanguageOut]
    starter_code: dict[str, str]


class SubmissionIn(BaseModel):
    problem_slug: str
    language: str
    # run: sample tests. submit: every test, credits today's problem. practice: every test,
    # never credited (past problems).
    kind: Literal["run", "submit", "practice"]
    code: str
    group_id: int | None = None  # the group it's made from; must be one of yours


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


class GroupRefOut(BaseModel):
    id: int
    name: str


class SubmissionOut(BaseModel):
    id: int
    problem_slug: str
    problem_title: str
    group: GroupRefOut | None
    code: str  # the submitter's own code (this endpoint is owner-only)
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


class HistoryDayOut(BaseModel):
    """One day of a group's past problems."""

    day: date
    is_today: bool
    problem: ProblemSummary
    solved_by_me: bool
    solved_count: int
    # Evaluated days: who counted that day. Today: current unpaused members.
    member_count: int
    kept: bool | None  # the day's streak outcome; None if not evaluated yet or nobody counted


class MySubmissionOut(BaseModel):
    id: int
    problem_slug: str
    problem_title: str
    difficulty: str
    group: GroupRefOut | None
    language: str
    kind: str
    status: str
    verdict: str | None
    passed: int
    total: int
    runtime_ms: int | None
    created_at: datetime


class MySubmissionsOut(BaseModel):
    items: list[MySubmissionOut]
    next_before_id: int | None  # pass as before_id for the next (older) page


class GroupStreakOut(BaseModel):
    group_id: int
    group_name: str
    current_streak: int
    best_streak: int


class StatsOut(BaseModel):
    problems_solved: int
    submissions: int  # judged submits and practice runs (not samples-only runs, not IE)
    accepted: int
    accepted_rate: float | None  # accepted / submissions; None with no submissions yet
    by_language: dict[str, int]  # distinct problems solved per language
    by_difficulty: dict[str, int]  # distinct problems solved per difficulty
    streaks: list[GroupStreakOut]
