from __future__ import annotations

import pytest

from app.core.exceptions import ParamError
from app.domain.model_config import validate_model_payload, validate_prompt_payload


def test_validate_model_payload_image_requires_resolution():
    with pytest.raises(ParamError):
        validate_model_payload(
            {"model_name": "x", "model_type": "image", "adapter_key": "stub", "support_resolution": []}
        )


def test_validate_model_payload_video_requires_duration():
    with pytest.raises(ParamError):
        validate_model_payload(
            {"model_name": "x", "model_type": "video", "adapter_key": "stub", "support_duration": []}
        )


def test_validate_model_payload_rejects_plaintext_secret():
    with pytest.raises(ParamError):
        validate_model_payload(
            {
                "model_name": "x",
                "model_type": "image",
                "adapter_key": "stub",
                "support_resolution": ["1K"],
                "config_json": {"api_key": "plaintext-secret"},
            }
        )


def test_validate_model_payload_accepts_env_reference_secret():
    result = validate_model_payload(
        {
            "model_name": "x",
            "model_type": "image",
            "adapter_key": "stub",
            "support_resolution": ["1K"],
            "config_json": {"api_key": "WANXIANG_API_KEY"},
        }
    )
    assert result["model_type"] == "image"
    assert result["config_json"] == {"api_key": "WANXIANG_API_KEY"}


def test_validate_prompt_payload_rejects_unknown_task_type():
    with pytest.raises(ParamError):
        validate_prompt_payload({"prompt_name": "p", "task_type": "unknown", "system_content": "c"})


def test_validate_prompt_payload_rejects_empty_content():
    with pytest.raises(ParamError):
        validate_prompt_payload({"prompt_name": "p", "task_type": "txt2img", "system_content": "  "})


def test_validate_prompt_payload_ok():
    result = validate_prompt_payload(
        {"prompt_name": "p", "task_type": "chat_general", "system_content": "c", "bind_model_id": 5}
    )
    assert result["task_type"] == "chat_general"
    assert result["bind_model_id"] == 5
