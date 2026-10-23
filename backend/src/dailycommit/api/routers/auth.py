from fastapi import APIRouter, Request, Response

from dailycommit.api.auth.sessions import end_session
from dailycommit.api.deps import DB, CurrentUser
from dailycommit.api.routers.groups import group_summaries
from dailycommit.config import settings
from dailycommit.schemas import MeOut, UserOut

router = APIRouter(tags=["auth"])


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, db: DB) -> None:
    await end_session(db, response, request.cookies.get(settings.session_cookie))
    await db.commit()


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, db: DB) -> MeOut:
    return MeOut(
        user=UserOut.model_validate(user, from_attributes=True),
        groups=await group_summaries(db, user.id),
    )
