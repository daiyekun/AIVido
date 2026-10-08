from __future__ import annotations

from app.core.exceptions import TaskStatusIllegalError

PENDING = "pending"
QUEUED = "queued"
RUNNING = "running"
SUCCESS = "success"
FAILED = "failed"
CANCELED = "canceled"

ALL_STATES = (PENDING, QUEUED, RUNNING, SUCCESS, FAILED, CANCELED)
TERMINAL_STATES = frozenset({SUCCESS, FAILED, CANCELED})
CANCELABLE_STATES = frozenset({PENDING, QUEUED})

TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING: frozenset({QUEUED, FAILED, CANCELED}),
    QUEUED: frozenset({RUNNING, FAILED, CANCELED}),
    RUNNING: frozenset({SUCCESS, FAILED, QUEUED}),
    SUCCESS: frozenset(),
    FAILED: frozenset(),
    CANCELED: frozenset(),
}


def ensure_known(status: str) -> None:
    if status not in ALL_STATES:
        raise TaskStatusIllegalError(f"未知任务状态: {status}")


def can_transition(from_status: str, to_status: str) -> bool:
    ensure_known(from_status)
    ensure_known(to_status)
    return to_status in TRANSITIONS[from_status]


def assert_transition(from_status: str, to_status: str) -> None:
    if not can_transition(from_status, to_status):
        raise TaskStatusIllegalError(f"任务状态不允许从 {from_status} 变更为 {to_status}")


def is_terminal(status: str) -> bool:
    ensure_known(status)
    return status in TERMINAL_STATES


def ensure_cancelable(status: str) -> None:
    ensure_known(status)
    if status not in CANCELABLE_STATES:
        raise TaskStatusIllegalError("仅排队中的任务可取消")


def display_status(status: str) -> str:
    ensure_known(status)
    if status in (PENDING, QUEUED):
        return "排队中"
    if status == RUNNING:
        return "生成中"
    if status == SUCCESS:
        return "已完成"
    if status == FAILED:
        return "已失败"
    return "已取消"
