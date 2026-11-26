"""OmniDrama 工业级 AI 导演智能体 (Director Agent - 吸收 shuohao-skills 规范升维版).

深度融合 shuohao-skills 工业短剧流水线标准：
1. 剧本管戏，分镜管拍：节拍流设计，严格分离动作拍 (action_beat) 与纯台词 (dialogue)，拟声词归入音效轨 (sfx)。
2. 冷开场钩子 (Cold Open Hook)：前 3 拍强制切入强冲突/生死悬念/极致反差，拒绝流水账。
3. 角色物理一致性锚点 (Character Consistency Anchors)：全剧锁定人物外观体素特征，杜绝脸崩漂移。
4. 旁白与环境白模分离：旁白镜头纯粹描写场景光影与环境，严禁生成虚拟人偶或“演员扮演旁白”。
5. 字节跳动火山方舟 Seedance 2.0 / 阿里万相 Wan 2.1 官方多模态提示词原生拼装与对齐。
6. 确定性语速与分镜时长约束：单镜头 2~5 秒严防模型抽搐，台词按 3.8 字/秒高精度测算。
"""
from __future__ import annotations

import os
import re
import json
from typing import Optional, List, Dict, Any, Union, Tuple
import requests

try:
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
except ImportError:
    from schemas.drama_schema import (
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

DIRECTOR_SYSTEM_PROMPT = """你是一名资深影视短剧总导演与工业级分镜大师。你的任务是将用户提供的小说或文本拆解为符合字节跳动火山方舟 Seedance 2.0、阿里万相 Wan 2.1 和电影实拍标准的工业级分镜剧本。

【核心导演法则（刻在骨子里）】：
1. 剧本管戏，分镜管拍：动作节拍 (action_beat) 与纯台词 (dialogue) 严格分离。
2. 台词必须是角色纯对白：严禁包含“某某说”、“冷笑道”或“砰砰砰”、“叹气”、“啊啊啊”等拟声词与动作叙述。
3. 拟声词与动作声必须归入 sfx 字段（如：木门重重撞击声、利刃出鞘铮鸣）。
4. 冷开场钩子 (Cold Open Hook)：全剧前 3 拍内必须爆发核心危机、生死抉择或极致冲突反差，3秒内牢牢抓住观众。
5. 角色一致性锚点 (visual_anchor)：登场角色必须有具体、稳定的物理体素特征（发型、脸型、服装主色调、配饰），全剧所有镜头保持一致。
6. 旁白与环境镜头规范：当 speaker 为“旁白”时，画面必须是宏大场景、气氛空镜或环境渲染，绝对严禁生成“演员扮演旁白”或任何人形替身！
7. 单镜头时长控制在 2~5 秒（单段 ≤ 15 秒），长对话必须切分为说话人特写与对手反应镜头。
8. 100% 忠于原著剧情与题材：分镜中的角色名、台词、场景、动作必须完全忠实于用户提供的小说原文与题材（如末世天灾囤物资、都市商战、古风言情等），严禁生造与原著无关的武侠玄幻套话！

请严格输出合法的 JSON 对象（不要使用 markdown 代码块包裹，直接输出纯 JSON），结构规范如下：
{
  "title": "短剧标题",
  "genre": "题材类型（如：都市修罗、玄幻逆袭、古风权谋）",
  "synopsis": "一句话核心主线大纲",
  "characters": [
    {
      "name": "角色名",
      "gender": "male 或 female",
      "visual_tags": "英文真实演员生图外观提示词 (例如: photorealistic Chinese male actor, 26 years old, sharp eyes, tailored suit, realistic skin texture, cinematic ARRI Alexa lighting, no cartoon, no anime)",
      "visual_anchor": "中文正面全身物理特征锚点 (例如: 黑色凌乱微卷碎发，剑眉锐利，深邃眼眸，身着玄黑修身劲装配暗银滚边，身形挺拔)",
      "voice_name": "zh-CN-YunxiNeural 或 zh-CN-XiaoxiaoNeural 或 zh-CN-YunjianNeural 或 zh-CN-YunyangNeural",
      "voice_prompt": "专属音色与情绪（例如: 冷静自持、隐忍中带着威压的青年男声）",
      "bio": "角色身份与性格"
    }
  ],
  "shots": [
    {
      "shot_id": 1,
      "shot_scale": "wide_shot 或 full_shot 或 medium_shot 或 close_up 或 extreme_close_up",
      "camera_motion": "zoom_in 或 zoom_out 或 pan_left 或 pan_right 或 shake 或 static",
      "speaker": "说话角色名 或 旁白",
      "dialogue": "角色纯台词（纯文本，绝不含拟声词、说话动词或括号；若为纯动作/空镜无台词则为空字符串 \"\"）",
      "action_beat": "画面动作节拍（具体描述此镜头中人物肢体动作、神态变化或环境突变）",
      "sfx": "拟声词与音效（例如: 沉重急促的撞击声 / 暴雨击打青石板声 / 刀剑铮鸣）",
      "blocking": "人物关系与构图逻辑（例如: 主角立于画面左侧三分线，反派跌坐在右下角地面，俯视压迫视角）",
      "visual_prompt": "英文真实电影剧照描述词 (例如: 8k cinematic live-action movie still, shot on ARRI Alexa 65, photorealistic Chinese actor playing the character, dramatic atmospheric lighting, 35mm film grain, shallow depth of field, authentic costume, masterpiece, no cartoon, no anime, vertical 9:16)",
      "seedance_prompt": "字节火山Seedance 2.0官方结构化多模态分镜词（整条中文，包含【人物关系与构图逻辑】、机位焦距运镜景别、画面动作、台词{}、音效<>）"
    }
  ]
}

【格式约束】：
- 至少拆解出 4 到 12 个紧凑连贯的分镜。
- shot_scale 只能是: extreme_close_up, close_up, medium_shot, full_shot, wide_shot 之一。
- camera_motion 只能是: zoom_in, zoom_out, pan_left, pan_right, shake, static 之一。
- 视觉描述词必须严格遵循真实真人演员电影质感，严禁出现 anime, manga, cartoon, 2D 等二次元词汇。
"""

ACTION_VERBS = [
    "狂妄大笑", "冷笑", "冷哼道", "怒吼", "大笑", "喊道", "喝道", "狂笑", "冷哼",
    "说道", "轻蔑道", "怒斥道", "笑道", "怒道", "说道", "道", "说", "吼道", "咆哮道",
    "颤声道", "冷声道", "沉声道", "低声道", "大声道", "厉声道", "哭喊道", "质问道",
    "启唇", "开口", "轻启朱唇", "朱唇微启", "叹道", "轻叹道", "低语道", "轻声道",
    "自语道", "回道", "应道", "答道", "反驳道", "啜泣道", "啜泣", "冷笑一声", "冷哼一声"
]

SFX_PATTERNS = [
    r"^[砰轰咚喀嚓沙呼啸噼啪铛铮叮咚唰嘶嗤吁嘎吱叹嘘哈哼呵呀哇咿嗷呜咕嘟咯噔啪]+[、，……！!~\s]*$",
    r"^(?:砰|轰|咚|咔嚓|啪|呼|唰|铛|嘎吱|呼啸|惨叫|叹气|冷笑)[、，……！!~\s]*$"
]

SPEAKER_STOPWORDS = {
    "旁白", "众人", "有人", "此言", "这时", "忽然", "突然", "顿时", "刹那", "立刻",
    "冷冷", "冷冷地", "不由", "不由得", "缓缓", "缓缓地", "猛地", "狠狠", "愤怒",
    "淡淡", "淡淡地", "哈哈", "咬牙", "转身", "抬头", "低头", "只见", "却见",
    "此时", "随即", "紧接着", "下一秒", "他", "她", "它", "我", "你", "这", "那",
    "环境", "Scene", "背景", "背景音", "空镜", "空镜头", "narrator", "scene", "environment", "bgm",
    "楚楚可怜", "神情冷峻"
}


def _is_sfx_or_onomatopoeia(text: str) -> bool:
    """判断一段文本是否纯属拟声词或音效动作."""
    clean = text.strip().strip("“”\"'『』()（）[]【】")
    if not clean:
        return True
    for pat in SFX_PATTERNS:
        if re.match(pat, clean):
            return True
    # 含有单纯拟声词重复的情况，如 "砰、砰砰……"
    stripped = re.sub(r"[、，……！!~\s\.\-]", "", clean)
    if stripped and len(stripped) <= 6 and all(c in "砰轰咚喀嚓沙呼啸噼啪铛铮叮唰嘶嗤吁嘎吱叹嘘哈哼呵呀哇嗷咕嘟咯噔啪" for c in stripped):
        return True
    return False


def _clean_dialogue_text(dialogue: str) -> str:
    """清洗台词文本：剥离舞台动作批注、某某道及多余标点."""
    d = dialogue.strip().strip("“”\"'『』")
    # 剥离括号内的舞台动作（如：(冷笑)、(咬牙切齿)）
    d = re.sub(r"[\(（][^\)）]+[\)）]", "", d).strip()
    # 剥离开头的说话动作前缀
    d = re.sub(r"^(?:冷笑(?:一声)?|怒喝(?:一声)?|沉声|轻蔑地|淡淡地|缓缓地)[：:，,\s]*", "", d).strip()
    return d


def _estimate_shot_duration(dialogue: str, has_dialogue: bool = True) -> float:
    """确定性时长测算（基于中文短剧标准语速 ~3.8 字/秒 + 停顿约束）."""
    if not has_dialogue or not dialogue.strip():
        return 2.8  # 纯动作/环境镜头默认 2.8 秒
    clean = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", dialogue)
    dur = len(clean) / 3.8 + 0.65
    return max(2.0, min(5.0, round(dur, 2)))


def build_seedance_prompt(
    blocking: str,
    shot_scale: ShotScaleEnum,
    camera_motion: CameraMotionEnum,
    action_beat: str,
    dialogue: str = "",
    sfx: str = "",
    character_name: str = "主角"
) -> str:
    """基于火山引擎官方规范组装 Seedance 2.0 结构化多模态视频提示词."""
    scale_map = {
        ShotScaleEnum.EXTREME_CLOSE_UP: ("极浅景深，85mm 长焦", "大特写", "中心构图"),
        ShotScaleEnum.CLOSE_UP: ("浅景深，50mm 定焦", "特写", "主体居中"),
        ShotScaleEnum.MEDIUM_SHOT: ("自然景深，35mm 人文", "中景", "三分法构图"),
        ShotScaleEnum.FULL_SHOT: ("大景深，28mm 广角", "全景", "人物全身透视"),
        ShotScaleEnum.WIDE_SHOT: ("超大景深，24mm 电影超广角", "远景", "宏大环境构图"),
    }
    lens, scale_zh, comp = scale_map.get(shot_scale, ("标准景深，50mm", "中景", "三分法构图"))

    motion_map = {
        CameraMotionEnum.ZOOM_IN: "缓慢推镜，视线逐步聚焦主体",
        CameraMotionEnum.ZOOM_OUT: "缓慢拉镜，展现周围压迫环境",
        CameraMotionEnum.PAN_LEFT: "平移镜头，自右向左巡视",
        CameraMotionEnum.PAN_RIGHT: "平移镜头，自左向右掠过",
        CameraMotionEnum.SHAKE: "手持微晃，营造紧迫悬疑呼吸感",
        CameraMotionEnum.STATIC: "固定机位，电影级平稳构图",
    }
    motion_zh = motion_map.get(camera_motion, "固定镜头")

    lines = []
    if blocking:
        lines.append(f"【人物关系与构图逻辑】\n{blocking.strip()}")
    lines.append(f"焦距与景深：{lens}")
    lines.append(f"构图：{comp}")
    lines.append(f"运镜：{motion_zh}")
    lines.append(f"景别：{scale_zh}")
    lines.append(f"画面：{action_beat.strip()}")
    if dialogue.strip():
        lines.append(f"台词：{{{dialogue.strip()}}}")
    if sfx.strip():
        lines.append(f"音效：<{sfx.strip()}>")

    return "\n".join(lines)


UNIVERSAL_CINEMATIC_PREFIX = (
    "8k cinematic live-action movie still, shot on ARRI Alexa 65, 35mm Panavision anamorphic lens, "
    "authentic film grain, masterpiece, photorealistic"
)

UNIVERSAL_NEGATIVE_PROMPT = (
    "bad anatomy, deformed face, inconsistent eyes, distorted pupils, extra limbs, mutated hands, "
    "bad proportions, plastic skin, unnatural smooth texture, blurry, low resolution, "
    "multiple people in solo portrait, watermark, signature, cartoon, anime, 3d, cgi, render, illustration, doll-like"
)


def compile_shot_visual_prompt(
    shot_scale: Union[str, ShotScaleEnum] = ShotScaleEnum.MEDIUM_SHOT,
    speaker: str = "旁白",
    action_beat: str = "",
    blocking: str = "",
    genre: str = "都市热血",
    character: Optional[CharacterAsset] = None,
    props: Optional[List[PropAsset]] = None,
    prop_refs: Optional[List[str]] = None,
    *,
    extra_prompt: str = "",
) -> str:
    """根据角色一致性控制卡编译电影级强锁定画面生图提示词.

    拼装标准规范:
    【强锁定前缀 (ARRI Alexa 65 + 骨相五官锁 + 发型发色锁 + 服饰装束锁) + 镜头景别/光学焦距 + 情绪动作/空间走位 + 道具交互 + 电影灯光/9:16 画幅锁定】
    对旁白、环境或 Scene 空镜镜头特殊处理，杜绝生成替身演员或人偶.
    """
    clean_spk = re.sub(r"[【】()（）\"“”'：:\s]", "", speaker or "")
    if (not clean_spk) or clean_spk in ["旁白", "Scene", "环境", "背景", "背景音", "空镜", "空镜头"] or clean_spk.lower() in ["narrator", "scene", "environment", "bgm"]:
        env_beat = action_beat.strip() if action_beat else "cinematic atmosphere"
        prompt_parts = [
            UNIVERSAL_CINEMATIC_PREFIX,
            f"atmospheric {genre} cinematic scene",
            env_beat,
        ]
        if blocking and ("镜头" in blocking or "全景" in blocking or "视角" in blocking):
            prompt_parts.append(blocking.strip())
        prompt_parts.extend([
            "dramatic volumetric atmospheric lighting",
            "dramatic cinema lighting",
            "photorealistic environment",
            "vertical 9:16",
            "no actors",
            "no cartoon",
            "no anime"
        ])
        if extra_prompt:
            prompt_parts.append(extra_prompt.strip())
        return ", ".join(p for p in prompt_parts if p)

    parts = [UNIVERSAL_CINEMATIC_PREFIX]

    # 1. 强锁定前缀 (Consistency Locking Prefix)
    if character:
        gender_term = "female" if getattr(character, "gender", "male") == "female" else "male"
        char_name = character.name or clean_spk
        c_prefix = f"photorealistic Chinese {gender_term} actor playing {char_name}"

        card = character.consistency_card
        if card:
            facial = card.facial_lock or getattr(card, "facial_bone_structure", "")
            hair = card.hair_lock or getattr(card, "hairstyle_and_color", "")
            costume = card.costume_lock or getattr(card, "costume_and_wardrobe", "")
            features = []
            if facial and facial.strip():
                features.append(f"facial features: {facial.strip()}")
            if hair and hair.strip():
                features.append(f"hairstyle: {hair.strip()}")
            if costume and costume.strip():
                features.append(f"costume: {costume.strip()}")
            if features:
                c_prefix += f", {', '.join(features)}"
            if character.visual_tags and character.visual_tags.strip():
                c_prefix += f", {character.visual_tags.strip()}"
        elif character.visual_anchor and character.visual_anchor.strip():
            c_prefix += f", {character.visual_anchor.strip()}"
            if character.visual_tags and character.visual_tags.strip():
                c_prefix += f", {character.visual_tags.strip()}"
        elif character.visual_tags and character.visual_tags.strip():
            c_prefix += f", {character.visual_tags.strip()}"

        parts.append(c_prefix)
    else:
        parts.append(f"photorealistic Chinese actor playing {clean_spk}")

    # 2. 镜头景别与电影光学焦距
    scale_val = shot_scale.value if hasattr(shot_scale, "value") else str(shot_scale).lower()
    scale_desc_map = {
        ShotScaleEnum.EXTREME_CLOSE_UP.value: "extreme close-up shot, 85mm portrait lens, razor-sharp focus on eyes and facial tension, shallow depth of field",
        ShotScaleEnum.CLOSE_UP.value: "close-up portrait shot, 50mm prime lens, expressive emotional intensity, cinematic bokeh",
        ShotScaleEnum.MEDIUM_SHOT.value: "medium shot, 35mm lens, waist-up view, interpersonal dynamics and natural perspective",
        ShotScaleEnum.FULL_SHOT.value: "full shot, 28mm wide lens, full body posture, dramatic body confrontation and tension",
        ShotScaleEnum.WIDE_SHOT.value: "wide shot, 24mm ultra-wide lens, environmental storytelling and cinematic scale",
    }
    scale_desc = scale_desc_map.get(
        scale_val,
        scale_desc_map.get(scale_val.replace(" ", "_"), f"{scale_val} shot, 50mm lens")
    )
    parts.append(scale_desc)

    # 3. 情绪动作与空间构图走位
    act_parts = []
    if action_beat and action_beat.strip():
        act_parts.append(action_beat.strip())
    if blocking and blocking.strip():
        act_parts.append(blocking.strip())
    if act_parts:
        parts.append(", ".join(act_parts))

    # 4. 关联道具整合交互 (matched from prop_refs)
    clean_prop_refs = [str(r).strip() for r in (prop_refs or []) if r and str(r).strip()]
    if clean_prop_refs:
        matched_props = []
        if props:
            matched_props = [p for p in props if getattr(p, "name", "") in clean_prop_refs]
        matched_names = set()
        for p in matched_props:
            p_name = getattr(p, "name", "")
            matched_names.add(p_name)
            v_tags = getattr(p, "visual_tags", "")
            f_lock = getattr(p, "feature_lock", "")
            p_details = []
            if v_tags and v_tags.strip():
                p_details.append(v_tags.strip())
            if f_lock and f_lock.strip():
                p_details.append(f_lock.strip())
            if p_details:
                parts.append(f"holding and showcasing {p_name}: {', '.join(p_details)}")
            else:
                parts.append(f"holding and showcasing {p_name}")
        for ref_name in clean_prop_refs:
            if ref_name not in matched_names:
                parts.append(f"holding and showcasing {ref_name}")

    # 5. 电影灯光与画质锁定
    parts.append("dramatic cinema lighting, subtle skin pores, vertical 9:16, no cartoon, no anime")
    if extra_prompt and extra_prompt.strip():
        parts.append(extra_prompt.strip())

    return ", ".join(p for p in parts if p)


def compile_shot_negative_prompt(
    character: Optional[CharacterAsset] = None,
    extra_negative: str = "",
    props: Optional[List[PropAsset]] = None,
    prop_refs: Optional[List[str]] = None,
) -> str:
    """组合通用电影防崩负向词与角色/道具专属防崩排异负向词."""
    neg_list = [UNIVERSAL_NEGATIVE_PROMPT]
    if character and character.consistency_card:
        card = character.consistency_card
        exclusive = card.exclusive_negative_prompt or getattr(card, "negative_prompt", "")
        if exclusive and exclusive.strip():
            neg_list.append(exclusive.strip())
    if props and prop_refs:
        clean_prop_refs = [str(r).strip() for r in prop_refs if r and str(r).strip()]
        for p in props:
            p_name = getattr(p, "name", "")
            p_neg = getattr(p, "negative_prompt", "")
            if p_name and p_name in clean_prop_refs and p_neg and p_neg.strip():
                neg_list.append(p_neg.strip())
    if extra_negative and extra_negative.strip():
        neg_list.append(extra_negative.strip())
    return ", ".join(neg_list)


def build_character_turnaround_prompt(character: CharacterAsset) -> str:
    """自动生成工业级角色标准 16:9 三视图 (正面/侧面90°/背面180° + 纯白影棚背景 + 胸像特写) 提示词."""
    gender_zh = "female" if getattr(character, "gender", "male") == "female" else "male"
    card = character.consistency_card

    appearance_details = []
    if card:
        facial = card.facial_lock or getattr(card, "facial_bone_structure", "")
        hair = card.hair_lock or getattr(card, "hairstyle_and_color", "")
        costume = card.costume_lock or getattr(card, "costume_and_wardrobe", "")
        if facial and facial.strip():
            appearance_details.append(facial.strip())
        if hair and hair.strip():
            appearance_details.append(hair.strip())
        if costume and costume.strip():
            appearance_details.append(costume.strip())
    elif character.visual_anchor and character.visual_anchor.strip():
        appearance_details.append(character.visual_anchor.strip())

    details_str = ", ".join(appearance_details) if appearance_details else (character.visual_tags or "")
    details_clause = f", {details_str}" if details_str else ""

    return (
        f"character design sheet, full body character turnaround, 3 views from multiple angles: "
        f"front view, side 90° profile view, back 180° view, standing pose, neutral expression, A-pose, "
        f"centered composition, clean solid pure white cyclorama studio background, studio neutral even lighting, "
        f"bust portrait close-up inset, "
        f"photorealistic Chinese {gender_zh} actor, 8k, ARRI Alexa 65 cinematic texture, authentic skin texture and pores"
        f"{details_clause}, masterpiece, high detail --ar 16:9 --no shadows on background, text, watermark, bad anatomy, deformed eyes"
    )


def build_prop_turnaround_prompt(prop: PropAsset) -> str:
    """自动生成工业级道具物品 16:9 三视图 (正视/侧视/45度等轴透视 + 纯白背景) 提示词."""
    details = []
    cat = getattr(prop, "category", "prop")
    v_tags = getattr(prop, "visual_tags", "")
    f_lock = getattr(prop, "feature_lock", "")
    if v_tags and v_tags.strip():
        details.append(v_tags.strip())
    if f_lock and f_lock.strip():
        details.append(f_lock.strip())
    details_str = f", {', '.join(details)}" if details else ""

    return (
        f"prop design turnaround sheet, 3 views: orthographic front view, side profile view, 45-degree isometric perspective view, "
        f"isolated on solid pure white background, softbox product studio lighting, 8k, sharp focus, "
        f"photorealistic {cat}{details_str}, authentic material textures, "
        f"masterpiece, octane render quality --ar 16:9 --no hands, human, text, watermark, heavy shadows"
    )


def build_multimodal_reference_config(
    character: Optional[CharacterAsset] = None,
    turnaround_image_url: Optional[str] = None,
    shot: Optional[Shot] = None,
    **kwargs
) -> Dict[str, Any]:
    """生成 Midjourney --cref、SD/ComfyUI IP-Adapter 与 Seedance 2.0 多图参考配置字典."""
    ref_urls: List[str] = []
    cref_weight: int = 100
    ip_adapter_weight: float = 0.8
    image_inputs: List[Dict[str, Any]] = []

    # 1. 显式传入的 turnaround_image_url 优先级最高
    if turnaround_image_url and str(turnaround_image_url).strip():
        u = str(turnaround_image_url).strip()
        ref_urls.append(u)
        image_inputs.append({"role": "face", "path": u, "weight": 1.0})

    # 2. 检查 character 资产内部配置
    if character:
        if character.turnaround_image and character.turnaround_image.strip():
            u = character.turnaround_image.strip()
            if u not in ref_urls:
                ref_urls.append(u)
                image_inputs.append({"role": "face", "path": u, "weight": 1.0})

        if character.consistency_card and character.consistency_card.reference_images:
            for ref_cfg in character.consistency_card.reference_images:
                u = getattr(ref_cfg, "url", "")
                if u and str(u).strip():
                    u = str(u).strip()
                    if u not in ref_urls:
                        ref_urls.append(u)
                    role_str = getattr(ref_cfg, "reference_type", None) or getattr(ref_cfg, "role", "face")
                    if hasattr(role_str, "value"):
                        role_str = role_str.value
                    image_inputs.append({
                        "role": str(role_str),
                        "path": u,
                        "weight": getattr(ref_cfg, "weight", 1.0)
                    })
                    if len(ref_urls) == 1 or ref_urls[0] == u:
                        if hasattr(ref_cfg, "cref_weight"):
                            cref_weight = ref_cfg.cref_weight
                        if hasattr(ref_cfg, "ip_adapter_weight"):
                            ip_adapter_weight = ref_cfg.ip_adapter_weight

    if not ref_urls:
        return {
            "midjourney": {},
            "ip_adapter": {},
            "seedance": {}
        }

    primary_url = ref_urls[0]

    # Midjourney --cref 配置
    midjourney_config = {
        "prompt_suffix": f"--cref {primary_url} --cw {cref_weight} --ar 9:16 --v 6.1",
        "cref_url": primary_url,
        "cref_weight": cref_weight,
        "aspect_ratio": "9:16",
        "version": "6.1"
    }

    # SD / ComfyUI IP-Adapter 参数
    ip_adapter_config = {
        "enabled": True,
        "image_path": primary_url,
        "weight": ip_adapter_weight,
        "weight_type": "linear",
        "model": "ip-adapter-plus_sdxl_vit-h.safetensors",
        "model_name": "ip-adapter-plus_sdxl_vit-h.safetensors",
        "image_inputs": image_inputs if image_inputs else [{"role": "face", "path": primary_url, "weight": 1.0}]
    }

    # Volcano Seedance 2.0 多图参考标记
    ref_indices = list(range(1, len(ref_urls) + 1))
    ref_tags = [f"@角色参考图{idx}" for idx in ref_indices]
    seedance_config = {
        "ref_indices": ref_indices,
        "ref_prompt_tag": ref_tags[0] if ref_tags else "@角色参考图1",
        "ref_prompt_tags": ref_tags,
        "image_url": primary_url,
        "image_urls": ref_urls
    }

    return {
        "midjourney": midjourney_config,
        "ip_adapter": ip_adapter_config,
        "seedance": seedance_config
    }


class DirectorAgent:
    compile_shot_visual_prompt = staticmethod(compile_shot_visual_prompt)
    compile_shot_negative_prompt = staticmethod(compile_shot_negative_prompt)
    build_character_turnaround_prompt = staticmethod(build_character_turnaround_prompt)
    build_prop_turnaround_prompt = staticmethod(build_prop_turnaround_prompt)
    build_multimodal_reference_config = staticmethod(build_multimodal_reference_config)

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.last_used_engine = "未执行"

    def _clean_speaker(self, raw_speaker: str) -> str:
        name = raw_speaker.strip().strip("“”\"'：:，,。()（）[]【】")
        # 清除修饰词与前缀
        name = re.sub(r"^(?:身边的|门外的|一旁的|迎出来的|跟前的|那|这个|这位|那个|一名|一个)", "", name)
        speech_suffixes = sorted(
            list(ACTION_VERBS) + [
                "冷笑道", "怒喝道", "颤声道", "冷声道", "沉声道", "低声道", "大声道", "厉声道",
                "冷笑一声", "冷哼一声", "怒吼道", "咆哮道", "哭喊道", "质问道", "反问道",
                "冷笑", "怒喝", "怒吼", "颤声", "冷哼", "喝道", "说道", "笑道", "怒道", "问道", "喊道",
                "冷冷地", "缓缓地", "淡淡地", "猛地", "不由得", "狠狠地", "咬牙切齿地", "冷冷", "缓缓", "淡淡",
                "小声说", "轻声说", "小声吸了吸鼻子", "吸了吸鼻子", "低声笑", "低笑道", "轻声", "小声",
                "提醒道", "提醒", "行礼道", "行礼", "自报家门", "平静地说", "平静地", "轻笑一声", "轻笑",
                "小声啜泣道", "小声啜泣", "啜泣道", "啜泣", "楚楚可怜道", "楚楚可怜", "轻咬下唇", "轻咬", "缓缓启唇", "启唇", "开口",
            ],
            key=len,
            reverse=True,
        )
        changed = True
        while changed:
            changed = False
            for suf in speech_suffixes:
                if name.endswith(suf) and len(name) > len(suf):
                    name = name[:-len(suf)].strip()
                    changed = True
                    break
        name = name.strip().strip("，,：: ")
        if (
            not name
            or name in SPEAKER_STOPWORDS
            or name.lower() in SPEAKER_STOPWORDS
            or name in speech_suffixes
            or len(name) > 6
            or len(name) < 2
        ):
            return "旁白"
        return name

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
        return json.loads(text)

    def _sanitize_or_enrich_raw_text(self, raw_text: str, title: str, genre: str) -> str:
        """解码还原番茄小说网页端 PUA 字体字符，并清理旧版本残留的虚假套话."""
        try:
            try:
                from providers.fanqie_provider import FanqieProvider
            except ImportError:
                from omnidrama.providers.fanqie_provider import FanqieProvider
            text = FanqieProvider.decode_pua(raw_text or "").strip()
        except Exception:
            text = re.sub(r"[\uE000-\uF8FF]", "", raw_text or "").strip()

        text = re.sub(r"（提示：AI\s*导演已围绕本章剧情完成[^）]*）", "", text).strip()

        # 剥离旧版缓存可能残留的与原著无关的通用玄幻套话
        legacy_fake_patterns = [
            r"^.*围绕第\d+章.*无论前方有多少强敌环伺.*$",
            r"^.*强敌首领.*大局已定，凭你一己之力.*$",
            r"^.*大长老.*失传已久的巅峰血脉彻底觉醒.*$",
            r"^.*大长老.*失传千年的至尊血脉觉醒.*$",
            r"^.*从今往后，这片天地的新秩序，由我来书写.*$",
            r"^.*属于我们的尊严与荣耀，今日谁也别想夺走半分.*$",
        ]
        for pat in legacy_fake_patterns:
            text = re.sub(pat, "", text, flags=re.MULTILINE).strip()

        # 过滤掉纯标点行或极短残缺行
        clean_lines = []
        for ln in text.splitlines():
            s = ln.strip()
            s_no_punct = re.sub(r"[。，、！？!?,.\s\"'“”【】（）()\-]", "", s)
            if len(s_no_punct) >= 2:
                clean_lines.append(s)

        if clean_lines:
            return "\n".join(clean_lines)

        return f"《{title}》（题材：{genre}）核心剧情拉开帷幕。"

    def _normalize_llm_project_dict(self, parsed: Dict[str, Any], title: str, genre: str) -> Dict[str, Any]:
        """对 LLM (Colab Qwen3.8-27B / Gemini / DeepSeek) 输出的 JSON 做弹性规范化，防止大小写或字段缺失导致回退."""
        if not isinstance(parsed, dict):
            raise ValueError("LLM output is not a JSON object")

        parsed["title"] = str(parsed.get("title") or title).strip() or title
        parsed["genre"] = str(parsed.get("genre") or genre).strip() or genre
        parsed["synopsis"] = str(parsed.get("synopsis") or f"《{title}》高能冲突爆发，主角绝地逆袭。").strip()

        valid_scales = {"extreme_close_up", "close_up", "medium_shot", "full_shot", "wide_shot"}
        valid_motions = {"zoom_in", "zoom_out", "pan_left", "pan_right", "shake", "static"}

        raw_shots = parsed.get("shots") or []
        norm_shots = []
        for idx, s in enumerate(raw_shots):
            if not isinstance(s, dict):
                continue
            raw_dlg = str(s.get("dialogue") or "").strip()
            raw_beat = str(s.get("action_beat") or s.get("description") or "").strip()
            # 剔除纯标点符号无效镜头
            if re.sub(r"[。，、！？!?,.\s\"'“”]", "", raw_dlg + raw_beat) == "":
                continue

            sc = str(s.get("shot_scale") or s.get("scale") or "medium_shot").strip().lower()
            if sc not in valid_scales:
                if "extreme" in sc or "大特写" in sc:
                    sc = "extreme_close_up"
                elif "close" in sc or "特写" in sc:
                    sc = "close_up"
                elif "full" in sc or "全景" in sc:
                    sc = "full_shot"
                elif "wide" in sc or "远景" in sc:
                    sc = "wide_shot"
                else:
                    sc = "medium_shot"

            mo = str(s.get("camera_motion") or s.get("motion") or "zoom_in").strip().lower()
            if mo not in valid_motions:
                if "out" in mo or "拉" in mo:
                    mo = "zoom_out"
                elif "left" in mo or "左" in mo:
                    mo = "pan_left"
                elif "right" in mo or "右" in mo:
                    mo = "pan_right"
                elif "shake" in mo or "震" in mo or "晃" in mo:
                    mo = "shake"
                elif "static" in mo or "固定" in mo:
                    mo = "static"
                else:
                    mo = "zoom_in"

            spk = str(s.get("speaker") or "旁白").strip() or "旁白"
            if not raw_beat:
                raw_beat = f"{spk}神色凛然，气场全开，画面光影极富张力。" if spk != "旁白" else f"宏大电影级场景展现《{title}》紧张局势。"
            vp = str(s.get("visual_prompt") or "").strip()
            if not vp:
                vp = (
                    f"8k cinematic live-action movie still, shot on ARRI Alexa 65, {sc}, "
                    f"atmospheric {genre} drama scene, {raw_beat}, authentic film texture, vertical 9:16, no cartoon, no anime"
                )

            norm_shots.append({
                "shot_id": len(norm_shots) + 1,
                "shot_scale": sc,
                "camera_motion": mo,
                "speaker": spk,
                "dialogue": raw_dlg if re.sub(r"[。，、！？!?,.\s]", "", raw_dlg) else raw_beat,
                "action_beat": raw_beat,
                "sfx": str(s.get("sfx") or ("惊雷轰鸣" if mo == "shake" else "环境氛围音")).strip(),
                "blocking": str(s.get("blocking") or "三分法电影构图，主体突出").strip(),
                "visual_prompt": vp,
                "seedance_prompt": str(s.get("seedance_prompt") or "").strip(),
            })

        if not norm_shots:
            raise ValueError("Normalized shots list is empty")
        parsed["shots"] = norm_shots

        raw_chars = parsed.get("characters") or []
        norm_chars = []
        seen_names = set()
        for c in raw_chars:
            if not isinstance(c, dict):
                continue
            cname = str(c.get("name") or "").strip()
            if not cname or cname == "旁白" or cname in seen_names:
                continue
            seen_names.add(cname)
            gender = str(c.get("gender") or ("female" if any(w in cname for w in "女姐母妻雪薇妃瑶琴妹娘柔晴月") else "male")).lower()
            if gender not in ("male", "female"):
                gender = "male"
            norm_chars.append({
                "name": cname,
                "gender": gender,
                "visual_tags": str(c.get("visual_tags") or c.get("traits") or f"photorealistic Chinese {gender} actor, 8k cinema still, playing {cname}, no cartoon, no anime").strip(),
                "visual_anchor": str(c.get("visual_anchor") or ("清冷高挑，乌黑长发，古风华服" if gender == "female" else "剑眉星目，身姿挺拔，玄黑劲装")).strip(),
                "voice_name": str(c.get("voice_name") or ("zh-CN-XiaoxiaoNeural" if gender == "female" else "zh-CN-YunxiNeural")).strip(),
                "voice_prompt": str(c.get("voice_prompt") or "富有戏剧张力的电影级原声台词").strip(),
                "bio": str(c.get("bio") or c.get("role") or f"《{title}》核心角色").strip(),
            })

        for ns in norm_shots:
            sp = ns["speaker"]
            if sp != "旁白" and sp not in seen_names:
                seen_names.add(sp)
                is_fem = any(w in sp for w in "女姐母妻雪薇妃瑶琴妹娘柔晴月")
                norm_chars.append({
                    "name": sp,
                    "gender": "female" if is_fem else "male",
                    "visual_tags": f"photorealistic Chinese {'female' if is_fem else 'male'} actor, 8k cinema still, playing {sp}, no cartoon, no anime",
                    "visual_anchor": "清冷高挑，乌黑长发" if is_fem else "剑眉星目，身姿挺拔，玄黑战袍",
                    "voice_name": "zh-CN-XiaoxiaoNeural" if is_fem else "zh-CN-YunxiNeural",
                    "voice_prompt": "沉稳坚毅的电影感声线",
                    "bio": f"《{title}》核心角色",
                })

        if not norm_chars:
            norm_chars.append({
                "name": "主角",
                "gender": "male",
                "visual_tags": "photorealistic Chinese male actor, 8k cinema still, determined eyes, no cartoon, no anime",
                "visual_anchor": "剑眉星目，身姿挺拔，玄黑修身战衣",
                "voice_name": "zh-CN-YunxiNeural",
                "voice_prompt": "磁性沉稳男主角声线",
                "bio": f"《{title}》第一主角",
            })
        parsed["characters"] = norm_chars
        return parsed

    def breakdown_story_offline(
        self,
        raw_text: str,
        title: str = "短剧第一集",
        genre: str = "都市热血"
    ) -> DramaProject:
        """本地高质量语法与分镜工程拆解（融合 shuohao-skills 工业级质量门）."""
        self.last_used_engine = "本地工业级分镜规则引擎 (shuohao-skills 规范)"
        raw_text = self._sanitize_or_enrich_raw_text(raw_text, title, genre)
        raw_lines = [
            line.strip() for line in raw_text.strip().split("\n")
            if line.strip() and not (line.strip().startswith("【") and line.strip().endswith("】"))
        ]

        # 1. 过滤番茄小说/阅读器网页端杂质（字数、时间、目录、书架废话）
        filtered_lines: List[str] = []
        for rl in raw_lines:
            if re.search(r"本章字数|更新时间|作者有话说|最新网址|加入书架|目录|下一[页章]|点击下载|请收藏", rl):
                continue
            if re.match(r"^第\s*\d+\s*[章节卷篇].*(?:字数|时间)", rl):
                continue
            filtered_lines.append(rl)

        # 2. 避免盲目切断引号对白与后文说话人，按自然段落与对白单元拆镜
        lines: List[str] = []
        for rl in filtered_lines:
            if '"' in rl or '“' in rl or "：" in rl or ":" in rl:
                # 含有台词对白的行，完整保留，绝不将引号和说话人切断
                lines.append(rl)
            elif len(rl) > 40:
                # 纯大段环境叙述，仅在引号外按标点拆分子句
                parts = [
                    p.strip().lstrip("”\"'』’")
                    for p in re.split(r"(?<=[。！？!?])\s*", rl)
                    if p.strip().lstrip("”\"'』’")
                ]
                lines.extend([pt for pt in parts if len(re.sub(r"[。，、！？!?,.\s\"'“”]", "", pt)) >= 4])
            else:
                if len(re.sub(r"[。，、！？!?,.\s\"'“”]", "", rl)) >= 3:
                    lines.append(rl)

        # 若整段剧情拆完不足 3 镜且不含引号对白（例如用户输入 1~2 句精炼故事梗概），
        # 按冲突节拍拆分出多镜分镜，杜绝短剧情退化成单镜/双镜“幻灯片”
        if 1 <= len(lines) <= 2 and all('"' not in ln and '“' not in ln for ln in lines):
            merged_plain = "，".join(lines)
            beat_parts = [
                p.strip()
                for p in re.split(r"[，,；;。！？!?]+", merged_plain)
                if len(re.sub(r"\s+", "", p)) >= 4
            ]
            if len(beat_parts) >= 3:
                lines = beat_parts

        if not lines:
            lines = [raw_text.strip() or f"《{title}》序幕拉开，宿命对决一触即发！"]

        # 3. 预扫描小说主要男女主姓名（同时兼容带引号对白体与无引号第三人称叙事梗概）
        main_female = ""
        main_male = ""
        narrative_action_names: List[str] = []
        _COMMON_SURNAMES = (
            "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
            "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
            "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
            "和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁"
            "杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍"
            "虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚"
            "程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓"
            "牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙"
            "叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴鬱胥能苍双"
            "闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农"
            "温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘"
            "匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空"
            "曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公楚慕容欧阳司马夏侯"
        )
        _NARRATIVE_VERBS = (
            "冷笑|怒斥|嘲讽|亮出|拔剑|甩出|跪地|转身|抬手|走入|冲入|盯着|握紧|喝道|冷哼|"
            "低语|轻笑|拍案|震怒|惨叫|惊恐|后退|大笑|微笑|落泪|反击|出手|下令|质问|怒吼|起身"
        )
        _NON_NAME_WORDS = {
            "雨夜", "寿宴", "豪门", "天台", "大堂", "众人", "全场", "门外", "此刻", "下一",
            "忽然", "突然", "当场", "瞬间", "原来", "其实", "竟然", "终于", "已经", "所有",
            "十万", "百亿", "黑金", "龙王", "保镖", "战神", "神将", "废物", "退婚", "冷眼",
        }
        full_plain_text = "\n".join(lines)
        for m_act in re.finditer(
            rf"(?<![\u4e00-\u9fa5])([{_COMMON_SURNAMES}][\u4e00-\u9fa5]{{1,2}})(?=(?:{_NARRATIVE_VERBS}|是|被|将|把|一|不|却|猛|冷))",
            full_plain_text,
        ):
            nm = m_act.group(1).strip()
            if nm and nm not in _NON_NAME_WORDS and nm not in narrative_action_names:
                narrative_action_names.append(nm)
        for role_kw in ("未婚妻", "岳母", "刀疤男", "大小姐", "女总裁", "恶少", "反派"):
            if role_kw in full_plain_text and role_kw not in narrative_action_names:
                narrative_action_names.append(role_kw)

        for nm in narrative_action_names:
            is_fem = any(w in nm for w in "女妹妻小姐姐母琴雪涵妃婉瑶虞梨娇儿娘姑娘")
            if is_fem and not main_female:
                main_female = nm
            elif not is_fem and not main_male:
                main_male = nm
        speech_verbs = [
            "冷哼了一整声", "笑了一声", "吸了吸鼻子", "冷哼了一声", "自报家门", "率先行礼",
            "咬牙切齿地", "漫不经心地", "平静地", "缓缓地", "冷冷地", "倔强地",
            "哭喊道", "质问道", "反驳道", "沉声道", "冷笑道", "嘲讽道", "怒斥道", "笑着说",
            "轻叹道", "低语道", "说道", "问道", "喊道", "笑道", "怒道", "冷笑", "冷哼",
            "低语", "低笑", "轻叹", "轻笑", "轻嗤", "自嘲", "嘟囔", "喃喃", "回应",
            "提醒", "惊呼", "行礼", "说", "道", "问", "喊",
            "小声啜泣道", "啜泣道", "楚楚可怜道", "缓缓启唇", "启唇", "开口", "啜泣"
        ]
        speech_verbs.sort(key=len, reverse=True)
        speech_verb_pat = (
            r"(?:漫不经心地|冷冷地|缓缓地|突然|微微|小声|轻声|倔强地|咬牙切齿地|平静地|低头|抬头|转身|见状|闻言|自报家门|率先行礼|小声啜泣|啜泣|楚楚可怜|轻咬下唇[，,]楚楚可怜|轻咬下唇|神情冷峻[，,]缓缓|神情冷峻)?"
            r"(?:" + "|".join(re.escape(v) for v in speech_verbs) + r")"
        )
        for line in lines:
            for m in re.finditer(r"([“\"])(.+?)[”\"]", line):
                pre = line[:m.start()].strip()
                suf = line[m.end():].strip()
                for seg in (pre, suf):
                    m_name = re.search(r"([\u4e00-\u9fa5]{2,4}?)\s*" + speech_verb_pat, seg)
                    if not m_name:
                        col_pre_scan = re.match(r"^([\u4e00-\u9fa5a-zA-Z0-9_]{2,8})[：:\s]*$", seg.strip())
                        if col_pre_scan:
                            m_name = col_pre_scan
                    if m_name:
                        cand = self._clean_speaker(m_name.group(1))
                        if cand != "旁白":
                            is_fem = any(w in cand for w in "女妹妻小姐姐母琴雪涵妃婉瑶虞梨娇儿娘姑娘")
                            if is_fem and not main_female:
                                main_female = cand
                            elif not is_fem and not main_male:
                                main_male = cand

        shots: List[Shot] = []
        characters_dict: Dict[str, CharacterAsset] = {}
        shot_id = 1
        is_romance = any(k in genre for k in ["甜宠", "言情", "现言", "古言", "恋爱", "青春", "校园"])

        for line in lines[:14]:
            speaker = "旁白"
            dialogue = ""
            action_beat = line
            sfx = ""

            # 1. 检测纯拟声词/环境音效（如“砰、砰砰……”、“轰隆一声巨响”）
            if _is_sfx_or_onomatopoeia(line):
                speaker = "旁白"
                dialogue = ""
                sfx = line.strip("、，……！!~")
                action_beat = f"画面聚焦环境震颤，伴随着{sfx}的巨大声响，气氛陡然压抑紧张。"
            else:
                # 2. 尝试提取说话人与纯台词（同时兼容前缀、后缀、自报家门与冒号格式）
                q_match = re.search(r"[“\"](.+?)[”\"]", line)
                if q_match:
                    dialogue = _clean_dialogue_text(q_match.group(1))
                    prefix = line[:q_match.start()].strip()
                    suffix = line[q_match.end():].strip()
                    cand = "旁白"

                    # A. 台词内自报家门
                    m_self = re.search(r"(?:在下|小的|在下是|我是|小女子|老夫|贫道)([\u4e00-\u9fa5]{2,3})", dialogue)
                    if m_self:
                        cand = self._clean_speaker(m_self.group(1))

                    # B. 引号前缀说话人 ("温梨小声吸了吸鼻子说：“...”" 或 "顾清雪：“...”")
                    if cand == "旁白" and prefix:
                        # 1) 优先检测冒号前缀 (如 "顾清雪：“想要公章？...”" 或 "林管家: \"...\"")
                        col_pre = re.match(r"^([\u4e00-\u9fa5a-zA-Z0-9_]{2,8})[：:\s]*$", prefix.strip())
                        if col_pre:
                            cand = self._clean_speaker(col_pre.group(1))
                        if cand == "旁白":
                            m_pre = re.search(r"([\u4e00-\u9fa5]{2,4}?)\s*" + speech_verb_pat + r"[：:，,\s]*$", prefix)
                            if m_pre:
                                cand = self._clean_speaker(m_pre.group(1))
                        if cand == "旁白":
                            m_sub = re.match(r"^([\u4e00-\u9fa5]{2,4}?)(?:[，,]|微微|转过身|俯下身|迈开长腿|伸手|率先行礼|抬头|猛然|看着|望着|轻笑|自报家门|小声|轻声|红着眼|咬|轻咬|楚楚可怜|神情|神色|一袭|从阴影中)", prefix)
                            if m_sub:
                                cand = self._clean_speaker(m_sub.group(1))

                    # C. 引号后缀说话人 ("“我才没有哭。”温梨小声吸了吸鼻子。")
                    if cand == "旁白" and suffix:
                        m_post = re.search(r"^([，,\s]*)([\u4e00-\u9fa5]{2,4}?)\s*" + speech_verb_pat, suffix)
                        if m_post:
                            cand = self._clean_speaker(m_post.group(2))
                        if cand == "旁白":
                            m_sub2 = re.match(r"^([，,\s]*)([\u4e00-\u9fa5]{2,4}?)(?:[，,]|唇角|神色|目光|眼神|轻笑|自报家门|转身|犹豫|小声|红着眼|吸了吸鼻子|倔强地)", suffix)
                            if m_sub2:
                                cand = self._clean_speaker(m_sub2.group(2))

                    # 角色称呼归一化 (如 "小姑娘" 映射回已识别的女主)
                    if cand in ("小姑娘", "少女", "女孩", "姑娘") and main_female:
                        cand = main_female
                    elif cand in ("男人", "少年", "青年") and main_male:
                        cand = main_male

                    speaker = cand
                    action_beat = (prefix or suffix) if (prefix or suffix) else f"{speaker}正色开口"
                else:
                    colon_match = re.match(r"^([^：:\s，,。]{2,10})[：:](.+)$", line)
                    if colon_match:
                        raw_spk = colon_match.group(1).strip()
                        speaker = self._clean_speaker(raw_spk)
                        dialogue = _clean_dialogue_text(colon_match.group(2))
                        action_beat = f"{speaker}神情肃穆，直视前方说出此话。"
                    else:
                        matched_actor = ""
                        for nm in narrative_action_names:
                            if nm in line:
                                matched_actor = nm
                                break
                        speaker = matched_actor or "旁白"
                        if len(line.strip()) >= 5 and not _is_sfx_or_onomatopoeia(line):
                            dialogue = _clean_dialogue_text(line)
                            action_beat = f"镜头展现{line.strip()}，营造深刻剧情氛围。"
                        else:
                            dialogue = ""
                            action_beat = line

            # 3. 角色资产自动收录与物理锚点锁定
            if speaker != "旁白" and speaker not in characters_dict:
                is_female = any(w in speaker for w in ["女", "妹", "妻", "小姐", "姐", "母", "琴", "雪", "涵", "妃", "婉", "瑶", "虞", "梨", "娇", "儿", "娘", "姑娘"])
                if is_romance:
                    anchor = (
                        f"容貌清纯甜美，灵动杏眸，栗色微卷柔顺长发，身着淡粉色软糯毛衣搭配百褶裙"
                        if is_female else
                        f"面容清俊立体，眼神深邃含笑，身材挺拔清瘦，身着纯白衬衫与浅灰休闲西裤"
                    )
                else:
                    anchor = (
                        f"清冷高挑，黑色长发及腰微挽发髻，杏眼明眸，身着素白流仙裙外罩淡青薄纱"
                        if is_female else
                        f"剑眉星目，黑色微卷短发，神色坚毅冷峻，身着墨黑挺拔修身风衣配银色领扣"
                    )
                voice_name = "zh-CN-XiaohanNeural" if is_female else "zh-CN-YunyangNeural"
                voice_prompt = "温柔甜美清纯少女原声音色" if is_female else "阳光清朗青年男主原声音色"
                characters_dict[speaker] = CharacterAsset(
                    name=speaker,
                    gender="female" if is_female else "male",
                    visual_tags=(
                        f"photorealistic Chinese {'female' if is_female else 'male'} actor, 8k cinema movie still, "
                        f"authentic facial skin texture, subtle pores, natural hair, playing {speaker}, "
                        f"dramatic film lighting, no cartoon, no anime"
                    ),
                    visual_anchor=anchor,
                    voice_name=voice_name,
                    voice_prompt=voice_prompt,
                    bio=f"《{title}》核心主要角色"
                )

            # 4. 景别与运镜规则
            scale = ShotScaleEnum.MEDIUM_SHOT
            motion = CameraMotionEnum.ZOOM_IN

            if shot_id == 1:
                scale = ShotScaleEnum.CLOSE_UP
                motion = CameraMotionEnum.ZOOM_IN
            elif shot_id == 2:
                scale = ShotScaleEnum.EXTREME_CLOSE_UP
                motion = CameraMotionEnum.STATIC
            elif any(w in line for w in ["眼神", "怒视", "咬牙", "冷笑", "冷冽", "杀意", "死", "盯着", "面孔", "对上"]):
                scale = ShotScaleEnum.CLOSE_UP
                motion = CameraMotionEnum.ZOOM_IN
            elif any(w in line for w in ["哈哈", "狂妄", "天际", "雷霆", "炸裂", "从天而降", "轰", "破门", "刀光"]):
                scale = ShotScaleEnum.FULL_SHOT
                motion = CameraMotionEnum.SHAKE
            elif any(w in line for w in ["大院", "大堂", "天下", "四周", "远方", "整座城", "狂风", "夜雨", "宅院", "深山"]):
                scale = ShotScaleEnum.WIDE_SHOT
                motion = CameraMotionEnum.ZOOM_OUT
            elif speaker != "旁白":
                scale = ShotScaleEnum.MEDIUM_SHOT
                motion = CameraMotionEnum.PAN_RIGHT if shot_id % 2 == 0 else CameraMotionEnum.PAN_LEFT

            # 5. 构图走位 (Blocking)
            if speaker == "旁白":
                blocking = "镜头聚焦环境全景与气氛烘托，无特定演员站位，视线开阔"
            else:
                side = "左侧" if shot_id % 2 == 1 else "右侧"
                blocking = f"{speaker}位于画面{side}三分线位置，正面面向镜头微侧45度，双眼专注注视前方对手"

            # 6. 生成视觉描述词与负向词 (严格一致性锁定，杜绝“actor playing 旁白”)
            char = characters_dict.get(speaker)
            visual_prompt = compile_shot_visual_prompt(
                shot_scale=scale,
                speaker=speaker,
                action_beat=action_beat,
                blocking=blocking,
                genre=genre,
                character=char,
                props=None,
                prop_refs=[]
            )
            negative_prompt = compile_shot_negative_prompt(character=char)

            # 多模态参考底图配置 (Midjourney, IP-Adapter, Seedance)
            ref_config = build_multimodal_reference_config(character=char)
            midjourney_prompt = ""
            if ref_config.get("midjourney") and ref_config["midjourney"].get("prompt_suffix"):
                midjourney_prompt = f"{visual_prompt} {ref_config['midjourney']['prompt_suffix']}".strip()
            ip_adapter_params = ref_config.get("ip_adapter") or {}

            # 7. 组装 Seedance 2.0 官方结构化提示词
            seedance_prompt = build_seedance_prompt(
                blocking=blocking,
                shot_scale=scale,
                camera_motion=motion,
                action_beat=action_beat,
                dialogue=dialogue,
                sfx=sfx,
                character_name=speaker
            )

            # 8. 确定性时长测算 (杜绝模型抽搐，单镜控制在 2.0s ~ 5.0s)
            est_duration = _estimate_shot_duration(dialogue, has_dialogue=bool(dialogue.strip()))

            shots.append(
                Shot(
                    shot_id=shot_id,
                    shot_scale=scale,
                    camera_motion=motion,
                    speaker=speaker,
                    dialogue=dialogue,
                    action_beat=action_beat,
                    sfx=sfx,
                    blocking=blocking,
                    seedance_prompt=seedance_prompt,
                    visual_prompt=visual_prompt,
                    negative_prompt=negative_prompt,
                    midjourney_prompt=midjourney_prompt,
                    ip_adapter_params=ip_adapter_params,
                    duration_seconds=est_duration
                )
            )
            shot_id += 1

        # 若提取角色过少，自动补齐符合题材的主配角矩阵，杜绝单一角色或全旁白
        if len(characters_dict) < 2:
            if is_romance:
                f_name = main_female or (title[:2] if len(title) >= 2 else "女主")
                m_name = main_male or "男主"
                if f_name not in characters_dict:
                    characters_dict[f_name] = CharacterAsset(
                        name=f_name,
                        gender="female",
                        visual_tags="photorealistic sweet beautiful Chinese actress, 20 years old, 8k cinema still",
                        visual_anchor="容貌清纯甜美，灵动杏眸，栗色微卷柔顺长发，身着淡粉色软糯毛衣搭配百褶裙",
                        voice_name="zh-CN-XiaohanNeural",
                        voice_prompt="温柔甜美清纯少女原声音色",
                        bio=f"《{title}》女主角"
                    )
                if m_name not in characters_dict:
                    characters_dict[m_name] = CharacterAsset(
                        name=m_name,
                        gender="male",
                        visual_tags="photorealistic handsome Chinese actor, 23 years old, 8k cinema still",
                        visual_anchor="面容清俊立体，眼神深邃含笑，身材挺拔清瘦，身着纯白衬衫与浅灰休闲西裤",
                        voice_name="zh-CN-YunyangNeural",
                        voice_prompt="阳光清朗青年男主原声音色",
                        bio=f"《{title}》男主角"
                    )
            else:
                if "主角" not in characters_dict:
                    characters_dict["主角"] = CharacterAsset(
                        name="主角",
                        gender="male",
                        visual_tags="photorealistic handsome Chinese male actor, 26 years old, determined expression, authentic skin texture and pores, realistic costume, 8k cinema still, no cartoon, no anime",
                        visual_anchor="身姿英挺，剑眉星目，黑色利落短发，身着玄黑挺拔风衣战甲",
                        voice_name="zh-CN-YunyangNeural",
                        voice_prompt="从容沉稳的男主角青年音",
                        bio=f"《{title}》核心主角"
                    )
                if "主要角色" not in characters_dict and len(characters_dict) < 2:
                    characters_dict["主要角色"] = CharacterAsset(
                        name="主要角色",
                        gender="female",
                        visual_tags="photorealistic Chinese actress, 24 years old, authentic skin pores, 8k cinema still",
                        visual_anchor="清冷出尘，柳叶明眸，身着典雅浅青色长裙",
                        voice_name="zh-CN-XiaohanNeural",
                        voice_prompt="清脆灵动的配角原声音色",
                        bio=f"《{title}》重要对手/配角"
                    )

        # 旁白根据题材定制差异化音色（甜宠言情用晓晓，热血玄幻用云希）
        narrator_voice = "zh-CN-XiaoxiaoNeural" if is_romance else "zh-CN-YunxiNeural"
        characters_dict["旁白"] = CharacterAsset(
            name="旁白",
            gender="female" if is_romance else "male",
            visual_tags=f"cinematic panoramic scene still for {genre}, ARRI Alexa 65, 8k masterpiece",
            visual_anchor="宏大光影氛围场景，电影质感空镜",
            voice_name=narrator_voice,
            voice_prompt="细腻沉浸式影视叙事旁白",
            bio="全剧讲述者与气氛渲染者"
        )

        # 确保所有角色资产均填充一致性卡与三视图定妆提示词
        for c in characters_dict.values():
            if c.name != "旁白":
                if not c.consistency_card:
                    c.consistency_card = CharacterConsistencyCard(
                        facial_lock=c.visual_anchor or "",
                        costume_lock=c.visual_tags or ""
                    )
                if not c.turnaround_prompt:
                    c.turnaround_prompt = build_character_turnaround_prompt(c)

        return DramaProject(
            title=title,
            genre=genre,
            synopsis=f"《{title}》核心冲突爆发，多方势力对峙，危机一触即发。",
            characters=list(characters_dict.values()),
            shots=shots
        )

    def _post_process_project(self, proj: DramaProject, title: str, genre: str) -> DramaProject:
        """对大模型返回的剧本做工业级质检门修复与对齐 (Quality Gate)."""
        char_map = {c.name: c for c in proj.characters}
        fixed_shots = []

        # 1. 确保所有登场角色具有 turnaround_prompt
        for char in proj.characters:
            if char.name != "旁白" and not char.turnaround_prompt:
                char.turnaround_prompt = build_character_turnaround_prompt(char)

        # 2. 确保所有道具资产具有 turnaround_prompt
        for prop in getattr(proj, "props", []):
            if not prop.turnaround_prompt:
                prop.turnaround_prompt = build_prop_turnaround_prompt(prop)

        for shot in proj.shots:
            # 1. 清洗台词：剔除拟声词与动作叙述
            raw_dialogue = shot.dialogue or ""
            if _is_sfx_or_onomatopoeia(raw_dialogue):
                if not shot.sfx:
                    shot.sfx = raw_dialogue.strip("、，……！!~")
                shot.dialogue = ""
            else:
                shot.dialogue = _clean_dialogue_text(raw_dialogue)

            char = char_map.get(shot.speaker)

            # 2. 严防“演员扮演旁白”与生成替身，并确保 visual_prompt 存在
            clean_shot_spk = re.sub(r"[【】()（）\"“”'：:\s]", "", shot.speaker or "")
            is_narrator_shot = (
                not clean_shot_spk
                or clean_shot_spk in ["旁白", "Scene", "环境", "背景", "背景音", "空镜", "空镜头"]
                or clean_shot_spk.lower() in ["narrator", "scene", "environment", "bgm"]
            )
            if is_narrator_shot:
                if "actor playing" in (shot.visual_prompt or "") or "playing " in (shot.visual_prompt or "") or not shot.visual_prompt:
                    shot.visual_prompt = compile_shot_visual_prompt(
                        shot_scale=shot.shot_scale,
                        speaker=shot.speaker,
                        action_beat=shot.action_beat or "cinematic environment",
                        blocking=shot.blocking or "",
                        genre=genre,
                        character=None,
                    )
            elif not shot.visual_prompt:
                shot.visual_prompt = compile_shot_visual_prompt(
                    shot_scale=shot.shot_scale,
                    speaker=shot.speaker,
                    action_beat=shot.action_beat,
                    blocking=shot.blocking or "",
                    genre=genre,
                    character=char,
                    props=getattr(proj, "props", []),
                    prop_refs=shot.prop_refs,
                )

            # 3. 补全负向词 (若未填写)
            if not shot.negative_prompt:
                shot.negative_prompt = compile_shot_negative_prompt(
                    character=char,
                    props=getattr(proj, "props", []),
                    prop_refs=shot.prop_refs,
                )

            # 4. 补全多模态参考底图配置 (若存在参考图且字段为空)
            ref_config = build_multimodal_reference_config(character=char)
            if not shot.midjourney_prompt and ref_config.get("midjourney") and ref_config["midjourney"].get("prompt_suffix"):
                shot.midjourney_prompt = f"{shot.visual_prompt} {ref_config['midjourney']['prompt_suffix']}".strip()
            if not shot.ip_adapter_params and ref_config.get("ip_adapter"):
                shot.ip_adapter_params = ref_config["ip_adapter"]

            # 5. 补全 Seedance 官方多模态提示词
            if not shot.seedance_prompt:
                shot.seedance_prompt = build_seedance_prompt(
                    blocking=shot.blocking or "角色正面面向镜头，三分法构图",
                    shot_scale=shot.shot_scale,
                    camera_motion=shot.camera_motion,
                    action_beat=shot.action_beat or shot.dialogue,
                    dialogue=shot.dialogue,
                    sfx=shot.sfx or "",
                    character_name=shot.speaker
                )

            # 6. 确定性时长校准
            if not shot.duration_seconds or shot.duration_seconds <= 0:
                shot.duration_seconds = _estimate_shot_duration(shot.dialogue, bool(shot.dialogue.strip()))

            fixed_shots.append(shot)

        proj.shots = fixed_shots
        return proj

    def breakdown_story(
        self,
        raw_text: str,
        title: str = "短剧第一集",
        genre: str = "都市热血",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",
        allow_colab_cold_boot: bool = True,
    ) -> DramaProject:
        """真实调用 LLM 大模型 (Colab Qwen3.8-27B-Uncensored / SiliconFlow / DeepSeek / Kimi / Claude / Gemini) 进行工业级分镜拆解."""
        raw_text = self._sanitize_or_enrich_raw_text(raw_text, title, genre)
        try:
            from core.runtime_context import get_provider_key
        except ImportError:
            from omnidrama.core.runtime_context import get_provider_key
        siliconflow_key = get_provider_key("SILICONFLOW_API_KEY")
        deepseek_key = get_provider_key("DEEPSEEK_API_KEY", explicit=api_key)
        moonshot_key = get_provider_key("MOONSHOT_API_KEY")
        anthropic_key = get_provider_key("ANTHROPIC_API_KEY")
        gemini_key = get_provider_key("GEMINI_API_KEY") or get_provider_key("GOOGLE_API_KEY")

        user_prompt = f"短剧标题: {title}\n题材: {genre}\n小说原文:\n{raw_text}"

        # 优先使用已配置 Key 的高速稳定云端大模型（2~6秒出专业多镜剧本），
        # 仅在未配置任何云端 API Key 或全部云端调用失败时，再回退尝试 Colab T4，避免用户干等 55 秒冷启动！

        # 1. 尝试硅基流动 SiliconFlow (国内免绑卡，含免费 Qwen2.5 与 DeepSeek-V3)
        if siliconflow_key:
            try:
                try:
                    from providers.siliconflow_provider import SiliconFlowProvider
                except ImportError:
                    from omnidrama.providers.siliconflow_provider import SiliconFlowProvider
                sf = SiliconFlowProvider(api_key=siliconflow_key)
                content_str, engine_name = sf.chat_completion(DIRECTOR_SYSTEM_PROMPT, user_prompt)
                parsed = self._normalize_llm_project_dict(self._extract_json(content_str), title, genre)
                proj = DramaProject.model_validate(parsed)
                proj = self._post_process_project(proj, title, genre)
                self.last_used_engine = engine_name
                return proj
            except Exception as e:
                print(f"[DirectorAgent] SiliconFlow 调用异常: {e}")

        # 2. 尝试 DeepSeek 官方 API (真实调用)
        if deepseek_key:
            try:
                base = (api_base or "https://api.deepseek.com").rstrip("/")
                url = f"{base}/chat/completions"
                headers = {"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"}
                payload = {
                    "model": model or "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["choices"][0]["message"]["content"]
                    parsed = self._normalize_llm_project_dict(self._extract_json(content_str), title, genre)
                    proj = DramaProject.model_validate(parsed)
                    proj = self._post_process_project(proj, title, genre)
                    self.last_used_engine = f"DeepSeek 大模型 ({model})"
                    return proj
            except Exception as e:
                print(f"[DirectorAgent] DeepSeek 调用异常: {e}")

        # 3. 尝试 Kimi (Moonshot AI)
        if moonshot_key:
            try:
                url = "https://api.moonshot.cn/v1/chat/completions"
                headers = {"Authorization": f"Bearer {moonshot_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "moonshot-v1-8k",
                    "messages": [
                        {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["choices"][0]["message"]["content"]
                    parsed = self._normalize_llm_project_dict(self._extract_json(content_str), title, genre)
                    proj = DramaProject.model_validate(parsed)
                    proj = self._post_process_project(proj, title, genre)
                    self.last_used_engine = "Kimi (Moonshot-v1)"
                    return proj
            except Exception as e:
                print(f"[DirectorAgent] Kimi 调用异常: {e}")

        # 4. 尝试 Anthropic Claude API
        if anthropic_key:
            try:
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 4096,
                    "system": DIRECTOR_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}]
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["content"][0]["text"]
                    parsed = self._normalize_llm_project_dict(self._extract_json(content_str), title, genre)
                    proj = DramaProject.model_validate(parsed)
                    proj = self._post_process_project(proj, title, genre)
                    self.last_used_engine = "Claude 3.5 Sonnet"
                    return proj
            except Exception as e:
                print(f"[DirectorAgent] Claude 调用异常: {e}")

        # 5. 尝试 Google Gemini API（多代模型自动平滑回退，避免单一模型 404/限流导致降级）
        if gemini_key:
            for g_model in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                    payload = {
                        "systemInstruction": {"parts": [{"text": DIRECTOR_SYSTEM_PROMPT}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}
                    }
                    resp = requests.post(url, json=payload, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        content_str = data["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = self._normalize_llm_project_dict(self._extract_json(content_str), title, genre)
                        proj = DramaProject.model_validate(parsed)
                        proj = self._post_process_project(proj, title, genre)
                        self.last_used_engine = f"Google Gemini ({g_model})"
                        return proj
                    else:
                        print(f"[DirectorAgent] Gemini ({g_model}) 返回 HTTP {resp.status_code}: {resp.text[:160]}")
                except Exception as e:
                    print(f"[DirectorAgent] Gemini ({g_model}) 调用异常: {e}")

        # 6. 备选尝试 Google Colab T4 1号机 (仅在云端 API 不可用且允许冷启动时短超时尝试)
        if allow_colab_cold_boot:
            try:
                try:
                    from providers.colab_cluster_provider import ColabClusterManager
                except ImportError:
                    from omnidrama.providers.colab_cluster_provider import ColabClusterManager
                cluster = ColabClusterManager.get_instance()
                content_str, engine_name = cluster.run_qwen_uncensored_director(
                    DIRECTOR_SYSTEM_PROMPT,
                    user_prompt,
                    allow_cold_boot=False,
                    timeout_sec=20,
                )
                parsed = self._normalize_llm_project_dict(self._extract_json(content_str), title, genre)
                proj = DramaProject.model_validate(parsed)
                proj = self._post_process_project(proj, title, genre)
                self.last_used_engine = engine_name
                return proj
            except Exception as colab_err:
                print(f"[DirectorAgent] Colab T4 Qwen3.8-27B 路由提示: {colab_err}")

        # 7. 兜底本地工业级规则拆解
        return self.breakdown_story_offline(raw_text, title=title, genre=genre)

    # 别名兼容：支持剧本拆解调用
    breakdown_script = breakdown_story
