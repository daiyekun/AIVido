from __future__ import annotations

import pytest

from app.core.exceptions import CapabilityUnsupportedError, ParamError
from app.domain.gen_type_resolver import (
    GEN_IMAGE,
    GEN_VIDEO,
    VIDEO_SUB_COPY,
    VIDEO_SUB_EDIT,
    resolve_task_type,
)


def test_image_no_asset_txt2img():
    assert resolve_task_type(GEN_IMAGE, None) == "txt2img"


def test_image_with_image_img2img():
    assert resolve_task_type(GEN_IMAGE, "image") == "img2img"


def test_image_with_video_rejected():
    with pytest.raises(CapabilityUnsupportedError):
        resolve_task_type(GEN_IMAGE, "video")


def test_video_no_asset_txt2vid():
    assert resolve_task_type(GEN_VIDEO, None) == "txt2vid"


def test_video_with_image_img2vid():
    assert resolve_task_type(GEN_VIDEO, "image") == "img2vid"


def test_video_copy_vid2vid():
    assert resolve_task_type(GEN_VIDEO, "video", VIDEO_SUB_COPY) == "vid2vid"


def test_video_edit_vid_edit():
    assert resolve_task_type(GEN_VIDEO, "video", VIDEO_SUB_EDIT) == "vid_edit"


def test_video_without_submode_rejected():
    with pytest.raises(ParamError):
        resolve_task_type(GEN_VIDEO, "video", None)


def test_unknown_gen_type_rejected():
    with pytest.raises(ParamError):
        resolve_task_type("audio_gen", None)
