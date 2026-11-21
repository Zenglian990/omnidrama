"""Empirical Adversarial Stress & Verification Test Suite for Milestone 5 (E2E Integration & Verification - R5).

Authored by challenger_m5_1 (Empirical Challenger) to independently stress-test:
1. Screenplay parsing with highly adversarial syntax (mixed quotes/no-quotes, nested quotes, multiple colons,
   inline bracketed stage directions, dialogue containing speech verbs, rapid alternation).
2. Narrator line parsing and phantom-actor immunity when narrator lines explicitly contain character names.
3. High-scale ensemble screenplay with 10+ characters and 4+ interacting props.
4. Multi-prop visual prompt and negative prompt compilation, turnaround generation, and reference config.
5. Project JSON serialization and deserialization roundtrip fidelity under multi-character multi-prop complexity.
"""
from pathlib import Path
import json
import pytest

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
from omnidrama.core.director import (
    DirectorAgent,
    compile_shot_visual_prompt,
    compile_shot_negative_prompt,
    build_character_turnaround_prompt,
    build_prop_turnaround_prompt,
    build_multimodal_reference_config,
    build_seedance_prompt,
    _estimate_shot_duration,
    _clean_dialogue_text,
    _is_sfx_or_onomatopoeia,
)
from omnidrama.config.archetypes import (
    BUILTIN_ARCHETYPES,
    apply_archetype_to_character,
    create_character_from_archetype,
)


@pytest.fixture(autouse=True)
def preserve_project_state():
    """Ensure current_project.json is not modified during test runs."""
    project_file = Path(__file__).resolve().parent.parent / "output" / "current_project.json"
    backup = None
    if project_file.exists():
        backup = project_file.read_text(encoding="utf-8")
    yield
    if backup is not None:
        project_file.write_text(backup, encoding="utf-8")


# =========================================================================
# Aspect 1: Screenplay Parsing with Adversarial Syntax
# =========================================================================

class TestAdversarialScreenplaySyntax:
    """Stress tests heuristic screenplay breakdown under chaotic, real-world author syntax."""

    def test_chaotic_syntax_breakdown(self):
        """Test screenplay mixing dialogue without quotes, nested quotes, multiple colons,

        stage directions in brackets, and dialogue containing speech verbs.
        """
        chaotic_script = (
            "林管家：老爷，大事不好了！苏少爷带人硬闯进来了！\n"
            "陆沉舟（脸色铁青，猛地捏碎手中的高脚杯）：[保镖封锁所有出口]放肆，谁给他的胆子！\n"
            "温梨冷笑道：“陆总，顾清雪刚才在电话里说‘永远不想再见到你’呢。”\n"
            "顾清雪：会议纪要如下：第一：交出公章；第二：立刻滚蛋；第三：永不录用。\n"
            "温梨小声啜泣道：“我没有说道歉，我只是说陆沉舟冷笑是不对的！”\n"
            "顾清雪：“放开我！”\n"
            "陆沉舟：“休想！”\n"
            "温梨：“沉舟哥哥小心！”\n"
            "萧绝：“陆沉舟，放开清雪。”\n"
            "砰！砰！砰！\n"
        )
        director = DirectorAgent()
        proj = director.breakdown_story_offline(chaotic_script, title="逆袭风云", genre="都市商战")

        assert isinstance(proj, DramaProject)
        assert len(proj.shots) >= 8

        # Verify speakers are properly cleaned without brackets or colon fragments
        valid_speakers = {"林管家", "陆沉舟", "温梨", "顾清雪", "萧绝", "旁白"}
        for shot in proj.shots:
            assert shot.speaker in valid_speakers, f"Unexpected speaker: {shot.speaker}"
            assert "[" not in shot.speaker and "]" not in shot.speaker
            assert "（" not in shot.speaker and "）" not in shot.speaker
            assert ":" not in shot.speaker and "：" not in shot.speaker

            # Verify shot duration is strictly clamped between 2.0 and 5.0 seconds
            assert 2.0 <= shot.duration_seconds <= 5.0

        # Verify sound effect shot
        sfx_shots = [s for s in proj.shots if s.sfx]
        assert len(sfx_shots) >= 1
        last_shot = proj.shots[-1]
        assert last_shot.speaker == "旁白"

    def test_dialogue_cleaning_under_nested_quotes_and_brackets(self):
        """Verify _clean_dialogue_text correctly removes stage directions in brackets."""
        raw_1 = "(冷笑一声)你以为你能逃得掉吗？(猛然抓住手腕)"
        assert _clean_dialogue_text(raw_1) == "你以为你能逃得掉吗？"

        raw_2 = "（咬牙切齿）顾清雪，算你狠！（转身离去）"
        assert _clean_dialogue_text(raw_2) == "顾清雪，算你狠！"

        raw_3 = "冷笑：把这串项链交出来。"
        assert _clean_dialogue_text(raw_3) == "把这串项链交出来。"

        raw_4 = "『绝不可能！』"
        assert _clean_dialogue_text(raw_4) == "绝不可能！"


