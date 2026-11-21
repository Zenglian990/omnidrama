"""OmniDrama 导演一致性引擎 (Milestone 3 Iteration 2 - R2) 经验性对抗挑战压力测试套件.

Author: challenger_m3_r2_1 (Empirical Challenger)
Target: omnidrama/core/director.py (Consistency Engine, Dialogue Extraction, Narrator Isolation, Prop Refs)
"""
import pytest
from typing import List, Dict, Any

from omnidrama.core.director import (
    DirectorAgent,
    UNIVERSAL_CINEMATIC_PREFIX,
    UNIVERSAL_NEGATIVE_PROMPT,
    compile_shot_visual_prompt,
    compile_shot_negative_prompt,
    build_character_turnaround_prompt,
    build_prop_turnaround_prompt,
    build_multimodal_reference_config,
    _estimate_shot_duration,
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


class TestExtremeSpeakerNarratorIsolation:
    """1. 极端说话人与旁白隔离对抗性测试"""

    @pytest.mark.parametrize("spk", [
        None,
        "",
        "   ",
        "\t\n  ",
        "【旁白】",
        "（旁白）",
        "“旁白”",
        "'旁白'",
        ":旁白:",
        "：旁白：",
        "【空镜】",
        "【空镜头】",
        "（空镜头）",
        "【Scene】",
        "【环境】",
        "【背景】",
        "【背景音】",
        "【bgm】",
        "【environment】",
        "【narrator】",
        "  空镜头  ",
        "  Scene  ",
    ])
    def test_narrator_isolation_never_hallucinates_actor(self, spk):
        """测试无论传入何种标点包裹或空白的旁白/空镜别名，绝不生成替身演员或 playing 词."""
        vp = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.WIDE_SHOT,
            speaker=spk,
            action_beat="乌云密布，雷声滚滚，青石阶被暴雨浸透",
            blocking="全景俯视视角",
            genre="古风权谋",
        )
        assert "no actors" in vp, f"Missing 'no actors' for speaker={spk!r}: {vp}"
        assert "actor playing" not in vp, f"Hallucinated actor for speaker={spk!r}: {vp}"
        assert "playing " not in vp, f"Hallucinated playing for speaker={spk!r}: {vp}"
        assert "vertical 9:16" in vp
        assert "dramatic cinema lighting" in vp


class TestAdversarialColonAndSpeechVerbExtraction:
    """2. 对抗性剧本对话提取与说话人清洗测试"""

    def test_colon_speaker_formats_in_offline_breakdown(self):
        """测试多种中文/英文冒号、空格及变体格式的准确解析."""
        d = DirectorAgent()

        lines = [
            ("林管家：“大小姐，交出令牌！”", "林管家"),
            ("林管家: “大小姐，交出令牌！”", "林管家"),
            ("林管家   ：   “大小姐，交出令牌！”", "林管家"),
            ("顾清雪: \"休想！\"", "顾清雪"),
            ("门外，林管家冷笑道：“大小姐，请回吧。”", "林管家"),
            ("顾清雪咬牙切齿地冷笑道：“想要公章？踩着我的尸体过去！”", "顾清雪"),
            ("顾清雪：“父亲，女儿定当百倍讨回！”", "顾清雪"),
        ]

        for script_line, expected_speaker in lines:
            proj = d.breakdown_story_offline(script_line, title="豪门对峙", genre="现代都市")
            assert len(proj.shots) >= 1
            actual_speaker = proj.shots[0].speaker
            assert actual_speaker == expected_speaker, (
                f"Failed for input line '{script_line}': expected {expected_speaker!r}, got {actual_speaker!r}"
            )

    def test_suffix_dialogue_speaker_extraction(self):
        """测试台词后置说话人格式（'“...”林管家冷笑道。'）的准确提取."""
        d = DirectorAgent()

        lines = [
            ("“大小姐，老爷已经去了。”林管家冷笑道。", "林管家"),
            ("“想要公章？除非踩着我的尸体过去！”顾清雪冷笑道。", "顾清雪"),
            ("“我才没有哭。”温梨小声吸了吸鼻子。", "温梨"),
        ]

        for script_line, expected_speaker in lines:
            proj = d.breakdown_story_offline(script_line, title="豪门测试", genre="现代都市")
            assert len(proj.shots) >= 1
            actual_speaker = proj.shots[0].speaker
            assert actual_speaker == expected_speaker, (
                f"Failed for input line '{script_line}': expected {expected_speaker!r}, got {actual_speaker!r}"
            )

    def test_multi_speaker_dialogue_offline_breakdown_full_scene(self):
        """测试多行剧本完整对峙场景，验证男女主角与对手被完整识别并拥有专属卡."""
        d = DirectorAgent()
        script = """
        【第1幕：灵堂夺权】
        滂沱大雨冲刷着顾家老宅的青石阶，雷声轰鸣。
        顾清雪跪在灵堂前，双拳攥紧。
        顾清雪：“父亲，女儿发誓，今日他们夺走的一切，我定当百倍讨回！”
        门外，林管家冷笑道：“大小姐，老爷已经去了，交出顾氏公章，你还能留一条生路。”
        顾清雪猛然抬头，桃花眼中冷意森然：“想要公章？除非踩着我的尸体过去！”
        """
        proj = d.breakdown_story_offline(script, title="真千金复仇记", genre="现代都市")

        char_names = {c.name for c in proj.characters}
        assert "顾清雪" in char_names
        assert "林管家" in char_names
        assert "旁白" in char_names

        # 检查分镜中的非旁白角色表演
        spk_list = [s.speaker for s in proj.shots]
        assert "顾清雪" in spk_list
        assert "林管家" in spk_list

        for s in proj.shots:
            if s.speaker in ["顾清雪", "林管家"]:
                assert f"playing {s.speaker}" in s.visual_prompt
                assert "no actors" not in s.visual_prompt
            elif s.speaker == "旁白":
                assert "no actors" in s.visual_prompt
                assert "actor playing" not in s.visual_prompt


