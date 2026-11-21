"""OmniDrama 导演一致性引擎 (Director Consistency Engine R2) 单元测试套件."""
import pytest
from typing import Dict, Any

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


class TestCompileShotVisualPrompt:
    """测试分镜画面视觉提示词编译流水线."""

    def test_compile_shot_visual_prompt_with_character_locks(self):
        """测试角色一致性控制卡（骨相五官锁、发型发色锁、服饰装束锁）强锁定编译."""
        char = CharacterAsset(
            name="林萧",
            gender="male",
            visual_tags="photorealistic Chinese actor, 27 years old",
            consistency_card=CharacterConsistencyCard(
                facial_lock="棱角分明冷峻骨相，高挺鼻梁，锐利深邃单眼皮",
                hair_lock="墨黑清爽微卷碎发，微乱发丝",
                costume_lock="深灰修身定制西装，内搭纯黑丝质衬衫",
                exclusive_negative_prompt="圆脸, 双眼皮, 运动服",
            )
        )

        prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.CLOSE_UP,
            speaker="林萧",
            action_beat="眼神冰冷凝视前方对手，唇角泛起讥讽冷笑",
            blocking="居于画面中央三分线，微侧身45度",
            genre="都市商战",
            character=char,
        )

        # 验证包含 ARRI 电影机画质与前缀
        assert "ARRI Alexa 65" in prompt
        assert "Panavision" in prompt
        assert "photorealistic Chinese male actor playing 林萧" in prompt

        # 验证包含三大物理特征锁
        assert "facial features: 棱角分明冷峻骨相，高挺鼻梁，锐利深邃单眼皮" in prompt
        assert "hairstyle: 墨黑清爽微卷碎发，微乱发丝" in prompt
        assert "costume: 深灰修身定制西装，内搭纯黑丝质衬衫" in prompt

        # 验证景别与光学焦距
        assert "close-up portrait shot" in prompt
        assert "50mm prime lens" in prompt

        # 验证动作节拍与构图走位
        assert "眼神冰冷凝视前方对手" in prompt
        assert "居于画面中央三分线" in prompt

        # 验证电影灯光与 9:16 画幅
        assert "dramatic cinema lighting" in prompt
        assert "vertical 9:16" in prompt
        assert "no cartoon" in prompt
        assert "no anime" in prompt

    def test_compile_shot_visual_prompt_scales(self):
        """测试不同镜头景别与对应的光学焦距/景深生成."""
        scales_and_keywords = [
            (ShotScaleEnum.EXTREME_CLOSE_UP, "extreme close-up shot, 85mm portrait lens"),
            (ShotScaleEnum.CLOSE_UP, "close-up portrait shot, 50mm prime lens"),
            (ShotScaleEnum.MEDIUM_SHOT, "medium shot, 35mm lens"),
            (ShotScaleEnum.FULL_SHOT, "full shot, 28mm wide lens"),
            (ShotScaleEnum.WIDE_SHOT, "wide shot, 24mm ultra-wide lens"),
        ]

        for scale, expected_keyword in scales_and_keywords:
            p = compile_shot_visual_prompt(
                shot_scale=scale,
                speaker="角色",
                action_beat="动作",
            )
            assert expected_keyword in p, f"Failed for scale {scale}: {p}"

    def test_compile_shot_visual_prompt_prop_interaction(self):
        """测试道具关联 (matched from prop_refs) 与特征锁交互整合."""
        char = CharacterAsset(name="陆沉", gender="male")
        props = [
            PropAsset(
                name="玄龙令",
                category="magical_item",
                visual_tags="纯黑玄铁铸造，雕刻张牙舞爪的五爪黑龙",
                feature_lock="表面泛着冰蓝色流光幽芒，边缘镶嵌冷银碎晶",
            ),
            PropAsset(
                name="防弹公文包",
                category="accessory",
                visual_tags="哑光黑碳纤维材质",
                feature_lock="隐蔽钛合金卡扣",
            )
        ]

        prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            speaker="陆沉",
            action_beat="高高举起令牌示众",
            character=char,
            props=props,
            prop_refs=["玄龙令"]
        )

        assert "holding and showcasing 玄龙令" in prompt
        assert "纯黑玄铁铸造" in prompt
        assert "表面泛着冰蓝色流光幽芒" in prompt
        # 未引用的道具不应出现在此镜头提示词中
        assert "防弹公文包" not in prompt

    def test_compile_shot_visual_prompt_narrator_and_environment(self):
        """测试旁白与空镜特殊处理（杜绝生成替身演员或人偶）."""
        for narrator_speaker in ["旁白", "Scene", "环境", "背景", "空镜", "narrator"]:
            prompt = compile_shot_visual_prompt(
                shot_scale=ShotScaleEnum.WIDE_SHOT,
                speaker=narrator_speaker,
                action_beat="雷暴雨夜，苏家老宅在闪电映照下显得格外森严",
                blocking="镜头自远方山顶俯瞰整座庄园全景",
                genre="都市修罗",
            )

            # 严防生成替身演员
            assert "actor playing" not in prompt
            assert "photorealistic Chinese actor" not in prompt
            assert "no actors" in prompt
            assert "no cartoon" in prompt
            assert "no anime" in prompt
            assert "atmospheric 都市修罗 cinematic scene" in prompt
            assert "vertical 9:16" in prompt

    def test_compile_shot_visual_prompt_fallback_without_consistency_card(self):
        """测试角色无 consistency_card 时回退至 visual_anchor 或 visual_tags."""
        char_anchor = CharacterAsset(
            name="楚晚宁",
            gender="female",
            visual_anchor="清冷出尘，柳叶双眸，素白长裙外罩淡青薄纱",
            visual_tags="photorealistic Chinese actress, 8k"
        )
        prompt = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            speaker="楚晚宁",
            action_beat="素手抚琴",
            character=char_anchor
        )

        assert "清冷出尘，柳叶双眸" in prompt
        assert "素白长裙外罩淡青薄纱" in prompt
        assert "photorealistic Chinese actress" in prompt


