"""OmniDrama 爆款人设母版库 (omnidrama/config/archetypes.py) 单元测试套件."""
import json
import pytest
from pydantic import ValidationError

from omnidrama.schemas.drama_schema import (
    CharacterAsset,
    CharacterConsistencyCard,
    ShotScaleEnum,
)
from omnidrama.config.archetypes import (
    BUILTIN_ARCHETYPES,
    DramaArchetype,
    ConsistencyCard,
    list_archetypes,
    get_archetype,
    apply_archetype_to_character,
    create_character_from_archetype,
    compile_character_consistency_prompt,
    compile_consistency_prompt,
)


class TestArchetypeRegistryCompleteness:
    """测试四大经典爆款人设母版的完整性与规范约束."""

    EXPECTED_IDS = [
        "04_modern_female_urban",
        "05_modern_male_boss",
        "06_ancient_male_noble",
        "08_antagonist_female_greentea",
    ]

    def test_registry_contains_all_canonical_archetypes(self):
        """验证内置字典包含全部 4 款指定母版."""
        for arch_id in self.EXPECTED_IDS:
            assert arch_id in BUILTIN_ARCHETYPES, f"母版库缺少核心母版: {arch_id}"
            arch = BUILTIN_ARCHETYPES[arch_id]
            assert isinstance(arch, DramaArchetype)
            assert arch.id == arch_id
            assert len(arch.code) == 2

    def test_modern_female_urban_spec(self):
        """验证 04 现代女主-都市丽人 的音色、锁脸及三视图提示词."""
        arch = BUILTIN_ARCHETYPES["04_modern_female_urban"]
        assert arch.name == "现代女主-都市丽人"
        assert arch.gender == "female"
        assert arch.role_type == "female_lead"
        assert arch.voice_name == "zh-CN-XiaoxiaoNeural"
        assert arch.voice_rate == "+2%"
        assert arch.voice_pitch == "+0Hz"
        
        # 一致性锁卡
        card = arch.consistency_card
        assert "oval face" in card.facial_lock
        assert "French-style" in card.hair_lock
        assert "oatmeal-white" in card.costume_lock
        assert "childish round face" in card.exclusive_negative_prompt
        
        # 三视图 16:9 提示词包含关键机位视点
        assert "front view" in arch.turnaround_prompt
        assert "90-degree side profile view" in arch.turnaround_prompt
        assert "180-degree rear view" in arch.turnaround_prompt
        assert "head-and-shoulders bust portrait" in arch.turnaround_prompt
        assert "pure plain white cyclorama" in arch.turnaround_prompt
        assert arch.generation_params.get("turnaround_aspect_ratio") == "16:9"

    def test_modern_male_boss_spec(self):
        """验证 05 现代男主-霸总 的音色、锁脸及三视图提示词."""
        arch = BUILTIN_ARCHETYPES["05_modern_male_boss"]
        assert arch.name == "现代男主-霸总"
        assert arch.gender == "male"
        assert arch.role_type == "male_lead"
        assert arch.voice_name == "zh-CN-YunxiNeural"
        assert arch.voice_rate == "-4%"
        assert arch.voice_pitch == "-3Hz"
        
        card = arch.consistency_card
        assert "angular mandibles" in card.facial_lock
        assert "slicked-back" in card.hair_lock
        assert "midnight-navy three-piece" in card.costume_lock
        assert "boyish baby face" in card.exclusive_negative_prompt
        
        assert "front view" in arch.turnaround_prompt
        assert "90-degree side profile" in arch.turnaround_prompt
        assert "180-degree rear view" in arch.turnaround_prompt

    def test_ancient_male_noble_spec(self):
        """验证 06 古装男主-清冷世子 的音色、锁脸及三视图提示词."""
        arch = BUILTIN_ARCHETYPES["06_ancient_male_noble"]
        assert arch.name == "古装男主-清冷世子"
        assert arch.gender == "male"
        assert arch.role_type == "male_lead"
        assert arch.voice_name == "zh-CN-YunjianNeural"
        assert arch.voice_rate == "-2%"
        assert arch.voice_pitch == "+1Hz"
        
        card = arch.consistency_card
        assert "classical Chinese" in card.facial_lock
        assert "topknot" in card.hair_lock
        assert "Hanfu" in card.costume_lock
        assert "modern clothing" in card.exclusive_negative_prompt
        
        assert "front view" in arch.turnaround_prompt
        assert "90-degree side profile" in arch.turnaround_prompt
        assert "180-degree rear view" in arch.turnaround_prompt

    def test_antagonist_female_greentea_spec(self):
        """验证 08 反派女二-绿茶千金 的音色、锁脸及三视图提示词."""
        arch = BUILTIN_ARCHETYPES["08_antagonist_female_greentea"]
        assert arch.name == "反派女二-绿茶千金"
        assert arch.gender == "female"
        assert arch.role_type == "antagonist_female"
        assert arch.voice_name == "zh-CN-XiaoyiNeural"
        assert arch.voice_rate == "+4%"
        assert arch.voice_pitch == "+3Hz"
        
        card = arch.consistency_card
        assert "heart-shaped Asian face" in card.facial_lock
        assert "half-up half-down princess" in card.hair_lock
        assert "tweed" in card.costume_lock
        assert "overt villain evil smirk" in card.exclusive_negative_prompt
        
        assert "front view" in arch.turnaround_prompt
        assert "90-degree side profile" in arch.turnaround_prompt
        assert "180-degree rear view" in arch.turnaround_prompt


