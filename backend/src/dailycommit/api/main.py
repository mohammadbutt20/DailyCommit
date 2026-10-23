from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, FastAPI
from redis.asyncio import Redis
from sqlalchemy import text

from dailycommit.api.auth import dev
from dailycommit.api.deps import DB, RedisDep
from dailycommit.api.routers import auth, groups, problems, submissions
from dailycommit.api.ws import Hub, websocket_endpoint
from dailycommit.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = Redis.from_url(settings.redis_url)
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    app.state.hub = Hub(app.state.redis)
    app.state.hub.start()
    yield
    await app.state.hub.stop()
    await app.state.arq.aclose()
    await app.state.redis.aclose()


app = FastAPI(
    title="Daily Commit",
    lifespan=lifespan,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
)

api = APIRouter(prefix="/api")


@api.get("/health", tags=["meta"])
async def health(db: DB, redis: RedisDep) -> dict[str, bool]:
    await db.execute(text("select 1"))
    await redis.ping()
    return {"ok": True}


api.include_router(auth.router)
api.include_router(groups.router)
api.include_router(problems.router)
api.include_router(submissions.router)
if settings.is_dev:
    api.include_router(dev.router)

app.include_router(api)
app.add_api_websocket_route("/ws", websocket_endpoint)
