from __future__ import annotations

from app.core.exceptions import CapabilityUnsupportedError, ParamError

GEN_IMAGE = "image_gen"
GEN_VIDEO = "video_gen"

TASK_TYPE_TXT2IMG = "txt2img"
TASK_TYPE_IMG2IMG = "img2img"
TASK_TYPE_TXT2VID = "txt2vid"
TASK_TYPE_IMG2VID = "img2vid"
TASK_TYPE_VID2VID = "vid2vid"
TASK_TYPE_VID_EDIT = "vid_edit"

VIDEO_SUB_COPY = "copy_style"
VIDEO_SUB_EDIT = "edit"


def resolve_task_type(
    gen_type: str,
    asset_media_type: str | None,
    video_sub_mode: str | None = None,
) -> str:
    """由前端输入（大类 + 是否上传素材 + 视频子模式）推断内部 task_type。"""
    if gen_type == GEN_IMAGE:
        if asset_media_type is None:
            return TASK_TYPE_TXT2IMG
        if asset_media_type == "image":
            return TASK_TYPE_IMG2IMG
        if asset_media_type == "video":
            raise CapabilityUnsupportedError("图片入口不支持视频素材")
        raise ParamError("素材类型非法")

    if gen_type == GEN_VIDEO:
        if asset_media_type is None:
            return TASK_TYPE_TXT2VID
        if asset_media_type == "image":
            return TASK_TYPE_IMG2VID
        if asset_media_type == "video":
            if video_sub_mode == VIDEO_SUB_COPY:
                return TASK_TYPE_VID2VID
            if video_sub_mode == VIDEO_SUB_EDIT:
                return TASK_TYPE_VID_EDIT
            raise ParamError("上传视频素材需指定子模式")
        raise ParamError("素材类型非法")

    raise ParamError("gen_type 非法")
