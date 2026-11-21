"""OmniDrama Milestone 1 核心数据契约实证挑战与压力验证套件 (Empirical Challenge & Stress Test Suite).

覆盖目标：
1. Midjourney --cref / --cw 提取与边界校验
2. ComfyUI IP-Adapter 参数边界与多模态映射
3. 1,000 个合成镜头的全链路模型序列化与反序列化性能基准与保真度
4. 反序列化模型在 omnidrama/core/director.py 与 omnidrama/web/app.py 中的直接消费契约
5. 极端边界值与容错排异测试 (Adversarial stress scenarios)
"""
import json
import time
import re
from pathlib import Path
from typing import Dict, Any, List

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


# =====================================================================
# 1. Midjourney --cref / --cw 参数提取与校验实证
# =====================================================================

class TestMidjourneyCrefCwValidation:
    """实证检验 Midjourney --cref 与 --cw 的边界控制与提取保真度."""

    def test_cref_weight_bounds_strict(self):
        """检验 --cw 参数边界：0 到 100 严格区间."""
        # 边界下限 0: 仅锁脸
        ref_zero = ReferenceImageConfig(url="https://mj.example/face.png", cref_weight=0)
        assert ref_zero.cref_weight == 0

        # 边界上限 100: 锁脸+发型+服装
        ref_hundred = ReferenceImageConfig(url="https://mj.example/face.png", cref_weight=100)
        assert ref_hundred.cref_weight == 100

        # 中间值 50
        ref_mid = ReferenceImageConfig(url="https://mj.example/face.png", cref_weight=50)
        assert ref_mid.cref_weight == 50

        # 越界值 < 0 必须抛出 ValidationError
        with pytest.raises(ValidationError) as exc_info:
            ReferenceImageConfig(url="https://mj.example/face.png", cref_weight=-1)
        assert "greater_than_equal" in str(exc_info.value) or "-1" in str(exc_info.value)

        # 越界值 > 100 必须抛出 ValidationError
        with pytest.raises(ValidationError) as exc_info:
            ReferenceImageConfig(url="https://mj.example/face.png", cref_weight=101)
        assert "less_than_equal" in str(exc_info.value) or "101" in str(exc_info.value)

    def test_cref_url_alias_and_extraction(self):
        """检验 cref_url 别名自动映射与 role 默认分配."""
        config_dict = {
            "cref_url": "https://cdn.midjourney.com/ref-uuid/0_0.png",
            "cref_weight": 85,
            "description": "女主都市职场妆造底图"
        }
        ref = ReferenceImageConfig.model_validate(config_dict)
        assert ref.url == "https://cdn.midjourney.com/ref-uuid/0_0.png"
        assert ref.role == ReferenceRoleEnum.FACE
        assert ref.cref_weight == 85
        assert ref.notes == "女主都市职场妆造底图"

    def test_shot_midjourney_prompt_compilation_and_extraction(self):
        """检验 Shot.midjourney_prompt 承载与参数反向解析能力."""
        prompt_str = (
            "photorealistic Chinese male actor, 26yo CEO, cinematic lighting "
            "--cref https://cdn.midjourney.com/boss_ref.png "
            "--cw 80 --ar 9:16 --v 6.0 --stylize 250"
        )
        shot = Shot(
            shot_id=1,
            dialogue="天凉了，该让王氏破产了。",
            visual_prompt="CEO standing before floor-to-ceiling office window",
            midjourney_prompt=prompt_str
        )
        assert shot.midjourney_prompt == prompt_str

        # 提取参数正则测试
        cref_match = re.search(r"--cref\s+(\S+)", shot.midjourney_prompt)
        cw_match = re.search(r"--cw\s+(\d+)", shot.midjourney_prompt)
        ar_match = re.search(r"--ar\s+(\S+)", shot.midjourney_prompt)

        assert cref_match is not None
        assert cref_match.group(1) == "https://cdn.midjourney.com/boss_ref.png"
        assert cw_match is not None
        assert int(cw_match.group(1)) == 80
        assert ar_match is not None
        assert ar_match.group(1) == "9:16"


