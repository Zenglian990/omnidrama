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
from typing import Optional, List, Dict, Any
import requests

try:
    from omnidrama.schemas.drama_schema import (
        DramaProject, CharacterAsset, Shot, ShotScaleEnum, CameraMotionEnum
    )
except ImportError:
    from schemas.drama_schema import (
        DramaProject, CharacterAsset, Shot, ShotScaleEnum, CameraMotionEnum
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
    "颤声道", "冷声道", "沉声道", "低声道", "大声道", "厉声道", "哭喊道", "质问道"
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
    "环境", "Scene", "背景"
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


class DirectorAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.last_used_engine = "未执行"

    def _clean_speaker(self, raw_speaker: str) -> str:
        name = raw_speaker.strip().strip("“”\"'：:")
        speech_suffixes = sorted(
            list(ACTION_VERBS) + [
                "冷笑道", "怒喝道", "颤声道", "冷声道", "沉声道", "低声道", "大声道", "厉声道",
                "冷笑一声", "冷哼一声", "怒吼道", "咆哮道", "哭喊道", "质问道", "反问道",
                "冷笑", "怒喝", "怒吼", "颤声", "冷哼", "喝道", "说道", "笑道", "怒道", "问道", "喊道",
                "冷冷地", "缓缓地", "淡淡地", "猛地", "不由得", "狠狠地", "咬牙切齿地", "冷冷", "缓缓", "淡淡",
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
        if (
            not name
            or name in SPEAKER_STOPWORDS
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

    def breakdown_story_offline(
        self,
        raw_text: str,
        title: str = "短剧第一集",
        genre: str = "都市热血"
    ) -> DramaProject:
        """本地高质量语法与分镜工程拆解（融合 shuohao-skills 工业级质量门）."""
        self.last_used_engine = "本地工业级分镜规则引擎 (shuohao-skills 规范)"
        raw_lines = [
            line.strip() for line in raw_text.strip().split("\n")
            if line.strip() and not (line.strip().startswith("【") and line.strip().endswith("】"))
        ]

        lines: List[str] = []
        for rl in raw_lines:
            if len(rl) > 35:
                parts = [
                    p.strip().lstrip("”\"'』’")
                    for p in re.split(r"(?<=[。！？!?][”\"'』’])\s*|(?<=[。！？!?])(?![”\"'』’])\s*", rl)
                    if p.strip().lstrip("”\"'』’")
                ]
                lines.extend(parts)
            else:
                lines.append(rl)

        if not lines:
            lines = [raw_text.strip() or f"《{title}》序幕拉开，宿命对决一触即发！"]

        shots: List[Shot] = []
        characters_dict: Dict[str, CharacterAsset] = {}
        shot_id = 1

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
                # 2. 尝试提取说话人与纯台词
                colon_match = re.match(r"^([^：:\s，,。]{2,10})[：:](.+)$", line)
                if colon_match:
                    raw_spk = colon_match.group(1).strip()
                    speaker = self._clean_speaker(raw_spk)
                    dialogue = _clean_dialogue_text(colon_match.group(2))
                    action_beat = f"{speaker}神情肃穆，直视前方说出此话。"
                else:
                    q_match = re.search(r"[“\"](.+?)[”\"]", line)
                    if q_match:
                        quoted_text = _clean_dialogue_text(q_match.group(1))
                        prefix = line[:q_match.start()]
                        direct_spk = re.search(
                            r"([\u4e00-\u9fa5]{2,4}?)(?:冷笑道?|怒喝道?|怒吼道?|颤声道?|低声道?|沉声道?|喝道|说道|笑道|怒道|问道|喊道|冷笑|冷哼|道|说|问)[：:，,\s]*$",
                            prefix,
                        )
                        cand = "旁白"
                        if direct_spk:
                            cand = self._clean_speaker(direct_spk.group(1))
                        if cand == "旁白":
                            subj_match = re.match(
                                r"^([\u4e00-\u9fa5]{2,3}?)(?:脸色|神色|目光|眼神|嘴角|转身|猛地|冷冷|缓缓|淡淡|不由|心中|闻言|见状|看着|望着)",
                                line,
                            )
                            if subj_match:
                                cand = self._clean_speaker(subj_match.group(1))
                        if cand != "旁白":
                            speaker = cand
                            dialogue = quoted_text
                            action_beat = prefix.strip("，,：: ") or f"{speaker}眼神如刀，语气冰冷刺骨。"
                        else:
                            # 带有引号但未明确识别人物，视作旁白环境对白
                            speaker = "旁白"
                            dialogue = quoted_text
                            action_beat = prefix.strip("，,：: ") or "画外音沉重低语，勾勒出暗潮汹涌的局势。"
                    else:
                        # 无引号：若为富含故事叙述的旁白背景句，由旁白念诵；拟声词或极短碎片作为纯动作/音效镜头
                        speaker = "旁白"
                        if len(line.strip()) >= 5 and not _is_sfx_or_onomatopoeia(line):
                            dialogue = _clean_dialogue_text(line)
                            action_beat = f"镜头展现{line.strip()}，环境光影深沉肃杀。"
                        else:
                            dialogue = ""
                            action_beat = line

            # 3. 角色资产自动收录与物理锚点锁定
            if speaker != "旁白" and speaker not in characters_dict:
                is_female = any(w in speaker for w in ["女", "妹", "妻", "小姐", "姐", "母", "琴", "雪", "涵", "妃", "婉", "瑶"])
                anchor = (
                    f"清冷高挑，黑色长发及腰微挽发髻，杏眼明眸，身着素白流仙裙外罩淡青薄纱"
                    if is_female else
                    f"剑眉星目，黑色微卷短发，神色坚毅冷峻，身着墨黑挺拔修身风衣配银色领扣"
                )
                characters_dict[speaker] = CharacterAsset(
                    name=speaker,
                    gender="female" if is_female else "male",
                    visual_tags=(
                        f"photorealistic Chinese {'female' if is_female else 'male'} actor, 8k cinema movie still, "
                        f"authentic facial skin texture, subtle pores, natural hair, playing {speaker}, "
                        f"dramatic film lighting, no cartoon, no anime"
                    ),
                    visual_anchor=anchor,
                    voice_name="zh-CN-XiaoxiaoNeural" if is_female else "zh-CN-YunxiNeural",
                    voice_prompt="沉着有力的原声对白，带有细腻的情绪起伏",
                    bio=f"《{title}》核心主要角色"
                )

            # 4. 景别与运镜规则
            scale = ShotScaleEnum.MEDIUM_SHOT
            motion = CameraMotionEnum.ZOOM_IN

            # 冷开场钩子 (前 2 镜给强特写或大环境压迫)
            if shot_id == 1:
                scale = ShotScaleEnum.CLOSE_UP
                motion = CameraMotionEnum.ZOOM_IN
            elif shot_id == 2:
                scale = ShotScaleEnum.EXTREME_CLOSE_UP
                motion = CameraMotionEnum.STATIC
            elif any(w in line for w in ["眼神", "怒视", "咬牙", "冷笑", "冷冽", "杀意", "死", "盯着", "面孔"]):
                scale = ShotScaleEnum.CLOSE_UP
                motion = CameraMotionEnum.ZOOM_IN
            elif any(w in line for w in ["哈哈", "狂妄", "天际", "雷霆", "炸裂", "从天而降", "轰", "破门", "刀光"]):
                scale = ShotScaleEnum.FULL_SHOT
                motion = CameraMotionEnum.SHAKE
            elif any(w in line for w in ["大院", "大堂", "天下", "四周", "远方", "整座城", "狂风", "夜雨"]):
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
                blocking = f"{speaker}位于画面{side}三分线位置，正面面向镜头微侧45度，双眼锐利盯视前方对手"

            # 6. 生成视觉描述词 (严格杜绝“actor playing 旁白”)
            if speaker in ["旁白", "Scene", "环境"]:
                visual_prompt = (
                    f"8k cinematic wide live-action movie still, shot on ARRI Alexa 65, 35mm Panavision anamorphic lens, "
                    f"atmospheric {genre} cinematic scene, {action_beat}, dramatic volumetric cinematic lighting, "
                    f"authentic realistic film texture, photorealistic environment, masterpiece, theatrical cinematography, "
                    f"no actors, no cartoon, no anime, vertical 9:16"
                )
            else:
                actor_anchor = characters_dict[speaker].visual_anchor
                visual_prompt = (
                    f"8k cinematic live-action movie still, shot on ARRI Alexa 65, 35mm Panavision anamorphic lens, "
                    f"{scale.value}, photorealistic Chinese actor playing {speaker}, {actor_anchor}, {action_beat}, "
                    f"authentic facial texture, subtle skin pores, realistic costume, theatrical cinema lighting, "
                    f"35mm film grain, blockbuster cinematography, masterpiece, no cartoon, no anime, vertical 9:16"
                )

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
                    duration_seconds=est_duration
                )
            )
            shot_id += 1

        if not characters_dict:
            characters_dict["主角"] = CharacterAsset(
                name="主角",
                gender="male",
                visual_tags="photorealistic handsome Chinese male actor, 26 years old, determined expression, authentic skin texture and pores, realistic costume, 8k cinema still, no cartoon, no anime",
                visual_anchor="身姿英挺，剑眉星目，黑色利落短发，身着玄黑修身战甲",
                voice_name="zh-CN-YunxiNeural",
                voice_prompt="从容沉稳的男主角青年音",
                bio="短剧男主角"
            )

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

        for shot in proj.shots:
            # 1. 清洗台词：剔除拟声词与动作叙述
            raw_dialogue = shot.dialogue or ""
            if _is_sfx_or_onomatopoeia(raw_dialogue):
                if not shot.sfx:
                    shot.sfx = raw_dialogue.strip("、，……！!~")
                shot.dialogue = ""
            else:
                shot.dialogue = _clean_dialogue_text(raw_dialogue)

            # 2. 严防“演员扮演旁白”
            if shot.speaker in ["旁白", "Scene", "环境"]:
                if "actor playing 旁白" in shot.visual_prompt or "playing 旁白" in shot.visual_prompt:
                    shot.visual_prompt = (
                        f"8k cinematic wide live-action movie still, shot on ARRI Alexa 65, 35mm Panavision anamorphic lens, "
                        f"atmospheric {genre} cinematic scene, {shot.action_beat or 'cinematic environment'}, "
                        f"dramatic cinematic lighting, volumetric mist, photorealistic environment, masterpiece, no actors, no cartoon, no anime, vertical 9:16"
                    )

            # 3. 补全 Seedance 官方多模态提示词
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

            # 4. 确定性时长校准
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
        model: str = "deepseek-chat"
    ) -> DramaProject:
        """真实调用 LLM 大模型 (SiliconFlow / DeepSeek / Kimi / Claude / Gemini) 进行工业级分镜拆解."""
        siliconflow_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
        deepseek_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        moonshot_key = os.environ.get("MOONSHOT_API_KEY", "").strip()
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        gemini_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", "")).strip()

        user_prompt = f"短剧标题: {title}\n题材: {genre}\n小说原文:\n{raw_text}"

        # 1. 优先尝试硅基流动 SiliconFlow (国内免绑卡，含免费 Qwen2.5 与 DeepSeek-V3)
        if siliconflow_key:
            try:
                try:
                    from providers.siliconflow_provider import SiliconFlowProvider
                except ImportError:
                    from omnidrama.providers.siliconflow_provider import SiliconFlowProvider
                sf = SiliconFlowProvider(api_key=siliconflow_key)
                content_str, engine_name = sf.chat_completion(DIRECTOR_SYSTEM_PROMPT, user_prompt)
                parsed = self._extract_json(content_str)
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
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["choices"][0]["message"]["content"]
                    parsed = self._extract_json(content_str)
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
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["choices"][0]["message"]["content"]
                    parsed = self._extract_json(content_str)
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
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["content"][0]["text"]
                    parsed = self._extract_json(content_str)
                    proj = DramaProject.model_validate(parsed)
                    proj = self._post_process_project(proj, title, genre)
                    self.last_used_engine = "Claude 3.5 Sonnet"
                    return proj
            except Exception as e:
                print(f"[DirectorAgent] Claude 调用异常: {e}")

        # 5. 尝试 Google Gemini API
        if gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                payload = {
                    "systemInstruction": {"parts": [{"text": DIRECTOR_SYSTEM_PROMPT}]},
                    "contents": [{"parts": [{"text": user_prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}
                }
                resp = requests.post(url, json=payload, timeout=45)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = self._extract_json(content_str)
                    proj = DramaProject.model_validate(parsed)
                    proj = self._post_process_project(proj, title, genre)
                    self.last_used_engine = "Google Gemini 2.5 Flash"
                    return proj
            except Exception as e:
                print(f"[DirectorAgent] Gemini 调用异常: {e}")

        # 6. 兜底本地工业级规则拆解
        return self.breakdown_story_offline(raw_text, title=title, genre=genre)
