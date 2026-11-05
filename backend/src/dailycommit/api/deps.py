from typing import Annotated

from arq import ArqRedis
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.api.auth.sessions import user_for_token
from dailycommit.config import settings
from dailycommit.db import get_db
from dailycommit.models import GroupMember, User

DB = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_arq(request: Request) -> ArqRedis:
    return request.app.state.arq


RedisDep = Annotated[Redis, Depends(get_redis)]
ArqDep = Annotated[ArqRedis, Depends(get_arq)]


async def current_user(request: Request, db: DB) -> User:
    user = await user_for_token(db, request.cookies.get(settings.session_cookie))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def require_member(db: AsyncSession, group_id: int, user_id: int) -> GroupMember:
    member = await db.scalar(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    if member is None:
        # 404 rather than 403: don't reveal which group ids exist.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return member


async def require_leader(db: AsyncSession, group_id: int, user_id: int) -> GroupMember:
    member = await require_member(db, group_id, user_id)
    if member.role != "leader":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Leaders only")
    return member
