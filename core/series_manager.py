"""OmniDrama 连续剧与多剧集连载管理器 (Multi-Episode Series Manager).

支持长篇小说自动切集、跨剧集角色资产/声线永久一致性锁定、
剧集状态追踪 (草稿 -> 编剧 -> 分镜 -> 成片 -> 剪映工程) 以及多语言出海短剧配置。
"""
import os
import json
import re
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional


class SeriesManager:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or "./output/series")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.data_dir / "series_registry.json"
        self._ensure_init()

    def _ensure_init(self):
        """初始化剧目注册表，内置默认示范连续剧《至尊龙王归位》."""
        if not self.index_file.exists():
            default_registry = {
                "active_series_id": "series_longwang",
                "series": [
                    {
                        "id": "series_longwang",
                        "title": "至尊龙王归位",
                        "genre": "都市战神爽文",
                        "language": "zh",
                        "synopsis": "三年前至尊龙王退隐都市，入赘林家受尽冷眼；三年后逆鳞触动，十万战神破门叩首！",
                        "global_characters": [
                            {
                                "name": "叶辰 (主角)",
                                "role": "至尊龙王",
                                "voice": "云希 (磁性沉稳霸道)",
                                "traits": "黑发冷眸，修罗战神之主，隐藏滔天权势",
                                "avatar": "/output/至尊龙王归位/shots/shot_004.jpg"
                            },
                            {
                                "name": "岳母柳琴",
                                "role": "刁难反派",
                                "voice": "晓晓 (尖酸刻薄逼迫)",
                                "traits": "翡翠旗袍，拜金势力，豪门大堂",
                                "avatar": "/output/至尊龙王归位/shots/shot_002.jpg"
                            },
                            {
                                "name": "赵公子",
                                "role": "狂妄对手",
                                "voice": "云健 (嚣张跋扈)",
                                "traits": "定制西装，手持红酒，自傲恶少",
                                "avatar": "/output/至尊龙王归位/shots/shot_005.jpg"
                            }
                        ],
                        "episodes": [
                            {
                                "id": "ep_001",
                                "episode_num": 1,
                                "title": "第 1 集：入赘三年，怒拔逆鳞",
                                "status": "COMPLETED",  # DRAFT, STORYBOARD, COMPLETED
                                "duration": 61.61,
                                "shots_count": 10,
                                "video_url": "/output/至尊龙王归位/至尊龙王归位_影视级成片.mp4",
                                "live_actor_video": "/output/至尊龙王归位/真人演员_叶辰_会说话.mp4"
                            },
                            {
                                "id": "ep_002",
                                "episode_num": 2,
                                "title": "第 2 集：十万神将，跪迎龙王",
                                "status": "STORYBOARD",
                                "duration": 65.0,
                                "shots_count": 12,
                                "video_url": "",
                                "live_actor_video": ""
                            },
                            {
                                "id": "ep_003",
                                "episode_num": 3,
                                "title": "第 3 集：赵家覆灭，江城变天",
                                "status": "DRAFT",
                                "duration": 0.0,
                                "shots_count": 0,
                                "video_url": "",
                                "live_actor_video": ""
                            }
                        ]
                    }
                ]
            }
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(default_registry, f, ensure_ascii=False, indent=2)

    def get_registry(self) -> Dict[str, Any]:
        with open(self.index_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_registry(self, data: Dict[str, Any]):
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_series(self, series_id: str) -> Optional[Dict[str, Any]]:
        reg = self.get_registry()
        for s in reg.get("series", []):
            if s["id"] == series_id:
                return s
        return None

    def add_episode(self, series_id: str, title: str, text: str = "") -> Dict[str, Any]:
        """向指定剧目新增一集."""
        reg = self.get_registry()
        target_series = None
        for s in reg["series"]:
            if s["id"] == series_id:
                target_series = s
                break

        if not target_series:
            raise ValueError(f"Series {series_id} not found")

        ep_num = len(target_series["episodes"]) + 1
        ep_id = f"ep_{uuid.uuid4().hex[:6]}"
        new_ep = {
            "id": ep_id,
            "episode_num": ep_num,
            "title": f"第 {ep_num} 集：{title}",
            "status": "DRAFT",
            "duration": 0.0,
            "shots_count": 0,
            "story_text": text,
            "video_url": "",
            "live_actor_video": ""
        }
        target_series["episodes"].append(new_ep)
        self.save_registry(reg)
        return new_ep

    def auto_split_novel(self, novel_text: str, chars_per_episode: int = 600) -> List[Dict[str, str]]:
        """长篇小说智能分集算法：按章节标题或高潮张力字数自动切分成连续剧集."""
        # 1. 尝试按章节正则切分 (例如：第X章、Chapter X)
        chapter_pattern = r"(第[0-9一二三四五六七八九十百千]+章[^\n]*|Chapter\s+[0-9]+[^\n]*)"
        parts = re.split(chapter_pattern, novel_text)

        episodes = []
        if len(parts) > 2:
            # 成功按章节匹配
            current_title = "序章"
            for i in range(1, len(parts), 2):
                ch_title = parts[i].strip()
                ch_content = parts[i+1].strip() if i+1 < len(parts) else ""
                episodes.append({
                    "title": ch_title,
                    "content": ch_content
                })
        else:
            # 按字数与换行自然切分
            paragraphs = novel_text.split("\n")
            current_buf = []
            cur_len = 0
            ep_idx = 1
            for p in paragraphs:
                p_str = p.strip()
                if not p_str:
                    continue
                current_buf.append(p_str)
                cur_len += len(p_str)
                if cur_len >= chars_per_episode:
                    episodes.append({
                        "title": f"第 {ep_idx} 集：风云突起",
                        "content": "\n".join(current_buf)
                    })
                    current_buf = []
                    cur_len = 0
                    ep_idx += 1
            if current_buf:
                episodes.append({
                    "title": f"第 {ep_idx} 集：风云突起",
                    "content": "\n".join(current_buf)
                })

        return episodes
