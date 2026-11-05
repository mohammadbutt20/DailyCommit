import secrets
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.api.deps import DB, CurrentUser, RedisDep, require_leader, require_member
from dailycommit.domain import timeutil
from dailycommit.domain.streaks import Member, eligible_members
from dailycommit.models import (
    Group,
    GroupDailyProblem,
    GroupDaySolve,
    GroupMember,
    GroupStreakDay,
    Problem,
    User,
)
from dailycommit.schemas import (
    DailyOverrideIn,
    GroupCreateIn,
    GroupDetail,
    GroupJoinIn,
    GroupRef,
    GroupSummary,
    InviteOut,
    LeaderboardEntry,
    LeaderboardOut,
    MemberOut,
    MemberUpdateIn,
    ProblemSummary,
    StreakDayOut,
)
from dailycommit.services import leaderboard
from dailycommit.services.clock import group_tz, today
from dailycommit.services.daily import daily_problem, ensure_daily_problem
from dailycommit.services.events import group_topic, publish

router = APIRouter(prefix="/groups", tags=["groups"])

_INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I


def _invite_code() -> str:
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(8))


def _summary(p: Problem | None) -> ProblemSummary | None:
    return ProblemSummary.model_validate(p, from_attributes=True) if p else None


async def group_summaries(db: AsyncSession, user_id: int) -> list[GroupSummary]:
    rows = (
        await db.execute(
            select(Group, GroupMember.role)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == user_id)
            .order_by(Group.name)
        )
    ).all()
    summaries = []
    for group, role in rows:
        day = today(group.id)
        count = await db.scalar(
            select(func.count()).select_from(GroupMember).where(GroupMember.group_id == group.id)
        )
        solved = await db.scalar(
            select(GroupDaySolve.user_id).where(
                GroupDaySolve.group_id == group.id,
                GroupDaySolve.day == day,
                GroupDaySolve.user_id == user_id,
            )
        )
        summaries.append(
            GroupSummary(
                id=group.id,
                name=group.name,
                role=role,
                member_count=count or 0,
                current_streak=group.current_streak,
                best_streak=group.best_streak,
                today_problem=_summary(await daily_problem(db, group.id, day)),
                solved_today=solved is not None,
            )
        )
    return summaries


@router.get("", response_model=list[GroupSummary])
async def my_groups(user: CurrentUser, db: DB) -> list[GroupSummary]:
    return await group_summaries(db, user.id)


@router.post("", response_model=GroupRef, status_code=201)
async def create_group(body: GroupCreateIn, user: CurrentUser, db: DB) -> GroupRef:
    day = today()
    for _ in range(5):
        code = _invite_code()
        if not await db.scalar(select(Group.id).where(Group.invite_code == code)):
            break
    group = Group(
        name=body.name.strip(),
        invite_code=code,
        created_by=user.id,
        # Nothing before today to evaluate.
        last_rolled_day=day - timedelta(days=1),
    )
    db.add(group)
    await db.flush()
    db.add(GroupMember(group_id=group.id, user_id=user.id, role="leader"))
    await ensure_daily_problem(db, group.id, day)
    await db.commit()
    return GroupRef(id=group.id)


@router.post("/join", response_model=GroupRef)
async def join_group(body: GroupJoinIn, user: CurrentUser, db: DB, redis: RedisDep) -> GroupRef:
    group = await db.scalar(
        select(Group).where(Group.invite_code == body.invite_code.strip().upper())
    )
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No group with that invite code")
    result = await db.execute(
        insert(GroupMember)
        .values(group_id=group.id, user_id=user.id, role="member")
        .on_conflict_do_nothing()
        .returning(GroupMember.user_id)
    )
    joined = result.scalar() is not None
    await db.commit()
    if joined:
        await publish(
            redis,
            group_topic(group.id),
            "join",
            {"user_id": user.id, "display_name": user.display_name},
        )
    return GroupRef(id=group.id)


