"""OmniDrama 核心数据契约 (drama_schema.py) 单元测试套件."""
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from omnidrama.schemas.drama_schema import (
    ShotScaleEnum,
    CameraMotionEnum,
    ReferenceRoleEnum,
    ReferenceImageConfig,
    CharacterConsistencyCard,
    CharacterAsset,
    PropAsset,
    Shot,
    DramaProject,
)


def test_reference_image_config_validation():
    """测试 ReferenceImageConfig 构造、默认值与边界权重."""
    ref = ReferenceImageConfig(url="https://example.com/face.png")
    assert ref.url == "https://example.com/face.png"
    assert ref.role == ReferenceRoleEnum.FACE
    assert ref.weight == 1.0
    assert ref.cref_weight == 100
    assert ref.ip_adapter_weight == 0.8
    assert ref.notes == ""

    # 自定义角色与合法权重
    ref_costume = ReferenceImageConfig(
        url="https://example.com/costume.png",
        role="costume",
        weight=0.85,
        cref_weight=80,
        ip_adapter_weight=1.1,
        notes="核心风衣设计"
    )
    assert ref_costume.role == "costume"
    assert ref_costume.weight == 0.85
    assert ref_costume.reference_type == "costume"
    assert ref_costume.description == "核心风衣设计"

    # 负数权重边界校验
    with pytest.raises(ValidationError):
        ReferenceImageConfig(url="https://example.com/bad.png", weight=-0.5)

    # cref_weight 边界校验 (>100)
    with pytest.raises(ValidationError):
        ReferenceImageConfig(url="https://example.com/bad.png", cref_weight=150)


def test_reference_image_config_coercion_and_aliases():
    """测试 ReferenceImageConfig 字符串自动转换与别名兼容."""
    # 字符串入参直接解析
    ref_from_str = ReferenceImageConfig.model_validate("https://example.com/direct.png")
    assert ref_from_str.url == "https://example.com/direct.png"
    assert ref_from_str.image_url == "https://example.com/direct.png"

    # 字典别名 image_url / cref_url / reference_type / description
    ref_dict = ReferenceImageConfig.model_validate({
        "image_url": "https://example.com/alias.png",
        "reference_type": "style",
        "description": "画风参考"
    })
    assert ref_dict.url == "https://example.com/alias.png"
    assert ref_dict.role == "style"
    assert ref_dict.notes == "画风参考"


def test_character_consistency_card_defaults():
    """测试 CharacterConsistencyCard 默认构造与空安全."""
    card = CharacterConsistencyCard()
    assert card.facial_lock == ""
    assert card.hair_lock == ""
    assert card.costume_lock == ""
    assert card.exclusive_negative_prompt == ""
    assert card.reference_images == []
    assert card.facial_bone_structure == ""
    assert card.hairstyle_and_color == ""
    assert card.costume_and_wardrobe == ""
    assert card.negative_prompt == ""


def test_character_consistency_card_full_and_aliases():
    """测试 CharacterConsistencyCard 完整设值、别名兼容与嵌套参考图类型转换."""
    card = CharacterConsistencyCard(
        facial_bone_structure="精致东方骨相，高颅顶，丹凤眼",
        hairstyle_and_color="墨黑长直发，两鬓留白",
        costume_and_wardrobe="玄黑暗纹织锦长袍，银丝滚边",
        negative_prompt="现代西服, 短发, 异色瞳",
        reference_images=[
            "https://example.com/face_str.png",
            ReferenceImageConfig(url="https://example.com/costume.png", role=ReferenceRoleEnum.COSTUME),
            {"url": "https://example.com/dict.png", "role": "style", "weight": 1.2}
        ]
    )
    assert card.facial_lock == "精致东方骨相，高颅顶，丹凤眼"
    assert card.hair_lock == "墨黑长直发，两鬓留白"
    assert card.costume_lock == "玄黑暗纹织锦长袍，银丝滚边"
    assert card.exclusive_negative_prompt == "现代西服, 短发, 异色瞳"
    assert len(card.reference_images) == 3
    assert card.reference_images[0].url == "https://example.com/face_str.png"
    assert card.reference_images[1].role == ReferenceRoleEnum.COSTUME
    assert card.reference_images[2].weight == 1.2


