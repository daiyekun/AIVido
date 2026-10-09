from __future__ import annotations

import pytest

from app.infrastructure.gateway.adapters import wanxiang_image
from app.infrastructure.gateway.adapters.wanxiang_image import WanxiangImageAdapter
from app.infrastructure.gateway.errors import ModelCallHttpError


def test_missing_api_key_env_raises():
    adapter = WanxiangImageAdapter({"config_json": {}})
    with pytest.raises(ModelCallHttpError):
        adapter._api_key()


def test_api_key_resolved_from_env(monkeypatch):
    monkeypatch.setenv("WANXIANG_API_KEY", "sk-test-123")
    adapter = WanxiangImageAdapter({"config_json": {"api_key_env": "WANXIANG_API_KEY"}})
    assert adapter._api_key() == "sk-test-123"


def test_normalize_size():
    adapter = WanxiangImageAdapter({"config_json": {}})
    assert adapter._normalize_size("1024*1024") == "1024x1024"
    assert adapter._normalize_size("1024x1024") == "1024x1024"


async def test_txt2img_openai_compat_flow(monkeypatch):
    adapter = WanxiangImageAdapter(
        {"config_json": {"api_key_env": "WANXIANG_API_KEY", "model": "qwen-image-3.0"}}
    )
    monkeypatch.setenv("WANXIANG_API_KEY", "sk-test-123")

    captured = {}

    async def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["body"] = kwargs.get("json")
        captured["url"] = url

        class Resp:
            status_code = 200
            headers = {"x-request-id": "req-1"}

            def json(self):
                return {"data": [{"url": "https://ex.com/x.png"}], "created": 123}

        return Resp()

    async def fake_download(url, trace_id):
        return b"PNGDATA"

    monkeypatch.setattr(wanxiang_image.gateway_client, "request", fake_request)
    monkeypatch.setattr(adapter, "_download", fake_download)

    result = await adapter.txt2img({"prompt": "a cat", "resolution": "1024*1024"}, "trace-1")

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/images/generations")
    assert captured["body"]["model"] == "qwen-image-3.0"
    assert captured["body"]["prompt"] == "a cat"
    assert captured["body"]["size"] == "1024x1024"
    assert captured["body"]["n"] == 1
    assert result.provider_task_id == "req-1"
    assert result.raw["image_bytes"] == b"PNGDATA"
    assert result.raw["image_url"] == "https://ex.com/x.png"
