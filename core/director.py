"""OmniDrama 导演智能体 (Director Agent).

负责调用真实大模型 API (SiliconFlow / DeepSeek / Kimi / Gemini / Claude) 将小说文本转化为结构化剧本与分镜资产。
"""
import os
import re
import json
from typing import Optional, List, Dict
import requests

try:
    from omnidrama.schemas.drama_schema import (
        DramaProject, CharacterAsset, Shot, ShotScaleEnum, CameraMotionEnum
    )
except ImportError:
    from schemas.drama_schema import (
        DramaProject, CharacterAsset, Shot, ShotScaleEnum, CameraMotionEnum
    )

DIRECTOR_SYSTEM_PROMPT = """你是一名资深真人影视短剧总导演。你的任务是将用户提供的小说或故事文本拆解为工业级真人实拍电影分镜剧本。
请严格输出合法的 JSON 对象（不要使用 markdown 代码块包裹，直接输出 JSON），结构必须完全匹配以下格式：
{
  "title": "短剧标题",
  "genre": "题材类型",
  "synopsis": "一句话大纲",
  "characters": [
    {
      "name": "角色名",
      "gender": "male 或 female",
      "visual_tags": "英文真实演员生图外观提示词，例如: photorealistic Chinese male actor, 26 years old, sharp eyes, tailored suit, realistic skin texture, cinematic ARRI Alexa lighting, no cartoon, no anime",
      "voice_name": "zh-CN-YunxiNeural 或 zh-CN-XiaoxiaoNeural 或 zh-CN-YunjianNeural 或 zh-CN-YunyangNeural",
      "bio": "角色身份描述（如：隐世龙王 / 豪门千金 / 铁血统帅）"
    }
  ],
  "shots": [
    {
      "shot_id": 1,
      "shot_scale": "wide_shot 或 full_shot 或 medium_shot 或 close_up 或 extreme_close_up",
      "camera_motion": "zoom_in 或 zoom_out 或 pan_left 或 pan_right 或 shake 或 static",
      "speaker": "说话角色名 或 旁白",
      "dialogue": "该镜头的纯台词或旁白对白（中文，严禁包含'某某说'或提示词标签）",
      "visual_prompt": "英文真实电影剧照描述词，用于顶级AI生图与图生视频，例如: 8k cinematic live-action movie still, shot on ARRI Alexa 65, photorealistic Chinese actor playing the character, dramatic atmospheric lighting, 35mm film grain, shallow depth of field, authentic costume, masterpiece, no cartoon, no anime, vertical 9:16"
    }
  ]
}
要求：
1. 至少拆解出 4 到 10 个紧凑高燃的分镜（shots），台词必须是角色纯对白，杜绝小说叙述废话。
2. shot_scale 只能取: extreme_close_up, close_up, medium_shot, full_shot, wide_shot 之一。
3. camera_motion 只能取: zoom_in, zoom_out, pan_left, pan_right, shake, static 之一。
4. 视觉描述词必须严格遵循真实真人演员电影质感，严禁出现 anime、manga、cartoon、2D 等任何二次元卡通词汇。
"""

ACTION_VERBS = ["狂妄大笑", "冷笑", "冷哼道", "怒吼", "大笑", "喊道", "喝道", "狂笑", "冷哼", "说道", "轻蔑道", "怒斥道", "笑道", "怒道", "说道", "道", "说"]


class DirectorAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.last_used_engine = "未执行"

    SPEAKER_STOPWORDS = {
        "旁白", "众人", "有人", "此言", "这时", "忽然", "突然", "顿时", "刹那", "立刻",
        "冷冷", "冷冷地", "不由", "不由得", "缓缓", "缓缓地", "猛地", "狠狠", "愤怒",
        "淡淡", "淡淡地", "哈哈", "咬牙", "转身", "抬头", "低头", "只见", "却见",
        "此时", "随即", "紧接着", "下一秒", "他", "她", "它", "我", "你", "这", "那"
    }

    def _clean_speaker(self, raw_speaker: str) -> str:
        name = raw_speaker.strip()
        # 按长度降序剥离复合动作/说话词缀，避免“萧玄冷笑道”残留“萧玄冷”
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
            or name in self.SPEAKER_STOPWORDS
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

    def breakdown_story_offline(self, raw_text: str, title: str = "短剧第一集", genre: str = "都市爽文") -> DramaProject:
        """本地语法规则拆解引擎（当未配置外部 LLM Key 时兜底使用）."""
        self.last_used_engine = "本地语法规则引擎 (未配置外部 LLM Key)"
        raw_lines = [line.strip() for line in raw_text.strip().split("\n") if line.strip() and not (line.strip().startswith("【") and line.strip().endswith("】"))]
        lines: List[str] = []
        for rl in raw_lines:
            if len(rl) > 35:
                # 将长段落按句号/感叹号/问号（含闭合引号）切分为独立镜头句
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
        for line in lines[:12]:
            speaker = "旁白"
            dialogue = line

            match = re.match(r"^([^：:\s，,。]{2,10})[：:](.+)$", line)
            if match:
                raw_spk = match.group(1).strip()
                speaker = self._clean_speaker(raw_spk)
                dialogue = match.group(2).strip().strip("“”\"'")
            else:
                # 识别带引号的对白，如：萧玄冷笑道：“……” 或 林清雪脸色苍白，猛地后退一步，颤声道：“……”
                q_match = re.search(r"[“\"](.+?)[”\"]", line)
                if q_match:
                    quoted_text = q_match.group(1).strip()
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

            if speaker != "旁白" and speaker not in characters_dict:
                is_female = any(w in speaker for w in ["女", "妹", "妻", "小姐", "姐", "母", "琴", "雪", "涵", "妃", "婉", "瑶"])
                characters_dict[speaker] = CharacterAsset(
                    name=speaker,
                    gender="female" if is_female else "male",
                    visual_tags=f"photorealistic Chinese {'female' if is_female else 'male'} actor, 8k cinema movie still, authentic facial skin texture, subtle pores, natural hair, playing {speaker}, dramatic film lighting, no cartoon, no anime",
                    voice_name="zh-CN-XiaoxiaoNeural" if is_female else "zh-CN-YunxiNeural",
                    bio="核心角色"
                )

            scale = ShotScaleEnum.MEDIUM_SHOT
            motion = CameraMotionEnum.ZOOM_IN

            if any(w in dialogue for w in ["眼神", "怒视", "咬牙", "冷笑", "冷冽", "杀意", "死", "杀无赦"]):
                scale = ShotScaleEnum.CLOSE_UP
                motion = CameraMotionEnum.ZOOM_IN
            elif any(w in dialogue for w in ["哈哈", "狂妄", "天际", "雷霆", "炸裂", "从天而降", "轰", "灭", "破门"]):
                scale = ShotScaleEnum.FULL_SHOT
                motion = CameraMotionEnum.SHAKE
            elif any(w in dialogue for w in ["大院", "大堂", "天下", "四周", "远方", "整座城", "狂风"]):
                scale = ShotScaleEnum.WIDE_SHOT
                motion = CameraMotionEnum.ZOOM_OUT
            elif speaker != "旁白":
                scale = ShotScaleEnum.MEDIUM_SHOT
                motion = CameraMotionEnum.PAN_RIGHT if shot_id % 2 == 0 else CameraMotionEnum.PAN_LEFT

            visual_prompt = (
                f"8k cinematic live-action movie still, shot on ARRI Alexa 65, 35mm Panavision anamorphic lens, "
                f"{scale.value}, photorealistic Chinese actor playing {speaker}, {dialogue}, "
                f"authentic facial texture, subtle skin pores, realistic costume, theatrical cinema lighting, 35mm film grain, "
                f"blockbuster cinematography, masterpiece, no cartoon, no anime, vertical 9:16"
            )

            shots.append(
                Shot(
                    shot_id=shot_id,
                    shot_scale=scale,
                    camera_motion=motion,
                    speaker=speaker,
                    dialogue=dialogue,
                    visual_prompt=visual_prompt
                )
            )
            shot_id += 1

        if not characters_dict:
            characters_dict["主角"] = CharacterAsset(
                name="主角",
                gender="male",
                visual_tags="photorealistic handsome Chinese male actor, 26 years old, determined expression, authentic skin texture and pores, realistic costume, 8k cinema still, no cartoon, no anime",
                voice_name="zh-CN-YunxiNeural",
                bio="男主角"
            )

        return DramaProject(
            title=title,
            genre=genre,
            characters=list(characters_dict.values()),
            shots=shots
        )

    def breakdown_story(
        self,
        raw_text: str,
        title: str = "短剧第一集",
        genre: str = "都市热血",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat"
    ) -> DramaProject:
        """真实调用用户配置的 LLM 大模型 (SiliconFlow / DeepSeek / Kimi / Claude / Gemini) 进行分镜拆解."""
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
                    self.last_used_engine = "Claude 3.5 Sonnet"
                    return proj
            except Exception as e:
                print(f"[DirectorAgent] Claude 调用异常: {e}")

        # 5. 尝试 Google Gemini API
        if gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
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
                    self.last_used_engine = "Google Gemini 2.0 Flash"
                    return proj
            except Exception as e:
                print(f"[DirectorAgent] Gemini 调用异常: {e}")

        # 6. 兜底本地规则拆解
        return self.breakdown_story_offline(raw_text, title=title, genre=genre)
