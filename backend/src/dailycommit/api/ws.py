"""WebSocket hub: one Redis pub/sub listener per API process fans events out to browsers.

Protocol (client -> server): {"op": "subscribe" | "unsubscribe", "topic": "submission:42"}
Server -> client: the published message verbatim: {"topic", "event", "data"}
"""

import asyncio
import contextlib
import logging
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy import select

from dailycommit.api.auth.sessions import user_for_token
from dailycommit.config import settings
from dailycommit.db import SessionLocal
from dailycommit.models import GroupMember, Submission

log = logging.getLogger(__name__)

TOPIC_PATTERNS = ("submission:*", "group:*")


class Hub:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.subscribers: dict[str, set[WebSocket]] = defaultdict(set)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _listen(self) -> None:
        while True:
            try:
                async with self.redis.pubsub() as pubsub:
                    await pubsub.psubscribe(*TOPIC_PATTERNS)
                    async for msg in pubsub.listen():
                        if msg["type"] == "pmessage":
                            await self._fan_out(_text(msg["channel"]), _text(msg["data"]))
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("pub/sub listener failed; reconnecting")
                await asyncio.sleep(1)

    async def _fan_out(self, topic: str, payload: str) -> None:
        for ws in list(self.subscribers.get(topic, ())):
            try:
                await ws.send_text(payload)
            except Exception:
                self.subscribers[topic].discard(ws)

    def subscribe(self, ws: WebSocket, topic: str) -> None:
        self.subscribers[topic].add(ws)

    def unsubscribe(self, ws: WebSocket, topic: str | None = None) -> None:
        topics = [topic] if topic else list(self.subscribers)
        for t in topics:
            self.subscribers.get(t, set()).discard(ws)
            if not self.subscribers.get(t):
                self.subscribers.pop(t, None)


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


async def _may_subscribe(user_id: int, topic: str) -> bool:
    kind, _, raw_id = topic.partition(":")
    if not raw_id.isdigit():
        return False
    async with SessionLocal() as db:
        if kind == "submission":
            owner = await db.scalar(select(Submission.user_id).where(Submission.id == int(raw_id)))
            return owner == user_id
        if kind == "group":
            member = await db.scalar(
                select(GroupMember.user_id).where(
                    GroupMember.group_id == int(raw_id), GroupMember.user_id == user_id
                )
            )
            return member is not None
    return False


async def websocket_endpoint(ws: WebSocket) -> None:
    hub: Hub = ws.app.state.hub
    async with SessionLocal() as db:
        user = await user_for_token(db, ws.cookies.get(settings.session_cookie))
    if user is None:
        await ws.close(code=4401)
        return
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            op, topic = msg.get("op"), str(msg.get("topic", ""))
            if op == "subscribe":
                if await _may_subscribe(user.id, topic):
                    hub.subscribe(ws, topic)
                else:
                    await ws.send_json(
                        {"topic": topic, "event": "error", "data": {"detail": "forbidden"}}
                    )
            elif op == "unsubscribe":
                hub.unsubscribe(ws, topic)
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        hub.unsubscribe(ws)
