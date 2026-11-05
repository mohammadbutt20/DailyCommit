"""Opaque server-side sessions. The cookie holds a random token; the DB holds only its hash.
Every login provider (dev now, Discord later) ends by calling `start_session`."""

import hashlib
import secrets
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from dailycommit.config import settings
from dailycommit.models import AuthIdentity, Session, User, utcnow


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def user_for_identity(
    db: AsyncSession, provider: str, provider_user_id: str, display_name: str
) -> User:
    user = await db.scalar(
        select(User)
        .join(AuthIdentity, AuthIdentity.user_id == User.id)
        .where(AuthIdentity.provider == provider, AuthIdentity.provider_user_id == provider_user_id)
    )
    if user is None:
        user = User(display_name=display_name)
        db.add(user)
        await db.flush()
        db.add(AuthIdentity(user_id=user.id, provider=provider, provider_user_id=provider_user_id))
    return user


async def start_session(db: AsyncSession, response: Response, user: User) -> None:
    token = secrets.token_urlsafe(32)
    ttl = timedelta(days=settings.session_ttl_days)
    db.add(Session(user_id=user.id, token_hash=hash_token(token), expires_at=utcnow() + ttl))
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


async def user_for_token(db: AsyncSession, token: str | None) -> User | None:
    if not token:
        return None
    return await db.scalar(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(Session.token_hash == hash_token(token), Session.expires_at > utcnow())
    )


async def end_session(db: AsyncSession, response: Response, token: str | None) -> None:
    if token:
        await db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
    response.delete_cookie(settings.session_cookie, path="/")