# =====================================================================
# 2. ComfyUI IP-Adapter 参数边界与映射实证
# =====================================================================

class TestComfyUIIpAdapterValidation:
    """实证检验 ComfyUI / SD IP-Adapter 权重边界与多参数字典结构."""

    def test_ip_adapter_weight_bounds(self):
        """检验 ip_adapter_weight 边界：0.0 到 1.5."""
        # 边界下限 0.0
        ref_zero = ReferenceImageConfig(url="https://example.com/ref.png", ip_adapter_weight=0.0)
        assert ref_zero.ip_adapter_weight == 0.0

        # 边界上限 1.5
        ref_max = ReferenceImageConfig(url="https://example.com/ref.png", ip_adapter_weight=1.5)
        assert ref_max.ip_adapter_weight == 1.5

        # 默认值 0.8
        ref_default = ReferenceImageConfig(url="https://example.com/ref.png")
        assert ref_default.ip_adapter_weight == 0.8

        # 越界值 < 0.0
        with pytest.raises(ValidationError):
            ReferenceImageConfig(url="https://example.com/ref.png", ip_adapter_weight=-0.05)

        # 越界值 > 1.5
        with pytest.raises(ValidationError):
            ReferenceImageConfig(url="https://example.com/ref.png", ip_adapter_weight=1.51)

    def test_shot_ip_adapter_params_rich_mapping(self):
        """检验 Shot.ip_adapter_params 支持生产级 ComfyUI 工作流参数节点映射."""
        comfy_node_params = {
            "model_name": "ip-adapter-plus_sdxl_vit-h.safetensors",
            "clip_vision": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
            "weight": 0.85,
            "weight_type": "ease in-out",
            "start_at": 0.0,
            "end_at": 0.85,
            "embeds_scaling": "V only",
            "image_inputs": [
                {"role": "face", "path": "assets/characters/05_boss/face.png", "weight": 1.0},
                {"role": "costume", "path": "assets/characters/05_boss/suit.png", "weight": 0.7}
            ]
        }

        shot = Shot(
            shot_id=2,
            dialogue="准备会议室。",
            visual_prompt="executive meeting room",
            ip_adapter_params=comfy_node_params
        )

        assert shot.ip_adapter_params["model_name"] == "ip-adapter-plus_sdxl_vit-h.safetensors"
        assert shot.ip_adapter_params["weight"] == 0.85
        assert len(shot.ip_adapter_params["image_inputs"]) == 2
        assert shot.ip_adapter_params["image_inputs"][0]["role"] == "face"

        # None 容错自动转换为空字典
        shot_none = Shot.model_validate({
            "shot_id": 3,
            "dialogue": "好的。",
            "visual_prompt": "assistant nodding",
            "ip_adapter_params": None
        })
        assert shot_none.ip_adapter_params == {}


# =====================================================================
# 3. 1,000 个合成镜头的全链路模型序列化与速度基准
# =====================================================================

