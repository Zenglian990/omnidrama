"""OmniDrama 4-Tier Opaque-Box E2E Integration Test Suite (Milestone 5 - R5).

Comprehensive end-to-end integration verification across all system layers:
- Tier 1 (Feature Coverage): Verify every R1-R4 feature in isolation (Schema, Archetypes, Director, Web API).
- Tier 2 (Boundary & Corner Cases): Empty/None values, extreme inputs, narrator permutations (zero hallucinations), malformed data.
- Tier 3 (Cross-Feature Combinations): Script breakdown -> Character auto-registration -> Archetype application -> Prompt compilation -> Multimodal config -> Project JSON serialization round-trip.
- Tier 4 (Real-World Screenplay Scenario): Complete 5-scene production screenplay featuring all 4 archetypes (都市丽人 顾清雪, 霸总 陆沉舟, 绿茶千金 温梨, 清冷世子 萧绝), key heirloom prop (传家玉玺), environmental narrator shots, and full project assembly.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, List

import pytest
from fastapi.testclient import TestClient

from omnidrama.schemas.drama_schema import (
    DramaProject,
    CharacterAsset,
    PropAsset,
    Shot,
    ShotScaleEnum,
    CameraMotionEnum,
    CharacterConsistencyCard,
    ReferenceImageConfig,
    ReferenceRoleEnum,
)
from omnidrama.config.archetypes import (
    BUILTIN_ARCHETYPES,
    DramaArchetype,
    list_archetypes,
    get_archetype,
    apply_archetype_to_character,
    create_character_from_archetype,
    compile_character_consistency_prompt,
)
from omnidrama.core.director import (
    DirectorAgent,
    UNIVERSAL_CINEMATIC_PREFIX,
    UNIVERSAL_NEGATIVE_PROMPT,
    compile_shot_visual_prompt,
    compile_shot_negative_prompt,
    build_character_turnaround_prompt,
    build_prop_turnaround_prompt,
    build_multimodal_reference_config,
    _clean_dialogue_text,
    _estimate_shot_duration,
)
from omnidrama.web.app import app, CharacterModel


@pytest.fixture(autouse=True)
def preserve_workspace_state():
    """Ensure current_project.json is preserved and restored after tests to prevent state leakage."""
    project_path = Path(__file__).resolve().parent.parent / "output" / "current_project.json"
    backup = None
    if project_path.exists():
        backup = project_path.read_text(encoding="utf-8")
    yield
    if backup is not None:
        project_path.write_text(backup, encoding="utf-8")


@pytest.fixture
def web_client():
    """FastAPI TestClient fixture for Web REST API tests."""
    return TestClient(app)


# ============================================================================
# Tier 1: Feature Coverage (R1-R4 in Isolation)
# ============================================================================

class TestTier1FeatureCoverage:
    """Tier 1: Verify every R1-R4 feature in isolation."""

    def test_r1_character_asset_consistency_fields(self):
        """Verify CharacterAsset consistency fields: turnaround_prompt, archetype, and consistency_card."""
        # 1. Default values backward compatibility
        char_default = CharacterAsset(name="测试角色")
        assert char_default.turnaround_prompt == ""
        assert char_default.archetype == ""
        assert char_default.consistency_card is None
        assert isinstance(char_default.safe_consistency_card, CharacterConsistencyCard)
        assert char_default.safe_consistency_card.facial_lock == ""

        # 2. Populated CharacterConsistencyCard with ReferenceImageConfig
        ref_img = ReferenceImageConfig(
            url="https://assets.omnidrama.ai/chars/female_ref.jpg",
            role=ReferenceRoleEnum.FACE,
            weight=1.0,
            cref_weight=100,
            ip_adapter_weight=0.85,
            notes="正面高清五官参考"
        )
        card = CharacterConsistencyCard(
            facial_lock="delicate Asian oval face, elegant straight nose, subtle aegyo sal",
            hair_lock="clavicle-grazing micro-curled lob, dark mocha brown",
            costume_lock="tailored oatmeal-white oversized blazer, silk ivory camisole",
            exclusive_negative_prompt="childish round face, blunt bangs, heavy makeup",
            reference_images=[ref_img]
        )
        char = CharacterAsset(
            name="顾清雪",
            gender="female",
            visual_tags="photorealistic Chinese actress, 26 years old, professional businesswoman",
            turnaround_prompt="Character model turnaround sheet, 3 views, 16:9 pure white cyclorama studio",
            archetype="04_modern_female_urban",
            consistency_card=card
        )

        assert char.name == "顾清雪"
        assert char.archetype == "04_modern_female_urban"
        assert "oval face" in char.safe_consistency_card.facial_lock
        assert "dark mocha brown" in char.safe_consistency_card.hair_lock
        assert len(char.safe_consistency_card.reference_images) == 1
        assert char.safe_consistency_card.reference_images[0].cref_weight == 100

        # 3. Serialization and deserialization roundtrip
        char_json = char.model_dump_json()
        restored_char = CharacterAsset.model_validate_json(char_json)
        assert restored_char.name == char.name
        assert restored_char.archetype == char.archetype
        assert restored_char.turnaround_prompt == char.turnaround_prompt
        assert restored_char.safe_consistency_card.facial_lock == card.facial_lock
        assert restored_char.safe_consistency_card.costume_lock == card.costume_lock
        assert restored_char.safe_consistency_card.reference_images[0].url == ref_img.url

    def test_r1_prop_asset_data_model(self):
        """Verify PropAsset data model, feature locks, turnaround prompt, and reference coercion."""
        prop = PropAsset(
            name="传家玉玺",
            category="heirloom",
            description="古老修仙门派代代相传的掌门信物，蕴含无上灵力",
            visual_tags="羊脂白玉，双龙戏珠钮，通体温润微透，古朴包浆",
            feature_lock="印底刻有'代天巡狩'金文古篆，玉身内部流淌隐约金色流光",
            turnaround_prompt="prop design turnaround sheet, 3 views, isolated on solid pure white background",
            negative_prompt="塑料质感, 粗糙树脂, 机械切割痕, 荧光绿",
            reference_images=["https://assets.omnidrama.ai/props/jade_seal_front.jpg"]
        )

        assert prop.name == "传家玉玺"
        assert prop.category == "heirloom"
        assert "羊脂白玉" in prop.visual_tags
        assert "金文古篆" in prop.feature_lock
        assert "塑料质感" in prop.negative_prompt
        assert len(prop.reference_images) == 1

        # Fallback default name when empty or whitespace provided
        prop_fallback = PropAsset(name="   ")
        assert prop_fallback.name == "未命名道具"

        # Roundtrip serialization
        p_json = prop.model_dump_json()
        restored_prop = PropAsset.model_validate_json(p_json)
        assert restored_prop.name == prop.name
        assert restored_prop.feature_lock == prop.feature_lock
        assert restored_prop.turnaround_prompt == prop.turnaround_prompt

    def test_r3_archetypes_catalog_and_voice_bindings(self):
        """Verify Archetypes catalog contains all 4 canonical archetypes with Edge-TTS bindings and specs."""
        expected_archetypes = {
            "04_modern_female_urban": {
                "name": "现代女主-都市丽人",
                "gender": "female",
                "voice_name": "zh-CN-XiaoxiaoNeural",
                "voice_rate": "+2%",
                "voice_pitch": "+0Hz",
            },
            "05_modern_male_boss": {
                "name": "现代男主-霸总",
                "gender": "male",
                "voice_name": "zh-CN-YunxiNeural",
                "voice_rate": "-4%",
                "voice_pitch": "-3Hz",
            },
            "06_ancient_male_noble": {
                "name": "古装男主-清冷世子",
                "gender": "male",
                "voice_name": "zh-CN-YunjianNeural",
                "voice_rate": "-2%",
                "voice_pitch": "+1Hz",
            },
            "08_antagonist_female_greentea": {
                "name": "反派女二-绿茶千金",
                "gender": "female",
                "voice_name": "zh-CN-XiaoyiNeural",
                "voice_rate": "+4%",
                "voice_pitch": "+3Hz",
            },
        }

        # Check catalog completeness
        all_archs = list_archetypes()
        assert len(all_archs) >= 4
        catalog_ids = {a["id"] for a in all_archs}

        for arch_id, expected in expected_archetypes.items():
            assert arch_id in catalog_ids
            arch = get_archetype(arch_id)
            assert arch is not None
            assert arch.name == expected["name"]
            assert arch.gender == expected["gender"]
            assert arch.voice_name == expected["voice_name"]
            assert arch.voice_rate == expected["voice_rate"]
            assert arch.voice_pitch == expected["voice_pitch"]

            # Consistency card locks present
            card = arch.consistency_card
            assert len(card.facial_lock.strip()) > 0
            assert len(card.hair_lock.strip()) > 0
            assert len(card.costume_lock.strip()) > 0
            assert len(card.exclusive_negative_prompt.strip()) > 0

            # Turnaround prompt complies with 16:9 pure white cyclorama standard
            assert "turnaround" in arch.turnaround_prompt.lower()
            assert "white" in arch.turnaround_prompt.lower()
            assert arch.generation_params.get("turnaround_aspect_ratio") == "16:9"

    def test_r2_director_prompt_compilation_locks_and_camera(self):
        """Verify Director prompt compilation: ARRI prefix, 3-tier locks, lens/scale, emotion/action, 9:16 vertical."""
        char = CharacterAsset(
            name="陆沉舟",
            gender="male",
            visual_tags="photorealistic Chinese actor, 28 years old",
            consistency_card=CharacterConsistencyCard(
                facial_lock="sculpted masculine Chinese jawline, sharp piercing eyes, cold gaze",
                hair_lock="neatly slicked-back side-part pompadour hairstyle, dark black",
                costume_lock="tailored Italian charcoal bespoke three-piece suit, silk pocket square",
                exclusive_negative_prompt="round face, casual wear, messy unkempt hair"
            )
        )

        visual_prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.CLOSE_UP,
            speaker="陆沉舟",
            action_beat="眉头微蹙，深邃眼神中透出一丝讥诮与冷厉",
            blocking="立于落地窗前左侧三分线，俯视城市夜景",
            genre="都市商战",
            character=char
        )

        # 1. ARRI cinematic prefix
        assert "8k cinematic live-action movie still, shot on ARRI Alexa 65" in visual_prompt

        # 2. Character identity & 3-tier physical locks
        assert "photorealistic Chinese male actor playing 陆沉舟" in visual_prompt
        assert "facial features: sculpted masculine Chinese jawline" in visual_prompt
        assert "hairstyle: neatly slicked-back side-part pompadour hairstyle" in visual_prompt
        assert "costume: tailored Italian charcoal bespoke three-piece suit" in visual_prompt

        # 3. Lens and shot scale mapping (CLOSE_UP -> 50mm prime lens)
        assert "close-up portrait shot, 50mm prime lens" in visual_prompt

        # 4. Action beat and spatial blocking
        assert "深邃眼神中透出一丝讥诮与冷厉" in visual_prompt
        assert "立于落地窗前左侧三分线" in visual_prompt

        # 5. Cinema lighting & 9:16 vertical aspect ratio
        assert "vertical 9:16" in visual_prompt
        assert "no cartoon, no anime" in visual_prompt

    def test_r2_anti_collapse_negative_prompt_merging(self):
        """Verify anti-collapse negative prompt merges universal base, character exclusive, and prop negatives."""
        char = CharacterAsset(
            name="温梨",
            consistency_card=CharacterConsistencyCard(
                exclusive_negative_prompt="overt villain smirk, harsh angular jaw, heavy dark gothic makeup"
            )
        )
        prop = PropAsset(
            name="定制蓝宝石项链",
            negative_prompt="粗糙廉价塑料, 褪色合金, 掉钻"
        )

        neg_prompt = compile_shot_negative_prompt(
            character=char,
            extra_negative="grainy blur, overexposure",
            props=[prop],
            prop_refs=["定制蓝宝石项链"]
        )

        # Universal negative base
        assert "bad anatomy, deformed face, inconsistent eyes" in neg_prompt
        assert "cartoon, anime, 3d, cgi" in neg_prompt

        # Character exclusive negative
        assert "overt villain smirk, harsh angular jaw" in neg_prompt

        # Prop negative
        assert "粗糙廉价塑料, 褪色合金" in neg_prompt

        # Extra negative
        assert "grainy blur, overexposure" in neg_prompt

    def test_r2_multimodal_reference_config(self):
        """Verify multimodal reference config for Midjourney --cref, IP-Adapter, and Volcano Seedance."""
        ref1 = ReferenceImageConfig(
            url="https://cdn.omnidrama.ai/face_ref_1.jpg",
            role=ReferenceRoleEnum.FACE,
            cref_weight=100,
            ip_adapter_weight=0.9
        )
        ref2 = ReferenceImageConfig(
            url="https://cdn.omnidrama.ai/costume_ref_2.jpg",
            role=ReferenceRoleEnum.COSTUME,
            cref_weight=80,
            ip_adapter_weight=0.7
        )
        char = CharacterAsset(
            name="顾清雪",
            turnaround_image="https://cdn.omnidrama.ai/turnaround_guqingxue.jpg",
            consistency_card=CharacterConsistencyCard(
                reference_images=[ref1, ref2]
            )
        )

        config = build_multimodal_reference_config(character=char)

        # 1. Midjourney --cref config
        mj = config["midjourney"]
        assert mj["cref_url"] == "https://cdn.omnidrama.ai/turnaround_guqingxue.jpg"
        assert mj["cref_weight"] == 100
        assert mj["aspect_ratio"] == "9:16"
        assert "--cref https://cdn.omnidrama.ai/turnaround_guqingxue.jpg --cw 100 --ar 9:16 --v 6.1" in mj["prompt_suffix"]

        # 2. ComfyUI IP-Adapter config
        ip = config["ip_adapter"]
        assert ip["enabled"] is True
        assert ip["image_path"] == "https://cdn.omnidrama.ai/turnaround_guqingxue.jpg"
        assert ip["model"] == "ip-adapter-plus_sdxl_vit-h.safetensors"
        assert len(ip["image_inputs"]) >= 3  # turnaround + ref1 + ref2

        # 3. Volcano Seedance 2.0 config
        sd = config["seedance"]
        assert "@角色参考图1" in sd["ref_prompt_tags"]
        assert "@角色参考图2" in sd["ref_prompt_tags"]
        assert len(sd["image_urls"]) >= 3

    def test_r2_turnaround_prompt_generation_character_and_prop(self):
        """Verify turnaround prompt generators produce 16:9 pure white cyclorama studio prompts."""
        # Character turnaround
        char = CharacterAsset(
            name="萧绝",
            gender="male",
            consistency_card=CharacterConsistencyCard(
                facial_lock="pale aristocratic complexion, razor-sharp jawline, melancholic cold phoenix eyes",
                hair_lock="flowing ink-black long hair half-tied with silver crown",
                costume_lock="moonlight-white ancient Hanfu robe with silver embroidered cloud patterns"
            )
        )
        char_turnaround = build_character_turnaround_prompt(char)
        assert "character design sheet, full body character turnaround, 3 views from multiple angles" in char_turnaround
        assert "front view, side 90° profile view, back 180° view" in char_turnaround
        assert "clean solid pure white cyclorama studio background" in char_turnaround
        assert "bust portrait close-up inset" in char_turnaround
        assert "photorealistic Chinese male actor" in char_turnaround
        assert "--ar 16:9" in char_turnaround

        # Prop turnaround
        prop = PropAsset(
            name="清寒古剑",
            category="weapon",
            visual_tags="玄铁重剑，寒光凛冽，剑鞘镶嵌幽蓝宝石",
            feature_lock="剑格雕刻盘龙纹，剑刃隐现七星连珠暗纹"
        )
        prop_turnaround = build_prop_turnaround_prompt(prop)
        assert "prop design turnaround sheet, 3 views: orthographic front view, side profile view, 45-degree isometric perspective view" in prop_turnaround
        assert "isolated on solid pure white background" in prop_turnaround
        assert "sharp focus" in prop_turnaround
        assert "--ar 16:9" in prop_turnaround
        assert "玄铁重剑" in prop_turnaround

    def test_r4_web_rest_api_archetypes_and_turnaround(self, web_client: TestClient):
        """Verify Web REST APIs: /api/archetypes, /api/archetypes/apply, and /api/characters/{name}/turnaround."""
        # 1. GET /api/archetypes
        resp_list = web_client.get("/api/archetypes")
        assert resp_list.status_code == 200
        archetypes = resp_list.json()
        assert len(archetypes) == 4
        arch_ids = {a["id"] for a in archetypes}
        assert "04_modern_female_urban" in arch_ids
        assert "05_modern_male_boss" in arch_ids
        assert "06_ancient_male_noble" in arch_ids
        assert "08_antagonist_female_greentea" in arch_ids

        # 2. POST /api/archetypes/apply
        apply_payload = {
            "character_name": "E2E_顾清雪",
            "archetype_id": "04_modern_female_urban",
            "custom_role": "商界女霸总"
        }
        resp_apply = web_client.post("/api/archetypes/apply", json=apply_payload)
        assert resp_apply.status_code == 200
        apply_res = resp_apply.json()
        assert apply_res["status"] == "success"
        char = apply_res["character"]
        assert char["name"] == "E2E_顾清雪"
        assert char["role"] == "商界女霸总"
        assert char["archetype"] == "04_modern_female_urban"
        assert "facial_lock" in char["consistency_card"]
        assert "costume_lock" in char["consistency_card"]

        # 3. POST /api/characters/{name}/turnaround
        resp_gen = web_client.post("/api/characters/E2E_顾清雪/turnaround", json={"prompt": "", "regenerate": True})
        assert resp_gen.status_code == 200
        gen_data = resp_gen.json()
        assert gen_data["status"] == "success"
        assert gen_data["turnaround_image"].endswith(".jpg")
        assert len(gen_data["turnaround_prompt"]) > 20

        # 4. GET /api/characters/{name}/turnaround
        resp_get = web_client.get("/api/characters/E2E_顾清雪/turnaround")
        assert resp_get.status_code == 200
        get_data = resp_get.json()
        assert get_data["status"] == "success"
        assert get_data["name"] == "E2E_顾清雪"
        assert get_data["archetype"] == "04_modern_female_urban"
        assert get_data["turnaround_image"] == gen_data["turnaround_image"]


# ============================================================================
# Tier 2: Boundary & Corner Cases
# ============================================================================

class TestTier2BoundaryAndCornerCases:
    """Tier 2: Boundary conditions, corner cases, narrator permutations, and robustness."""

    def test_empty_whitespace_and_none_values(self):
        """Verify system behavior on empty strings, whitespaces, and None values."""
        # 1. Empty/whitespace prop name falls back safely
        prop_blank = PropAsset(name="")
        assert prop_blank.name == "未命名道具"

        prop_ws = PropAsset(name="   \t\n  ")
        assert prop_ws.name == "未命名道具"

        # 2. Missing consistency card uses safe_consistency_card without crash
        char_empty = CharacterAsset(name="路人甲", consistency_card=None)
        assert char_empty.safe_consistency_card is not None
        assert char_empty.safe_consistency_card.facial_lock == ""
        assert char_empty.safe_consistency_card.hair_lock == ""

        # 3. Prompt compiler with empty / None / missing inputs
        empty_prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            speaker="",
            action_beat="",
            blocking="",
            genre="",
            character=None,
            props=None,
            prop_refs=[]
        )
        # Empty speaker is treated as narrator/atmospheric scene
        assert "atmospheric" in empty_prompt
        assert "no actors" in empty_prompt
        assert "vertical 9:16" in empty_prompt

        # 4. Negative prompt compiler with None / empty inputs
        empty_neg = compile_shot_negative_prompt(
            character=None,
            extra_negative="",
            props=None,
            prop_refs=[]
        )
        assert "bad anatomy, deformed face" in empty_neg

        # 5. Multimodal reference config with empty character
        empty_ref_cfg = build_multimodal_reference_config(character=None)
        assert empty_ref_cfg["midjourney"] == {}
        assert empty_ref_cfg["ip_adapter"] == {}
        assert empty_ref_cfg["seedance"] == {}

    def test_extreme_inputs_foreign_languages_emojis_long_text(self):
        """Verify extreme inputs: foreign scripts, unicode emojis, and ultra-long text."""
        # Foreign scripts and emojis
        emoji_dialogue = "💥👑『絶対に許さない！』🔥🔥 너는 죽었다... 💀"
        clean_dlg = _clean_dialogue_text(emoji_dialogue)
        assert "絶対に許さない！" in clean_dlg
        assert "너는 죽었다" in clean_dlg

        # Ultra-long script lines (1500 chars)
        long_line = "顾清雪冷冷说道：“" + ("战" * 1500) + "！”"
        clean_long = _clean_dialogue_text(long_line)
        dur = _estimate_shot_duration(clean_long)
        # Duration must strictly stay bounded between 2.0s and 5.0s
        assert 2.0 <= dur <= 5.0

        # Character with ultra-long descriptions
        long_char = CharacterAsset(
            name="楚九歌",
            visual_tags="photorealistic Chinese actor " * 50,
            consistency_card=CharacterConsistencyCard(
                facial_lock="sharp jaw " * 50,
                hair_lock="black hair " * 50,
                costume_lock="silk robe " * 50
            )
        )
        prompt_long = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.FULL_SHOT,
            speaker="楚九歌",
            action_beat="动作 " * 50,
            character=long_char
        )
        assert "ARRI Alexa 65" in prompt_long
        assert "photorealistic Chinese male actor playing 楚九歌" in prompt_long
        assert "vertical 9:16" in prompt_long

    def test_narrator_permutations_zero_phantom_hallucinations(self):
        """Verify all narrator permutations produce zero phantom actor hallucinations."""
        narrator_variants = [
            "旁白",
            "【旁白】",
            "(旁白)",
            "（旁白）",
            "  旁白  ",
            "空镜",
            "空镜头",
            "【空镜头】",
            "Scene",
            "scene",
            "SCENE",
            "环境",
            "【环境】",
            "背景",
            "背景音",
            "narrator",
            "NARRATOR",
        ]

        agent = DirectorAgent()

        for variant in narrator_variants:
            # 1. Cleaner maps variant to '旁白'
            cleaned = agent._clean_speaker(variant)
            assert cleaned == "旁白", f"Speaker '{variant}' was cleaned to '{cleaned}', expected '旁白'"

            # 2. Visual prompt must strictly enforce NO ACTORS and NEVER produce 'actor playing 旁白'
            shot_prompt = compile_shot_visual_prompt(
                shot_scale=ShotScaleEnum.WIDE_SHOT,
                speaker=variant,
                action_beat="暴雨倾盆，雷电撕裂乌云笼罩的静谧山巅",
                genre="悬疑奇幻"
            )

            assert "no actors" in shot_prompt, f"Variant '{variant}' missing 'no actors' in prompt: {shot_prompt}"
            assert "photorealistic environment" in shot_prompt
            assert "actor playing" not in shot_prompt, f"Variant '{variant}' generated phantom actor: {shot_prompt}"
            assert "playing 旁白" not in shot_prompt
            assert "playing Scene" not in shot_prompt

    def test_malformed_missing_consistency_cards_and_coercion(self):
        """Verify coercion of malformed consistency card dicts and reference image inputs."""
        # 1. Reference images coerced from raw string URL list
        raw_card_dict = {
            "facial_bone_structure": "骨相立体立体冷峻",  # legacy key
            "hairstyle_and_color": "黑色碎发",        # legacy key
            "costume_and_wardrobe": "深色西服",       # legacy key
            "negative_prompt": "崩脸",               # legacy key
            "reference_images": [
                "https://cdn.omnidrama.ai/raw_url_1.jpg",
                {"url": "https://cdn.omnidrama.ai/dict_url_2.jpg", "role": "costume"},
                None,  # should be filtered out
            ]
        }
        card = CharacterConsistencyCard.model_validate(raw_card_dict)
        assert card.facial_lock == "骨相立体立体冷峻"
        assert card.hair_lock == "黑色碎发"
        assert card.costume_lock == "深色西服"
        assert card.exclusive_negative_prompt == "崩脸"
        assert len(card.reference_images) == 2
        assert card.reference_images[0].url == "https://cdn.omnidrama.ai/raw_url_1.jpg"
        assert card.reference_images[1].role == ReferenceRoleEnum.COSTUME


# ============================================================================
# Tier 3: Cross-Feature Combinations
# ============================================================================

class TestTier3CrossFeatureCombinations:
    """Tier 3: Multi-feature integration, script breakdown to prompt compilation, and serialization roundtrip."""

    def test_script_breakdown_to_archetype_application_and_multimodal_pipeline(self):
        """Verify end-to-end flow: script breakdown -> auto-registration -> archetype apply -> prompt compilation -> multimodal ref."""
        script_text = """
