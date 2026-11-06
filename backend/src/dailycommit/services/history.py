"""A group's past daily problems, and a member's own submissions and stats."""

from collections import Counter
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.domain import stats
from dailycommit.models import (
    Group,
    GroupDailyProblem,
    GroupDaySolve,
    GroupMember,
    GroupStreakDay,
    Problem,
    Submission,
)
from dailycommit.schemas import (
    GroupRefOut,
    GroupStreakOut,
    HistoryDayOut,
    MySubmissionOut,
    MySubmissionsOut,
    ProblemSummary,
    StatsOut,
)


async def group_history(
    db: AsyncSession, group_id: int, user_id: int, today: date, day: date | None = None
) -> list[HistoryDayOut]:
    """Every day up to and including `today` that had a problem, newest first (or just `day`).
    Days after today (a leader's pick for tomorrow) are never included."""
    query = (
        select(GroupDailyProblem.day, Problem)
        .join(Problem, Problem.id == GroupDailyProblem.problem_id)
        .where(GroupDailyProblem.group_id == group_id, GroupDailyProblem.day <= today)
        .order_by(GroupDailyProblem.day.desc())
    )
    if day is not None:
        query = query.where(GroupDailyProblem.day == day)
    rows = (await db.execute(query)).all()
    if not rows:
        return []
    days = [d for d, _ in rows]

    solves = (
        await db.execute(
            select(GroupDaySolve.day, GroupDaySolve.user_id).where(
                GroupDaySolve.group_id == group_id, GroupDaySolve.day.in_(days)
            )
        )
    ).all()
    solved_count = Counter(d for d, _ in solves)
    mine = {d for d, uid in solves if uid == user_id}
    evaluated = {
        s.day: s
        for s in (
            await db.scalars(
                select(GroupStreakDay).where(
                    GroupStreakDay.group_id == group_id, GroupStreakDay.day.in_(days)
                )
            )
        ).all()
    }
    active_members = await db.scalar(
        select(func.count())
        .select_from(GroupMember)
        .where(GroupMember.group_id == group_id, GroupMember.paused.is_(False))
    )
    return [
        HistoryDayOut(
            day=d,
            is_today=d == today,
            problem=ProblemSummary.model_validate(problem, from_attributes=True),
            solved_by_me=d in mine,
            solved_count=solved_count[d],
            member_count=evaluated[d].eligible_count if d in evaluated else active_members or 0,
            kept=evaluated[d].kept if d in evaluated else None,
        )
        for d, problem in rows
    ]


async def my_submissions(
    db: AsyncSession, user_id: int, limit: int, before_id: int | None
) -> MySubmissionsOut:
    """Only `user_id`'s own submissions, newest first, paged by id."""
    query = (
        select(Submission, Problem, Group)
        .join(Problem, Problem.id == Submission.problem_id)
        .outerjoin(Group, Group.id == Submission.group_id)
        .where(Submission.user_id == user_id)
        .order_by(Submission.id.desc())
        .limit(limit + 1)
    )
    if before_id is not None:
        query = query.where(Submission.id < before_id)
    rows = (await db.execute(query)).all()
    page = rows[:limit]
    return MySubmissionsOut(
        items=[
            MySubmissionOut(
                id=s.id,
                problem_slug=p.slug,
                problem_title=p.title,
                difficulty=p.difficulty,
                group=GroupRefOut(id=g.id, name=g.name) if g else None,
                language=s.language,
                kind=s.kind,
                status=s.status,
                verdict=s.verdict,
                passed=s.passed,
                total=s.total,
                runtime_ms=s.runtime_ms,
                created_at=s.created_at,
            )
            for s, p, g in page
        ],
        next_before_id=page[-1][0].id if len(rows) > limit else None,
    )


async def my_stats(db: AsyncSession, user_id: int) -> StatsOut:
    facts = [
        stats.SubmissionFact(pid, kind, status, verdict, language, difficulty)
        for pid, kind, status, verdict, language, difficulty in (
            await db.execute(
                select(
                    Submission.problem_id,
                    Submission.kind,
                    Submission.status,
                    Submission.verdict,
                    Submission.language,
                    Problem.difficulty,
                )
                .join(Problem, Problem.id == Submission.problem_id)
                .where(Submission.user_id == user_id)
            )
        ).all()
    ]
    s = stats.compute(facts)
    groups = (
        await db.scalars(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == user_id)
            .order_by(Group.name)
        )
    ).all()
    return StatsOut(
        problems_solved=s.problems_solved,
        submissions=s.submissions,
        accepted=s.accepted,
        accepted_rate=s.accepted_rate,
        by_language=s.by_language,
        by_difficulty=s.by_difficulty,
        streaks=[
            GroupStreakOut(
                group_id=g.id,
                group_name=g.name,
                current_streak=g.current_streak,
                best_streak=g.best_streak,
            )
            for g in groups
        ],
    )