class TestCompileShotNegativePrompt:
    """测试防崩排异负向提示词编译流水线."""

    def test_compile_shot_negative_prompt_universal_and_exclusive(self):
        """测试通用电影防崩词与角色专属负向词融合."""
        char = CharacterAsset(
            name="顾寒",
            consistency_card=CharacterConsistencyCard(
                exclusive_negative_prompt="blond hair, blue eyes, modern suit, smiling, round face"
            )
        )

        neg = compile_shot_negative_prompt(character=char)

        # 通用防崩词存在
        assert "bad anatomy" in neg
        assert "deformed face" in neg
        assert "plastic skin" in neg
        assert "cartoon, anime, 3d, cgi" in neg

        # 角色专属负向词存在
        assert "blond hair, blue eyes, modern suit, smiling, round face" in neg

    def test_compile_shot_negative_prompt_with_props_and_extras(self):
        """测试道具专属负向词与额外负向词注入."""
        prop = PropAsset(
            name="九龙神鼎",
            negative_prompt="modern plastic, rusty iron, neon light"
        )

        neg = compile_shot_negative_prompt(
            character=None,
            extra_negative="extra blur, watermark",
            props=[prop],
            prop_refs=["九龙神鼎"]
        )

        assert "bad anatomy" in neg
        assert "modern plastic, rusty iron, neon light" in neg
        assert "extra blur, watermark" in neg