class TestArchetypeQueryAndLookup:
    """测试母版列表与灵活检索 API."""

    def test_list_archetypes_structure_and_order(self):
        """测试 list_archetypes 返回标准字典列表且排序稳定."""
        items = list_archetypes()
        assert len(items) == 4
        codes = [item["code"] for item in items]
        assert codes == ["04", "05", "06", "08"]

        for item in items:
            assert "id" in item
            assert "name" in item
            assert "gender" in item
            assert "role_type" in item
            assert "summary" in item
            assert "voice_name" in item
            assert "voice_rate" in item
            assert "voice_pitch" in item
            assert "voice_display" in item
            assert "visual_anchor" in item
            assert item["aspect_ratio"] == "9:16"
            assert item["turnaround_aspect_ratio"] == "16:9"

    def test_get_archetype_by_full_id(self):
        """测试通过完整全局 ID 检索."""
        arch = get_archetype("04_modern_female_urban")
        assert arch is not None
        assert arch.code == "04"
        assert arch.name == "现代女主-都市丽人"

    def test_get_archetype_by_code_prefix(self):
        """测试通过短代号检索 (04, 05, 06, 08)."""
        for code in ["04", "05", "06", "08"]:
            arch = get_archetype(code)
            assert arch is not None
            assert arch.code == code

        # 单数字前缀兼容
        arch_4 = get_archetype("4")
        assert arch_4 is not None
        assert arch_4.code == "04"

    def test_get_archetype_by_chinese_name(self):
        """测试通过中文名称或子串检索."""
        arch = get_archetype("现代男主-霸总")
        assert arch is not None
        assert arch.id == "05_modern_male_boss"

        arch_sub = get_archetype("清冷世子")
        assert arch_sub is not None
        assert arch_sub.id == "06_ancient_male_noble"

    def test_get_archetype_case_insensitive_and_whitespace(self):
        """测试大小写及空白字符鲁棒性."""
        arch = get_archetype("  04_MODERN_FEMALE_URBAN  ")
        assert arch is not None
        assert arch.id == "04_modern_female_urban"

    def test_get_archetype_non_existent(self):
        """测试检索不存在的母版安全返回 None."""
        assert get_archetype("99_fantasy_alien") is None
        assert get_archetype("") is None
        assert get_archetype(None) is None

    def test_get_archetype_whitespace_and_hyphen_edge_cases(self):
        """测试纯空白字符、制表换行符以及单一连字符检索安全返回 None，杜绝误匹配."""
        assert get_archetype("   ") is None
        assert get_archetype("\t\n") is None
        assert get_archetype("-") is None


