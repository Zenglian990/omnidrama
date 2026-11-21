"""OmniDrama 导演一致性引擎 (Director Consistency Engine R2) 独立对抗性验证测试套件.

Author: challenger_m3_2 (Empirical Challenger)
Target: Milestone 3 (Director Consistency Engine - R2)
"""
import pytest
from pydantic import ValidationError
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


class TestMultimodalReferenceConfigEmpirical:
    """1. 经验性压力验证 build_multimodal_reference_config"""

    def test_midjourney_syntax_and_default_parameters(self):
        """验证 Midjourney --cref <url> --cw <weight> --ar 9:16 --v 6.1 完整语法规范."""
        ref = ReferenceImageConfig(url="https://cdn.example.com/character_turnaround.png")
        char = CharacterAsset(
            name="冷傲天",
            consistency_card=CharacterConsistencyCard(reference_images=[ref])
        )
        config = build_multimodal_reference_config(character=char)
        mj = config["midjourney"]

        assert "cref_url" in mj
        assert mj["cref_url"] == "https://cdn.example.com/character_turnaround.png"
        assert mj["cref_weight"] == 100
        assert mj["aspect_ratio"] == "9:16"
        assert mj["version"] == "6.1"
        assert mj["prompt_suffix"] == "--cref https://cdn.example.com/character_turnaround.png --cw 100 --ar 9:16 --v 6.1"

    def test_midjourney_cw_boundary_0_and_100(self):
        """验证 Midjourney 权重边界值 0 与 100 的准确透传与生成."""
        # 边界 1: cw = 0 (仅锁脸，不锁服饰)
        ref_0 = ReferenceImageConfig(url="https://cdn.example.com/face_only.png", cref_weight=0)
        char_0 = CharacterAsset(name="李雪", consistency_card=CharacterConsistencyCard(reference_images=[ref_0]))
        cfg_0 = build_multimodal_reference_config(character=char_0)
        assert cfg_0["midjourney"]["cref_weight"] == 0
        assert "--cw 0" in cfg_0["midjourney"]["prompt_suffix"]

        # 边界 2: cw = 100 (全面锁定)
        ref_100 = ReferenceImageConfig(url="https://cdn.example.com/full_body.png", cref_weight=100)
        char_100 = CharacterAsset(name="李雪", consistency_card=CharacterConsistencyCard(reference_images=[ref_100]))
        cfg_100 = build_multimodal_reference_config(character=char_100)
        assert cfg_100["midjourney"]["cref_weight"] == 100
        assert "--cw 100" in cfg_100["midjourney"]["prompt_suffix"]

    def test_midjourney_cw_out_of_bounds_validation(self):
        """验证非法超出边界的 cref_weight 会被 schema 校验拦截，杜绝脏参数下发."""
        with pytest.raises(ValidationError):
            ReferenceImageConfig(url="https://cdn.example.com/test.png", cref_weight=-1)

        with pytest.raises(ValidationError):
            ReferenceImageConfig(url="https://cdn.example.com/test.png", cref_weight=101)

        with pytest.raises(ValidationError):
            ReferenceImageConfig(url="https://cdn.example.com/test.png", ip_adapter_weight=-0.1)

        with pytest.raises(ValidationError):
            ReferenceImageConfig(url="https://cdn.example.com/test.png", ip_adapter_weight=1.6)

    def test_comfyui_ip_adapter_model_and_image_inputs_structure(self):
        """验证 ComfyUI IP-Adapter 模型名称、image_inputs 结构体规范."""
        refs = [
            ReferenceImageConfig(url="https://cdn.example.com/face.png", role=ReferenceRoleEnum.FACE, weight=1.0),
            ReferenceImageConfig(url="https://cdn.example.com/costume.png", role=ReferenceRoleEnum.COSTUME, weight=0.7),
            ReferenceImageConfig(url="https://cdn.example.com/pose.png", role=ReferenceRoleEnum.POSE, weight=0.5),
        ]
        char = CharacterAsset(name="多图角色", consistency_card=CharacterConsistencyCard(reference_images=refs))
        cfg = build_multimodal_reference_config(character=char)
        ip = cfg["ip_adapter"]

        assert ip["enabled"] is True
        assert ip["model"] == "ip-adapter-plus_sdxl_vit-h.safetensors"
        assert ip["model_name"] == "ip-adapter-plus_sdxl_vit-h.safetensors"
        assert ip["image_path"] == "https://cdn.example.com/face.png"
        assert len(ip["image_inputs"]) == 3

        # 检查结构体的每个字段
        assert ip["image_inputs"][0] == {"role": "face", "path": "https://cdn.example.com/face.png", "weight": 1.0}
        assert ip["image_inputs"][1] == {"role": "costume", "path": "https://cdn.example.com/costume.png", "weight": 0.7}
        assert ip["image_inputs"][2] == {"role": "pose", "path": "https://cdn.example.com/pose.png", "weight": 0.5}

    def test_volcano_seedance_2_reference_tags_and_indices(self):
        """验证火山引擎 Seedance 2.0 @角色参考图N 标签与 1-based 序号映射."""
        refs = [
            ReferenceImageConfig(url=f"https://cdn.example.com/ref_{i}.png", role=ReferenceRoleEnum.FACE)
            for i in range(1, 5)
        ]
        char = CharacterAsset(name="四图角色", consistency_card=CharacterConsistencyCard(reference_images=refs))
        cfg = build_multimodal_reference_config(character=char)
        sd = cfg["seedance"]

        assert sd["ref_indices"] == [1, 2, 3, 4]
        assert sd["ref_prompt_tag"] == "@角色参考图1"
        assert sd["ref_prompt_tags"] == ["@角色参考图1", "@角色参考图2", "@角色参考图3", "@角色参考图4"]
        assert sd["image_url"] == "https://cdn.example.com/ref_1.png"
        assert sd["image_urls"] == [f"https://cdn.example.com/ref_{i}.png" for i in range(1, 5)]

    def test_multimodal_priority_resolution(self):
        """验证多模态底图解析优先级：显式入参 turnaround_image_url > 角色 turnaround_image > 一致性卡 reference_images."""
        char = CharacterAsset(
            name="优先测试",
            turnaround_image="https://cdn.example.com/char_turnaround.png",
            consistency_card=CharacterConsistencyCard(
                reference_images=[ReferenceImageConfig(url="https://cdn.example.com/card_ref.png")]
            )
        )
        # 1. 显式传入 turnaround_image_url
        cfg1 = build_multimodal_reference_config(character=char, turnaround_image_url="https://cdn.example.com/explicit.png")
        assert cfg1["midjourney"]["cref_url"] == "https://cdn.example.com/explicit.png"
        assert cfg1["seedance"]["image_urls"][0] == "https://cdn.example.com/explicit.png"
        assert cfg1["seedance"]["image_urls"][1] == "https://cdn.example.com/char_turnaround.png"
        assert cfg1["seedance"]["image_urls"][2] == "https://cdn.example.com/card_ref.png"

        # 2. 未显式传入，但有 character.turnaround_image
        cfg2 = build_multimodal_reference_config(character=char)
        assert cfg2["midjourney"]["cref_url"] == "https://cdn.example.com/char_turnaround.png"

    def test_multimodal_reference_empty_graceful_fallback(self):
        """验证无参考底图时的安全兜底，返回空字典且不报错."""
        assert build_multimodal_reference_config(None) == {"midjourney": {}, "ip_adapter": {}, "seedance": {}}
        char_empty = CharacterAsset(name="无图角色")
        assert build_multimodal_reference_config(char_empty) == {"midjourney": {}, "ip_adapter": {}, "seedance": {}}


