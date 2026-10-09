from __future__ import annotations

from typing import Any


def estimate_credit(
    price_config_json: dict[str, Any] | None,
    resolution: str | None = None,
    duration: Any = None,
) -> float:
    """计费骨架：按档位（分辨率或时长）从计价配置取预估积分，取不到返回 0。"""
    if not price_config_json:
        return 0.0
    key: str | None = None
    if resolution is not None and resolution != "":
        key = str(resolution)
    elif duration is not None and duration != "":
        key = str(duration)
    if key is not None and key in price_config_json:
        value = price_config_json[key]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0