class TestTurnaroundPrompts:
    """测试人物与道具 16:9 标准三视图提示词生成."""

    def test_build_character_turnaround_prompt_complete(self):
        """测试 16:9 角色正/侧90°/背180°+纯白背景+胸像特写三视图定妆提示词."""
        char = CharacterAsset(
            name="苏清雪",
            gender="female",
            consistency_card=CharacterConsistencyCard(
                facial_lock="精致鹅蛋脸，柳叶眉，桃花眼含情，微翘鼻尖",
                hair_lock="柔顺墨黑及腰长直发，两缕龙须刘海",
                costume_lock="淡蓝织金流仙裙，腰系白玉环佩",
            )
        )

        prompt = build_character_turnaround_prompt(char)

        # 验证三视图角度
        assert "3 views from multiple angles" in prompt
        assert "front view" in prompt
        assert "side 90° profile view" in prompt
        assert "back 180° view" in prompt

        # 验证背景与构图
        assert "clean solid pure white cyclorama studio background" in prompt
        assert "bust portrait close-up inset" in prompt
        assert "standing pose, neutral expression, A-pose" in prompt

        # 验证特征锁注入
        assert "精致鹅蛋脸" in prompt
        assert "柔顺墨黑及腰长直发" in prompt
        assert "淡蓝织金流仙裙" in prompt

        # 验证 16:9 画幅与负向剔除
        assert "--ar 16:9" in prompt
        assert "--no shadows on background, text, watermark, bad anatomy, deformed eyes" in prompt

    def test_build_character_turnaround_prompt_fallback_anchor(self):
        """测试无 consistency_card 角色根据 visual_anchor 生成三视图提示词."""
        char = CharacterAsset(
            name="叶天帝",
            gender="male",
            visual_anchor="重瞳剑眉，黑色短发，身着玄黑战甲配金色龙纹",
            visual_tags="handsome Chinese actor, 8k"
        )
        prompt = build_character_turnaround_prompt(char)

        assert "3 views from multiple angles" in prompt
        assert "front view" in prompt
        assert "side 90° profile view" in prompt
        assert "back 180° view" in prompt
        assert "重瞳剑眉，黑色短发，身着玄黑战甲配金色龙纹" in prompt
        assert "--ar 16:9" in prompt

    def test_build_prop_turnaround_prompt_complete(self):
        """测试 16:9 道具正视/侧视/45度等轴透视三视图提示词."""
        prop = PropAsset(
            name="斩龙剑",
            category="ancient_sword",
            visual_tags="八面汉剑形制，剑身通体乌黑，剑柄缠绕玄色丝绦",
            feature_lock="剑脊开有三道血槽，隐隐泛着赤红血芒与符文铭刻",
        )

        prompt = build_prop_turnaround_prompt(prop)

        # 验证三视图视角
        assert "orthographic front view" in prompt
        assert "side profile view" in prompt
        assert "45-degree isometric perspective view" in prompt

        # 验证纯白背景与工业产品级光影
        assert "isolated on solid pure white background" in prompt
        assert "softbox product studio lighting" in prompt
        assert "octane render quality" in prompt

        # 验证特征与 16:9 画幅
        assert "ancient_sword" in prompt
        assert "八面汉剑形制" in prompt
        assert "隐隐泛着赤红血芒与符文铭刻" in prompt
        assert "--ar 16:9" in prompt