class TestPropInteractionEmpirical:
    """2. 经验性压力验证道具交互与防崩负向词拼装"""

    @pytest.fixture
    def sample_props(self) -> List[PropAsset]:
        return [
            PropAsset(
                name="玄龙令",
                category="token",
                visual_tags="纯黑玄铁铸造，雕刻五爪金龙盘踞",
                feature_lock="表面泛着深邃暗金流光符文，边缘刻有古老篆字",
                negative_prompt="modern plastic, cheap metal, glossy plastic card"
            ),
            PropAsset(
                name="斩龙剑",
                category="weapon",
                visual_tags="八面汉剑古朴厚重，剑鞘饰以玄武岩纹理",
                feature_lock="剑身贯穿三道血色导血槽，出鞘时泛起极寒青霜白气",
                negative_prompt="toy sword, blunt blade, neon lights"
            )
        ]

    def test_prop_refs_visual_and_negative_prompt_incorporation(self, sample_props):
        """验证分镜在 prop_refs 中关联道具时，其特征锁、外貌描述与专属负向词均准确注入."""
        char = CharacterAsset(name="陆沉", gender="male")
        vp = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            speaker="陆沉",
            action_beat="右手猛然拔剑出鞘，左手高举令牌",
            character=char,
            props=sample_props,
            prop_refs=["玄龙令", "斩龙剑"]
        )

        # 验证两件道具的外貌与特征锁均进入提示词
        assert "holding and showcasing 玄龙令: 纯黑玄铁铸造，雕刻五爪金龙盘踞, 表面泛着深邃暗金流光符文，边缘刻有古老篆字" in vp
        assert "holding and showcasing 斩龙剑: 八面汉剑古朴厚重，剑鞘饰以玄武岩纹理, 剑身贯穿三道血色导血槽，出鞘时泛起极寒青霜白气" in vp

        np = compile_shot_negative_prompt(
            character=char,
            props=sample_props,
            prop_refs=["玄龙令", "斩龙剑"]
        )
        assert "modern plastic, cheap metal, glossy plastic card" in np
        assert "toy sword, blunt blade, neon lights" in np

    def test_unreferenced_props_strictly_isolated(self, sample_props):
        """验证未在 prop_refs 中引用的道具绝对不会污染当前镜头的生图与负向词."""
        char = CharacterAsset(name="陆沉", gender="male")
        vp = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.CLOSE_UP,
            speaker="陆沉",
            action_beat="凝视令牌",
            character=char,
            props=sample_props,
            prop_refs=["玄龙令"]  # 仅引用玄龙令
        )
        assert "玄龙令" in vp
        assert "斩龙剑" not in vp

        np = compile_shot_negative_prompt(
            character=char,
            props=sample_props,
            prop_refs=["玄龙令"]
        )
        assert "modern plastic, cheap metal" in np
        assert "toy sword" not in np

    def test_non_existent_prop_graceful_fallback(self, sample_props):
        """验证当 prop_refs 引用了不存在的道具名时，代码优雅降级不抛异常，且负向词安全运行."""
        char = CharacterAsset(name="陆沉", gender="male")
        # 引用了不存在的道具 "昆仑神玉"
        vp = compile_shot_visual_prompt(
            shot_scale=ShotScaleEnum.MEDIUM_SHOT,
            speaker="陆沉",
            action_beat="佩戴玉佩",
            character=char,
            props=sample_props,
            prop_refs=["昆仑神玉", "玄龙令"]
        )
        # 存在的道具有详细特征，不存在的道具有兜底声明，系统稳定不崩溃
        assert "holding and showcasing 玄龙令: 纯黑玄铁铸造" in vp
        assert "holding and showcasing 昆仑神玉" in vp

        np = compile_shot_negative_prompt(
            character=char,
            props=sample_props,
            prop_refs=["昆仑神玉"]
        )
        # 不存在的道具不产生负向词污染，通用负向词正常输出
        assert "bad anatomy" in np
        assert "plastic skin" in np

    def test_props_none_or_empty_safe_execution(self):
        """验证 props 为 None、[]，prop_refs 为 None、[] 的各种边界组合均不崩溃."""
        char = CharacterAsset(name="路人", gender="male")
        # 1. props=None, prop_refs=None
        vp1 = compile_shot_visual_prompt(speaker="路人", character=char, props=None, prop_refs=None)
        np1 = compile_shot_negative_prompt(character=char, props=None, prop_refs=None)
        assert ("photorealistic Chinese male actor playing 路人" in vp1 or "photorealistic Chinese actor playing 路人" in vp1)
        assert "bad anatomy" in np1

        # 2. props=None, prop_refs=["神秘符文"]
        vp2 = compile_shot_visual_prompt(speaker="路人", character=char, props=None, prop_refs=["神秘符文"])
        np2 = compile_shot_negative_prompt(character=char, props=None, prop_refs=["神秘符文"])
        assert "holding and showcasing 神秘符文" in vp2
        assert "bad anatomy" in np2

        # 3. character=None (无角色对象)
        vp3 = compile_shot_visual_prompt(speaker="路人", character=None, props=None, prop_refs=None)
        assert "photorealistic Chinese actor playing 路人" in vp3


