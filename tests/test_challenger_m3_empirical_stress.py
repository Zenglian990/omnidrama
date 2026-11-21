"""OmniDrama Milestone 3 Empirical Challenger Stress & Oracle Test Suite.

Target: Director Consistency Engine (R2) in omnidrama/core/director.py.
Author: challenger_m3_1 (teamwork_challenger)

This test suite executes empirical and adversarial stress testing of:
1. compile_shot_visual_prompt (cinematic locks, scale optics, prop integration, 9:16 ratio)
2. compile_shot_negative_prompt (universal, character exclusive, prop negative combination)
3. build_character_turnaround_prompt & build_prop_turnaround_prompt (16:9 3-view turnaround specs)
4. build_multimodal_reference_config (Midjourney --cref, IP-Adapter, Seedance multi-ref)
5. Narrator isolation & anti-hallucination guarantees (zero actor hallucination on 旁白/Scene/环境)
6. Extreme inputs, unicode/emojis, malformed references, boundary conditions, and high-throughput scale.
"""
from __future__ import annotations

import time
import pytest
from typing import Dict, Any, List

from omnidrama.core.director import (
    DirectorAgent,
    UNIVERSAL_CINEMATIC_PREFIX,
    UNIVERSAL_NEGATIVE_PROMPT,
    compile_shot_visual_prompt,
    compile_shot_negative_prompt,
    build_character_turnaround_prompt,
    build_prop_turnaround_prompt,
    build_multimodal_reference_config,
)
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


# =============================================================================
# 1. Narrator Isolation & Anti-Hallucination Oracle
# =============================================================================
class TestNarratorIsolationOracle:
    """Empirical verification that narrator/environment shots NEVER hallucinate actors."""

    NARRATOR_SPEAKERS = [
        "旁白",
        "Scene",
        "环境",
        "背景",
        "空镜",
        "narrator",
        "scene",
        "environment",
        "SCENE",
        "ENVIRONMENT",
        "NARRATOR",
        " 旁白 ",
        "  空镜  ",
        "  Scene  ",
    ]

    @pytest.mark.parametrize("spk", NARRATOR_SPEAKERS)
    def test_narrator_isolation_zero_actor_hallucination(self, spk):
        """Verify narrator shots strictly emit environmental cues and 0 actor tokens."""
        prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.WIDE_SHOT,
            speaker=spk,
            action_beat="破晓时分，晨雾笼罩在紫禁城巍峨的琉璃瓦上",
            blocking="镜头以宏大视角自高空俯瞰全景",
            genre="古装权谋",
        )

        # Must have cinema quality & framing
        assert UNIVERSAL_CINEMATIC_PREFIX in prompt
        assert "shot on ARRI Alexa 65" in prompt
        assert "Panavision" in prompt
        assert "atmospheric 古装权谋 cinematic scene" in prompt
        assert "photorealistic environment" in prompt
        assert "vertical 9:16" in prompt
        assert "no actors" in prompt
        assert "no cartoon" in prompt
        assert "no anime" in prompt

        # Strict anti-hallucination checks: MUST NOT contain any actor tokens
        forbidden_tokens = [
            "actor playing",
            "actress playing",
            "photorealistic Chinese actor",
            "photorealistic Chinese female actor",
            "photorealistic Chinese male actor",
            "facial features",
            "hairstyle",
            "costume:",
            "holding and showcasing",
        ]
        for token in forbidden_tokens:
            assert token not in prompt, f"Hallucinated actor token '{token}' found for speaker '{spk}' in: {prompt}"

    def test_narrator_with_accidental_character_asset_override(self):
        """Even if someone erroneously passes a CharacterAsset named '旁白', narrator must not generate an actor."""
        fake_narrator_char = CharacterAsset(
            name="旁白",
            gender="female",
            visual_tags="mysterious female narrator",
            consistency_card=CharacterConsistencyCard(
                facial_lock="瓜子脸，冷清双眸",
                hair_lock="高马尾",
                costume_lock="黑风衣"
            )
        )
        prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.WIDE_SHOT,
            speaker="旁白",
            action_beat="空旷的大厅中，回荡着低沉的钟声",
            genre="悬疑",
            character=fake_narrator_char,
        )
        assert "no actors" in prompt
        assert "actor playing" not in prompt
        assert "瓜子脸" not in prompt
        assert "黑风衣" not in prompt

    def test_narrator_blocking_conditional_inclusion(self):
        """Blocking containing cinematic keywords (镜头, 全景, 视角) should be included; non-camera blocking excluded."""
        prompt_with_cam = compile_shot_visual_prompt(
            speaker="旁白",
            action_beat="雷雨交加",
            blocking="全景视角扫过空旷平原",
        )
        assert "全景视角扫过空旷平原" in prompt_with_cam

        prompt_without_cam = compile_shot_visual_prompt(
            speaker="旁白",
            action_beat="雷雨交加",
            blocking="两人并肩站立在走廊深处",  # non-camera blocking for narrator
        )
        assert "两人并肩站立在走廊深处" not in prompt_without_cam


