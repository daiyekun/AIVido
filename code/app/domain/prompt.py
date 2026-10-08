from __future__ import annotations

from dataclasses import dataclass

TASK_TYPE_GENERATE = ("txt2img", "img2img", "txt2vid", "vid2vid", "vid_edit", "img2vid")
TASK_TYPE_CHAT = "chat_general"
TASK_TYPE_ALL = TASK_TYPE_GENERATE + (TASK_TYPE_CHAT,)

SCOPE_MODEL = "model"
SCOPE_GLOBAL = "global"


@dataclass(frozen=True)
class PromptCandidate:
    prompt_id: int
    task_type: str
    bind_model_id: int | None
    system_content: str
    is_enable: bool
    sort: int


@dataclass(frozen=True)
class PromptMatch:
    prompt_id: int
    system_content: str
    scope: str
    task_type: str
    bind_model_id: int | None


def match_prompt(task_type: str, model_id: int | None, candidates: list[PromptCandidate]) -> PromptMatch | None:
    enabled = [
        candidate
        for candidate in candidates
        if candidate.is_enable and candidate.task_type == task_type and candidate.system_content
    ]
    if not enabled:
        return None

    def ordered(pool: list[PromptCandidate]) -> list[PromptCandidate]:
        return sorted(pool, key=lambda item: (-item.sort, -item.prompt_id))

    bound = [item for item in enabled if model_id is not None and item.bind_model_id == model_id]
    if bound:
        best = ordered(bound)[0]
        return PromptMatch(
            prompt_id=best.prompt_id,
            system_content=best.system_content,
            scope=SCOPE_MODEL,
            task_type=task_type,
            bind_model_id=best.bind_model_id,
        )

    global_pool = [item for item in enabled if item.bind_model_id is None]
    if global_pool:
        best = ordered(global_pool)[0]
        return PromptMatch(
            prompt_id=best.prompt_id,
            system_content=best.system_content,
            scope=SCOPE_GLOBAL,
            task_type=task_type,
            bind_model_id=None,
        )

    return None
