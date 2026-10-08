from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.config import settings
from app.infrastructure.mq.topology import ALL_QUEUES, BINDINGS, EXCHANGES


def _auth() -> tuple[str, str]:
    return (settings.mq_user, settings.mq_pass)


def _vhost() -> str:
    return quote(settings.mq_vhost, safe="")


def declare_all(client: httpx.Client) -> None:
    vhost = _vhost()
    for exchange in EXCHANGES:
        client.put(
            f"{settings.mq_api}/exchanges/{vhost}/{exchange['name']}",
            json={
                "type": exchange["type"],
                "durable": exchange["durable"],
                "auto_delete": False,
                "internal": False,
                "arguments": {},
            },
        ).raise_for_status()
    for queue in ALL_QUEUES:
        client.put(
            f"{settings.mq_api}/queues/{vhost}/{queue['name']}",
            json={"durable": True, "auto_delete": False, "arguments": queue["args"]},
        ).raise_for_status()
    for exchange_name, queue_name, routing_key in BINDINGS:
        client.post(
            f"{settings.mq_api}/bindings/{vhost}/e/{exchange_name}/q/{queue_name}",
            json={"routing_key": routing_key, "arguments": {}},
        ).raise_for_status()


def verify(client: httpx.Client) -> list[str]:
    problems: list[str] = []
    vhost = _vhost()
    for exchange in EXCHANGES:
        resp = client.get(f"{settings.mq_api}/exchanges/{vhost}/{exchange['name']}")
        if resp.status_code != 200:
            problems.append(f"exchange missing: {exchange['name']}")
        elif resp.json().get("type") != exchange["type"]:
            problems.append(
                f"exchange type mismatch: {exchange['name']} expected {exchange['type']}"
            )
    for queue in ALL_QUEUES:
        resp = client.get(f"{settings.mq_api}/queues/{vhost}/{queue['name']}")
        if resp.status_code != 200:
            problems.append(f"queue missing: {queue['name']}")
            continue
        live_args = resp.json().get("arguments") or {}
        if live_args != queue["args"]:
            problems.append(
                f"queue args mismatch: {queue['name']} expected {queue['args']} got {live_args}"
            )
    live_bindings: dict[str, set[tuple[str, str]]] = {}
    for exchange in EXCHANGES:
        resp = client.get(
            f"{settings.mq_api}/exchanges/{vhost}/{exchange['name']}/bindings/source"
        )
        bindings = resp.json() if resp.status_code == 200 else []
        live_bindings[exchange["name"]] = {
            (str(item.get("destination", "")), str(item.get("routing_key", "")))
            for item in bindings
        }
    for exchange_name, queue_name, routing_key in BINDINGS:
        if (queue_name, routing_key) not in live_bindings.get(exchange_name, set()):
            problems.append(
                f"binding missing: {exchange_name} -> {queue_name} ({routing_key})"
            )
    return problems


def main() -> int:
    with httpx.Client(auth=_auth(), timeout=settings.mq_api_timeout) as client:
        try:
            declare_all(client)
            problems = verify(client)
        except httpx.HTTPError as exc:
            print(f"RabbitMQ topology init failed: {exc}")
            return 1
    if problems:
        for problem in problems:
            print(f"FAIL {problem}")
        return 1
    print(
        f"RabbitMQ topology declared ({len(EXCHANGES)} exchanges / "
        f"{len(ALL_QUEUES)} queues / {len(BINDINGS)} bindings)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