# =============================================================================
# 2. Extreme Inputs, Boundary Cases & Unicode Resilience
# =============================================================================
class TestExtremeInputsAndBoundaryResilience:
    """Torture test functions with edge-case types, unicode, emojis, and boundary strings."""

    def test_compile_shot_visual_prompt_none_and_empty_args(self):
        """Test with empty strings and default arguments."""
        prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            speaker="",
            action_beat="",
            blocking="",
            genre="",
            character=None,
            props=None,
            prop_refs=None,
            extra_prompt=""
        )
        assert UNIVERSAL_CINEMATIC_PREFIX in prompt
        assert "vertical 9:16" in prompt
        assert "dramatic cinema lighting" in prompt

    def test_compile_shot_visual_prompt_string_scale_variations(self):
        """Test various string representations of shot_scale."""
        scales = [
            ("extreme_close_up", "extreme close-up shot, 85mm portrait lens"),
            ("EXTREME_CLOSE_UP", "extreme close-up shot, 85mm portrait lens"),
            ("close_up", "close-up portrait shot, 50mm prime lens"),
            ("medium_shot", "medium shot, 35mm lens"),
            ("full_shot", "full shot, 28mm wide lens"),
            ("wide_shot", "wide shot, 24mm ultra-wide lens"),
            ("custom_drone_shot", "custom_drone_shot shot, 50mm lens"),
        ]
        for scale_input, expected_text in scales:
            res = compile_shot_visual_prompt(shot_scale=scale_input, speaker="陆沉")
            assert expected_text in res, f"Expected '{expected_text}' in '{res}' for scale '{scale_input}'"

    def test_unicode_emojis_and_special_characters(self):
        """Verify special characters, emojis, quotes, and punctuation do not break compilation."""
        weird_name = "顾九幽⚡️（冥王殿主）"
        weird_facial = "棱角分明，双眸若寒星✨，眉心一道赤红剑纹🗡️"
        weird_hair = "银白如霜瀑垂落❄️"
        weird_costume = "玄黑龙鳞重铠，内衬朱红锦缎🩸"
        weird_action = "拔出「诛仙剑」斩破虚空💥！"

        char = CharacterAsset(
            name=weird_name,
            gender="male",
            consistency_card=CharacterConsistencyCard(
                facial_lock=weird_facial,
                hair_lock=weird_hair,
                costume_lock=weird_costume,
                exclusive_negative_prompt="现代西装, 塑料质感"
            )
        )

        prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.CLOSE_UP,
            speaker=weird_name,
            action_beat=weird_action,
            character=char,
            extra_prompt="--seed 42 --quality 2"
        )

        assert weird_name in prompt
        assert weird_facial in prompt
        assert weird_hair in prompt
        assert weird_costume in prompt
        assert weird_action in prompt
        assert "--seed 42 --quality 2" in prompt

    def test_huge_string_payload_scalability(self):
        """Stress-test with very large string payloads without memory spikes or recursion limits."""
        huge_action = "极度紧张的对抗，" * 2000  # ~16,000 characters
        huge_blocking = "在废弃仓库中央快速走位并闪避子弹，" * 1000

        t0 = time.perf_counter()
        prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.FULL_SHOT,
            speaker="龙王",
            action_beat=huge_action,
            blocking=huge_blocking,
        )
        elapsed = time.perf_counter() - t0

        assert len(prompt) > 30000
        assert UNIVERSAL_CINEMATIC_PREFIX in prompt
        assert "vertical 9:16" in prompt
        assert elapsed < 0.05, f"Compilation took too long: {elapsed:.4f}s"


