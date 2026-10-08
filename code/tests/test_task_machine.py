from __future__ import annotations

import pytest

from app.core.exceptions import TaskStatusIllegalError
from app.domain.task_machine import (
    CANCELED,
    FAILED,
    PENDING,
    QUEUED,
    RUNNING,
    SUCCESS,
    assert_transition,
    can_transition,
    display_status,
    ensure_cancelable,
    is_terminal,
)


def test_valid_transitions():
    assert can_transition(PENDING, QUEUED)
    assert can_transition(PENDING, FAILED)
    assert can_transition(PENDING, CANCELED)
    assert can_transition(QUEUED, RUNNING)
    assert can_transition(QUEUED, FAILED)
    assert can_transition(QUEUED, CANCELED)
    assert can_transition(RUNNING, SUCCESS)
    assert can_transition(RUNNING, FAILED)
    assert can_transition(RUNNING, QUEUED)


def test_invalid_transitions():
    assert not can_transition(SUCCESS, FAILED)
    assert not can_transition(FAILED, SUCCESS)
    assert not can_transition(CANCELED, RUNNING)
    assert not can_transition(PENDING, SUCCESS)


def test_assert_transition_raises_on_illegal():
    with pytest.raises(TaskStatusIllegalError):
        assert_transition(SUCCESS, FAILED)


def test_assert_transition_ok_on_legal():
    assert_transition(PENDING, QUEUED)


def test_terminal_states():
    assert is_terminal(SUCCESS)
    assert is_terminal(FAILED)
    assert is_terminal(CANCELED)
    assert not is_terminal(PENDING)
    assert not is_terminal(QUEUED)
    assert not is_terminal(RUNNING)


def test_cancelable_states():
    ensure_cancelable(PENDING)
    ensure_cancelable(QUEUED)
    with pytest.raises(TaskStatusIllegalError):
        ensure_cancelable(RUNNING)
    with pytest.raises(TaskStatusIllegalError):
        ensure_cancelable(SUCCESS)


def test_display_status_mapping():
    assert display_status(PENDING) == "排队中"
    assert display_status(QUEUED) == "排队中"
    assert display_status(RUNNING) == "生成中"
    assert display_status(SUCCESS) == "已完成"
    assert display_status(FAILED) == "已失败"
    assert display_status(CANCELED) == "已取消"


def test_unknown_status_rejected():
    with pytest.raises(TaskStatusIllegalError):
        can_transition("bogus", SUCCESS)
