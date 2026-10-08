from __future__ import annotations

import re
from typing import Any, Mapping

from app.core.exceptions import ParamError, TierOutOfRangeError
from app.domain.prompt import TASK_TYPE_ALL

MODEL_TYPES = ("image", "video")
GEN_TYPES = ("image_gen", "video_gen")
VIDEO_SUB_MODES = ("copy_style", "edit")

_SECRET_KEY_PATTERN = re.compile(
    r"(api_?key|secret|token|password|passwd|credential|private_?key)", re.IGNORECASE
)
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MODEL_NAME_PATTERN = re.compile(r"^[^\s]+$")
_ADAPTER_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_.\-]{1,64}$")
_PHONE_PATTERN = re.compile(r"^1\d{10}$")


def is_valid_phone(phone: str) -> bool:
    return bool(phone) and bool(_PHONE_PATTERN.match(phone))


def validate_model_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    model_name = str(payload.get("model_name") or "").strip()
    if not model_name or len(model_name) > 128 or not _MODEL_NAME_PATTERN.match(model_name):
        raise ParamError("模型名称非法")
    result["model_name"] = model_name

    model_type = str(payload.get("model_type") or "").strip()
    if model_type not in MODEL_TYPES:
        raise ParamError("模型类型必须为 image 或 video")
    result["model_type"] = model_type

    adapter_key = str(payload.get("adapter_key") or "").strip()
    if not _ADAPTER_KEY_PATTERN.match(adapter_key):
        raise ParamError("适配器标识非法")
    result["adapter_key"] = adapter_key

    sort = payload.get("sort", 0)
    if sort is None:
        sort = 0
    if not isinstance(sort, int) or isinstance(sort, bool) or sort < 0 or sort > 1_000_000:
        raise ParamError("排序值必须为 0-1000000 的整数")
    result["sort"] = sort

    resolutions = payload.get("support_resolution", [])
    if resolutions is None:
        resolutions = []
    if not isinstance(resolutions, list) or len(resolutions) > 20:
        raise ParamError("支持分辨率必须为数组且不超过 20 项")
    clean_resolutions: list[str] = []
    for item in resolutions:
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > 32:
            raise ParamError("支持分辨率配置非法")
        clean_resolutions.append(item.strip())
    if model_type == "image" and not clean_resolutions:
        raise ParamError("图片模型必须配置至少一个分辨率档位")
    result["support_resolution"] = clean_resolutions

    durations = payload.get("support_duration", [])
    if durations is None:
        durations = []
    if not isinstance(durations, list) or len(durations) > 20:
        raise ParamError("支持时长必须为数组且不超过 20 项")
    clean_durations: list[int] = []
    for item in durations:
        if not isinstance(item, int) or isinstance(item, bool) or item <= 0 or item > 600:
            raise ParamError("支持时长必须为 1-600 的整数秒")
        clean_durations.append(item)
    if model_type == "video" and not clean_durations:
        raise ParamError("视频模型必须配置至少一个时长档位")
    result["support_duration"] = clean_durations

    config_json = payload.get("config_json", {})
    if config_json is None:
        config_json = {}
    if not isinstance(config_json, dict):
        raise ParamError("适配器配置必须为 JSON 对象")
    for key, value in config_json.items():
        if not isinstance(key, str) or len(key) > 64:
            raise ParamError("适配器配置键非法")
        if _SECRET_KEY_PATTERN.search(key) and value not in (None, ""):
            if not isinstance(value, str) or not _ENV_NAME_PATTERN.match(value):
                raise ParamError(f"密钥字段 {key} 只允许保存环境变量名，禁止明文入库")
    result["config_json"] = config_json

    price_config = payload.get("price_config_json", {})
    if price_config is None:
        price_config = {}
    if not isinstance(price_config, dict):
        raise ParamError("计价配置必须为 JSON 对象")
    result["price_config_json"] = price_config

    remark = str(payload.get("remark") or "")
    if len(remark) > 512:
        raise ParamError("备注长度不能超过 512")
    result["remark"] = remark

    is_enable = payload.get("is_enable", True)
    if not isinstance(is_enable, bool):
        raise ParamError("启用标识必须为布尔值")
    result["is_enable"] = is_enable

    return result


def ensure_resolution_supported(model_conf: Mapping[str, Any], resolution: str | None) -> None:
    if not resolution:
        return
    supported = model_conf.get("support_resolution") or []
    if supported and resolution not in supported:
        raise TierOutOfRangeError(f"模型不支持分辨率档位: {resolution}")


def ensure_duration_supported(model_conf: Mapping[str, Any], duration: Any) -> None:
    if duration in (None, ""):
        return
    try:
        duration_int = int(duration)
    except (TypeError, ValueError) as exc:
        raise TierOutOfRangeError(f"时长档位非法: {duration}") from exc
    supported = model_conf.get("support_duration") or []
    if supported and duration_int not in supported:
        raise TierOutOfRangeError(f"模型不支持时长档位: {duration_int}")


def ensure_tiers_supported(
    model_conf: Mapping[str, Any],
    resolution: str | None = None,
    duration: Any = None,
) -> None:
    ensure_resolution_supported(model_conf, resolution)
    ensure_duration_supported(model_conf, duration)


def validate_prompt_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    prompt_name = str(payload.get("prompt_name") or "").strip()
    if not prompt_name or len(prompt_name) > 128:
        raise ParamError("模板名称非法")
    task_type = str(payload.get("task_type") or "").strip()
    if task_type not in TASK_TYPE_ALL:
        raise ParamError(f"task_type 必须为 {'/'.join(TASK_TYPE_ALL)} 之一")
    system_content = str(payload.get("system_content") or "")
    if not system_content.strip():
        raise ParamError("系统提示词内容不能为空")
    if len(system_content) > 20000:
        raise ParamError("系统提示词内容过长")
    sort = payload.get("sort", 0)
    if sort is None:
        sort = 0
    if not isinstance(sort, int) or isinstance(sort, bool) or sort < 0 or sort > 1_000_000:
        raise ParamError("优先级必须为 0-1000000 的整数")
    remark = str(payload.get("remark") or "")
    if len(remark) > 512:
        raise ParamError("备注长度不能超过 512")
    is_enable = payload.get("is_enable", True)
    if not isinstance(is_enable, bool):
        raise ParamError("启用标识必须为布尔值")
    bind_model_id = payload.get("bind_model_id")
    if bind_model_id is not None:
        if not isinstance(bind_model_id, int) or isinstance(bind_model_id, bool) or bind_model_id <= 0:
            raise ParamError("绑定模型 ID 非法")
    return {
        "prompt_name": prompt_name,
        "task_type": task_type,
        "bind_model_id": bind_model_id,
        "system_content": system_content,
        "is_enable": is_enable,
        "sort": sort,
        "remark": remark,
    }
