"""Read-only client for LeetCode's public GraphQL API (the one leetcode.com itself uses).

It's unofficial: no key, no published contract, and it may change or rate-limit. Everything
that talks to LeetCode goes through here so a breaking change is fixed in one place. Callers
pass an httpx.AsyncClient (tests use httpx.MockTransport).
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

GRAPHQL_URL = "https://leetcode.com/graphql"
SITE = "https://leetcode.com"
HEADERS = {"Referer": f"{SITE}/", "User-Agent": "DailyCommit/0.1 (group practice tracker)"}
TIMEOUT_S = 15.0

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_URL_RE = re.compile(r"^https?://(?:www\.)?leetcode\.(?:com|cn)/problems/([a-z0-9-]+)", re.I)


class LeetCodeError(Exception):
    """LeetCode was unreachable, refused, or answered with something unexpected."""


@dataclass(frozen=True)
class Question:
    slug: str
    frontend_id: str
    title: str
    difficulty: str  # easy | medium | hard
    topics: list[str]  # LeetCode tag slugs, e.g. "hash-table"
    content_html: str | None  # None for paid-only questions
    paid_only: bool

    @property
    def url(self) -> str:
        return problem_url(self.slug)


@dataclass(frozen=True)
class AcceptedSubmission:
    id: str
    slug: str
    at: datetime  # UTC


def problem_url(slug: str) -> str:
    return f"{SITE}/problems/{slug}/"


def parse_slug(value: str) -> str | None:
    """'two-sum', 'https://leetcode.com/problems/two-sum/description/' -> 'two-sum'."""
    value = value.strip()
    m = _URL_RE.match(value)
    slug = (m.group(1) if m else value).lower()
    return slug if _SLUG_RE.match(slug) else None


async def _query(client: httpx.AsyncClient, query: str, variables: dict[str, Any]) -> dict:
    try:
        r = await client.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=HEADERS,
            timeout=TIMEOUT_S,
        )
    except httpx.HTTPError as e:
        raise LeetCodeError(f"LeetCode unreachable: {e.__class__.__name__}") from e
    if r.status_code != 200:
        raise LeetCodeError(f"LeetCode returned HTTP {r.status_code}")
    try:
        body = r.json()
    except ValueError as e:
        raise LeetCodeError("LeetCode returned a non-JSON response") from e
    if body.get("errors"):
        raise LeetCodeError(f"LeetCode error: {body['errors'][0].get('message', '?')}")
    return body.get("data") or {}


_QUESTION = """
query question($slug: String!) {
  question(titleSlug: $slug) {
    questionFrontendId title titleSlug difficulty isPaidOnly content
    topicTags { slug }
  }
}"""


def _question(q: dict) -> Question:
    return Question(
        slug=q["titleSlug"],
        frontend_id=str(q["questionFrontendId"]),
        title=q["title"],
        difficulty=str(q["difficulty"]).lower(),
        topics=[t["slug"] for t in q.get("topicTags") or []],
        content_html=q.get("content"),
        paid_only=bool(q.get("isPaidOnly")),
    )


async def fetch_question(client: httpx.AsyncClient, slug: str) -> Question | None:
    """The full question, or None if LeetCode has no question with that slug."""
    q = (await _query(client, _QUESTION, {"slug": slug})).get("question")
    return _question(q) if q else None


_LIST = """
query list($limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  questionList(categorySlug: "", limit: $limit, skip: $skip, filters: $filters) {
    totalNum
    data { titleSlug isPaidOnly }
  }
}"""


async def list_slugs(
    client: httpx.AsyncClient,
    *,
    difficulty: str | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
    limit: int = 50,
    include_paid: bool = False,
) -> list[str]:
    """Slugs from LeetCode's problem list with its own filters (difficulty, topic tags, search)."""
    filters: dict[str, Any] = {}
    if difficulty:
        filters["difficulty"] = difficulty.upper()
    if tags:
        filters["tags"] = tags
    if search:
        filters["searchKeywords"] = search
    slugs: list[str] = []
    skip = 0
    while len(slugs) < limit:
        page = min(100, limit - len(slugs))
        data = await _query(client, _LIST, {"limit": page, "skip": skip, "filters": filters})
        rows = (data.get("questionList") or {}).get("data") or []
        if not rows:
            break
        slugs += [r["titleSlug"] for r in rows if include_paid or not r.get("isPaidOnly")]
        skip += len(rows)
    return slugs[:limit]


_PLAN = """
query plan($slug: String!) {
  studyPlanV2Detail(planSlug: $slug) {
    name
    planSubGroups { name questions { titleSlug paidOnly } }
  }
}"""


async def study_plan(
    client: httpx.AsyncClient, plan_slug: str, include_paid: bool = False
) -> tuple[str, list[str]]:
    """(plan name, slugs in the plan's order), e.g. 'top-interview-150', 'leetcode-75'."""
    plan = (await _query(client, _PLAN, {"slug": plan_slug})).get("studyPlanV2Detail")
    if not plan:
        raise LeetCodeError(f"no LeetCode study plan {plan_slug!r}")
    slugs = [
        q["titleSlug"]
        for group in plan.get("planSubGroups") or []
        for q in group.get("questions") or []
        if include_paid or not q.get("paidOnly")
    ]
    return plan["name"], slugs


_RECENT_AC = """
query recentAc($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) { id titleSlug timestamp }
}"""


async def recent_accepted(
    client: httpx.AsyncClient, username: str, limit: int = 20
) -> list[AcceptedSubmission]:
    """The user's most recent accepted submissions (LeetCode caps this at 20; public data)."""
    rows = (await _query(client, _RECENT_AC, {"username": username, "limit": limit})).get(
        "recentAcSubmissionList"
    )
    return [
        AcceptedSubmission(
            id=str(r["id"]),
            slug=r["titleSlug"],
            at=datetime.fromtimestamp(int(r["timestamp"]), UTC),
        )
        for r in rows or []
    ]


_PROFILE = """
query profile($username: String!) {
  matchedUser(username: $username) { username profile { aboutMe } }
}"""


async def fetch_profile(client: httpx.AsyncClient, username: str) -> tuple[str, str] | None:
    """(canonical username, profile summary text), or None if there's no such user."""
    user = (await _query(client, _PROFILE, {"username": username})).get("matchedUser")
    if not user:
        return None
    return user["username"], (user.get("profile") or {}).get("aboutMe") or ""


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT_S)
