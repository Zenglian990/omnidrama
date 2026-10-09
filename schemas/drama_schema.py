"""OmniDrama 核心数据契约 (Data Contracts)."""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ShotScaleEnum(str, Enum):
    EXTREME_CLOSE_UP = "extreme_close_up"  # 大特写（眼部、嘴角神态）
    CLOSE_UP = "close_up"                  # 特写（头部肖像、情绪爆发）
    MEDIUM_SHOT = "medium_shot"            # 中景（半身、互动对话）
    FULL_SHOT = "full_shot"                # 全景（全身动作、肢体对抗）
    WIDE_SHOT = "wide_shot"                # 远景（大环境、氛围烘托）


class CameraMotionEnum(str, Enum):
    ZOOM_IN = "zoom_in"      # 镜头推进（聚焦强调、紧张压迫）
    ZOOM_OUT = "zoom_out"    # 镜头拉远（揭示环境、悬念收尾）
    PAN_LEFT = "pan_left"    # 镜头向左平移（横向巡视、转场）
    PAN_RIGHT = "pan_right"  # 镜头向右平移
    SHAKE = "shake"          # 镜头震动（受击、震惊、爆炸、情绪激动）
    STATIC = "static"        # 静止镜头（平稳过渡）


class CharacterAsset(BaseModel):
    name: str = Field(..., description="角色姓名")
    gender: str = Field(default="male", description="性别: male / female")
    visual_tags: str = Field(..., description="锁脸与外观特征Tag，用于保持图像一致性")
    voice_name: str = Field(default="zh-CN-YunxiNeural", description="绑定的edge-tts音色代号")
    bio: Optional[str] = Field(default="", description="角色人设背景")


class Shot(BaseModel):
    shot_id: int = Field(..., description="镜头序号")
    shot_scale: ShotScaleEnum = Field(default=ShotScaleEnum.MEDIUM_SHOT, description="景别")
    camera_motion: CameraMotionEnum = Field(default=CameraMotionEnum.ZOOM_IN, description="运镜动作")
    speaker: str = Field(default="旁白", description="说话人姓名")
    dialogue: str = Field(..., description="台词或旁白文本")
    visual_prompt: str = Field(..., description="分镜画面生图提示词 (含风格与人物外观约束)")
    duration_seconds: Optional[float] = Field(default=None, description="镜头时长（秒），由语音生成时长决定")
    image_path: Optional[str] = Field(default=None, description="生成的画面静图路径")
    audio_path: Optional[str] = Field(default=None, description="生成的语音音频路径")


class DramaProject(BaseModel):
    title: str = Field(..., description="短剧/漫剧标题")
    genre: str = Field(default="都市热血", description="题材类型")
    synopsis: str = Field(default="", description="剧情大纲")
    characters: List[CharacterAsset] = Field(default_factory=list, description="登场角色资产列表")
    shots: List[Shot] = Field(default_factory=list, description="全剧分镜列表")
