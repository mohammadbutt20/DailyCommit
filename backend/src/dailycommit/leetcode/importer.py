"""Import LeetCode questions into `problems` (source='leetcode').

Upsert by slug; unchanged questions are skipped via content_hash. Paid-only questions are
skipped (LeetCode doesn't serve their statements). A slug already used by a local problem
is left alone. Statements are sanitized here, once, so the browser can render them as-is.
"""

import hashlib
from dataclasses import dataclass, field

import httpx
import nh3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.leetcode.client import Question, fetch_question
from dailycommit.models import Problem


def sanitize(html: str) -> str:
    """LeetCode's statement HTML, reduced to safe markup (no scripts, styles or handlers)."""
    return nh3.clean(html, link_rel="noopener noreferrer nofollow").strip()


def content_hash(q: Question) -> str:
    raw = "\x1f".join([q.title, q.difficulty, ",".join(q.topics), q.content_html or ""])
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class ImportResult:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # slug -> reason


def apply_question(row: Problem, q: Question) -> None:
    row.source = "leetcode"
    row.source_url = q.url
    row.frontend_id = q.frontend_id
    row.title = q.title[:120]
    row.difficulty = q.difficulty
    row.topics = [t[:40] for t in q.topics]
    row.statement_md = ""
    row.statement_html = sanitize(q.content_html or "")
    row.signature = row.compare = row.limits = None
    row.content_hash = content_hash(q)
    row.retired = False


async def import_question(db: AsyncSession, q: Question, result: ImportResult) -> Problem | None:
    if q.paid_only or not q.content_html:
        result.skipped[q.slug] = "paid-only"
        return None
    row = await db.scalar(select(Problem).where(Problem.slug == q.slug))
    if row is not None and row.source != "leetcode":
        result.skipped[q.slug] = "slug is used by a local problem"
        return None
    if row is None:
        row = Problem(slug=q.slug)
        db.add(row)
        apply_question(row, q)
        result.added.append(q.slug)
    elif row.content_hash == content_hash(q) and not row.retired:
        result.unchanged.append(q.slug)
    else:
        apply_question(row, q)
        result.updated.append(q.slug)
    await db.flush()
    return row


async def import_slugs(
    db: AsyncSession, client: httpx.AsyncClient, slugs: list[str]
) -> ImportResult:
    result = ImportResult()
    for slug in dict.fromkeys(slugs):  # dedupe, keep order
        q = await fetch_question(client, slug)
        if q is None:
            result.skipped[slug] = "not found on LeetCode"
            continue
        await import_question(db, q, result)
    return result


async def ensure_leetcode_problem(
    db: AsyncSession, client: httpx.AsyncClient, slug: str
) -> Problem | None:
    """The problem for this LeetCode slug, importing it first if needed (leader picks)."""
    row = await db.scalar(select(Problem).where(Problem.slug == slug))
    if row is not None:
        return None if row.retired else row
    q = await fetch_question(client, slug)
    if q is None:
        return None
    return await import_question(db, q, ImportResult())