class TestSerializationPerformance1000Shots:
    """压力测试：验证 1,000 个高维多模态分镜下的往返序列化耗时与保真度."""

    @pytest.fixture(scope="class")
    def synthetic_1000_shots_project(self) -> DramaProject:
        """生成包含完整角色一致性卡、多道具及 1,000 个多模态镜头的工程对象."""
        characters = [
            CharacterAsset(
                name="顾沉舟",
                gender="male",
                visual_tags="photorealistic Chinese male actor, 28 years old, sharp suit, 8k cinema still",
                visual_anchor="身姿高大挺拔，黑色侧分油头，金丝眼镜，手工定制暗蓝西装",
                archetype="05_modern_male_boss",
                turnaround_prompt="16:9 full-body model sheet, front view, side view, back view, white cyclorama background",
                turnaround_image="/output/gu_turnaround.png",
                consistency_card=CharacterConsistencyCard(
                    facial_lock="刀削斧凿般的锋利下颌线，深邃眼眸，微薄唇形",
                    hair_lock="侧分背头，乌黑有光泽，发蜡定型无碎发",
                    costume_lock="定制三件套暗蓝条纹羊毛西装，温莎结丝质领带，银质腕表",
                    exclusive_negative_prompt="休闲服, 凌乱发型, 娃娃脸, 浓妆, 崩坏",
                    reference_images=[
                        ReferenceImageConfig(url="https://ref.com/gu_face.png", role=ReferenceRoleEnum.FACE, cref_weight=95, ip_adapter_weight=1.1),
                        ReferenceImageConfig(url="https://ref.com/gu_suit.png", role=ReferenceRoleEnum.COSTUME, cref_weight=80, ip_adapter_weight=0.9),
                    ]
                )
            ),
            CharacterAsset(
                name="苏清颜",
                gender="female",
                visual_tags="photorealistic Chinese female actress, 25 years old, elegant urban lady, 8k cinema still",
                visual_anchor="波浪长卷发，浅杏色风衣，珍珠耳坠，清冷独立",
                archetype="04_modern_female_urban",
                consistency_card=CharacterConsistencyCard(
                    facial_lock="精致小巧鹅蛋脸，柳叶眉，清澈鹿眼",
                    hair_lock="深栗色自然大波浪卷发，过肩长度",
                    costume_lock="浅杏色双排扣风衣，内搭米白高领针织衫",
                    exclusive_negative_prompt="古装, 浓艳浓妆, 暴露服饰, 假发感"
                )
            )
        ]

        props = [
            PropAsset(
                name="顾氏总裁黑卡",
                category="accessory",
                description="全球限量百夫长黑金卡，象征顾氏家族最高财权",
                visual_tags="titanium black card, embossed gold lettering",
                feature_lock="纯黑哑光钛金材质，表面暗金双龙暗纹",
                turnaround_prompt="16:9 prop design sheet, angled macro close-up, front, back",
                negative_prompt="plastic, colorful, fake"
            ),
            PropAsset(
                name="定情翡翠玉镯",
                category="accessory",
                feature_lock="老坑玻璃种帝王绿，通体荧光微泛，内部无棉絮",
                turnaround_prompt="16:9 jewelry turnaround, studio lighting"
            )
        ]

        scales = list(ShotScaleEnum)
        motions = list(CameraMotionEnum)

        shots = []
        for i in range(1, 1001):
            sc = scales[i % len(scales)]
            mot = motions[i % len(motions)]
            speaker = "顾沉舟" if i % 3 == 1 else ("苏清颜" if i % 3 == 2 else "旁白")
            shots.append(
                Shot(
                    shot_id=i,
                    shot_scale=sc,
                    camera_motion=mot,
                    speaker=speaker,
                    dialogue=f"分镜 #{i}：在这个城市，没有人可以挑战既定的规则。" if speaker != "旁白" else "",
                    action_beat=f"镜头 #{i} 角色眼神交锋，光影迅速切换" if i % 2 == 0 else f"镜头 #{i} 大环境气氛渲染",
                    visual_prompt=f"8k cinematic frame #{i}, {sc.value}, {mot.value}, ARRI Alexa 65, 35mm film grain, 9:16",
                    sfx=f"第 {i:04d} 镜 · 重音悬念音效" if i % 5 == 0 else "",
                    blocking="人物立于左侧黄金分割线，背景虚化" if i % 2 == 1 else "大景深双人对峙",
                    seedance_prompt=f"【机位: {sc.value} | 运镜: {mot.value}】 角色站在聚光灯下，台词：{{第{i}幕}}，音效：<风雨声>",
                    duration_seconds=3.5 + (i % 3) * 0.5,
                    negative_prompt="low quality, deformed, extra fingers, cartoon, 3d render",
                    prop_refs=["顾氏总裁黑卡"] if i % 10 == 0 else (["定情翡翠玉镯"] if i % 15 == 0 else []),
                    midjourney_prompt=f"cinematic live-action shot #{i} --cref https://ref.com/gu_face.png --cw 90 --ar 9:16",
                    ip_adapter_params={
                        "weight": 0.85,
                        "start_at": 0.0,
                        "end_at": 0.9,
                        "shot_index": i
                    }
                )
            )

        return DramaProject(
            title="千镜工业级性能测试短剧",
            genre="都市商战修罗场",
            synopsis="千镜史诗级巨制，验证海量镜头下 OmniDrama 契约引擎极致响应速度。",
            characters=characters,
            props=props,
            shots=shots
        )

    def test_roundtrip_speed_and_fidelity_1000_shots(self, synthetic_1000_shots_project):
        """测试 1,000 镜头的序列化与反序列化速度与数据保真度."""
        proj = synthetic_1000_shots_project
        assert len(proj.shots) == 1000
        assert len(proj.characters) == 2
        assert len(proj.props) == 2

        # 1. 序列化耗时评估 (model_dump_json)
        t0 = time.perf_counter()
        json_output = proj.model_dump_json()
        dump_time = time.perf_counter() - t0

        payload_bytes = len(json_output.encode("utf-8"))
        payload_kb = payload_bytes / 1024.0

        # 2. 反序列化耗时评估 (DramaProject.model_validate_json)
        t1 = time.perf_counter()
        reloaded = DramaProject.model_validate_json(json_output)
        load_time = time.perf_counter() - t1

        # 打印性能基准指标
        print(f"\n[1,000 Shots Benchmark] Payload: {payload_kb:.2f} KB")
        print(f"[1,000 Shots Benchmark] model_dump_json: {dump_time * 1000:.2f} ms")
        print(f"[1,000 Shots Benchmark] model_validate_json: {load_time * 1000:.2f} ms")

        # 性能断言：1,000 镜头在现代化 Pydantic v2 环境下，序列化与反序列化均应在 500ms 内完成
        assert dump_time < 0.5, f"序列化耗时超标: {dump_time:.4f}s > 0.5s"
        assert load_time < 0.5, f"反序列化耗时超标: {load_time:.4f}s > 0.5s"

        # 3. 严格数据保真度对比 (0 字段丢失、0 截断)
        assert reloaded.title == proj.title
        assert len(reloaded.characters) == 2
        assert len(reloaded.props) == 2
        assert len(reloaded.shots) == 1000

        # 抽样与全量比对
        for i in range(1000):
            orig_s = proj.shots[i]
            re_s = reloaded.shots[i]
            assert re_s.shot_id == orig_s.shot_id
            assert re_s.shot_scale == orig_s.shot_scale
            assert re_s.camera_motion == orig_s.camera_motion
            assert re_s.speaker == orig_s.speaker
            assert re_s.dialogue == orig_s.dialogue
            assert re_s.visual_prompt == orig_s.visual_prompt
            assert re_s.negative_prompt == orig_s.negative_prompt
            assert re_s.prop_refs == orig_s.prop_refs
            assert re_s.midjourney_prompt == orig_s.midjourney_prompt
            assert re_s.ip_adapter_params == orig_s.ip_adapter_params

        # 验证角色卡与参考底图配置保真度
        char0 = reloaded.characters[0]
        assert char0.name == "顾沉舟"
        assert char0.archetype == "05_modern_male_boss"
        assert char0.consistency_card is not None
        assert char0.consistency_card.facial_lock == "刀削斧凿般的锋利下颌线，深邃眼眸，微薄唇形"
        assert len(char0.consistency_card.reference_images) == 2
        assert char0.consistency_card.reference_images[0].cref_weight == 95
        assert char0.consistency_card.reference_images[1].ip_adapter_weight == 0.9

        # 验证道具资产保真度
        prop0 = reloaded.props[0]
        assert prop0.name == "顾氏总裁黑卡"
        assert prop0.feature_lock == "纯黑哑光钛金材质，表面暗金双龙暗纹"