class TestBreakdownStoryOfflineAndPostProcessMultiScene:
    """3. 经验性压力验证复杂多幕多角色短剧拆解与后处理流水线"""

    def test_post_process_project_prop_binding_and_sanitization(self):
        """验证 _post_process_project 为项目绑定道具、补全分镜道具交互并消除脏数据."""
        director = DirectorAgent()

        # 构造预置项目，包含角色、道具与分镜
        proj = DramaProject(
            title="绝世龙王之战神归来",
            genre="都市热血",
            characters=[
                CharacterAsset(
                    name="顾清雪",
                    gender="female",
                    consistency_card=CharacterConsistencyCard(
                        facial_lock="清冷素雅鹅蛋脸，星眸微寒",
                        costume_lock="纯黑素缟丧服"
                    ),
                    turnaround_prompt=""  # 留空待后处理补齐
                ),
                CharacterAsset(
                    name="陆沉",
                    gender="male",
                    consistency_card=CharacterConsistencyCard(
                        facial_lock="刀削斧凿坚毅面容，双目如鹰",
                        costume_lock="墨黑龙纹风衣"
                    ),
                    turnaround_prompt=""  # 留空待后处理补齐
                )
            ],
            props=[
                PropAsset(
                    name="玄龙令",
                    category="token",
                    visual_tags="纯黑玄铁铸造，雕刻五爪金龙盘踞",
                    feature_lock="表面泛着深邃暗金流光符文",
                    negative_prompt="modern plastic card"
                ),
                PropAsset(
                    name="斩龙剑",
                    category="ancient_sword",
                    visual_tags="八面汉剑古朴厚重",
                    feature_lock="剑身贯穿三道血色导血槽",
                    negative_prompt="toy sword"
                )
            ],
            shots=[
                Shot(
                    shot_id=1,
                    speaker="顾清雪",
                    dialogue="想要顾家基业？踩着我的尸体过去！",
                    action_beat="抽出短刃",
                    prop_refs=["玄龙令"],
                    visual_prompt="",
                    negative_prompt=""
                ),
                Shot(
                    shot_id=2,
                    speaker="陆沉",
                    dialogue="动她一下试试！",
                    action_beat="拔剑出鞘",
                    prop_refs=["斩龙剑"],
                    visual_prompt="",
                    negative_prompt=""
                ),
                Shot(
                    shot_id=3,
                    speaker="旁白",
                    dialogue="",
                    action_beat="夜雨雷暴",
                    visual_prompt="8k movie, actor playing 旁白, nice lighting"  # 模拟错误生成的脏提示词
                )
            ]
        )

        # 执行后处理质检门
        processed = director._post_process_project(proj, proj.title, proj.genre)

        # 1. 验证角色三视图均已自动补齐
        assert processed.characters[0].turnaround_prompt != ""
        assert "character design sheet" in processed.characters[0].turnaround_prompt
        assert "--ar 16:9" in processed.characters[0].turnaround_prompt
        assert processed.characters[1].turnaround_prompt != ""

        # 2. 验证道具三视图均已自动补齐
        assert processed.props[0].turnaround_prompt != ""
        assert "prop design turnaround sheet, 3 views" in processed.props[0].turnaround_prompt
        assert "--ar 16:9" in processed.props[0].turnaround_prompt
        assert processed.props[1].turnaround_prompt != ""
        assert "prop design turnaround sheet, 3 views" in processed.props[1].turnaround_prompt

        # 3. 验证顾清雪镜头重新编译并注入了玄龙令特征与专属负向词
        s1 = processed.shots[0]
        assert "holding and showcasing 玄龙令: 纯黑玄铁铸造，雕刻五爪金龙盘踞, 表面泛着深邃暗金流光符文" in s1.visual_prompt
        assert "modern plastic card" in s1.negative_prompt
        assert "bad anatomy" in s1.negative_prompt

        # 4. 验证陆沉镜头重新编译并注入了斩龙剑特征与专属负向词
        s2 = processed.shots[1]
        assert "holding and showcasing 斩龙剑: 八面汉剑古朴厚重, 剑身贯穿三道血色导血槽" in s2.visual_prompt
        assert "toy sword" in s2.negative_prompt

        # 5. 验证篡改的旁白镜头被质检门净化，根绝替身演员
        s3 = processed.shots[2]
        assert "actor playing 旁白" not in s3.visual_prompt
        assert "no actors" in s3.visual_prompt
        assert "atmospheric 都市热血 cinematic scene" in s3.visual_prompt

    def test_offline_breakdown_empirical_discovery_character_extraction_limits(self):
        """经验性验证：breakdown_story_offline 中说话人提取正则对 '角色名：“台词”' 格式与复合动词的精确解析."""
        director = DirectorAgent()

        # 场景 A: 经典剧本冒号台词格式 "顾清雪：“...”"
        script_colon = """
        顾清雪：“想要公章？踩着我的尸体过去！”
        林管家冷笑道：“大小姐，识相的就交出来。”
        """
        proj = director.breakdown_story_offline(script_colon, title="测试", genre="现代都市")

        # 验证修复后：标准冒号剧本格式正确提取角色名为 "顾清雪"
        shot1 = proj.shots[0]
        assert shot1.speaker == "顾清雪"

        # 场景 B: 包含谓语动词前缀 "林管家冷笑道：“...”" 正确提取为 "林管家"，不再被贪婪截断为 "林管家冷"
        char_names = [c.name for c in proj.characters]
        assert "林管家" in char_names
        assert "林管家冷" not in char_names