深夜，顾氏集团顶层总裁办公室，狂风骤雨击打着巨大的落地玻璃幕墙。
顾清雪：“想要抢走顾氏的公章？陆沉舟，你未免太狂妄了！”
陆沉舟冷笑道：“顾清雪，商业战场从来只认输赢，不问手段。”
（温梨从阴影中缓缓走出，眼眶泛红，楚楚可怜）
温梨小声啜泣道：“清雪姐姐，沉舟哥哥也是为了公司好，你何必苦苦相逼呢？”
陆沉舟冷哼一声：“不必跟她废话，明天的董事会自见分晓。”
雷霆轰鸣，一道惨白闪电骤然撕裂整座城市的夜空。
"""

        agent = DirectorAgent()
        project = agent.breakdown_script(
            raw_text=script_text,
            title="商战之女王归来",
            genre="都市商战言情"
        )

        assert isinstance(project, DramaProject)
        assert project.title == "商战之女王归来"
        assert len(project.shots) >= 5

        # 1. Verify character auto-registration
        registered_names = {c.name for c in project.characters}
        assert "顾清雪" in registered_names
        assert "陆沉舟" in registered_names
        assert "温梨" in registered_names
        assert "旁白" in registered_names

        # 2. Apply canonical archetypes to auto-registered characters
        char_map = {c.name: c for c in project.characters}

        # Apply 04_modern_female_urban to 顾清雪
        char_gu = apply_archetype_to_character(char_map["顾清雪"], "04_modern_female_urban")
        assert char_gu.archetype == "04_modern_female_urban"
        assert "oval face" in char_gu.safe_consistency_card.facial_lock

        # Apply 05_modern_male_boss to 陆沉舟
        char_lu = apply_archetype_to_character(char_map["陆沉舟"], "05_modern_male_boss")
        assert char_lu.archetype == "05_modern_male_boss"
        assert "sculpted masculine Chinese jawline" in char_lu.safe_consistency_card.facial_lock

        # Apply 08_antagonist_female_greentea to 温梨
        char_wen = apply_archetype_to_character(char_map["温梨"], "08_antagonist_female_greentea")
        assert char_wen.archetype == "08_antagonist_female_greentea"
        assert "heart-shaped Asian face" in char_wen.safe_consistency_card.facial_lock

        # Update project characters
        char_map["顾清雪"] = char_gu
        char_map["陆沉舟"] = char_lu
        char_map["温梨"] = char_wen
        project.characters = list(char_map.values())

        # 3. Add key prop and associate with shots
        prop_seal = PropAsset(
            name="顾氏集团公章",
            category="prop",
            visual_tags="红木纯铜公章，雕刻精细顾氏印徽",
            feature_lock="章身黄铜包边，底座带微凹防伪纹"
        )
        prop_seal.turnaround_prompt = build_prop_turnaround_prompt(prop_seal)
        project.props = [prop_seal]

        # 4. Re-compile shot visual prompts and multimodal reference configs
        for shot in project.shots:
            speaker = shot.speaker
            char = char_map.get(speaker)
            prop_refs = ["顾氏集团公章"] if speaker == "顾清雪" else []
            shot.prop_refs = prop_refs

            # Visual prompt compilation
            shot.visual_prompt = compile_shot_visual_prompt(
                shot_scale=shot.shot_scale,
                speaker=speaker,
                action_beat=shot.action_beat,
                blocking=shot.blocking,
                genre=project.genre,
                character=char,
                props=project.props,
                prop_refs=prop_refs
            )

            # Negative prompt compilation
            shot.negative_prompt = compile_shot_negative_prompt(
                character=char,
                props=project.props,
                prop_refs=prop_refs
            )

            # Multimodal reference config
            ref_cfg = build_multimodal_reference_config(character=char)
            if ref_cfg.get("midjourney") and ref_cfg["midjourney"].get("prompt_suffix"):
                shot.midjourney_prompt = f"{shot.visual_prompt} {ref_cfg['midjourney']['prompt_suffix']}"
            shot.ip_adapter_params = ref_cfg.get("ip_adapter") or {}

            # Verifications per shot
            if speaker == "顾清雪":
                assert "photorealistic Chinese female actor playing 顾清雪" in shot.visual_prompt
                assert "facial features: delicate Asian oval face" in shot.visual_prompt
                assert "holding and showcasing 顾氏集团公章" in shot.visual_prompt
            elif speaker == "陆沉舟":
                assert "photorealistic Chinese male actor playing 陆沉舟" in shot.visual_prompt
                assert "facial features: sculpted masculine Chinese jawline" in shot.visual_prompt
            elif speaker == "温梨":
                assert "photorealistic Chinese female actor playing 温梨" in shot.visual_prompt
                assert "heart-shaped Asian face" in shot.visual_prompt
            elif speaker == "旁白":
                assert "no actors" in shot.visual_prompt
                assert "actor playing" not in shot.visual_prompt

    def test_full_project_json_serialization_and_roundtrip_fidelity(self):
        """Verify 100% preservation of consistency locks, props, and turnaround metadata upon JSON round-trip."""
        # 1. Assemble complete DramaProject
        char1 = create_character_from_archetype(
            archetype_id="04_modern_female_urban",
            character_name="林沐雪",
            custom_role="女总裁",
            turnaround_image="https://cdn.omnidrama.ai/turnaround_linmuxue.jpg"
        )
        char2 = create_character_from_archetype(
            archetype_id="06_ancient_male_noble",
            character_name="容景",
            custom_role="清冷世子",
            turnaround_image="https://cdn.omnidrama.ai/turnaround_rongjing.jpg"
        )
        prop1 = PropAsset(
            name="凤羽灵簪",
            category="jewelry",
            description="上古灵鸟尾羽锻造的发簪",
            visual_tags="赤金镶嵌红宝石，尾翼雕空微颤",
            feature_lock="簪头凤目镶嵌深红石榴石，微发赤芒",
            turnaround_prompt="prop turnaround sheet, 16:9, white background",
            negative_prompt="粗劣发簪, 塑料假珠"
        )

        shot1 = Shot(
            shot_id=1,
            shot_scale=ShotScaleEnum.CLOSE_UP,
            camera_motion=CameraMotionEnum.ZOOM_IN,
            speaker="林沐雪",
            dialogue="凭你也想掌控这柄灵簪？",
            action_beat="指尖抚过凤羽灵簪，眼神凌厉如刀",
            sfx="凤鸣清啸",
            blocking="居于画面中央，手持灵簪向前直指",
            visual_prompt="8k cinematic live-action movie still, shot on ARRI Alexa 65...",
            negative_prompt="bad anatomy, extra fingers, 粗劣发簪",
            midjourney_prompt="8k cinematic still --cref https://cdn.omnidrama.ai/turnaround_linmuxue.jpg --cw 100",
            ip_adapter_params={"enabled": True, "weight": 0.8},
            prop_refs=["凤羽灵簪"],
            duration_seconds=3.2
        )

        original_project = DramaProject(
            title="双世之凤羽传说",
            genre="古今双穿言情",
            synopsis="现代商业女强人携上古信物穿越时空，与清冷世子携手破局。",
            characters=[char1, char2],
            props=[prop1],
            shots=[shot1]
        )

        # 2. Serialize to JSON string
        project_json_str = original_project.model_dump_json(indent=2)
        assert len(project_json_str) > 100

        # 3. Deserialize back into DramaProject
        restored_project = DramaProject.model_validate_json(project_json_str)

        # 4. Assert 100% preservation across all domains
        assert restored_project.title == original_project.title
        assert restored_project.genre == original_project.genre
        assert len(restored_project.characters) == 2
        assert len(restored_project.props) == 1
        assert len(restored_project.shots) == 1

        # Character 1 preservation
        c1 = next(c for c in restored_project.characters if c.name == "林沐雪")
        assert c1.archetype == "04_modern_female_urban"
        assert c1.turnaround_image == "https://cdn.omnidrama.ai/turnaround_linmuxue.jpg"
        assert c1.safe_consistency_card.facial_lock == char1.safe_consistency_card.facial_lock
        assert c1.safe_consistency_card.hair_lock == char1.safe_consistency_card.hair_lock
        assert c1.safe_consistency_card.costume_lock == char1.safe_consistency_card.costume_lock
        assert c1.safe_consistency_card.exclusive_negative_prompt == char1.safe_consistency_card.exclusive_negative_prompt

        # Character 2 preservation
        c2 = next(c for c in restored_project.characters if c.name == "容景")
        assert c2.archetype == "06_ancient_male_noble"
        assert c2.safe_consistency_card.facial_lock == char2.safe_consistency_card.facial_lock
        assert c2.voice_name == "zh-CN-YunjianNeural"

        # Prop preservation
        p = restored_project.props[0]
        assert p.name == "凤羽灵簪"
        assert p.category == "jewelry"
        assert p.feature_lock == prop1.feature_lock
        assert p.turnaround_prompt == prop1.turnaround_prompt
        assert p.negative_prompt == prop1.negative_prompt

        # Shot preservation
        s = restored_project.shots[0]
        assert s.shot_id == 1
        assert s.speaker == "林沐雪"
        assert s.prop_refs == ["凤羽灵簪"]
        assert s.midjourney_prompt == shot1.midjourney_prompt
        assert s.ip_adapter_params == shot1.ip_adapter_params
        assert s.duration_seconds == 3.2


# ============================================================================
# Tier 4: Real-World Screenplay Scenario
# ============================================================================

class TestTier4RealWorldScreenplayScenario:
    """Tier 4: End-to-end breakdown of a realistic 5-scene short drama script featuring all 4 archetypes and props."""

    def test_five_scene_production_screenplay_e2e_breakdown(self):
        """End-to-end verification of realistic 5-scene screenplay with 4 archetypes, key prop, and zero hallucinations."""
        realistic_screenplay = """