class TestBuildMultimodalReferenceConfig:
    """测试多模态参考底图管道 (Midjourney, IP-Adapter, Seedance 2.0)."""

    def test_multimodal_reference_with_turnaround_image_url(self):
        """测试显式传入 turnaround_image_url 时的多模态参数生成."""
        config = build_multimodal_reference_config(
            character=None,
            turnaround_image_url="https://cdn.omnidrama.com/assets/turnaround_female_04.png"
        )

        # Midjourney
        mj = config["midjourney"]
        assert "--cref https://cdn.omnidrama.com/assets/turnaround_female_04.png" in mj["prompt_suffix"]
        assert "--cw 100" in mj["prompt_suffix"]
        assert "--ar 9:16" in mj["prompt_suffix"]
        assert mj["cref_url"] == "https://cdn.omnidrama.com/assets/turnaround_female_04.png"
        assert mj["cref_weight"] == 100

        # IP-Adapter
        ip = config["ip_adapter"]
        assert ip["enabled"] is True
        assert ip["image_path"] == "https://cdn.omnidrama.com/assets/turnaround_female_04.png"
        assert ip["weight"] == 0.8
        assert ip["model_name"] == "ip-adapter-plus_sdxl_vit-h.safetensors"
        assert ip["model"] == "ip-adapter-plus_sdxl_vit-h.safetensors"
        assert len(ip["image_inputs"]) >= 1

        # Seedance 2.0
        sd = config["seedance"]
        assert sd["ref_prompt_tag"] == "@角色参考图1"
        assert sd["ref_indices"] == [1]
        assert sd["image_url"] == "https://cdn.omnidrama.com/assets/turnaround_female_04.png"

    def test_multimodal_reference_with_character_consistency_card(self):
        """测试从角色一致性卡中提取多张参考图的权重配置."""
        char = CharacterAsset(
            name="楚天行",
            consistency_card=CharacterConsistencyCard(
                reference_images=[
                    ReferenceImageConfig(
                        url="https://ref.com/chutianxing_face.png",
                        role=ReferenceRoleEnum.FACE,
                        cref_weight=85,
                        ip_adapter_weight=0.9,
                        weight=1.0
                    ),
                    ReferenceImageConfig(
                        url="https://ref.com/chutianxing_costume.png",
                        role=ReferenceRoleEnum.COSTUME,
                        weight=0.75
                    )
                ]
            )
        )

        config = build_multimodal_reference_config(character=char)

        # Midjourney
        assert config["midjourney"]["cref_url"] == "https://ref.com/chutianxing_face.png"
        assert config["midjourney"]["cref_weight"] == 85
        assert "--cw 85" in config["midjourney"]["prompt_suffix"]

        # IP-Adapter
        assert config["ip_adapter"]["weight"] == 0.9
        assert len(config["ip_adapter"]["image_inputs"]) == 2
        assert config["ip_adapter"]["image_inputs"][0]["role"] == "face"
        assert config["ip_adapter"]["image_inputs"][1]["role"] == "costume"

        # Seedance
        assert config["seedance"]["ref_indices"] == [1, 2]
        assert config["seedance"]["ref_prompt_tag"] == "@角色参考图1"
        assert len(config["seedance"]["image_urls"]) == 2

    def test_multimodal_reference_empty_fallback(self):
        """测试无参考图时的空字典安全回退."""
        char_empty = CharacterAsset(name="路人甲")
        config = build_multimodal_reference_config(character=char_empty)

        assert config["midjourney"] == {}
        assert config["ip_adapter"] == {}
        assert config["seedance"] == {}