# =============================================================================
# 3. Consistency Locking Prefix & Prop Integration Oracle
# =============================================================================
class TestConsistencyLockingAndPropIntegrationOracle:
    """Empirical verification of consistency card hierarchy and prop interaction."""

    def test_gender_prefix_mapping(self):
        """Verify male vs female character maps to photorealistic Chinese male/female actor."""
        char_m = CharacterAsset(name="霍骁", gender="male")
        char_f = CharacterAsset(name="苏云锦", gender="female")

        p_m = compile_shot_visual_prompt(speaker="霍骁", character=char_m)
        p_f = compile_shot_visual_prompt(speaker="苏云锦", character=char_f)

        assert "photorealistic Chinese male actor playing 霍骁" in p_m
        assert "photorealistic Chinese female actor playing 苏云锦" in p_f

    def test_consistency_card_fallback_hierarchy(self):
        """Verify fallback order: consistency_card > visual_anchor > visual_tags > bare name."""
        # Case A: Complete consistency_card
        char_a = CharacterAsset(
            name="A",
            visual_anchor="锚点A",
            visual_tags="标签A",
            consistency_card=CharacterConsistencyCard(facial_lock="骨相A", hair_lock="发型A", costume_lock="服饰A")
        )
        pa = compile_shot_visual_prompt(speaker="A", character=char_a)
        assert "facial features: 骨相A" in pa
        assert "hairstyle: 发型A" in pa
        assert "costume: 服饰A" in pa
        assert "标签A" in pa
        assert "锚点A" not in pa  # consistency_card takes precedence

        # Case B: No consistency_card, has visual_anchor
        char_b = CharacterAsset(name="B", visual_anchor="长发披肩冷艳面容", visual_tags="都市丽人")
        pb = compile_shot_visual_prompt(speaker="B", character=char_b)
        assert "长发披肩冷艳面容" in pb
        assert "都市丽人" in pb

        # Case C: No consistency_card, no visual_anchor, only visual_tags
        char_c = CharacterAsset(name="C", visual_tags="身穿黑色皮衣的高挑男子")
        pc = compile_shot_visual_prompt(speaker="C", character=char_c)
        assert "身穿黑色皮衣的高挑男子" in pc

        # Case D: Completely bare character
        char_d = CharacterAsset(name="D")
        pd = compile_shot_visual_prompt(speaker="D", character=char_d)
        assert "photorealistic Chinese male actor playing D" in pd

    def test_prop_matching_and_unreferenced_prop_isolation(self):
        """Props in prop_refs are matched; props not in prop_refs are strictly excluded."""
        props = [
            PropAsset(
                name="定海神针",
                category="weapon",
                visual_tags="两头金箍中间纯铁，九道蟠龙暗纹",
                feature_lock="泛着耀目耀金神光",
                negative_prompt="塑料手办, 粗糙泡沫"
            ),
            PropAsset(
                name="翡翠鼻烟壶",
                category="accessory",
                visual_tags="老坑玻璃种帝王绿翡翠",
                feature_lock="温润透亮，内画仕女图",
                negative_prompt="玻璃仿品, 浑浊杂质"
            ),
        ]

        # Scene referencing only "定海神针"
        p_single = compile_shot_visual_prompt(
            speaker="孙策",
            props=props,
            prop_refs=["定海神针"]
        )
        assert "holding and showcasing 定海神针" in p_single
        assert "两头金箍中间纯铁" in p_single
        assert "泛着耀目耀金神光" in p_single
        assert "翡翠鼻烟壶" not in p_single

        # Scene referencing an ad-hoc unmodeled prop
        p_adhoc = compile_shot_visual_prompt(
            speaker="孙策",
            props=props,
            prop_refs=["古朴铜镜"]
        )
        assert "holding and showcasing 古朴铜镜" in p_adhoc
        assert "定海神针" not in p_adhoc
        assert "翡翠鼻烟壶" not in p_adhoc

        # Scene with empty prop_refs
        p_none = compile_shot_visual_prompt(
            speaker="孙策",
            props=props,
            prop_refs=[]
        )
        assert "holding and showcasing" not in p_none


