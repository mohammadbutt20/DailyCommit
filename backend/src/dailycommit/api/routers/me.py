"""The signed-in member's own history and stats. Everything here is scoped to the caller:
there is no way to ask for another user's submissions."""

from fastapi import APIRouter, Query

from dailycommit.api.deps import DB, CurrentUser
from dailycommit.schemas import MySubmissionsOut, StatsOut
from dailycommit.services.history import my_stats, my_submissions

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/submissions", response_model=MySubmissionsOut)
async def list_my_submissions(
    user: CurrentUser,
    db: DB,
    limit: int = Query(default=50, ge=1, le=100),
    before_id: int | None = Query(default=None, ge=1),
) -> MySubmissionsOut:
    """Your submissions, newest first. Pass `next_before_id` back as `before_id` for older ones."""
    return await my_submissions(db, user.id, limit, before_id)


@router.get("/stats", response_model=StatsOut)
async def get_my_stats(user: CurrentUser, db: DB) -> StatsOut:
    return await my_stats(db, user.id)