@router.get("/{group_id}", response_model=GroupDetail)
async def group_detail(group_id: int, user: CurrentUser, db: DB) -> GroupDetail:
    me = await require_member(db, group_id, user.id)
    group = await db.get(Group, group_id)
    assert group is not None
    tz = group_tz(group_id)
    day = today(group_id)
    start = timeutil.day_start(day, tz)

    members = (
        await db.execute(
            select(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id)
            .order_by(User.display_name)
        )
    ).all()
    solved_at = dict(
        (
            await db.execute(
                select(GroupDaySolve.user_id, GroupDaySolve.solved_at).where(
                    GroupDaySolve.group_id == group_id, GroupDaySolve.day == day
                )
            )
        )
        .tuples()
        .all()
    )
    eligible = {
        m.user_id
        for m in eligible_members(
            [Member(gm.user_id, gm.joined_at, gm.paused) for gm, _ in members], start
        )
    }
    recent = (
        await db.scalars(
            select(GroupStreakDay)
            .where(GroupStreakDay.group_id == group_id)
            .order_by(GroupStreakDay.day.desc())
            .limit(14)
        )
    ).all()
    tomorrow = None
    if me.role == "leader":
        tomorrow = await daily_problem(db, group_id, day + timedelta(days=1))

    return GroupDetail(
        id=group.id,
        name=group.name,
        invite_code=group.invite_code,
        my_role=me.role,
        current_streak=group.current_streak,
        best_streak=group.best_streak,
        today=day,
        day_ends_at=timeutil.day_end(day, tz),
        today_problem=_summary(await daily_problem(db, group_id, day)),
        tomorrow_problem=_summary(tomorrow),
        members=[
            MemberOut(
                user_id=u.id,
                display_name=u.display_name,
                avatar_url=u.avatar_url,
                role=gm.role,
                paused=gm.paused,
                eligible_today=u.id in eligible,
                solved_today=u.id in solved_at,
                solved_at=solved_at.get(u.id),
            )
            for gm, u in members
        ],
        recent_days=[StreakDayOut.model_validate(d, from_attributes=True) for d in recent],
    )


@router.patch("/{group_id}/members/{user_id}", status_code=204)
async def update_member(
    group_id: int, user_id: int, body: MemberUpdateIn, user: CurrentUser, db: DB
) -> None:
    await require_leader(db, group_id, user.id)
    member = await require_member(db, group_id, user_id)
    member.paused = body.paused
    await db.commit()


@router.put("/{group_id}/daily/{day}", status_code=204)
async def set_daily_problem(
    group_id: int, day: date, body: DailyOverrideIn, user: CurrentUser, db: DB
) -> None:
    await require_leader(db, group_id, user.id)
    if day <= today(group_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only future days can be changed")
    problem = await db.scalar(
        select(Problem).where(Problem.slug == body.problem_slug, Problem.retired.is_(False))
    )
    if problem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    await db.execute(
        insert(GroupDailyProblem)
        .values(group_id=group_id, day=day, problem_id=problem.id, assigned_by=user.id)
        .on_conflict_do_update(
            index_elements=["group_id", "day"],
            set_={"problem_id": problem.id, "assigned_by": user.id},
        )
    )
    await db.commit()


@router.post("/{group_id}/invite/rotate", response_model=InviteOut)
async def rotate_invite(group_id: int, user: CurrentUser, db: DB) -> InviteOut:
    await require_leader(db, group_id, user.id)
    group = await db.get(Group, group_id)
    assert group is not None
    group.invite_code = _invite_code()
    await db.commit()
    return InviteOut(invite_code=group.invite_code)


@router.get("/{group_id}/leaderboard", response_model=LeaderboardOut)
async def get_leaderboard(
    group_id: int,
    user: CurrentUser,
    db: DB,
    redis: RedisDep,
    period: Literal["day", "week"] = "day",
) -> LeaderboardOut:
    await require_member(db, group_id, user.id)
    day = today(group_id)
    entries = await leaderboard.get_leaderboard(db, redis, group_id, period, day)
    return LeaderboardOut(period=period, day=day, entries=[LeaderboardEntry(**e) for e in entries])