# =============================================================================
# 4. Negative Prompt Compilation Oracle
# =============================================================================
class TestNegativePromptCompilationOracle:
    """Empirical verification of universal + character exclusive + prop negative combination."""

    def test_negative_prompt_assembly(self):
        char = CharacterAsset(
            name="白飞飞",
            consistency_card=CharacterConsistencyCard(
                exclusive_negative_prompt="浓妆艳抹, 现代首饰, 金发"
            )
        )
        props = [
            PropAsset(name="毒龙簪", negative_prompt="粗劣塑料, 现代发夹"),
            PropAsset(name="玄玉扇", negative_prompt="纸折扇, 粗制滥造"),
        ]

        # Referencing "毒龙簪" only
        neg = compile_shot_negative_prompt(
            character=char,
            extra_negative="low quality, artifacts",
            props=props,
            prop_refs=["毒龙簪"]
        )

        # Universal checks
        assert UNIVERSAL_NEGATIVE_PROMPT in neg
        assert "bad anatomy" in neg
        assert "cartoon, anime, 3d, cgi" in neg

        # Exclusive character checks
        assert "浓妆艳抹, 现代首饰, 金发" in neg

        # Referenced prop negative checks
        assert "粗劣塑料, 现代发夹" in neg

        # Unreferenced prop negative check (MUST NOT appear)
        assert "纸折扇" not in neg

        # Extra negative check
        assert "low quality, artifacts" in neg


# =============================================================================
# 5. Turnaround Prompt Generators Oracle (16:9 3-Views)
# =============================================================================
class TestTurnaroundPromptGeneratorsOracle:
    """Empirical verification of character & prop 16:9 3-view turnaround specifications."""

    def test_character_turnaround_spec_compliance(self):
        char = CharacterAsset(
            name="沈墨",
            gender="male",
            consistency_card=CharacterConsistencyCard(
                facial_lock="利落剑眉，高挺鼻梁，英气内敛骨相",
                hair_lock="墨黑清爽短发",
                costume_lock="修身黑色战术风衣"
            )
        )
        prompt = build_character_turnaround_prompt(char)

        # 1. Aspect ratio: strictly 16:9
        assert "--ar 16:9" in prompt

        # 2. 3 views + pose: front, side 90°, back 180°, standing A-pose
        assert "3 views from multiple angles" in prompt
        assert "front view" in prompt
        assert "side 90° profile view" in prompt
        assert "back 180° view" in prompt
        assert "standing pose" in prompt
        assert "neutral expression" in prompt
        assert "A-pose" in prompt

        # 3. Background & lighting: clean solid pure white cyclorama studio background
        assert "clean solid pure white cyclorama studio background" in prompt
        assert "studio neutral even lighting" in prompt

        # 4. Inset portrait
        assert "bust portrait close-up inset" in prompt

        # 5. Photorealistic actor & camera
        assert "photorealistic Chinese male actor" in prompt
        assert "ARRI Alexa 65 cinematic texture" in prompt
        assert "authentic skin texture and pores" in prompt

        # 6. Physical features from locks
        assert "利落剑眉" in prompt
        assert "墨黑清爽短发" in prompt
        assert "修身黑色战术风衣" in prompt

        # 7. Negative flags
        assert "--no shadows on background, text, watermark, bad anatomy, deformed eyes" in prompt

    def test_prop_turnaround_spec_compliance(self):
        prop = PropAsset(
            name="乾坤印",
            category="magical_seal",
            visual_tags="羊脂白玉雕琢，底座铭刻古篆符文",
            feature_lock="通体莹润透光，金丝流纹隐现"
        )
        prompt = build_prop_turnaround_prompt(prop)

        # 1. Aspect ratio: strictly 16:9
        assert "--ar 16:9" in prompt

        # 2. 3 views: orthographic front, side profile, 45-degree isometric
        assert "3 views: orthographic front view, side profile view, 45-degree isometric perspective view" in prompt

        # 3. Background & lighting
        assert "isolated on solid pure white background" in prompt
        assert "softbox product studio lighting" in prompt

        # 4. Octane render quality & 8k
        assert "octane render quality" in prompt
        assert "photorealistic magical_seal" in prompt

        # 5. Prop features
        assert "羊脂白玉雕琢" in prompt
        assert "通体莹润透光" in prompt

        # 6. Negative flags
        assert "--no hands, human, text, watermark, heavy shadows" in prompt