# =====================================================================
# 4. 下游组件直接消费契约实证 (director.py & app.py)
# =====================================================================

class TestDownstreamContractConsumption:
    """实证检验反序列化模型能否被 director.py 与 web/app.py 无缝消费."""

    def test_director_post_process_consumption(self):
        """检验 director.py 的 _post_process_project 能否直接消费反序列化的 DramaProject."""
        from omnidrama.core.director import DirectorAgent

        raw_json_str = json.dumps({
            "title": "破茧成蝶",
            "genre": "都市言情",
            "synopsis": "寒门少女蜕变为商界精英",
            "characters": [
                {
                    "name": "林浅",
                    "gender": "female",
                    "visual_tags": "photorealistic Chinese actress, 23yo, 8k cinema still",
                    "visual_anchor": "长发及腰，素雅衬衫",
                    "voice_name": "zh-CN-XiaoxiaoNeural",
                    "turnaround_prompt": "16:9 turnaround",
                    "consistency_card": {
                        "facial_lock": "秀气五官，坚定眼神",
                        "hair_lock": "黑长直"
                    }
                }
            ],
            "props": [
                {"name": "老式怀表", "feature_lock": "表盘裂纹，内嵌黑白合照"}
            ],
            "shots": [
                {
                    "shot_id": 1,
                    "shot_scale": "close_up",
                    "camera_motion": "zoom_in",
                    "speaker": "林浅",
                    "dialogue": "（咬牙切齿）我一定能做到！",  # 包含括号内动作叙述，测试清洗逻辑
                    "visual_prompt": "8k cinematic shot of a young woman",
                    "prop_refs": ["老式怀表"],
                    "negative_prompt": "blurry, deformed",
                    "midjourney_prompt": "cinematic still --cref https://ex.com/face.png --cw 100",
                    "ip_adapter_params": {"weight": 0.8}
                },
                {
                    "shot_id": 2,
                    "shot_scale": "wide_shot",
                    "camera_motion": "pan_left",
                    "speaker": "旁白",
                    "dialogue": "",
                    "visual_prompt": "8k wide city sunset",
                    "sfx": "呼啸风声"
                }
            ]
        })

        # 1. 反序列化
        proj = DramaProject.model_validate_json(raw_json_str)

        # 2. 传递给 DirectorAgent 内部后处理引擎
        director = DirectorAgent()
        processed_proj = director._post_process_project(proj, proj.title, proj.genre)

        # 3. 验证消费后逻辑一致性
        assert isinstance(processed_proj, DramaProject)
        assert len(processed_proj.shots) == 2
        # 第一镜台词应被清洗（去除括号动作批注）
        assert "我一定能做到" in processed_proj.shots[0].dialogue
        assert "咬牙切齿" not in processed_proj.shots[0].dialogue
        # 负向词、道具引用与多模态参数未丢失
        assert processed_proj.shots[0].negative_prompt == "blurry, deformed"
        assert processed_proj.shots[0].prop_refs == ["老式怀表"]
        assert processed_proj.shots[0].midjourney_prompt == "cinematic still --cref https://ex.com/face.png --cw 100"
        assert processed_proj.shots[0].ip_adapter_params == {"weight": 0.8}
        # 第二镜 Seedance 提示词自动补全（将 wide_shot 翻译为中文 景别：远景）
        assert processed_proj.shots[1].seedance_prompt is not None
        assert "景别：远景" in processed_proj.shots[1].seedance_prompt or "超大景深" in processed_proj.shots[1].seedance_prompt

    def test_web_app_model_interop(self):
        """检验 web/app.py 中的 CharacterModel、字典载荷与 CharacterAsset 相互流转."""
        from omnidrama.web.app import CharacterModel

        # 模拟前端 POST /api/characters 提交的数据
        web_char = CharacterModel(
            name="楚天骄",
            role="战神男二",
            voice="云扬 (狂放桀骜)",
            traits="身形巍峨，银发剑眉，黑色作战服"
        )
        web_char_dict = web_char.model_dump()

        # 验证直接流转至 CharacterAsset 契约模型
        schema_char = CharacterAsset.model_validate(web_char_dict)
        assert schema_char.name == "楚天骄"
        assert schema_char.bio == "战神男二"
        assert schema_char.voice_name == "云扬 (狂放桀骜)"
        assert schema_char.visual_tags == "身形巍峨，银发剑眉，黑色作战服"
        assert schema_char.safe_consistency_card.facial_lock == ""

        # 验证挂载一致性卡后回流至前端格式
        schema_char.consistency_card = CharacterConsistencyCard(facial_lock="鹰钩鼻，眼角带疤")
        dumped_for_web = schema_char.model_dump()
        assert dumped_for_web["consistency_card"]["facial_lock"] == "鹰钩鼻，眼角带疤"


