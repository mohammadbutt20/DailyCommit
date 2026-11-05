"""Live events. A topic name is also its Redis pub/sub channel; the API's WebSocket hub forwards
messages verbatim to subscribed browsers."""

import json
from typing import Any

from redis.asyncio import Redis


def submission_topic(submission_id: int) -> str:
    return f"submission:{submission_id}"


def group_topic(group_id: int) -> str:
    return f"group:{group_id}"


async def publish(redis: Redis, topic: str, event: str, data: dict[str, Any]) -> None:
    await redis.publish(topic, json.dumps({"topic": topic, "event": event, "data": data}))
