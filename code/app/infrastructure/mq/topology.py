from __future__ import annotations

EXCHANGE_TASK = "gen.task.exchange"
EXCHANGE_RETRY = "gen.retry.exchange"
EXCHANGE_DLX = "gen.dlx.exchange"

EXCHANGE_TYPES: dict[str, str] = {
    EXCHANGE_TASK: "direct",
    EXCHANGE_RETRY: "direct",
    EXCHANGE_DLX: "fanout",
}

BIZ_TYPES: tuple[str, ...] = ("image", "video", "chat")

TASK_QUEUES: dict[str, str] = {
    "image": "q.gen.image",
    "video": "q.gen.video",
    "chat": "q.gen.chat",
}

TASK_ROUTING_KEYS: dict[str, str] = {
    "image": "gen.image",
    "video": "gen.video",
    "chat": "gen.chat",
}

TASK_ENTRY_NAMES: dict[str, str] = {
    "image": "workers.tasks_image.run_image_task",
    "video": "workers.tasks_video.run_video_task",
    "chat": "workers.tasks_chat.run_chat_task",
}

RETRY_TIER_TTL_MS: dict[str, int] = {"30s": 30_000, "2m": 120_000, "10m": 600_000}
RETRY_TIER_BY_COUNT: tuple[tuple[int, str], ...] = ((3, "10m"), (2, "2m"), (1, "30s"))

DLQ_NAME = "q.gen.dlq"
DLQ_ROUTING_KEY = "gen.dlq"


def retry_queue_name(biz: str, tier: str) -> str:
    return f"q.retry.{biz}.{tier}"


def retry_routing_key(biz: str, tier: str) -> str:
    return f"retry.{biz}.{tier}"


def retry_tier(retry_count: int) -> str:
    return next((tier for count, tier in RETRY_TIER_BY_COUNT if retry_count >= count), "30s")


def retry_queue_args(biz: str, tier: str) -> dict[str, int | str]:
    return {
        "x-message-ttl": RETRY_TIER_TTL_MS[tier],
        "x-dead-letter-exchange": EXCHANGE_TASK,
        "x-dead-letter-routing-key": TASK_ROUTING_KEYS[biz],
    }


EXCHANGES: list[dict[str, object]] = [
    {"name": name, "type": EXCHANGE_TYPES[name], "durable": True}
    for name in (EXCHANGE_TASK, EXCHANGE_RETRY, EXCHANGE_DLX)
]

MAIN_QUEUE_ARGS: dict[str, dict[str, str]] = {
    queue_name: {"x-dead-letter-exchange": EXCHANGE_DLX} for queue_name in TASK_QUEUES.values()
}

MAIN_QUEUES: list[dict[str, object]] = [
    {"name": queue_name, "args": args} for queue_name, args in MAIN_QUEUE_ARGS.items()
]

RETRY_QUEUES: list[dict[str, object]] = [
    {"name": retry_queue_name(biz, tier), "args": retry_queue_args(biz, tier)}
    for biz in BIZ_TYPES
    for tier in RETRY_TIER_TTL_MS
]

DLQ: dict[str, object] = {"name": DLQ_NAME, "args": {}}

ALL_QUEUES: list[dict[str, object]] = MAIN_QUEUES + RETRY_QUEUES + [DLQ]

BINDINGS: list[tuple[str, str, str]] = [
    (EXCHANGE_TASK, TASK_QUEUES[biz], TASK_ROUTING_KEYS[biz]) for biz in BIZ_TYPES
] + [(EXCHANGE_DLX, DLQ_NAME, "")] + [
    (EXCHANGE_RETRY, retry_queue_name(biz, tier), retry_routing_key(biz, tier))
    for biz in BIZ_TYPES
    for tier in RETRY_TIER_TTL_MS
]

ROUTABLE_KEYS: set[tuple[str, str]] = {
    (EXCHANGE_TASK, routing_key) for routing_key in TASK_ROUTING_KEYS.values()
} | {
    (EXCHANGE_RETRY, retry_routing_key(biz, tier))
    for biz in BIZ_TYPES
    for tier in RETRY_TIER_TTL_MS
}


def is_routable(exchange: str, routing_key: str) -> bool:
    if exchange == EXCHANGE_DLX:
        return True
    return (exchange, routing_key) in ROUTABLE_KEYS