class TestMalformedPropRefsAndNegatives:
    """3. 道具关联与负向词对抗性脏数据注入测试"""

    def test_dirty_prop_refs_sanitized(self):
        """测试 prop_refs 含有 None、空字符串、全空格字符时，不污染 visual_prompt."""
        props = [
            PropAsset(
                name="玄龙令",
                visual_tags="玄铁铸造，盘龙纹饰",
                feature_lock="深邃暗金光泽",
                negative_prompt="modern plastic, toy badge"
            )
        ]
        char = CharacterAsset(name="陆沉", gender="male")

        dirty_refs = [None, "", "   ", "\t", "  玄龙令  "]
        vp = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            speaker="陆沉",
            character=char,
            props=props,
            prop_refs=dirty_refs
        )

        assert "holding and showcasing None" not in vp
        assert "holding and showcasing  " not in vp
        assert "holding and showcasing 玄龙令" in vp

        neg = compile_shot_negative_prompt(
            character=char,
            props=props,
            prop_refs=dirty_refs
        )
        assert "None" not in neg
        assert "modern plastic, toy badge" in neg
        assert "bad anatomy" in neg

    def test_props_with_empty_tags_and_locks(self):
        """测试道具对象字段为空或仅有名字时的安全格式化."""
        props = [PropAsset(name="古卷", visual_tags="", feature_lock="", negative_prompt="")]
        vp = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.CLOSE_UP,
            speaker="陆沉",
            props=props,
            prop_refs=["古卷"]
        )
        assert "holding and showcasing 古卷" in vp
        assert "holding and showcasing 古卷:" not in vp


class TestPostProcessProjectQualityGateRobustness:
    """4. 导演后处理质检门 _post_process_project 极端防御测试"""

    def test_post_process_sanitizes_bracketed_narrators(self):
        """测试若大模型或上游传入带有括号的旁白与脏演员词，质检门强制净化."""
        d = DirectorAgent()
        proj = DramaProject(
            title="防御测试",
            genre="古风权谋",
            characters=[
                CharacterAsset(name="顾清雪", gender="female", turnaround_prompt="")
            ],
            shots=[
                Shot(
                    shot_id=1,
                    shot_scale=ShotScaleEnum.WIDE_SHOT,
                    camera_motion=CameraMotionEnum.STATIC,
                    speaker="【旁白】",
                    dialogue="",
                    action_beat="风雪漫天",
                    visual_prompt="photorealistic Chinese actor playing 【旁白】, 8k cinema",
                    negative_prompt="",
                ),
                Shot(
                    shot_id=2,
                    shot_scale=ShotScaleEnum.MEDIUM_SHOT,
                    camera_motion=CameraMotionEnum.ZOOM_IN,
                    speaker="空镜头",
                    dialogue="",
                    action_beat="空旷的大殿，烛火摇曳",
                    visual_prompt="photorealistic actor playing 空镜头, dramatic lighting",
                    negative_prompt="",
                ),
                Shot(
                    shot_id=3,
                    shot_scale=ShotScaleEnum.CLOSE_UP,
                    camera_motion=CameraMotionEnum.STATIC,
                    speaker="顾清雪",
                    dialogue="“我回来了。”",
                    action_beat="顾清雪眼神冰冷",
                    visual_prompt="",
                    negative_prompt="",
                )
            ]
        )

        cleaned = d._post_process_project(proj, title=proj.title, genre=proj.genre)

        # 镜头 1 (【旁白】) 净化
        s1 = cleaned.shots[0]
        assert "no actors" in s1.visual_prompt
        assert "actor playing" not in s1.visual_prompt
        assert "bad anatomy" in s1.negative_prompt

        # 镜头 2 (空镜头) 净化
        s2 = cleaned.shots[1]
        assert "no actors" in s2.visual_prompt
        assert "actor playing" not in s2.visual_prompt
        assert "bad anatomy" in s2.negative_prompt

        # 镜头 3 (顾清雪) 自动补齐视觉提示词与角色一致性
        s3 = cleaned.shots[2]
        assert "playing 顾清雪" in s3.visual_prompt
        assert "no actors" not in s3.visual_prompt

        # 角色 turnaround_prompt 自动补齐
        assert cleaned.characters[0].turnaround_prompt != ""
        assert "character design sheet" in cleaned.characters[0].turnaround_prompt


class TestDurationEstimationBoundary:
    """5. 确定性时长测算边界测试"""

    def test_duration_boundaries(self):
        """测试 2.0s 下限、5.0s 上限与空台词 2.8s 默认值."""
        # 空台词
        assert _estimate_shot_duration("", has_dialogue=False) == 2.8
        assert _estimate_shot_duration("   ", has_dialogue=True) == 2.8

        # 极短台词 (1-2字) 触及 2.0s 保护下限
        assert _estimate_shot_duration("走！") == 2.0
        assert _estimate_shot_duration("快走！") >= 2.0

        # 超长台词 (50字以上) 触及 5.0s 保护上限
        long_line = "今天无论你们来多少人，动用多少手段，只要我顾清雪还站在这里一天，这顾氏集团的公章与大权，你们休想染指半分！"
        assert _estimate_shot_duration(long_line) == 5.0
