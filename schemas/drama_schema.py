"""OmniDrama 核心数据契约 (Data Contracts - 电影级角色与道具资产一致性控制升级版)."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator


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


class ReferenceRoleEnum(str, Enum):
    """多模态参考底图角色类型枚举."""
    FACE = "face"          # 骨相五官锁 (Face / Facial identity)
    COSTUME = "costume"    # 服饰装束锁 (Costume / Clothing / Accessories)
    STYLE = "style"        # 画风质感锁 (Art style / Lighting / Palette)
    POSE = "pose"          # 肢体姿态锁 (Body pose / Framing / Silhouette)
    GENERAL = "general"    # 全身综合参考 (Full-body general reference)


class ReferenceImageConfig(BaseModel):
    """多模态参考底图配置 (用于 Midjourney --cref, IP-Adapter, Seedance 2.0 参考图管道)."""
    url: str = Field(default="", description="参考底图 URL 或本地文件路径")
    role: Union[ReferenceRoleEnum, str] = Field(
        default=ReferenceRoleEnum.FACE,
        description="参考底图作用类型: face(骨相五官), costume(服饰装束), style(画风光影), pose(姿态动作), general(全身综合)"
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="参考权重 (IP-Adapter 为 0.0~2.0，Midjourney --cw 可支持 0~100)"
    )
    cref_weight: int = Field(
        default=100,
        ge=0,
        le=100,
        description="Midjourney --cw 角色权重 (0~100, 0仅锁脸, 100锁脸与服饰)"
    )
    ip_adapter_weight: float = Field(
        default=0.8,
        ge=0.0,
        le=1.5,
        description="ComfyUI / SD IP-Adapter 注入权重 (0.0~1.5)"
    )
    notes: Optional[str] = Field(
        default="",
        description="参考图备注说明或局部特征提示"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_ref_config(cls, data: Any):
        if isinstance(data, str):
            return {"url": data}
        if not isinstance(data, dict):
            return data
        if "image_url" in data and "url" not in data:
            data["url"] = data["image_url"]
        if "cref_url" in data and "url" not in data:
            data["url"] = data["cref_url"]
            data.setdefault("role", ReferenceRoleEnum.FACE)
        if "reference_type" in data and "role" not in data:
            data["role"] = data["reference_type"]
        if "description" in data and "notes" not in data:
            data["notes"] = data["description"]
        return data

    @property
    def image_url(self) -> str:
        return self.url

    @property
    def reference_type(self) -> str:
        return str(self.role.value if hasattr(self.role, "value") else self.role)

    @property
    def description(self) -> str:
        return self.notes or ""


class CharacterConsistencyCard(BaseModel):
    """专业电影级角色一致性控制卡 (Character Consistency Card)."""
    facial_lock: str = Field(
        default="",
        description="骨相五官锁 (五官骨骼比例、眼型、鼻梁、唇部及面部标志性特征)"
    )
    hair_lock: str = Field(
        default="",
        description="发型发色锁 (发型轮廓、发色、发丝质感与光泽度)"
    )
    costume_lock: str = Field(
        default="",
        description="服饰装束锁 (标志性服装款式、材质、核心配色方案与配饰)"
    )
    exclusive_negative_prompt: str = Field(
        default="",
        description="角色专属防崩排异负向提示词 (排除走形、非设定特征、异色等)"
    )
    reference_images: List[ReferenceImageConfig] = Field(
        default_factory=list,
        description="多模态参考底图配置列表"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_consistency_card(cls, data: Any):
        if not isinstance(data, dict):
            return data
        if "facial_bone_structure" in data and not data.get("facial_lock"):
            data["facial_lock"] = data["facial_bone_structure"]
        if "hairstyle_and_color" in data and not data.get("hair_lock"):
            data["hair_lock"] = data["hairstyle_and_color"]
        if "costume_and_wardrobe" in data and not data.get("costume_lock"):
            data["costume_lock"] = data["costume_and_wardrobe"]
        if "negative_prompt" in data and not data.get("exclusive_negative_prompt"):
            data["exclusive_negative_prompt"] = data["negative_prompt"]
        if "reference_image" in data and not data.get("reference_images"):
            ref = data["reference_image"]
            data["reference_images"] = [ref] if ref else []
        return data

    @field_validator("reference_images", mode="before")
    @classmethod
    def coerce_reference_images(cls, v):
        if not v:
            return []
        if isinstance(v, list):
            res = []
            for item in v:
                if item is None:
                    continue
                if isinstance(item, str):
                    res.append({"url": item})
                elif isinstance(item, (dict, ReferenceImageConfig)):
                    res.append(item)
            return res
        return v

    @property
    def facial_bone_structure(self) -> str:
        return self.facial_lock

    @property
    def hairstyle_and_color(self) -> str:
        return self.hair_lock

    @property
    def costume_and_wardrobe(self) -> str:
        return self.costume_lock

    @property
    def negative_prompt(self) -> str:
        return self.exclusive_negative_prompt


class CharacterAsset(BaseModel):
    name: str = Field(..., description="角色姓名")
    gender: str = Field(default="male", description="性别: male / female")
    visual_tags: str = Field(default="", description="锁脸与外观特征Tag，用于保持图像一致性")
    voice_name: str = Field(default="zh-CN-YunxiNeural", description="绑定的edge-tts音色代号")
    bio: Optional[str] = Field(default="", description="角色人设背景")
    visual_anchor: Optional[str] = Field(default="", description="正面全身物理特征锚点（发型、面容、服装主色调、配饰）")
    voice_prompt: Optional[str] = Field(default="", description="角色专属音色与情绪提示词")
    turnaround_prompt: Optional[str] = Field(
        default="",
        description="16:9 人物三视图定妆提示词 (正/侧/背+胸像特写，纯白无缝影棚背景)"
    )
    turnaround_image: Optional[str] = Field(
        default="",
        description="已生成的人物三视图定妆图像路径或URL"
    )
    archetype: Optional[str] = Field(
        default="",
        description="绑定的人设母版原型 ID (如 04_modern_female_urban, 05_modern_male_boss 等)"
    )
    consistency_card: Optional[CharacterConsistencyCard] = Field(
        default=None,
        description="专业电影级角色一致性控制卡"
    )

    @property
    def safe_consistency_card(self) -> CharacterConsistencyCard:
        """安全访问一致性控制卡，避免 None 导致 AttributeError."""
        return self.consistency_card or CharacterConsistencyCard()

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any):
        if not isinstance(data, dict):
            return data
        if not data.get("visual_tags"):
            if data.get("traits"):
                data["visual_tags"] = data["traits"]
        if not data.get("bio"):
            if data.get("role"):
                data["bio"] = data["role"]
        if not data.get("voice_name"):
            if data.get("voice"):
                data["voice_name"] = data["voice"]
        if data.get("consistency_card") == "":
            data["consistency_card"] = None
        return data


class PropAsset(BaseModel):
    """重要道具资产 (Prop Asset - 支持道具三视图与特征锁定)."""
    name: str = Field(default="未命名道具", description="道具名称")
    category: str = Field(default="prop", description="道具类别 (weapon, vehicle, magical_item, accessory, object 等)")
    description: Optional[str] = Field(default="", description="道具背景故事与核心功能描述")
    visual_tags: str = Field(default="", description="道具材质、时代风格与视觉生成外观提示词")
    feature_lock: Optional[str] = Field(default="", description="道具特征锁定词 (材质纹理、符文雕花、专属光芒/色彩)")
    turnaround_prompt: Optional[str] = Field(default="", description="16:9 道具多角度/三视图工业设计提示词")
    negative_prompt: Optional[str] = Field(default="", description="道具专属防变形负向词")
    reference_images: List[str] = Field(default_factory=list, description="道具多角度设计或参考底图 URL 列表")

    @field_validator("name", mode="before")
    @classmethod
    def ensure_name(cls, v):
        if not v or not str(v).strip():
            return "未命名道具"
        return str(v).strip()

    @model_validator(mode="before")
    @classmethod
    def normalize_prop(cls, data: Any):
        if not isinstance(data, dict):
            return data
        if "reference_image" in data and not data.get("reference_images"):
            ref = data["reference_image"]
            data["reference_images"] = [ref] if ref else []
        return data

    @field_validator("reference_images", mode="before")
    @classmethod
    def coerce_prop_refs(cls, v):
        if not v:
            return []
        if isinstance(v, list):
            out = []
            for item in v:
                if item is None:
                    continue
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    out.append(str(item.get("url") or item.get("path") or ""))
                else:
                    out.append(str(item))
            return [x for x in out if x]
        return v


class Shot(BaseModel):
    shot_id: int = Field(..., description="镜头序号")
    shot_scale: ShotScaleEnum = Field(default=ShotScaleEnum.MEDIUM_SHOT, description="景别")
    camera_motion: CameraMotionEnum = Field(default=CameraMotionEnum.ZOOM_IN, description="运镜动作")
    speaker: str = Field(default="旁白", description="说话人姓名")
    dialogue: str = Field(..., description="台词或旁白文本")
    visual_prompt: str = Field(..., description="分镜画面生图提示词 (含风格与人物外观约束)")
    action_beat: Optional[str] = Field(default="", description="动作节拍/画面关键事件")
    sfx: Optional[str] = Field(default="", description="环境音效/拟声动作声")
    blocking: Optional[str] = Field(default="", description="人物关系与构图走位")
    seedance_prompt: Optional[str] = Field(default="", description="字节火山Seedance 2.0官方结构化多模态分镜词")
    duration_seconds: Optional[float] = Field(default=None, description="镜头时长（秒），由语音生成时长决定")
    image_path: Optional[str] = Field(default=None, description="生成的画面静图路径")
    audio_path: Optional[str] = Field(default=None, description="生成的语音音频路径")
    negative_prompt: Optional[str] = Field(
        default="",
        description="当前镜头的负向生图提示词 (防崩词/排异词)"
    )
    prop_refs: List[str] = Field(
        default_factory=list,
        description="当前镜头引用的道具名称列表"
    )
    midjourney_prompt: Optional[str] = Field(
        default="",
        description="针对 Midjourney 编译的专业提示词 (含 --cref, --cw, --ar 9:16 等)"
    )
    ip_adapter_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="ComfyUI / SD IP-Adapter 多图参考与权重控制参数字典"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_shot(cls, data: Any):
        if not isinstance(data, dict):
            return data
        if "shot_id" not in data and "id" in data:
            data["shot_id"] = data["id"]
        if "shot_scale" not in data and "scale" in data:
            data["shot_scale"] = str(data["scale"]).lower()
        elif "shot_scale" in data and isinstance(data["shot_scale"], str):
            data["shot_scale"] = data["shot_scale"].lower()
        if "camera_motion" not in data and "motion" in data:
            data["camera_motion"] = str(data["motion"]).lower()
        elif "camera_motion" in data and isinstance(data["camera_motion"], str):
            data["camera_motion"] = data["camera_motion"].lower()
        if "image_path" not in data and "image" in data:
            data["image_path"] = data["image"]
        if "audio_path" not in data and "audio" in data:
            data["audio_path"] = data["audio"]
        return data

    @field_validator("prop_refs", mode="before")
    @classmethod
    def coerce_prop_refs(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(item) for item in v if item is not None]
        return v

    @field_validator("ip_adapter_params", mode="before")
    @classmethod
    def coerce_ip_params(cls, v):
        if v is None:
            return {}
        return v


class DramaProject(BaseModel):
    title: str = Field(..., description="短剧/漫剧标题")
    genre: str = Field(default="都市热血", description="题材类型")
    synopsis: str = Field(default="", description="剧情大纲")
    characters: List[CharacterAsset] = Field(default_factory=list, description="登场角色资产列表")
    shots: List[Shot] = Field(default_factory=list, description="全剧分镜列表")
    props: List[PropAsset] = Field(default_factory=list, description="全剧道具资产列表")

    @field_validator("props", mode="before")
    @classmethod
    def coerce_props(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            res = []
            for item in v:
                if item is None:
                    continue
                if isinstance(item, str):
                    if item.strip():
                        res.append({"name": item.strip()})
                elif isinstance(item, (dict, PropAsset)):
                    res.append(item)
            return res
        return v

    @field_validator("characters", "shots", mode="before")
    @classmethod
    def coerce_lists(cls, v):
        if v is None:
            return []
        return v


__all__ = [
    "ShotScaleEnum",
    "CameraMotionEnum",
    "ReferenceRoleEnum",
    "ReferenceImageConfig",
    "CharacterConsistencyCard",
    "CharacterAsset",
    "PropAsset",
    "Shot",
    "DramaProject",
]
