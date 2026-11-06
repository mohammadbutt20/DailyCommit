"""The current user's LeetCode account, and checking LeetCode for their solves.

Linking proves ownership: we hand out a short code, the user pastes it into their LeetCode
profile's Summary, and we look for it there. Without that, anyone could claim a stronger
friend's account and collect their solves.
"""

import secrets

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from dailycommit.api.deps import DB, CurrentUser, RedisDep
from dailycommit.leetcode import client as lc
from dailycommit.models import User
from dailycommit.schemas import LeetCodeAccountOut, LeetCodeCheckOut, LeetCodeLinkIn
from dailycommit.services.leetcode_solves import check_user, owed_problems

router = APIRouter(prefix="/me/leetcode", tags=["leetcode"])
CHECK_COOLDOWN_S = 15


def _out(user: User) -> LeetCodeAccountOut:
    return LeetCodeAccountOut(
        username=user.leetcode_username,
        pending_username=user.leetcode_pending_username,
        verify_code=user.leetcode_verify_code,
    )


async def _taken_by_other(db, user: User, username: str) -> bool:
    other = await db.scalar(
        select(User.id).where(
            func.lower(User.leetcode_username) == username.lower(), User.id != user.id
        )
    )
    return other is not None


@router.get("", response_model=LeetCodeAccountOut)
async def get_account(user: CurrentUser) -> LeetCodeAccountOut:
    return _out(user)


@router.put("", response_model=LeetCodeAccountOut)
async def start_link(body: LeetCodeLinkIn, user: CurrentUser, db: DB) -> LeetCodeAccountOut:
    """Step 1: name the account. Returns the code to put in that profile's Summary."""
    try:
        async with lc.new_client() as http:
            profile = await lc.fetch_profile(http, body.username.strip())
    except lc.LeetCodeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No LeetCode user with that username")
    username, _ = profile
    if user.leetcode_username and user.leetcode_username.lower() == username.lower():
        return _out(user)  # already linked to this account
    if await _taken_by_other(db, user, username):
        raise HTTPException(status.HTTP_409_CONFLICT, "Another member already linked that account")
    user.leetcode_pending_username = username
    user.leetcode_verify_code = f"dailycommit-{secrets.token_hex(3)}"
    await db.commit()
    return _out(user)


@router.post("/verify", response_model=LeetCodeAccountOut)
async def verify_link(user: CurrentUser, db: DB) -> LeetCodeAccountOut:
    """Step 2: the code is in the profile's Summary, so the account is theirs."""
    pending, code = user.leetcode_pending_username, user.leetcode_verify_code
    if not pending or not code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Start by entering your LeetCode username")
    try:
        async with lc.new_client() as http:
            profile = await lc.fetch_profile(http, pending)
    except lc.LeetCodeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That LeetCode user no longer exists")
    username, about = profile
    if code not in about:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Didn't find {code} in the Summary of leetcode.com/u/{username} yet. "
            "Save it there, then try again (LeetCode can take a minute to update).",
        )
    if await _taken_by_other(db, user, username):
        raise HTTPException(status.HTTP_409_CONFLICT, "Another member already linked that account")
    user.leetcode_username = username
    user.leetcode_pending_username = user.leetcode_verify_code = None
    await db.commit()
    return _out(user)


@router.delete("", status_code=204)
async def unlink(user: CurrentUser, db: DB) -> None:
    user.leetcode_username = None
    user.leetcode_pending_username = user.leetcode_verify_code = None
    await db.commit()


@router.post("/check", response_model=LeetCodeCheckOut)
async def check_now(user: CurrentUser, db: DB, redis: RedisDep) -> LeetCodeCheckOut:
    """Look for today's accepted LeetCode solves right away instead of waiting for the
    scheduler (which checks every few minutes anyway)."""
    if not user.leetcode_username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link your LeetCode account first")
    if not await redis.set(f"rl:lc-check:{user.id}", 1, nx=True, ex=CHECK_COOLDOWN_S):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, f"Checked moments ago; wait {CHECK_COOLDOWN_S}s"
        )
    owed = await owed_problems(db, user.id)
    try:
        async with lc.new_client() as http:
            credited = await check_user(db, redis, http, user, owed)
    except lc.LeetCodeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    return LeetCodeCheckOut(credited=len(credited))
