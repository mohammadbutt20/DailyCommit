from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.api.deps import DB, ArqDep, CurrentUser, RedisDep, require_member
from dailycommit.config import settings
from dailycommit.models import Group, Problem, Submission, SubmissionResult
from dailycommit.sandbox.languages import LANGUAGES
from dailycommit.schemas import GroupRefOut, SubmissionIn, SubmissionOut, SubmissionResultOut
from dailycommit.services.testcases import tests_for_run

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut, status_code=201)
async def create_submission(
    body: SubmissionIn, user: CurrentUser, db: DB, redis: RedisDep, arq: ArqDep
) -> SubmissionOut:
    if body.language not in LANGUAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported language {body.language}")
    if len(body.code.encode()) > settings.max_code_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Code is too long")
    problem = await db.scalar(
        select(Problem).where(Problem.slug == body.problem_slug, Problem.retired.is_(False))
    )
    if problem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    if not problem.judgeable:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This problem can't be judged here; solve it on LeetCode"
        )
    if body.group_id is not None:
        await require_member(db, body.group_id, user.id)  # 404 for groups you're not in

    rate_key = f"rl:submit:{user.id}"
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, 60)
    if count > settings.submissions_per_minute:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down; try again in a minute")

    sub = Submission(
        user_id=user.id,
        problem_id=problem.id,
        language=body.language,
        kind=body.kind,
        code=body.code,
        group_id=body.group_id,
    )
    db.add(sub)
    await db.commit()
    await arq.enqueue_job("run_submission", sub.id)
    return await _submission_out(db, sub, problem)


@router.get("/{submission_id}", response_model=SubmissionOut)
async def get_submission(submission_id: int, user: CurrentUser, db: DB) -> SubmissionOut:
    sub = await db.get(Submission, submission_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    problem = await db.get(Problem, sub.problem_id)
    assert problem is not None
    return await _submission_out(db, sub, problem)


async def _submission_out(db: AsyncSession, sub: Submission, problem: Problem) -> SubmissionOut:
    results = (
        await db.scalars(
            select(SubmissionResult)
            .where(SubmissionResult.submission_id == sub.id)
            .order_by(SubmissionResult.ordinal)
        )
    ).all()
    tests = await tests_for_run(db, problem.id, sub.kind) if results else []
    out = []
    for r in results:
        test = tests[r.ordinal] if r.ordinal < len(tests) else None
        sample = bool(test and test.is_sample)
        out.append(
            SubmissionResultOut(
                ordinal=r.ordinal,
                verdict=r.verdict,
                time_ms=r.time_ms,
                sample=sample,
                input=test.input if test and sample else None,
                expected=test.expected if test and sample else None,
                actual=r.actual,
                stdout=r.stdout,
                error=r.error,
            )
        )
    group = await db.get(Group, sub.group_id) if sub.group_id is not None else None
    return SubmissionOut(
        id=sub.id,
        problem_slug=problem.slug,
        problem_title=problem.title,
        group=GroupRefOut(id=group.id, name=group.name) if group else None,
        code=sub.code,
        language=sub.language,
        kind=sub.kind,
        status=sub.status,
        verdict=sub.verdict,
        passed=sub.passed,
        total=sub.total,
        runtime_ms=sub.runtime_ms,
        error=sub.error,
        created_at=sub.created_at,
        finished_at=sub.finished_at,
        results=out,
    )
