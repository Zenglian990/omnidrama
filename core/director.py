"""OmniDrama 导演智能体 (Director Agent).

负责将小说文本转化为符合 BigBanana 影视级规范的结构化剧本与分镜资产。
"""
import os
import re
import json
from typing import Optional, List, Dict
import requests

from omnidrama.schemas.drama_schema import (
    DramaProject, CharacterAsset, Shot, ShotScaleEnum, CameraMotionEnum
)

DIRECTOR_SYSTEM_PROMPT = """你是一名资深短剧/漫剧总导演。你的任务是将用户提供的爽文小说或故事文本拆解为工业级分镜剧本。
必须严格遵循以下规则：
1. 提取所有出场角色的姓名、性别、固定外貌特征Tag（用于保证生图不换脸）、推荐配音音色。
2. 将剧情切分为连贯的单镜头（Shot）。
3. 每个镜头必须指定景别（extreme_close_up, close_up, medium_shot, full_shot, wide_shot）。
4. 每个镜头必须指定运镜（zoom_in, zoom_out, pan_left, pan_right, shake, static）。
5. 必须输出严格符合 JSON 格式的内容，不要包含任何 markdown 标记以外的多余解释。
"""

ACTION_VERBS = ["狂妄大笑", "冷笑", "冷哼道", "怒吼", "大笑", "喊道", "喝道", "狂笑", "冷哼", "说道", "轻蔑道", "怒斥道", "笑道", "怒道", "说道", "道", "说"]

class DirectorAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")

    def _clean_speaker(self, raw_speaker: str) -> str:
        name = raw_speaker.strip()
        for v in ACTION_VERBS:
            if name.endswith(v) and len(name) > len(v):
                name = name[:-len(v)].strip()
                break
        return name

    def breakdown_story_offline(self, raw_text: str, title: str = "短剧第一集", genre: str = "都市爽文") -> DramaProject:
        """离线/规则引擎：即使无网络或无 API Key，也能依据剧本句法自动拆解镜头与角色."""
        lines = [line.strip() for line in raw_text.strip().split("\n") if line.strip()]
        shots: List[Shot] = []
        characters_dict: Dict[str, CharacterAsset] = {}

        shot_id = 1
        for line in lines:
            if line.startswith("【") and line.endswith("】"):
                continue

            speaker = "旁白"
            dialogue = line

            # 匹配 角色名[动作]：台词 或 角色名:台词
            match = re.match(r"^([^：:\s]{1,16})[：:](.+)$", line)
            if match:
                raw_spk = match.group(1).strip()
                speaker = self._clean_speaker(raw_spk)
                dialogue = match.group(2).strip().strip("“”\"'")

            # 自动维护角色资产表
            if speaker != "旁白" and speaker not in characters_dict:
                is_female = any(w in speaker for w in ["女", "妹", "妻", "小姐", "姐"])
                characters_dict[speaker] = CharacterAsset(
                    name=speaker,
                    gender="female" if is_female else "male",
                    visual_tags=f"{speaker}, anime aesthetic, detailed face, sharp eyes, high contrast",
                    voice_name="zh-CN-XiaoxiaoNeural" if is_female else "zh-CN-YunxiNeural"
                )

            # 启发式影视导演规则：根据台词与语义智能决策景别和运镜
            scale = ShotScaleEnum.MEDIUM_SHOT
            motion = CameraMotionEnum.ZOOM_IN

            if any(w in dialogue for w in ["眼神", "怒视", "咬牙", "冷笑", "冷冽", "杀意", "死"]):
                scale = ShotScaleEnum.CLOSE_UP
                motion = CameraMotionEnum.ZOOM_IN
            elif any(w in dialogue for w in ["哈哈", "狂妄", "天际", "雷霆", "炸裂", "从天而降", "轰", "灭"]):
                scale = ShotScaleEnum.FULL_SHOT
                motion = CameraMotionEnum.SHAKE
            elif any(w in dialogue for w in ["大院", "天下", "四周", "远方", "整座城"]):
                scale = ShotScaleEnum.WIDE_SHOT
                motion = CameraMotionEnum.ZOOM_OUT
            elif speaker != "旁白":
                scale = ShotScaleEnum.MEDIUM_SHOT
                motion = CameraMotionEnum.PAN_RIGHT if shot_id % 2 == 0 else CameraMotionEnum.PAN_LEFT

            # 构造生图提示词
            visual_prompt = f"masterpiece, anime comic drama style, {scale.value}, {speaker} in scene, cinematic lighting, vibrant composition"

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
                visual_tags="young hero, determined expression, black hair",
                voice_name="zh-CN-YunxiNeural"
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
        """智能体导演调用：支持 DeepSeek / OpenAI 兼容接口，若未配置或失败则自动降级离线引擎."""
        target_key = api_key or self.api_key
        if not target_key or not api_base:
            return self.breakdown_story_offline(raw_text, title=title, genre=genre)

        try:
            url = f"{api_base.rstrip('/')}/chat/completions"
            headers = {"Authorization": f"Bearer {target_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
                    {"role": "user", "content": f"短剧标题: {title}\n题材: {genre}\n小说原文:\n{raw_text}"}
                ],
                "response_format": {"type": "json_object"}
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            if resp.status_code == 200:
                data = resp.json()
                content_str = data["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                return DramaProject.model_validate(parsed)
        except Exception:
            pass

        return self.breakdown_story_offline(raw_text, title=title, genre=genre)