def test_character_asset_backward_compatibility():
    """测试 CharacterAsset 向后兼容性 (不传新字段也能正常构造)."""
    char = CharacterAsset(
        name="叶辰",
        visual_tags="handsome Chinese actor, sharp eyes",
        visual_anchor="身着玄黑劲装"
    )
    assert char.turnaround_prompt == ""
    assert char.turnaround_image == ""
    assert char.archetype == ""
    assert char.consistency_card is None
    # 测试 safe_consistency_card 属性即使在 None 时也不会抛出 AttributeError
    assert char.safe_consistency_card.facial_lock == ""
    assert char.safe_consistency_card.exclusive_negative_prompt == ""


def test_character_asset_with_consistency_card():
    """测试 CharacterAsset 搭载母版原型与一致性卡."""
    card = CharacterConsistencyCard(facial_lock="刀削斧凿般的下颌线，冷冽鹰隼般的眼眸")
    char = CharacterAsset(
        name="顾沉舟",
        visual_tags="tall, sharp suited CEO",
        archetype="05_modern_male_boss",
        turnaround_prompt="16:9 model sheet, three views, white cyclorama background",
        turnaround_image="/output/char_05_turnaround.png",
        consistency_card=card
    )
    assert char.archetype == "05_modern_male_boss"
    assert char.turnaround_prompt == "16:9 model sheet, three views, white cyclorama background"
    assert char.turnaround_image == "/output/char_05_turnaround.png"
    assert char.consistency_card is not None
    assert char.consistency_card.facial_lock == "刀削斧凿般的下颌线，冷冽鹰隼般的眼眸"
    assert char.safe_consistency_card.facial_lock == "刀削斧凿般的下颌线，冷冽鹰隼般的眼眸"


def test_character_asset_legacy_key_normalization():
    """测试 CharacterAsset 从旧版/前端字段 (traits, role, voice) 自动规范化."""
    legacy_char_dict = {
        "name": "易冷",
        "role": "男一号 / 核心主角 (顶级特工)",
        "voice": "云希 (磁性沉稳霸道)",
        "traits": "8k电影级真人视觉，32岁，短寸发型，黑色战术风衣",
        "consistency_card": ""  # 空字符串自动转为 None
    }
    char = CharacterAsset.model_validate(legacy_char_dict)
    assert char.name == "易冷"
    assert char.visual_tags == "8k电影级真人视觉，32岁，短寸发型，黑色战术风衣"
    assert char.bio == "男一号 / 核心主角 (顶级特工)"
    assert char.voice_name == "云希 (磁性沉稳霸道)"
    assert char.consistency_card is None


def test_prop_asset_validation():
    """测试 PropAsset 模型校验、默认值与序列化."""
    prop = PropAsset(
        name="龙王令牌",
        category="magical_item",
        description="号令四海八荒龙王殿的至尊至宝",
        visual_tags="ancient dark gold medallion, dragon engraving",
        feature_lock="玄金重铸，盘龙双眸嵌血玉",
        turnaround_prompt="16:9 prop turnaround, front, side, angled close-up",
        negative_prompt="modern text, plastic, cartoon",
        reference_images=["https://example.com/prop_ref1.png", {"url": "https://example.com/prop_ref2.png"}]
    )
    assert prop.name == "龙王令牌"
    assert prop.category == "magical_item"
    assert prop.feature_lock == "玄金重铸，盘龙双眸嵌血玉"
    assert prop.negative_prompt == "modern text, plastic, cartoon"
    assert len(prop.reference_images) == 2
    assert prop.reference_images[1] == "https://example.com/prop_ref2.png"

    dumped = prop.model_dump()
    assert dumped["name"] == "龙王令牌"
    assert dumped["feature_lock"] == "玄金重铸，盘龙双眸嵌血玉"

    # 空名称默认容错
    prop_unnamed = PropAsset(name="   ")
    assert prop_unnamed.name == "未命名道具"