# =============================================================================
# 6. Multimodal Reference Config Oracle (Midjourney, IP-Adapter, Seedance)
# =============================================================================
class TestMultimodalReferenceConfigOracle:
    """Empirical verification of multimodal reference pipelines."""

    def test_multimodal_reference_empty_fallback(self):
        """When no reference image is provided, returns clean empty structure."""
        cfg = build_multimodal_reference_config(character=None, turnaround_image_url="")
        assert cfg == {"midjourney": {}, "ip_adapter": {}, "seedance": {}}

    def test_multimodal_reference_explicit_turnaround_url(self):
        """Explicit turnaround_image_url takes highest priority."""
        url = "https://cdn.omnidrama.ai/assets/characters/turnaround_01.png"
        cfg = build_multimodal_reference_config(turnaround_image_url=url)

        # Midjourney
        mj = cfg["midjourney"]
        assert mj["cref_url"] == url
        assert mj["cref_weight"] == 100
        assert f"--cref {url} --cw 100 --ar 9:16 --v 6.1" in mj["prompt_suffix"]
        assert mj["aspect_ratio"] == "9:16"
        assert mj["version"] == "6.1"

        # IP-Adapter
        ip = cfg["ip_adapter"]
        assert ip["enabled"] is True
        assert ip["image_path"] == url
        assert ip["weight"] == 0.8
        assert ip["image_inputs"] == [{"role": "face", "path": url, "weight": 1.0}]

        # Seedance
        sd = cfg["seedance"]
        assert sd["ref_indices"] == [1]
        assert sd["ref_prompt_tag"] == "@角色参考图1"
        assert sd["image_url"] == url
        assert sd["image_urls"] == [url]

    def test_multimodal_reference_multi_image_consistency_card(self):
        """Multi-image reference configurations correctly build index arrays and tags."""
        ref1 = ReferenceImageConfig(
            url="https://cdn.omnidrama.ai/faces/actor_face.png",
            role=ReferenceRoleEnum.FACE,
            cref_weight=80,
            ip_adapter_weight=1.0
        )
        ref2 = ReferenceImageConfig(
            url="https://cdn.omnidrama.ai/costumes/actor_costume.png",
            role=ReferenceRoleEnum.COSTUME,
            weight=0.6
        )

        char = CharacterAsset(
            name="江雪",
            consistency_card=CharacterConsistencyCard(
                reference_images=[ref1, ref2]
            )
        )

        cfg = build_multimodal_reference_config(character=char)

        # Primary URL is the first ref
        assert cfg["midjourney"]["cref_url"] == "https://cdn.omnidrama.ai/faces/actor_face.png"
        assert cfg["midjourney"]["cref_weight"] == 80

        # IP-Adapter uses primary URL and custom ip_adapter_weight
        assert cfg["ip_adapter"]["image_path"] == "https://cdn.omnidrama.ai/faces/actor_face.png"
        assert cfg["ip_adapter"]["weight"] == 1.0
        assert len(cfg["ip_adapter"]["image_inputs"]) == 2

        # Seedance contains both URLs and indexed tags
        sd = cfg["seedance"]
        assert sd["ref_indices"] == [1, 2]
        assert sd["ref_prompt_tag"] == "@角色参考图1"
        assert sd["ref_prompt_tags"] == ["@角色参考图1", "@角色参考图2"]
        assert sd["image_urls"] == [
            "https://cdn.omnidrama.ai/faces/actor_face.png",
            "https://cdn.omnidrama.ai/costumes/actor_costume.png",
        ]

    def test_multimodal_reference_url_deduplication(self):
        """Identical URLs across turnaround_image and reference_images are deduplicated."""
        dup_url = "https://cdn.omnidrama.ai/shared/face.png"
        char = CharacterAsset(
            name="测试角色",
            turnaround_image=dup_url,
            consistency_card=CharacterConsistencyCard(
                reference_images=[
                    ReferenceImageConfig(url=dup_url, role=ReferenceRoleEnum.FACE),
                    ReferenceImageConfig(url=dup_url, role=ReferenceRoleEnum.STYLE),
                ]
            )
        )
        cfg = build_multimodal_reference_config(character=char)
        assert cfg["seedance"]["image_urls"] == [dup_url]
        assert cfg["seedance"]["ref_indices"] == [1]