class TestDirectorStoryBreakdownOfflineConsistency:
    """测试完整离线导演分镜拆解中一致性引擎的端到端集成."""

    def test_offline_breakdown_consistency_pipeline(self):
        """测试 DirectorAgent().breakdown_story_offline 完整分镜拆解中的一致性锁与多模态参数."""
        director = DirectorAgent()
        sample_text = """
        【第1幕：豪门绝境】
        滂沱大雨冲刷着顾家老宅的青石阶，雷声轰鸣。
        顾清雪跪在灵堂前，双拳攥紧，指甲深深嵌进掌心。
        顾清雪：“父亲，女儿发誓，今日他们夺走的一切，我定当百倍讨回！”
        门外，林管家冷笑道：“大小姐，老爷已经去了，交出顾氏公章，你还能留一条生路。”
        顾清雪猛然抬头，桃花眼中冷意森然：“想要公章？除非踩着我的尸体过去！”
        """

        project = director.breakdown_story_offline(
            sample_text,
            title="真千金重生复仇记",
            genre="现代都市"
        )

        assert isinstance(project, DramaProject)
        assert project.title == "真千金重生复仇记"
        assert len(project.characters) >= 2
        assert len(project.shots) >= 4

        # 1. 验证所有角色（除旁白外）均填充了三视图定妆提示词与一致性卡
        char_names = [c.name for c in project.characters if c.name != "旁白"]
        assert "顾清雪" in char_names
        assert "林管家" in char_names
        for char in project.characters:
            if char.name != "旁白":
                assert char.turnaround_prompt, f"Character {char.name} missing turnaround_prompt"
                assert "character design sheet" in char.turnaround_prompt
                assert "--ar 16:9" in char.turnaround_prompt
                assert char.consistency_card is not None

        # 2. 验证非旁白对话镜头存在且含有角色表演
        char_shots = [s for s in project.shots if s.speaker not in ["旁白", "Scene", "环境", "背景", "空镜", "空镜头"]]
        assert len(char_shots) >= 3, f"Expected at least 3 character dialogue shots, got {len(char_shots)}"
        assert any(s.speaker == "顾清雪" for s in char_shots)
        assert any(s.speaker == "林管家" for s in char_shots)
        for cs in char_shots:
            assert f"playing {cs.speaker}" in cs.visual_prompt

        # 3. 验证所有分镜的 visual_prompt、negative_prompt 与时长完整合规
        for shot in project.shots:
            # 视觉提示词包含 ARRI 电影机画质与 9:16 画幅
            assert "ARRI Alexa 65" in shot.visual_prompt
            assert "vertical 9:16" in shot.visual_prompt

            # 防崩负向词不为空且包含通用电影防崩词
            assert shot.negative_prompt, f"Shot {shot.shot_id} missing negative_prompt"
            assert "bad anatomy" in shot.negative_prompt
            assert "deformed face" in shot.negative_prompt

            # 若为旁白镜头，严禁出现替身演员
            if shot.speaker in ["旁白", "Scene", "环境", "背景", "空镜", "空镜头"]:
                assert "actor playing" not in shot.visual_prompt
                assert "no actors" in shot.visual_prompt

            # 若为说话角色镜头，必须含有角色表演
            elif shot.speaker in ["顾清雪", "林管家"]:
                assert f"playing {shot.speaker}" in shot.visual_prompt

            # 镜头属性合规
            assert isinstance(shot.shot_scale, ShotScaleEnum)
            assert isinstance(shot.camera_motion, CameraMotionEnum)
            assert shot.duration_seconds is not None and shot.duration_seconds >= 2.0

    def test_post_process_project_consistency_and_props(self):
        """测试 _post_process_project 对缺失一致性提示词和道具三视图的自动补齐."""
        director = DirectorAgent()

        proj = DramaProject(
            title="修仙剑神传",
            genre="仙侠玄幻",
            characters=[
                CharacterAsset(
                    name="白子画",
                    gender="male",
                    visual_anchor="白衣胜雪，长发飘逸，剑眉星目",
                    turnaround_prompt="",  # 故意留空
                )
            ],
            props=[
                PropAsset(
                    name="断念剑",
                    category="ancient_sword",
                    visual_tags="青霜玄冰古剑",
                    feature_lock="剑身寒光逼人",
                    turnaround_prompt="",  # 故意留空
                )
            ],
            shots=[
                Shot(
                    shot_id=1,
                    speaker="白子画",
                    dialogue="此剑出鞘，不染凡尘。",
                    action_beat="拔剑出鞘",
                    visual_prompt="",  # 故意留空
                    negative_prompt="",  # 故意留空
                    prop_refs=["断念剑"]
                )
            ]
        )

        processed = director._post_process_project(proj, proj.title, proj.genre)

        # 角色三视图自动补齐
        assert processed.characters[0].turnaround_prompt != ""
        assert "character design sheet" in processed.characters[0].turnaround_prompt

        # 道具三视图自动补齐
        assert processed.props[0].turnaround_prompt != ""
        assert "prop design turnaround sheet" in processed.props[0].turnaround_prompt
        assert "orthographic front view" in processed.props[0].turnaround_prompt

        # 分镜视觉提示词与负向词自动编译
        s1 = processed.shots[0]
        assert "ARRI Alexa 65" in s1.visual_prompt
        assert "holding and showcasing 断念剑" in s1.visual_prompt
        assert "bad anatomy" in s1.negative_prompt