def test_shot_new_fields_and_legacy_aliases():
    """测试 Shot 新增负向词、道具引用与多模态参数以及旧版键名兼容."""
    # 默认值
    shot_default = Shot(
        shot_id=1,
        dialogue="今日我重返江城！",
        visual_prompt="a man standing in heavy rain"
    )
    assert shot_default.negative_prompt == ""
    assert shot_default.prop_refs == []
    assert shot_default.midjourney_prompt == ""
    assert shot_default.ip_adapter_params == {}

    # 旧版键名 (id, scale, motion, image, audio) 与大写 Enum 字符串
    legacy_shot_dict = {
        "id": 10,
        "speaker": "易冷",
        "scale": "WIDE_SHOT",
        "motion": "ZOOM_IN",
        "dialogue": "雨停了。",
        "visual_prompt": "8k cinematic wide shot",
        "image": "/output/shot10.png",
        "audio": "/output/shot10.mp3",
        "prop_refs": None,
        "ip_adapter_params": None
    }
    shot_legacy = Shot.model_validate(legacy_shot_dict)
    assert shot_legacy.shot_id == 10
    assert shot_legacy.shot_scale == ShotScaleEnum.WIDE_SHOT
    assert shot_legacy.camera_motion == CameraMotionEnum.ZOOM_IN
    assert shot_legacy.image_path == "/output/shot10.png"
    assert shot_legacy.audio_path == "/output/shot10.mp3"
    assert shot_legacy.prop_refs == []
    assert shot_legacy.ip_adapter_params == {}


def test_drama_project_props_coercion():
    """测试 DramaProject.props 对 None 与字符串列表的自动容错转换."""
    # props 为 None 自动转为空列表
    proj_none = DramaProject.model_validate({
        "title": "测试项目",
        "props": None
    })
    assert proj_none.props == []

    # props 为字符串列表时自动转换为 PropAsset 对象
    proj_str_props = DramaProject.model_validate({
        "title": "测试项目",
        "props": ["龙王令", "修罗戒", {"name": "诛仙剑", "category": "weapon"}]
    })
    assert len(proj_str_props.props) == 3
    assert proj_str_props.props[0].name == "龙王令"
    assert proj_str_props.props[0].category == "prop"
    assert proj_str_props.props[1].name == "修罗戒"
    assert proj_str_props.props[2].name == "诛仙剑"
    assert proj_str_props.props[2].category == "weapon"


def test_drama_project_roundtrip_serialization():
    """测试完整 DramaProject 序列化与反序列化双向一致性."""
    proj = DramaProject(
        title="龙王回归",
        genre="都市爽文",
        synopsis="三年之期已到，恭迎龙王！",
        characters=[
            CharacterAsset(
                name="叶辰",
                visual_tags="sharp eyes, tall figure",
                archetype="05_modern_male_boss",
                turnaround_prompt="16:9 model sheet, three views",
                consistency_card=CharacterConsistencyCard(
                    facial_lock="深邃剑眉，冷冽眼眸",
                    costume_lock="黑色定制西装",
                    exclusive_negative_prompt="浓妆, 崩坏",
                    reference_images=[ReferenceImageConfig(url="https://example.com/yc.png")]
                )
            )
        ],
        shots=[
            Shot(
                shot_id=1,
                dialogue="我回来了",
                visual_prompt="a man returns under dark storm clouds",
                negative_prompt="cartoon, flat color",
                prop_refs=["龙王令牌"],
                midjourney_prompt="cinematic still --cref https://example.com/yc.png --cw 100 --ar 9:16",
                ip_adapter_params={"weight": 1.2}
            )
        ],
        props=[
            PropAsset(
                name="龙王令牌",
                category="magical_item",
                feature_lock="玄金盘龙",
                turnaround_prompt="16:9 prop views"
            )
        ]
    )

    json_str = proj.model_dump_json()
    reloaded = DramaProject.model_validate_json(json_str)

    assert reloaded.title == "龙王回归"
    assert len(reloaded.characters) == 1
    assert reloaded.characters[0].name == "叶辰"
    assert reloaded.characters[0].archetype == "05_modern_male_boss"
    assert reloaded.characters[0].consistency_card is not None
    assert reloaded.characters[0].consistency_card.facial_lock == "深邃剑眉，冷冽眼眸"
    assert len(reloaded.props) == 1
    assert reloaded.props[0].name == "龙王令牌"
    assert reloaded.shots[0].prop_refs == ["龙王令牌"]
    assert reloaded.shots[0].midjourney_prompt.startswith("cinematic still")
    assert reloaded.shots[0].ip_adapter_params["weight"] == 1.2


