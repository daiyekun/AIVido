from __future__ import annotations

import pytest

from app.domain.prompt import SCOPE_GLOBAL, SCOPE_MODEL, PromptCandidate, match_prompt


def _c(prompt_id: int, bind_model_id: int | None, *, sort: int = 0, is_enable: bool = True) -> PromptCandidate:
    return PromptCandidate(
        prompt_id=prompt_id,
        task_type="txt2img",
        bind_model_id=bind_model_id,
        system_content="system prompt",
        is_enable=is_enable,
        sort=sort,
    )


def test_match_prefers_model_scoped_highest_priority():
    candidates = [
        _c(1, 10, sort=5),
        _c(2, 10, sort=9),
        _c(3, None, sort=100),
    ]
    result = match_prompt("txt2img", 10, candidates)
    assert result is not None
    assert result.prompt_id == 2
    assert result.scope == SCOPE_MODEL
    assert result.bind_model_id == 10


def test_match_falls_back_to_global_when_no_model_binding():
    candidates = [_c(3, None, sort=1)]
    result = match_prompt("txt2img", 10, candidates)
    assert result is not None
    assert result.prompt_id == 3
    assert result.scope == SCOPE_GLOBAL
    assert result.bind_model_id is None


def test_match_returns_none_when_no_candidates():
    assert match_prompt("txt2img", 10, []) is None


def test_match_returns_none_when_all_disabled():
    candidates = [_c(1, 10, is_enable=False)]
    assert match_prompt("txt2img", 10, candidates) is None


def test_match_filters_by_task_type():
    candidates = [_c(1, 10)]
    assert match_prompt("img2img", 10, candidates) is None


def test_match_ignores_model_binding_when_model_id_is_none():
    candidates = [_c(1, 10, sort=1), _c(2, None, sort=5)]
    result = match_prompt("txt2img", None, candidates)
    assert result is not None
    assert result.prompt_id == 2
    assert result.scope == SCOPE_GLOBAL