【第1场：现代都市·顾氏董事会】
暴雨如注，乌云低垂，闪电如利刃撕裂繁华都市的暮色天际。
顾清雪身着燕麦白定制西装，猛地将财务清算文件拍在长桌之上。
顾清雪：“这份账目亏空两个亿，温副总，你作何解释？！”

【第2场：现代都市·霸总降临】
厚重胡桃木大门被猛然推开，皮鞋踏在实木地板上发出沉闷声响。
陆沉舟一身炭黑三件套西装迈步而入，周身散发令人窒息的凌厉气场。
陆沉舟冷笑道：“顾总好大的威风，但我陆氏投资的项目，还轮不到你来查账。”

【第3场：现代都市·绿茶陷害】
温梨躲在陆沉舟身后，眼角泛起晶莹泪光，半扎人鱼卷发微颤。
温梨轻咬下唇，楚楚可怜道：“沉舟哥哥，都是梨梨办事不力，你千万别为了我和清雪姐姐伤了和气……”

【第4场：古今戏中戏·清冷世子】
时光流转如幻梦，水榭回廊间，青石板落满幽凉月华。
萧绝一袭月白云纹长袍立于风中，神色疏离清寒，仿佛九天谪仙不染尘埃。
萧绝神情冷峻，缓缓启唇：“世间荣华不过过眼云烟，唯有此信物，永世不易。”