def test_production_current_project_json_loading():
    """测试加载生产格式 current_project.json（若未入库或被前置测试覆盖，则使用标准生产快照夹具），确保 0 ValidationError."""
    project_path = Path(__file__).resolve().parent.parent / "output" / "current_project.json"
    raw_data = None
    if project_path.exists():
        try:
            loaded = json.loads(project_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("title") == "特工易冷":
                raw_data = loaded
        except Exception:
            raw_data = None

    if raw_data is None:
        raw_data = {
            "title": "特工易冷",
            "genre": "都市冷面特工爽剧",
            "characters": [
                {
                    "name": "易冷",
                    "role": "男一号 / 核心主角 (顶级特工)",
                    "voice": "云希 (磁性沉稳霸道)",
                    "traits": "8k电影级真人视觉，冷峻剑眉，黑色战术风衣",
                    "avatar": "/api/shots/1/image",
                },
                {
                    "name": "易暖暖",
                    "role": "女主角",
                    "voice": "晓涵 (温柔清纯甜美)",
                    "traits": "清纯坚韧",
                    "avatar": "/api/shots/2/image",
                },
                {
                    "name": "刀疤强",
                    "role": "反派头目",
                    "voice": "云健 (嚣张跋扈)",
                    "traits": "凶狠嚣张",
                    "avatar": "/api/shots/3/image",
                },
            ],
            "shots": [
                {
                    "id": i,
                    "speaker": "易冷" if i % 2 == 1 else "刀疤强",
                    "scale": "WIDE_SHOT" if i == 1 else "CLOSE_UP",
                    "motion": "ZOOM_IN",
                    "dialogue": f"第 {i} 镜测试台词",
                    "visual_prompt": f"cinematic shot {i}",
                    "image": f"/api/shots/{i}/image",
                    "audio": f"/api/shots/{i}/audio",
                }
                for i in range(1, 7)
            ],
        }

    project = DramaProject.model_validate(raw_data)
    assert project.title == "特工易冷"
    assert len(project.characters) == 3
    assert len(project.shots) == 6
    assert project.props == []

    # 验证角色字段映射
    char0 = project.characters[0]
    assert char0.name == "易冷"
    assert "8k电影级真人视觉" in char0.visual_tags
    assert char0.bio == "男一号 / 核心主角 (顶级特工)"
    assert char0.voice_name == "云希 (磁性沉稳霸道)"
    assert char0.turnaround_prompt == ""
    assert char0.safe_consistency_card.facial_lock == ""

    # 验证镜头字段映射
    shot0 = project.shots[0]
    assert shot0.shot_id == 1
    assert shot0.shot_scale == ShotScaleEnum.WIDE_SHOT
    assert shot0.camera_motion == CameraMotionEnum.ZOOM_IN
    assert shot0.image_path == "/api/shots/1/image"
    assert shot0.audio_path == "/api/shots/1/audio"
    assert shot0.negative_prompt == ""
    assert shot0.prop_refs == []