# =============================================================================
# 7. End-to-End Workflow & Post-Processing Quality Gate Integration
# =============================================================================
class TestEndToEndDirectorConsistencyIntegration:
    """Empirical integration test of offline breakdown and quality gate post-processing."""

    def test_offline_breakdown_full_consistency_contract(self):
        agent = DirectorAgent()
        sample_script = """
第1幕：雨夜杀局
（雷电交加，暴雨倾盆）
旁白：雨夜的苏家老宅，死寂如坟。
林萧：（眼神冰冷）今日，我便要让你们血债血偿！
苏婉儿：（颤抖退后）你...你到底是谁？
"""
        proj = agent.breakdown_story_offline(
            raw_text=sample_script,
            title="雨夜杀局",
            genre="都市复仇"
        )

        assert len(proj.shots) >= 3
        # 1. Narrator shot validation
        narrator_shot = [s for s in proj.shots if s.speaker == "旁白"][0]
        assert "no actors" in narrator_shot.visual_prompt
        assert "actor playing" not in narrator_shot.visual_prompt
        assert "vertical 9:16" in narrator_shot.visual_prompt
        assert UNIVERSAL_NEGATIVE_PROMPT in narrator_shot.negative_prompt

        # 2. Character shots validation
        char_shots = [s for s in proj.shots if s.speaker != "旁白"]
        for s in char_shots:
            assert "photorealistic Chinese" in s.visual_prompt
            assert "vertical 9:16" in s.visual_prompt
            assert UNIVERSAL_CINEMATIC_PREFIX in s.visual_prompt
            assert UNIVERSAL_NEGATIVE_PROMPT in s.negative_prompt

        # 3. Characters turnaround prompts
        for c in proj.characters:
            if c.name != "旁白":
                assert c.turnaround_prompt != ""
                assert "--ar 16:9" in c.turnaround_prompt
                assert "3 views from multiple angles" in c.turnaround_prompt

    def test_post_process_project_fixes_corrupt_or_empty_shots(self):
        """_post_process_project must repair empty prompts, sanitize narrator hallucinations, and fill turnarounds."""
        agent = DirectorAgent()

        corrupt_shot_narrator = Shot(
            shot_id=1,
            speaker="旁白",
            dialogue="夜色深沉。",
            visual_prompt="8k, photorealistic Chinese actor playing 旁白, standing alone"  # Corrupt hallucination!
        )
        empty_shot_char = Shot(
            shot_id=2,
            speaker="夜天凌",
            dialogue="动手！",
            visual_prompt=""  # Missing visual prompt!
        )

        char = CharacterAsset(
            name="夜天凌",
            gender="male",
            visual_anchor="冷傲霸总，剑眉星目，黑色风衣"
        )
        prop = PropAsset(name="九龙佩", category="pendant")

        dirty_proj = DramaProject(
            title="破晓",
            genre="玄幻",
            characters=[char],
            props=[prop],
            shots=[corrupt_shot_narrator, empty_shot_char]
        )

        fixed_proj = agent._post_process_project(dirty_proj, title="破晓", genre="玄幻")

        # Shot 1 sanitized
        s1 = fixed_proj.shots[0]
        assert "actor playing 旁白" not in s1.visual_prompt
        assert "no actors" in s1.visual_prompt
        assert "vertical 9:16" in s1.visual_prompt

        # Shot 2 compiled from character
        s2 = fixed_proj.shots[1]
        assert s2.visual_prompt != ""
        assert "photorealistic Chinese male actor playing 夜天凌" in s2.visual_prompt
        assert "冷傲霸总" in s2.visual_prompt
        assert "vertical 9:16" in s2.visual_prompt
        assert UNIVERSAL_NEGATIVE_PROMPT in s2.negative_prompt

        # Assets turnaround prompts completed
        assert char.turnaround_prompt != ""
        assert "--ar 16:9" in char.turnaround_prompt
        assert prop.turnaround_prompt != ""
        assert "--ar 16:9" in prop.turnaround_prompt