# =========================================================================
# Aspect 2: Narrator Immunity & Phantom Prevention
# =========================================================================

class TestNarratorImmunityAndPhantomPrevention:
    """Stress tests narrator shots to guarantee zero phantom actor hallucinations

    even when narration text explicitly references characters.
    """

    def test_narrator_lines_referencing_characters_remain_clean_environment_shots(self):
        """Test screenplay where narrator lines explicitly mention character names.

        Ensures narrator lines are NOT falsely converted to character shots.
        """
        script_with_named_narration = (
            "旁白：此时顾清雪与陆沉舟在暴雨中对视，周围杀机四伏。\n"
            "【旁白】陆沉舟的目光穿透迷雾，温梨倒在血泊中。\n"
            "(Scene) 暴雨倾盆，顾清雪手中的玉玺发出耀眼光芒。\n"
            "环境：陆沉舟的豪华办公室中，散落着温梨的项链。\n"
            "【空镜头】狂风呼啸，吹散了顾清雪与萧绝的誓言。\n"
            "顾清雪：“我绝不会妥协。”\n"
            "陆沉舟：“这由不得你。”\n"
        )
        director = DirectorAgent()
        proj = director.breakdown_story_offline(script_with_named_narration, title="迷雾抉择", genre="都市热血")

        narrator_shots = [s for s in proj.shots if s.speaker in ("旁白", "Scene", "环境", "空镜", "空镜头")]
        character_shots = [s for s in proj.shots if s.speaker not in ("旁白", "Scene", "环境", "空镜", "空镜头")]

        # Exactly lines 1-5 must be narrator shots, lines 6-7 character shots
        assert len(narrator_shots) >= 4
        assert len(character_shots) >= 2

        # Verify each narrator shot visual prompt strictly contains no actors
        for n_shot in narrator_shots:
            vp = n_shot.visual_prompt
            assert "no actors" in vp, f"Narrator shot prompt lacks 'no actors': {vp}"
            assert "no cartoon" in vp
            assert "no anime" in vp
            # MUST NOT contain phantom actor generation strings
            assert "actor playing 旁白" not in vp
            assert "actor playing Scene" not in vp
            assert "actor playing 环境" not in vp
            assert "actor playing 空镜" not in vp

        # Verify character shots for 顾清雪 and 陆沉舟 contain actor playing directives
        q_shot = next(s for s in character_shots if s.speaker == "顾清雪")
        assert "actor playing 顾清雪" in q_shot.visual_prompt
        l_shot = next(s for s in character_shots if s.speaker == "陆沉舟")
        assert "actor playing 陆沉舟" in l_shot.visual_prompt

    def test_post_process_project_cleanses_narrator_phantom_actors(self):
        """Verify _post_process_project actively strips phantom actors if an LLM hallucinated them."""
        director = DirectorAgent()
        dirty_project = DramaProject(
            title="清洗测试",
            genre="悬疑",
            synopsis="测试",
            characters=[
                CharacterAsset(name="旁白", gender="female"),
                CharacterAsset(name="顾清雪", gender="female"),
            ],
            shots=[
                Shot(
                    shot_id=1,
                    speaker="旁白",
                    dialogue="",
                    action_beat="乌云密布，雷声滚滚",
                    visual_prompt="8k, photorealistic Chinese actor playing 旁白, dramatic lighting",
                ),
                Shot(
                    shot_id=2,
                    speaker="【旁白】",
                    dialogue="",
                    action_beat="空旷的大厅中，只剩下一张红木桌椅",
                    visual_prompt="",
                ),
            ]
        )
        cleaned = director._post_process_project(dirty_project, title="清洗测试", genre="悬疑")
        for s in cleaned.shots:
            assert "actor playing 旁白" not in s.visual_prompt
            assert "no actors" in s.visual_prompt


