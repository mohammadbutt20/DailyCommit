"""LeetCode client parsing and statement sanitizing, with LeetCode's API mocked."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from dailycommit.leetcode import client as lc
from dailycommit.leetcode.importer import content_hash, sanitize


def run(handler, fn, *args, **kwargs):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await fn(http, *args, **kwargs)

    return asyncio.run(go())


def graphql(data: dict | None = None, *, status: int = 200, errors=None):
    """Handler answering every query with `data`; records the requests it saw."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == lc.GRAPHQL_URL
        seen.append(json.loads(request.content))
        body = {"data": data} if errors is None else {"errors": errors}
        return httpx.Response(status, json=body)

    handler.seen = seen  # type: ignore[attr-defined]
    return handler


@pytest.mark.parametrize(
    ("value", "slug"),
    [
        ("two-sum", "two-sum"),
        ("  Two-Sum ", "two-sum"),
        ("https://leetcode.com/problems/two-sum/", "two-sum"),
        ("https://leetcode.com/problems/lru-cache/description/?envType=study-plan", "lru-cache"),
        ("http://www.leetcode.com/problems/3sum", "3sum"),
        ("https://evil.example/problems/two-sum", None),
        ("two sum", None),
        ("", None),
        ("../etc", None),
    ],
)
def test_parse_slug(value, slug):
    assert lc.parse_slug(value) == slug


def test_fetch_question():
    handler = graphql(
        {
            "question": {
                "questionFrontendId": "1",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "difficulty": "Easy",
                "isPaidOnly": False,
                "content": "<p>Given</p>",
                "topicTags": [{"slug": "array"}, {"slug": "hash-table"}],
            }
        }
    )
    q = run(handler, lc.fetch_question, "two-sum")
    assert q == lc.Question(
        "two-sum", "1", "Two Sum", "easy", ["array", "hash-table"], "<p>Given</p>", False
    )
    assert q.url == "https://leetcode.com/problems/two-sum/"
    assert handler.seen[0]["variables"] == {"slug": "two-sum"}


def test_fetch_question_missing():
    assert run(graphql({"question": None}), lc.fetch_question, "nope") is None


def test_list_slugs_pages_filters_and_drops_paid():
    pages = [
        [{"titleSlug": f"p{i}", "isPaidOnly": i % 3 == 0} for i in range(100)],
        [{"titleSlug": f"q{i}", "isPaidOnly": False} for i in range(100)],
    ]
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body["variables"])
        rows = pages[len(seen) - 1] if len(seen) <= len(pages) else []
        return httpx.Response(200, json={"data": {"questionList": {"totalNum": 200, "data": rows}}})

    slugs = run(handler, lc.list_slugs, difficulty="medium", tags=["graph"], limit=120)
    assert len(slugs) == 120 and "p0" not in slugs and "p1" in slugs
    assert seen[0]["filters"] == {"difficulty": "MEDIUM", "tags": ["graph"]}
    assert [v["skip"] for v in seen] == [0, 100]


def test_study_plan_flattens_groups_in_order():
    handler = graphql(
        {
            "studyPlanV2Detail": {
                "name": "Top Interview 150",
                "planSubGroups": [
                    {"name": "Array", "questions": [{"titleSlug": "a", "paidOnly": False}]},
                    {
                        "name": "Graph",
                        "questions": [
                            {"titleSlug": "b", "paidOnly": True},
                            {"titleSlug": "c", "paidOnly": False},
                        ],
                    },
                ],
            }
        }
    )
    assert run(handler, lc.study_plan, "top-interview-150") == ("Top Interview 150", ["a", "c"])


def test_unknown_study_plan_raises():
    with pytest.raises(lc.LeetCodeError):
        run(graphql({"studyPlanV2Detail": None}), lc.study_plan, "nope")


def test_recent_accepted():
    handler = graphql(
        {
            "recentAcSubmissionList": [
                {"id": "123", "titleSlug": "two-sum", "timestamp": "1793836800"}
            ]
        }
    )
    [ac] = run(handler, lc.recent_accepted, "ada")
    assert ac == lc.AcceptedSubmission("123", "two-sum", datetime(2026, 11, 5, 0, 0, tzinfo=UTC))


def test_profile():
    handler = graphql({"matchedUser": {"username": "Ada", "profile": {"aboutMe": "hi dc-1"}}})
    assert run(handler, lc.fetch_profile, "ada") == ("Ada", "hi dc-1")
    assert run(graphql({"matchedUser": None}), lc.fetch_profile, "ghost") is None


@pytest.mark.parametrize(
    "handler",
    [
        graphql(status=429),
        graphql(errors=[{"message": "That user does not exist."}]),
        lambda request: httpx.Response(200, text="<html>cloudflare</html>"),
    ],
)
def test_leetcode_failures_raise(handler):
    with pytest.raises(lc.LeetCodeError):
        run(handler, lc.recent_accepted, "ada")


def test_sanitize_keeps_formatting_and_drops_active_content():
    html = (
        '<p style="color:red" onclick="x()">Hi <code>nums</code><sup>2</sup></p>'
        "<script>alert(1)</script>"
        '<img src="https://assets.leetcode.com/a.png" onerror="x()">'
        '<a href="javascript:alert(1)">bad</a><a href="https://en.wikipedia.org/">ok</a>'
        "<pre><strong>Input:</strong> nums = [1]</pre>"
    )
    out = sanitize(html)
    for bad in ("<script", "onclick", "onerror", "style=", "javascript:"):
        assert bad not in out
    for good in (
        "<code>nums</code>",
        "<sup>2</sup>",
        'src="https://assets.leetcode.com/a.png"',
        "<pre>",
    ):
        assert good in out
    assert 'rel="noopener noreferrer nofollow"' in out


def test_content_hash_tracks_statement():
    q = lc.Question("a", "1", "A", "easy", ["x"], "<p>1</p>", False)
    changed = lc.Question("a", "1", "A", "easy", ["x"], "<p>2</p>", False)
    assert content_hash(q) == content_hash(q) != content_hash(changed)