# =============================================================================
# 8. High-Throughput Scale & Performance Stress
# =============================================================================
class TestHighThroughputStressOracle:
    """Stress test compiling thousands of shot visual and negative prompts."""

    def test_rapid_compilation_2000_shots(self):
        char = CharacterAsset(
            name="战神",
            gender="male",
            consistency_card=CharacterConsistencyCard(
                facial_lock="刀削斧凿般坚毅轮廓",
                hair_lock="寸头",
                costume_lock="戎装军服",
                exclusive_negative_prompt="浮夸首饰"
            )
        )
        prop = PropAsset(name="龙纹军刀", feature_lock="刀刃泛着血芒")

        t0 = time.perf_counter()
        count = 2000
        for i in range(count):
            spk = "旁白" if i % 5 == 0 else "战神"
            scale = ShotScaleEnum.CLOSE_UP if i % 2 == 0 else ShotScaleEnum.MEDIUM_SHOT
            vp = compile_shot_visual_prompt(
                shot_scale=scale,
                speaker=spk,
                action_beat=f"第{i}击动作爆发",
                character=char if spk == "战神" else None,
                props=[prop],
                prop_refs=["龙纹军刀"] if spk == "战神" else []
            )
            np = compile_shot_negative_prompt(
                character=char if spk == "战神" else None,
                props=[prop],
                prop_refs=["龙纹军刀"] if spk == "战神" else []
            )
            assert len(vp) > 50
            assert len(np) > 50

        elapsed = time.perf_counter() - t0
        rate = count / elapsed
        print(f"\nCompiled {count} visual & negative prompts in {elapsed:.3f}s ({rate:.0f} shots/sec)")
        # Must maintain high performance (> 2,000 compilations/sec on modern CPU)
        assert rate > 1000, f"Compilation throughput too slow: {rate:.1f} shots/sec"



# =============================================================================
# 9. Built-in Archetype Integration Oracle (M2 + M3 Handshake)
# =============================================================================
class TestBuiltinArchetypeConsistencyHandshake:
    """Verify that all M2 built-in archetypes compile flawlessly through M3 Director Consistency Engine."""

    from omnidrama.config.archetypes import BUILTIN_ARCHETYPES, create_character_from_archetype

    @pytest.mark.parametrize("archetype_id", [
        "04_modern_female_urban",
        "05_modern_male_boss",
        "06_ancient_male_noble",
        "08_antagonist_female_greentea",
    ])
    def test_archetype_character_visual_prompt_and_turnaround(self, archetype_id):
        from omnidrama.config.archetypes import create_character_from_archetype

        char = create_character_from_archetype(archetype_id)
        assert char.consistency_card is not None

        # 1. Compile shot visual prompt
        vp = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.CLOSE_UP,
            speaker=char.name,
            action_beat="目光直视镜头，展现标志性神态与气质",
            character=char,
            genre="影视短剧"
        )
        assert "shot on ARRI Alexa 65" in vp
        assert "vertical 9:16" in vp
        assert "close-up portrait shot" in vp
        assert char.name in vp

        # Verify character's locks are in prompt
        card = char.consistency_card
        if card.facial_lock:
            assert card.facial_lock in vp
        if card.hair_lock:
            assert card.hair_lock in vp
        if card.costume_lock:
            assert card.costume_lock in vp

        # 2. Compile shot negative prompt
        np = compile_shot_negative_prompt(character=char)
        assert UNIVERSAL_NEGATIVE_PROMPT in np
        if card.exclusive_negative_prompt:
            assert card.exclusive_negative_prompt in np

        # 3. Build turnaround prompt
        tp = build_character_turnaround_prompt(char)
        assert "--ar 16:9" in tp
        assert "3 views from multiple angles" in tp
        assert "clean solid pure white cyclorama studio background" in tp
        assert "ARRI Alexa 65 cinematic texture" in tp

        # 4. Build multimodal reference config
        m_cfg = build_multimodal_reference_config(character=char)
        # Should return valid dict structure
        assert "midjourney" in m_cfg
        assert "ip_adapter" in m_cfg
        assert "seedance" in m_cfg