# =========================================================================
# Aspect 3: 10+ Characters Ensemble Scale and Multi-Prop Interlocking
# =========================================================================

class TestHighScaleEnsembleAndMultiPropInterlocking:
    """Stress tests system scaling to 10+ characters, multiple props,

    and complex prompt and reference configuration compiling.
    """

    def test_ten_plus_characters_and_four_props_e2e_pipeline(self):
        """Construct a 12-character ensemble with 4 distinct props and verify:

        1. Consistency card applications from canonical archetypes.
        2. Prop turnaround prompt generation.
        3. Shot visual prompt compilation with character locks, lens optics, and prop showcases.
        4. Negative prompt compilation merging universal, character, and prop negatives.
        5. Multimodal reference config generation (Midjourney, IP-Adapter, Seedance).
        6. Full JSON serialization roundtrip fidelity.
        """
        # 1. Define 12 distinct characters
        char_defs = [
            ("顾清雪", "04_modern_female_urban"),
            ("陆沉舟", "05_modern_male_boss"),
            ("温梨", "08_antagonist_female_greentea"),
            ("萧绝", "06_ancient_male_noble"),
            ("苏慕远", None),
            ("林管家", None),
            ("赵助理", None),
            ("陈长老", None),
            ("白护士", None),
            ("黑客阿飞", None),
            ("江夫人", None),
            ("沈老爷子", None),
        ]

        characters = []
        for name, arch_id in char_defs:
            if arch_id:
                char = create_character_from_archetype(arch_id, name)
            else:
                is_female = name in ("白护士", "江夫人")
                char = CharacterAsset(
                    name=name,
                    gender="female" if is_female else "male",
                    visual_tags=f"photorealistic Chinese {'actress' if is_female else 'actor'}, authentic skin pores, playing {name}",
                    visual_anchor=f"{name}标志性外观特征",
                    consistency_card=CharacterConsistencyCard(
                        facial_lock=f"{name}特征骨相五官",
                        costume_lock=f"{name}职业定制装束",
                        exclusive_negative_prompt=f"bad {name} facial symmetry"
                    )
                )
            char.turnaround_prompt = build_character_turnaround_prompt(char)
            characters.append(char)

        assert len(characters) == 12

        # 2. Define 4 distinct props
        props = [
            PropAsset(
                name="传家玉玺",
                category="heirloom",
                feature_lock="imperial dragon carving in mutton fat jade",
                visual_tags="translucent green jade seal, imperial dragon finial, 8k product still",
                negative_prompt="plastic, cracked, cheap glass"
            ),
            PropAsset(
                name="绝密股权书",
                category="document",
                feature_lock="black leather folder with gold embossed seal",
                visual_tags="official corporate acquisition contracts with stamped red seals",
                negative_prompt="crumpled paper, torn pages"
            ),
            PropAsset(
                name="暗纹银匕首",
                category="weapon",
                feature_lock="engraved damascus steel blade with sapphire hilt",
                visual_tags="sharp silver ornamental dagger, intricate runic engravings",
                negative_prompt="wooden toy, blunt edge, rust"
            ),
            PropAsset(
                name="解毒血清",
                category="medicine",
                feature_lock="glowing blue liquid in titanium syringe",
                visual_tags="sci-fi medical auto-injector, fluorescent cyan glow",
                negative_prompt="empty tube, broken syringe"
            ),
        ]

        for p in props:
            p.turnaround_prompt = build_prop_turnaround_prompt(p)
            assert "prop design turnaround sheet, 3 views" in p.turnaround_prompt
            assert "--ar 16:9" in p.turnaround_prompt
            assert p.feature_lock in p.turnaround_prompt

        # 3. Construct shots binding characters, props, camera optics, and actions
        shots = [
            # Shot 1: 顾清雪 holding 传家玉玺 (Close-Up, 50mm)
            Shot(
                shot_id=1,
                shot_scale=ShotScaleEnum.CLOSE_UP,
                camera_motion=CameraMotionEnum.ZOOM_IN,
                speaker="顾清雪",
                dialogue="这就是你们苦心寻找的玉玺。",
                visual_prompt="",
                action_beat="顾清雪高举传家玉玺，眼神冰冷决绝",
                blocking="顾清雪位于画面中央，手部前推展现玉玺",
                prop_refs=["传家玉玺"],
            ),
            # Shot 2: 陆沉舟 holding 绝密股权书 and 暗纹银匕首 (Medium Shot, 35mm)
            Shot(
                shot_id=2,
                shot_scale=ShotScaleEnum.MEDIUM_SHOT,
                camera_motion=CameraMotionEnum.PAN_LEFT,
                speaker="陆沉舟",
                dialogue="签了它，或者选这把刀。",
                visual_prompt="",
                action_beat="陆沉舟一手将股权书拍在桌上，另一手拔出暗纹银匕首插在桌面",
                blocking="陆沉舟居高临下俯视，压迫感十足",
                prop_refs=["绝密股权书", "暗纹银匕首"],
            ),
            # Shot 3: 温梨 holding 解毒血清 (Extreme Close-Up, 85mm)
            Shot(
                shot_id=3,
                shot_scale=ShotScaleEnum.EXTREME_CLOSE_UP,
                camera_motion=CameraMotionEnum.STATIC,
                speaker="温梨",
                dialogue="沉舟哥哥，只有我能救你……",
                visual_prompt="",
                action_beat="温梨指尖颤抖地握着解毒血清，眼中泪光流转",
                blocking="眼部与药剂瓶双重特写，焦点在晶莹液体",
                prop_refs=["解毒血清"],
            ),
            # Shot 4: 萧绝 (Full Shot, 28mm)
            Shot(
                shot_id=4,
                shot_scale=ShotScaleEnum.FULL_SHOT,
                camera_motion=CameraMotionEnum.SHAKE,
                speaker="萧绝",
                dialogue="陆沉舟，今日谁也动不了清雪。",
                visual_prompt="",
                action_beat="萧绝拔剑跨步上前，玄黑披风在狂风中猎猎作响",
                blocking="萧绝挡在顾清雪身前，形成坚固防线",
                prop_refs=[],
            ),
            # Shot 5: 旁白 (Wide Shot, 24mm)
            Shot(
                shot_id=5,
                shot_scale=ShotScaleEnum.WIDE_SHOT,
                camera_motion=CameraMotionEnum.ZOOM_OUT,
                speaker="旁白",
                dialogue="",
                visual_prompt="",
                action_beat="大厦顶楼暴风雨倾盆而下，雷电撕裂黑夜",
                blocking="俯瞰城市全景，雷暴笼罩整座摩天大楼",
                prop_refs=[],
            ),
        ]

        char_map = {c.name: c for c in characters}

        # 4. Compile visual prompts and negative prompts for each shot
        for s in shots:
            ch = char_map.get(s.speaker)
            s.visual_prompt = compile_shot_visual_prompt(
                shot_scale=s.shot_scale,
                speaker=s.speaker,
                action_beat=s.action_beat,
                blocking=s.blocking,
                genre="都市修罗",
                character=ch,
                props=props,
                prop_refs=s.prop_refs,
            )
            s.negative_prompt = compile_shot_negative_prompt(
                character=ch,
                props=props,
                prop_refs=s.prop_refs,
            )

        # 5. Verify Shot 1 (顾清雪 + 传家玉玺)
        s1 = shots[0]
        assert "close-up portrait shot, 50mm prime lens" in s1.visual_prompt
        assert "holding and showcasing 传家玉玺" in s1.visual_prompt
        assert "imperial dragon carving in mutton fat jade" in s1.visual_prompt
        assert "plastic, cracked, cheap glass" in s1.negative_prompt
        assert "bad anatomy" in s1.negative_prompt

        # 6. Verify Shot 2 (陆沉舟 + 绝密股权书 + 暗纹银匕首)
        s2 = shots[1]
        assert "medium shot, 35mm lens" in s2.visual_prompt
        assert "holding and showcasing 绝密股权书" in s2.visual_prompt
        assert "holding and showcasing 暗纹银匕首" in s2.visual_prompt
        assert "crumpled paper, torn pages" in s2.negative_prompt
        assert "wooden toy, blunt edge, rust" in s2.negative_prompt

        # 7. Verify Shot 3 (温梨 + 解毒血清)
        s3 = shots[2]
        assert "extreme close-up shot, 85mm portrait lens" in s3.visual_prompt
        assert "holding and showcasing 解毒血清" in s3.visual_prompt
        assert "empty tube, broken syringe" in s3.negative_prompt

        # 8. Verify Shot 5 (旁白)
        s5 = shots[4]
        assert "no actors" in s5.visual_prompt
        assert "photorealistic Chinese actor" not in s5.visual_prompt

        # 9. Verify Multimodal reference generation for 顾清雪
        char_q = char_map["顾清雪"]
        char_q.turnaround_image = "https://cdn.omnidrama.ai/turnaround/guqingxue.png"
        ref_cfg = build_multimodal_reference_config(character=char_q)
        assert "--cref https://cdn.omnidrama.ai/turnaround/guqingxue.png" in ref_cfg["midjourney"]["prompt_suffix"]
        assert ref_cfg["ip_adapter"]["enabled"] is True
        assert "@角色参考图1" in ref_cfg["seedance"]["ref_prompt_tag"]

        # 10. Assemble complete DramaProject and test JSON roundtrip
        project = DramaProject(
            title="十角色四道具史诗大剧",
            genre="都市商战修罗场",
            synopsis="顾家与陆家在商界风云中的恩怨情仇，多方势力搏杀对决。",
            characters=characters,
            props=props,
            shots=shots,
        )

        json_bytes = project.model_dump_json()
        assert len(json_bytes) > 2000

        # Reload and check 100% preservation
        reloaded = DramaProject.model_validate_json(json_bytes)
        assert reloaded.title == "十角色四道具史诗大剧"
        assert len(reloaded.characters) == 12
        assert len(reloaded.props) == 4
        assert len(reloaded.shots) == 5

        # Check props reloaded
        prop_names = [p.name for p in reloaded.props]
        assert "传家玉玺" in prop_names
        assert "绝密股权书" in prop_names
        assert "暗纹银匕首" in prop_names
        assert "解毒血清" in prop_names

        # Check shot 2 prop_refs preserved
        assert reloaded.shots[1].prop_refs == ["绝密股权书", "暗纹银匕首"]
        assert reloaded.shots[0].prop_refs == ["传家玉玺"]


