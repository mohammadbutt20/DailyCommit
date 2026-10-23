"""Dev-only login: pick any name, no password. Registered only when ENV=dev (see api/main.py)."""

from fastapi import APIRouter, Response
from sqlalchemy import select

from dailycommit.api.auth.sessions import start_session, user_for_identity
from dailycommit.api.deps import DB
from dailycommit.models import AuthIdentity, User
from dailycommit.schemas import DevLoginIn, UserOut

router = APIRouter(prefix="/auth/dev", tags=["auth"])


@router.get("/users", response_model=list[UserOut])
async def dev_users(db: DB) -> list[User]:
    return list(
        (
            await db.scalars(
                select(User)
                .join(AuthIdentity, AuthIdentity.user_id == User.id)
                .where(AuthIdentity.provider == "dev")
                .order_by(User.display_name)
            )
        ).all()
    )


@router.post("/login", response_model=UserOut)
async def dev_login(body: DevLoginIn, response: Response, db: DB) -> User:
    name = body.name.strip()
    user = await user_for_identity(db, "dev", name.lower(), name)
    await start_session(db, response, user)
    await db.commit()
    return user