【第5场：高潮信物·权谋对决】
萧绝从怀中取出流光溢彩的传家玉玺，羊脂白玉在月光下泛起纯净圣洁光辉。
旁白：“千年的宿命轮回在此刻交错，商界权谋与前世誓约，终将在这一枚传家玉玺中决出终局。”
"""

        agent = DirectorAgent()
        project = agent.breakdown_script(
            raw_text=realistic_screenplay,
            title="凤鸣九天之双世权谋",
            genre="都市商战穿越双强言情"
        )

        assert isinstance(project, DramaProject)
        assert project.title == "凤鸣九天之双世权谋"
        assert len(project.shots) >= 5

        # 1. Verify all 4 characters auto-recognized or registered
        char_names = {c.name for c in project.characters}
        assert "顾清雪" in char_names
        assert "陆沉舟" in char_names
        assert "温梨" in char_names
        assert "萧绝" in char_names
        assert "旁白" in char_names

        # 2. Enrich and apply all 4 canonical archetypes (04, 05, 06, 08)
        char_map = {c.name: c for c in project.characters}

        # 04 现代女主-都市丽人 -> 顾清雪
        char_gu = apply_archetype_to_character(char_map["顾清雪"], "04_modern_female_urban")
        char_gu.turnaround_prompt = build_character_turnaround_prompt(char_gu)
        char_gu.turnaround_image = "https://cdn.omnidrama.ai/turnarounds/guqingxue.jpg"
        char_map["顾清雪"] = char_gu

        # 05 现代男主-霸总 -> 陆沉舟
        char_lu = apply_archetype_to_character(char_map["陆沉舟"], "05_modern_male_boss")
        char_lu.turnaround_prompt = build_character_turnaround_prompt(char_lu)
        char_lu.turnaround_image = "https://cdn.omnidrama.ai/turnarounds/luchenzhou.jpg"
        char_map["陆沉舟"] = char_lu

        # 08 反派女二-绿茶千金 -> 温梨
        char_wen = apply_archetype_to_character(char_map["温梨"], "08_antagonist_female_greentea")
        char_wen.turnaround_prompt = build_character_turnaround_prompt(char_wen)
        char_wen.turnaround_image = "https://cdn.omnidrama.ai/turnarounds/wenli.jpg"
        char_map["温梨"] = char_wen

        # 06 古装男主-清冷世子 -> 萧绝
        char_xiao = apply_archetype_to_character(char_map["萧绝"], "06_ancient_male_noble")
        char_xiao.turnaround_prompt = build_character_turnaround_prompt(char_xiao)
        char_xiao.turnaround_image = "https://cdn.omnidrama.ai/turnarounds/xiaojue.jpg"
        char_map["萧绝"] = char_xiao

        project.characters = list(char_map.values())

        # 3. Create and bind Key Prop: 传家玉玺
        key_prop = PropAsset(
            name="传家玉玺",
            category="heirloom",
            description="连接前世古风宗门与今生顾氏家族的核心信物",
            visual_tags="温润羊脂白玉，双龙戏珠雕钮，四方印体透光无瑕",
            feature_lock="印底阳刻'受命于天'小篆，印角微嵌极细暗金纹",
            turnaround_prompt="",
            negative_prompt="粗劣塑料, 玻璃树脂, 机械切割假玉"
        )
        key_prop.turnaround_prompt = build_prop_turnaround_prompt(key_prop)
        project.props = [key_prop]

        # 4. Verify Turnaround Prompts for all entities
        for c in project.characters:
            if c.name != "旁白":
                assert c.turnaround_prompt is not None and len(c.turnaround_prompt) > 0
                assert "--ar 16:9" in c.turnaround_prompt
                assert "3 views" in c.turnaround_prompt
                assert "pure white" in c.turnaround_prompt

        assert "--ar 16:9" in key_prop.turnaround_prompt
        assert "isometric perspective" in key_prop.turnaround_prompt

        # 5. Compile and validate all shots in assembly
        narrator_shot_count = 0
        character_shot_count = 0

        for shot in project.shots:
            speaker = shot.speaker
            char = char_map.get(speaker)

            # Bind prop to 萧绝 / 顾清雪 climax shots
            prop_refs = ["传家玉玺"] if speaker == "萧绝" or "玉玺" in shot.action_beat else []
            shot.prop_refs = prop_refs

            # Compile visual prompt
            shot.visual_prompt = compile_shot_visual_prompt(
                shot_scale=shot.shot_scale,
                speaker=speaker,
                action_beat=shot.action_beat,
                blocking=shot.blocking,
                genre=project.genre,
                character=char,
                props=project.props,
                prop_refs=prop_refs
            )

            # Compile negative prompt
            shot.negative_prompt = compile_shot_negative_prompt(
                character=char,
                props=project.props,
                prop_refs=prop_refs
            )

            # Multimodal reference configuration
            ref_cfg = build_multimodal_reference_config(character=char)
            if ref_cfg.get("midjourney") and ref_cfg["midjourney"].get("prompt_suffix"):
                shot.midjourney_prompt = f"{shot.visual_prompt} {ref_cfg['midjourney']['prompt_suffix']}"
            shot.ip_adapter_params = ref_cfg.get("ip_adapter") or {}

            # Strict validations
            if speaker == "旁白":
                narrator_shot_count += 1
                assert "no actors" in shot.visual_prompt
                assert "actor playing" not in shot.visual_prompt
                assert "playing 旁白" not in shot.visual_prompt
            else:
                character_shot_count += 1
                assert "8k cinematic live-action movie still, shot on ARRI Alexa 65" in shot.visual_prompt
                assert f"playing {speaker}" in shot.visual_prompt
                assert "vertical 9:16" in shot.visual_prompt

                # Check archetype consistency card locks applied
                if speaker == "顾清雪":
                    assert "facial features: delicate Asian oval face" in shot.visual_prompt
                elif speaker == "陆沉舟":
                    assert "facial features: sculpted masculine Chinese jawline" in shot.visual_prompt
                elif speaker == "温梨":
                    assert "heart-shaped Asian face" in shot.visual_prompt
                elif speaker == "萧绝":
                    assert "aristocratic" in shot.visual_prompt and "classical Chinese" in shot.visual_prompt
                    assert "holding and showcasing 传家玉玺" in shot.visual_prompt

            # Verify negative prompt anti-collapse
            assert "bad anatomy, deformed face" in shot.negative_prompt
            if char and char.consistency_card and char.consistency_card.exclusive_negative_prompt:
                assert char.consistency_card.exclusive_negative_prompt in shot.negative_prompt
            if prop_refs:
                assert "粗劣塑料, 玻璃树脂" in shot.negative_prompt

            # Duration constraint
            assert 2.0 <= shot.duration_seconds <= 5.0

        assert narrator_shot_count >= 1, "Scenario should contain at least one environmental narrator shot"
        assert character_shot_count >= 4, "Scenario should contain shots for character interactions"

        # 6. Validate Clean Project Export & Serialization
        project_dict = project.model_dump()
        assert project_dict["title"] == "凤鸣九天之双世权谋"
        assert len(project_dict["characters"]) == 5
        assert len(project_dict["props"]) == 1
        assert len(project_dict["shots"]) >= 5

        # Re-import from dictionary to guarantee seamless interoperability
        reimported_project = DramaProject.model_validate(project_dict)
        assert reimported_project.title == project.title
        assert len(reimported_project.characters) == len(project.characters)
        assert len(reimported_project.props) == len(project.props)
        assert len(reimported_project.shots) == len(project.shots)