# =========================================================================
# Aspect 4: Corner Cases & Fault Tolerance
# =========================================================================

class TestCornerCasesAndFaultTolerance:
    """Stress tests corner cases, missing references, boundary lengths, and coercion."""

    def test_unmatched_prop_refs_graceful_handling(self):
        """Verify that referencing non-existent props doesn't crash prompt compilation."""
        p_vp = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            speaker="陆沉舟",
            action_beat="陆沉舟凝视桌面",
            props=[PropAsset(name="传家玉玺")],
            prop_refs=["神秘黑卡", "未知图腾"],
        )
        assert "holding and showcasing 神秘黑卡" in p_vp
        assert "holding and showcasing 未知图腾" in p_vp

        p_neg = compile_shot_negative_prompt(
            props=[PropAsset(name="传家玉玺", negative_prompt="cheap_acrylic_cracked")],
            prop_refs=["神秘黑卡"],
        )
        # Should not include 传家玉玺's negative prompt since it wasn't referenced
        assert "cheap_acrylic_cracked" not in p_neg
        assert "bad anatomy" in p_neg

    def test_shot_duration_clamping_extremes(self):
        """Verify deterministic shot duration calculations across extreme boundaries."""
        # Pure action / environment / empty dialogue -> 2.8s
        assert _estimate_shot_duration("", has_dialogue=False) == 2.8
        assert _estimate_shot_duration("   ", has_dialogue=True) == 2.8

        # Ultra-short dialogue (1 char) -> minimum 2.0s
        assert _estimate_shot_duration("走", has_dialogue=True) == 2.0

        # Ultra-long dialogue (2000 chars) -> maximum 5.0s
        long_monologue = "顾清雪冷冷说道，" * 300
        assert _estimate_shot_duration(long_monologue, has_dialogue=True) == 5.0

    def test_seedance_prompt_structure_integrity(self):
        """Verify build_seedance_prompt conforms strictly to Volcano Seedance 2.0 specifications."""
        seedance = build_seedance_prompt(
            blocking="顾清雪立于左侧三分线，陆沉舟坐于正中老板椅",
            shot_scale=ShotScaleEnum.CLOSE_UP,
            camera_motion=CameraMotionEnum.ZOOM_IN,
            action_beat="顾清雪双目泛红，猛地将文件摔在办公桌上",
            dialogue="你欠顾家的，今天必须连本带利还清！",
            sfx="文件重重砸在桌面闷响",
            character_name="顾清雪"
        )
        assert "【人物关系与构图逻辑】" in seedance
        assert "顾清雪立于左侧三分线" in seedance
        assert "焦距与景深：浅景深，50mm 定焦" in seedance
        assert "构图：主体居中" in seedance
        assert "运镜：缓慢推镜，视线逐步聚焦主体" in seedance
        assert "景别：特写" in seedance
        assert "画面：顾清雪双目泛红" in seedance
        assert "台词：{你欠顾家的，今天必须连本带利还清！}" in seedance
        assert "音效：<文件重重砸在桌面闷响>" in seedance

    def test_speaker_boundary_lengths_and_stopwords(self):
        """Verify speaker cleaning for stopwords and length boundaries (<2 or >6 chars)."""
        director = DirectorAgent()

        # Stopwords fall back to 旁白
        assert director._clean_speaker("旁白") == "旁白"
        assert director._clean_speaker("众人") == "旁白"
        assert director._clean_speaker("此时") == "旁白"
        assert director._clean_speaker("Scene") == "旁白"
        assert director._clean_speaker("【空镜头】") == "旁白"
        assert director._clean_speaker("narrator") == "旁白"

        # Single character falls back to 旁白
        assert director._clean_speaker("王") == "旁白"

        # More than 6 characters falls back to 旁白
        assert director._clean_speaker("上官欧阳慕容复绝天") == "旁白"

        # 2 to 4 characters clean speaker
        assert director._clean_speaker("陆沉舟") == "陆沉舟"
        assert director._clean_speaker("顾清雪：") == "顾清雪"
        assert director._clean_speaker("“温梨”") == "温梨"
        assert director._clean_speaker("【萧绝】") == "萧绝"

    def test_reference_image_config_coercion_and_properties(self):
        """Verify ReferenceImageConfig coerces legacy fields and handles edge types."""
        cfg1 = ReferenceImageConfig(url="https://example.com/face.jpg")
        assert cfg1.role == ReferenceRoleEnum.FACE
        assert cfg1.weight == 1.0
        assert cfg1.image_url == "https://example.com/face.jpg"
        assert cfg1.reference_type == "face"

        # Coerce from legacy dict
        cfg2 = ReferenceImageConfig.model_validate({
            "image_url": "https://example.com/costume.jpg",
            "reference_type": "costume",
            "description": "古风华服刺绣"
        })
        assert cfg2.url == "https://example.com/costume.jpg"
        assert cfg2.role == "costume"
        assert cfg2.notes == "古风华服刺绣"
        assert cfg2.description == "古风华服刺绣"

