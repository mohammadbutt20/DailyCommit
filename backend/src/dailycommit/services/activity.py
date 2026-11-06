from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.domain.activity import Activity, join_id, recent_activity, solve_id
from dailycommit.models import GroupDailyProblem, GroupDaySolve, GroupMember, Problem, User


async def group_activity(db: AsyncSession, group_id: int, limit: int) -> list[Activity]:
    """The group's most recent solves and joins from the database, newest first."""
    solves = (
        await db.execute(
            select(GroupDaySolve, User.display_name, Problem.slug)
            .join(User, User.id == GroupDaySolve.user_id)
            .outerjoin(
                GroupDailyProblem,
                (GroupDailyProblem.group_id == GroupDaySolve.group_id)
                & (GroupDailyProblem.day == GroupDaySolve.day),
            )
            .outerjoin(Problem, Problem.id == GroupDailyProblem.problem_id)
            .where(GroupDaySolve.group_id == group_id)
            .order_by(GroupDaySolve.solved_at.desc())
            .limit(limit)
        )
    ).all()
    joins = (
        await db.execute(
            select(GroupMember, User.display_name)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id)
            .order_by(GroupMember.joined_at.desc())
            .limit(limit)
        )
    ).all()
    return recent_activity(
        [
            *(
                Activity(
                    id=solve_id(s.day, s.user_id),
                    kind="solve",
                    user_id=s.user_id,
                    display_name=name,
                    at=s.solved_at,
                    problem_slug=slug,
                )
                for s, name, slug in solves
            ),
            *(
                Activity(
                    id=join_id(m.user_id),
                    kind="join",
                    user_id=m.user_id,
                    display_name=name,
                    at=m.joined_at,
                )
                for m, name in joins
            ),
        ],
        limit,
    )