class TestAdversarialTurnaroundAndNegativeEdgeCases:
    """4. 角色三视图与负向词对抗性极端用例测试"""

    def test_character_turnaround_without_consistency_card_or_anchor(self):
        """测试完全空白特征的角色生成三视图提示词时的安全兜底."""
        minimal_char = CharacterAsset(name="无名氏", gender="male")
        prompt = build_character_turnaround_prompt(minimal_char)
        assert "character design sheet" in prompt
        assert "photorealistic Chinese male actor" in prompt
        assert "--ar 16:9" in prompt

    def test_prop_turnaround_with_minimal_fields(self):
        """测试极简道具（无 visual_tags, feature_lock）生成三视图提示词."""
        prop = PropAsset(name="铜镜")
        prompt = build_prop_turnaround_prompt(prop)
        assert "prop design turnaround sheet" in prompt
        assert "photorealistic prop" in prompt
        assert "--ar 16:9" in prompt

    def test_compile_shot_visual_prompt_narrator_variants(self):
        """测试各种旁白、环境别名（中文与英文大小写）均触发环境空镜分支."""
        variants = ["旁白", "Scene", "环境", "背景", "空镜", "narrator", "scene", "environment", "NARRATOR"]
        for v in variants:
            vp = compile_shot_visual_prompt(speaker=v, action_beat="山崩地裂")
            assert "no actors" in vp, f"Failed for variant {v}: {vp}"
            assert "actor playing" not in vp, f"Failed for variant {v}: {vp}"

    def test_compile_shot_negative_prompt_with_multiple_extras(self):
        """测试多层叠加负向词（通用防崩 + 角色专属 + 道具专属 + 额外自定义）无截断与排异."""
        char = CharacterAsset(
            name="天师",
            consistency_card=CharacterConsistencyCard(exclusive_negative_prompt="modern suit, short hair")
        )
        prop = PropAsset(name="拂尘", negative_prompt="nylon bristles")
        neg = compile_shot_negative_prompt(
            character=char,
            extra_negative="blurry hands, duplicate objects",
            props=[prop],
            prop_refs=["拂尘"]
        )

        assert "bad anatomy" in neg
        assert "modern suit, short hair" in neg
        assert "nylon bristles" in neg
        assert "blurry hands, duplicate objects" in neg