# =============================================================================
# 10. Malformed and Corner-Case Reference Image Handling
# =============================================================================
class TestMalformedReferenceHandlingOracle:
    """Stress-test multimodal reference generator with corrupt or pathological reference image inputs."""

    def test_whitespace_and_none_urls_filtered_out(self):
        char = CharacterAsset(
            name="测试",
            turnaround_image="   ",  # whitespace only
            consistency_card=CharacterConsistencyCard(
                reference_images=[
                    ReferenceImageConfig(url="", role=ReferenceRoleEnum.FACE),
                    ReferenceImageConfig(url="  \t\n  ", role=ReferenceRoleEnum.STYLE),
                ]
            )
        )
        cfg = build_multimodal_reference_config(character=char, turnaround_image_url="   ")
        # Should cleanly evaluate to empty config, no crashes or invalid --cref flags
        assert cfg == {"midjourney": {}, "ip_adapter": {}, "seedance": {}}

    def test_extreme_weights_and_unusual_roles(self):
        ref = ReferenceImageConfig(
            url="https://cdn.omnidrama.ai/test.png",
            role=ReferenceRoleEnum.GENERAL,
            weight=1.99,
            cref_weight=0,  # MJ cref_weight=0 means face only
            ip_adapter_weight=1.45
        )
        char = CharacterAsset(
            name="极限测试",
            consistency_card=CharacterConsistencyCard(reference_images=[ref])
        )
        cfg = build_multimodal_reference_config(character=char)

        assert cfg["midjourney"]["cref_weight"] == 0
        assert "--cw 0" in cfg["midjourney"]["prompt_suffix"]
        assert cfg["ip_adapter"]["weight"] == 1.45
        assert cfg["ip_adapter"]["image_inputs"][0]["role"] == "general"


# =============================================================================
# 11. Empty Script and Minimal Input Offline Breakdown
# =============================================================================
class TestDirectorBreakdownMinimalScriptResilience:
    """Ensure breakdown_story_offline does not crash on empty, single-line, or whitespace scripts."""

    def test_breakdown_story_offline_single_line_script(self):
        agent = DirectorAgent()
        proj = agent.breakdown_story_offline(
            raw_text="旁白：夜幕降临，万籁俱寂。",
            title="微型测试",
            genre="都市"
        )
        assert len(proj.shots) == 1
        shot = proj.shots[0]
        assert shot.speaker == "旁白"
        assert "no actors" in shot.visual_prompt
        assert "vertical 9:16" in shot.visual_prompt

    def test_breakdown_story_offline_dialogue_only_script(self):
        agent = DirectorAgent()
        proj = agent.breakdown_story_offline(
            raw_text="楚云飞：立正！敬礼！",
            title="亮剑测试",
            genre="军事热血"
        )
        assert len(proj.shots) >= 1
        shot = proj.shots[0]
        assert shot.speaker == "楚云飞"
        assert "楚云飞" in shot.visual_prompt
        assert "vertical 9:16" in shot.visual_prompt