# =====================================================================
# 5. 极端对抗性测试与容错排异验证 (Adversarial Edge Cases)
# =====================================================================

class TestAdversarialEdgeCases:
    """对抗性检验：测试脏数据、类型降级、空输入与异常格式下的系统鲁棒性."""

    def test_hostile_shots_normalization(self):
        """测试异常大小写、非标键名、混合空值与畸形 Enum 输入."""
        hostile_shot = {
            "id": 999,
            "scale": "WIDE_SHOT",               # 大写旧版键
            "motion": "SHAKE",                  # 大写运镜
            "speaker": "神秘人",
            "dialogue": "……",
            "visual_prompt": "foggy mountain",
            "image": "/output/shots/999.png",   # 旧版 image 键
            "audio": None,                      # audio 为 None
            "prop_refs": None,                  # None 列表
            "ip_adapter_params": None           # None 字典
        }
        s = Shot.model_validate(hostile_shot)
        assert s.shot_id == 999
        assert s.shot_scale == ShotScaleEnum.WIDE_SHOT
        assert s.camera_motion == CameraMotionEnum.SHAKE
        assert s.image_path == "/output/shots/999.png"
        assert s.audio_path is None
        assert s.prop_refs == []
        assert s.ip_adapter_params == {}

    def test_prop_asset_hostile_and_empty_inputs(self):
        """测试道具资产空名称防御、脏 reference_images 字典列表清洗."""
        dirty_prop = {
            "name": "   ",                      # 纯空白名
            "reference_images": [
                None,
                "",
                "https://cdn.com/prop.png",
                {"url": "https://cdn.com/dict_prop.png"},
                {"path": "local/path/prop.jpg"},
                12345
            ]
        }
        p = PropAsset.model_validate(dirty_prop)
        assert p.name == "未命名道具"
        assert len(p.reference_images) == 4
        assert p.reference_images[0] == "https://cdn.com/prop.png"
        assert p.reference_images[1] == "https://cdn.com/dict_prop.png"
        assert p.reference_images[2] == "local/path/prop.jpg"
        assert p.reference_images[3] == "12345"

    def test_character_consistency_card_empty_string_resilience(self):
        """测试前端表单提交 consistency_card='' 时的自动容错."""
        payload = {
            "name": "测试角色",
            "consistency_card": ""
        }
        char = CharacterAsset.model_validate(payload)
        assert char.consistency_card is None
        # safe_consistency_card 不发生 AttributeError
        assert char.safe_consistency_card.facial_lock == ""
        assert char.safe_consistency_card.hair_lock == ""
        assert char.safe_consistency_card.reference_images == []