class TestCharacterInstantiationAndApplication:
    """测试 CharacterAsset 创建、套用与深拷贝隔离性."""

    def test_create_character_from_archetype_default_name(self):
        """测试工厂函数生成默认姓名角色."""
        char = create_character_from_archetype("04")
        assert isinstance(char, CharacterAsset)
        assert char.name == "都市丽人"
        assert char.gender == "female"
        assert char.archetype == "04_modern_female_urban"
        assert char.voice_name == "zh-CN-XiaoxiaoNeural"
        assert char.turnaround_prompt != ""
        assert char.consistency_card is not None
        assert "oval face" in char.consistency_card.facial_lock

    def test_create_character_from_archetype_custom_name(self):
        """测试工厂函数生成自定义姓名角色."""
        char = create_character_from_archetype("05_modern_male_boss", character_name="顾霆琛")
        assert char.name == "顾霆琛"
        assert char.gender == "male"
        assert char.archetype == "05_modern_male_boss"
        assert char.voice_name == "zh-CN-YunxiNeural"

    def test_create_character_invalid_archetype_raises(self):
        """测试无效母版抛出 ValueError."""
        with pytest.raises(ValueError, match="未找到人设母版"):
            create_character_from_archetype("invalid_archetype_id")

    def test_create_character_whitespace_raises_value_error(self):
        """验证纯空白母版代号创建角色抛出 ValueError 而非静默套用母版 04."""
        with pytest.raises(ValueError, match="未找到人设母版"):
            create_character_from_archetype("   ")

    def test_apply_archetype_to_character(self):
        """测试将母版属性套用到现有角色."""
        existing = CharacterAsset(
            name="林楚楚",
            gender="female",
            visual_tags="simple girl",
            voice_name="zh-CN-XiaoxiaoNeural",
            bio="普通打工妹"
        )
        updated = apply_archetype_to_character(existing, "08_antagonist_female_greentea")
        assert updated.name == "林楚楚"  # 保留原有姓名
        assert updated.archetype == "08_antagonist_female_greentea"
        assert updated.voice_name == "zh-CN-XiaoyiNeural"
        assert "tweed" in updated.consistency_card.costume_lock
        assert "【人设母版: 反派女二-绿茶千金】" in updated.bio

    def test_apply_archetype_with_custom_name_override(self):
        """测试套用母版同时重命名角色."""
        existing = CharacterAsset(
            name="临时名",
            gender="male",
            visual_tags="temp",
        )
        updated = apply_archetype_to_character(existing, "06", custom_name="谢无妄")
        assert updated.name == "谢无妄"
        assert updated.gender == "male"
        assert updated.archetype == "06_ancient_male_noble"
        assert updated.voice_name == "zh-CN-YunjianNeural"

    def test_apply_archetype_invalid_id_raises(self):
        """测试套用无效母版抛出 ValueError."""
        char = CharacterAsset(name="测试")
        with pytest.raises(ValueError, match="未找到人设母版"):
            apply_archetype_to_character(char, "invalid_id")

    def test_apply_archetype_whitespace_raises_value_error(self):
        """验证纯空白母版代号套用到角色抛出 ValueError 而非静默覆盖."""
        char = CharacterAsset(name="测试角色")
        with pytest.raises(ValueError, match="未找到人设母版"):
            apply_archetype_to_character(char, "   ")

    def test_deep_copy_isolation_between_characters(self):
        """验证生成的多个角色对象及其一致性卡相互独立，避免引用共享污染."""
        char1 = create_character_from_archetype("05", character_name="总裁A")
        char2 = create_character_from_archetype("05", character_name="总裁B")

        assert char1.consistency_card is not char2.consistency_card
        assert char1.consistency_card is not BUILTIN_ARCHETYPES["05_modern_male_boss"].consistency_card

        # 修改 char1 不应影响 char2 或原始模板
        char1.consistency_card.facial_lock = "custom modified facial lock"
        assert char2.consistency_card.facial_lock != "custom modified facial lock"
        assert "angular mandibles" in BUILTIN_ARCHETYPES["05_modern_male_boss"].consistency_card.facial_lock


