from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from dailycommit.api.deps import DB, CurrentUser
from dailycommit.models import Problem, TestCase
from dailycommit.problems.schema import Signature
from dailycommit.sandbox.languages import LANGUAGES
from dailycommit.schemas import LanguageOut, ParamOut, ProblemDetail, ProblemSummary, SampleOut

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("", response_model=list[ProblemSummary])
async def list_problems(user: CurrentUser, db: DB) -> list[Problem]:
    return list(
        (
            await db.scalars(
                select(Problem).where(Problem.retired.is_(False)).order_by(Problem.title)
            )
        ).all()
    )


@router.get("/{slug}", response_model=ProblemDetail)
async def get_problem(slug: str, user: CurrentUser, db: DB) -> ProblemDetail:
    problem = await db.scalar(select(Problem).where(Problem.slug == slug))
    if problem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    # Only sample tests ever leave the backend.
    samples = (
        await db.scalars(
            select(TestCase)
            .where(TestCase.problem_id == problem.id, TestCase.is_sample.is_(True))
            .order_by(TestCase.ordinal)
        )
    ).all()
    sig = Signature(**problem.signature)
    return ProblemDetail(
        slug=problem.slug,
        title=problem.title,
        difficulty=problem.difficulty,
        topics=problem.topics,
        statement_md=problem.statement_md,
        function=sig.function,
        params=[ParamOut(name=p.name, type=p.type) for p in sig.params],
        returns=sig.returns,
        time_limit_ms=problem.limits["time_ms"],
        memory_limit_mb=problem.limits["memory_mb"],
        samples=[SampleOut(input=t.input, expected=t.expected) for t in samples],
        languages=[
            LanguageOut(id=lang.id, name=lang.name, monaco=lang.monaco)
            for lang in LANGUAGES.values()
        ],
        starter_code={lang.id: lang.starter_code(sig) for lang in LANGUAGES.values()},
    )