class TestConsistencyPromptCompilation:
    """测试分镜强锁定正向提示词与专属防崩负向词编译."""

    def test_compile_prompt_with_consistency_card(self):
        """测试含一致性控制卡的角色编译提示词."""
        char = create_character_from_archetype("04_modern_female_urban", character_name="姜若南")
        pos, neg = compile_character_consistency_prompt(
            character=char,
            shot_scale="close_up",
            emotion_action="眼中闪过一丝锐利的决断，冷冷抬眸注视对手"
        )
        
        # 正向词验证
        assert "8k cinematic live-action movie still" in pos
        assert "shot on ARRI Alexa 65" in pos
        assert "close up" in pos
        assert "photorealistic Chinese actor playing 姜若南" in pos
        assert "oval face structure" in pos
        assert "French-style" in pos
        assert "oatmeal-white" in pos
        assert "眼中闪过一丝锐利的决断" in pos
        assert "vertical 9:16" in pos
        
        # 负向词验证
        assert "cartoon, anime, 3d render" in neg
        assert "childish round face" in neg

    def test_compile_prompt_with_shot_scale_enum(self):
        """测试使用 ShotScaleEnum 传入景别参数."""
        char = create_character_from_archetype("05_modern_male_boss", character_name="陆琛")
        pos, neg = compile_character_consistency_prompt(
            character=char,
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            emotion_action="抬手整理定制西装袖扣"
        )
        assert "medium shot" in pos
        assert "陆琛" in pos
        assert "angular mandibles" in pos
        assert "抬手整理定制西装袖扣" in pos
        assert "boyish baby face" in neg

    def test_compile_prompt_fallback_without_card(self):
        """测试不具备一致性卡的角色退化为 visual_tags / visual_anchor."""
        char = CharacterAsset(
            name="路人甲",
            gender="male",
            visual_tags="ordinary bystander, wearing blue coat",
            visual_anchor="身穿蓝色外套的路人",
            consistency_card=None
        )
        pos, neg = compile_character_consistency_prompt(char, shot_scale="wide_shot")
        assert "ordinary bystander, wearing blue coat" in pos
        assert "photorealistic Chinese actor playing 路人甲" in pos
        assert "cartoon, anime, 3d render" in neg

    def test_compile_consistency_prompt_alias(self):
        """测试兼容别名 compile_consistency_prompt 与主函数功能完全一致."""
        char = create_character_from_archetype("06_ancient_male_noble", character_name="萧景琰")
        pos1, neg1 = compile_character_consistency_prompt(char, shot_scale="extreme_close_up")
        pos2, neg2 = compile_consistency_prompt(char, shot_scale="extreme_close_up")
        assert pos1 == pos2
        assert neg1 == neg2

    def test_compile_prompt_with_none_shot_scale(self):
        """测试 shot_scale 为 None 时默认输出 medium shot，无字面量 'None' 或多余逗号 ', , '."""
        char = create_character_from_archetype("04")
        pos, neg = compile_character_consistency_prompt(char, shot_scale=None)
        assert "medium shot" in pos
        assert "None" not in pos
        assert ", ," not in pos

    def test_compile_prompt_empty_locks_and_action_no_double_commas(self):
        """测试角色无特征锁且无动作时输出整洁，绝不产生双逗号 (', , ')."""
        char = CharacterAsset(name="Alice", visual_tags="", visual_anchor="", consistency_card=None)
        pos, neg = compile_character_consistency_prompt(char, shot_scale="medium_shot", emotion_action="")
        assert ", ," not in pos
        assert "photorealistic Chinese actor playing Alice" in pos

    def test_compile_prompt_newline_sanitization(self):
        """测试角色姓名与动作描述中的换行符被转义为空格."""
        char = CharacterAsset(name="李\n雷\r\n", visual_tags="student", consistency_card=None)
        pos, neg = compile_character_consistency_prompt(char, emotion_action="站立\n沉思\r\n")
        assert "\n" not in pos
        assert "\r" not in pos
        assert "playing 李 雷" in pos
        assert "站立 沉思" in pos


class TestPydanticCompatibilityAndSerialization:
    """测试母版与角色资产的序列化与向后兼容接口."""

    def test_drama_archetype_properties(self):
        """测试 DramaArchetype 属性快捷访问器."""
        arch = BUILTIN_ARCHETYPES["06_ancient_male_noble"]
        assert arch.voice_name == "zh-CN-YunjianNeural"
        assert arch.voice_rate == "-2%"
        assert arch.voice_pitch == "+1Hz"
        assert "清冽" in arch.voice_prompt
        assert arch.recommended_params == arch.generation_params
        assert arch.description == arch.summary

    def test_character_roundtrip_json_serialization(self):
        """测试带母版与一致性卡的角色能够正确无损进行 JSON 序列化与反序列化."""
        char = create_character_from_archetype("08", character_name="苏白莲")
        json_str = char.model_dump_json()
        
        parsed = json.loads(json_str)
        assert parsed["name"] == "苏白莲"
        assert parsed["archetype"] == "08_antagonist_female_greentea"
        assert "consistency_card" in parsed
        assert "facial_lock" in parsed["consistency_card"]
        assert "heart-shaped" in parsed["consistency_card"]["facial_lock"]

        # 反序列化恢复
        restored = CharacterAsset.model_validate_json(json_str)
        assert restored.name == char.name
        assert restored.archetype == char.archetype
        assert restored.consistency_card is not None
        assert restored.consistency_card.costume_lock == char.consistency_card.costume_lock
        assert restored.turnaround_prompt == char.turnaround_prompt

    def test_consistency_card_alias(self):
        """验证 ConsistencyCard 别名指向 CharacterConsistencyCard."""
        assert ConsistencyCard is CharacterConsistencyCard
        card = ConsistencyCard(facial_lock="test face")
        assert isinstance(card, CharacterConsistencyCard)
        assert card.facial_lock == "test face"
