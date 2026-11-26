"""OmniDrama 连续剧与多剧集连载管理器 (Multi-Episode Series Manager).

支持长篇小说自动切集、跨剧集角色资产/声线永久一致性锁定、
剧集状态追踪 (草稿 -> 编剧 -> 分镜 -> 成片 -> 剪映工程) 以及多语言出海短剧配置。
"""
from __future__ import annotations

import os
import json
import re
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from core.storage import atomic_write_json, safe_read_json
except ImportError:
    from omnidrama.core.storage import atomic_write_json, safe_read_json


class SeriesManager:
    def __init__(self, data_dir: Optional[str] = None):
        default_dir = Path(__file__).resolve().parent.parent / "output" / "series"
        self.data_dir = Path(data_dir) if data_dir else default_dir
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
                                "avatar": "/assets/cinematic_actors/actor_yileng.jpg"
                            },
                            {
                                "name": "岳母柳琴",
                                "role": "刁难反派",
                                "voice": "晓晓 (尖酸刻薄逼迫)",
                                "traits": "翡翠旗袍，拜金势力，豪门大堂",
                                "avatar": "/assets/cinematic_actors/actor_yinuannuan.jpg"
                            },
                            {
                                "name": "赵公子",
                                "role": "狂妄对手",
                                "voice": "云健 (嚣张跋扈)",
                                "traits": "定制西装，手持红酒，自傲恶少",
                                "avatar": "/assets/cinematic_actors/actor_scar_gangster.jpg"
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
                                "video_url": "/api/video/stream?mode=full",
                                "live_actor_video": "/api/video/stream?mode=live"
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
            atomic_write_json(self.index_file, default_registry)

    def get_registry(self) -> Dict[str, Any]:
        data = safe_read_json(self.index_file)
        if not isinstance(data, dict):
            self._ensure_init()
            data = safe_read_json(self.index_file, default={"active_series_id": "", "series": []})
        return data

    def save_registry(self, data: Dict[str, Any]):
        atomic_write_json(self.index_file, data)

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

    def save_split_episodes(
        self,
        episodes: List[Dict[str, str]],
        series_id: Optional[str] = None,
        series_title: Optional[str] = None,
        genre: str = "都市战神爽文",
    ) -> Dict[str, Any]:
        """将小说自动切分结果真实持久化写入剧集注册表，并返回新增分集与最新注册表."""
        reg = self.get_registry()
        target_series = None

        if series_title and series_title.strip():
            clean_title = series_title.strip()
            for s in reg.get("series", []):
                if s.get("title") == clean_title:
                    target_series = s
                    break
            if not target_series:
                new_sid = f"series_{uuid.uuid4().hex[:8]}"
                target_series = {
                    "id": new_sid,
                    "title": clean_title,
                    "genre": genre or "都市战神爽文",
                    "language": "zh",
                    "synopsis": (episodes[0].get("content", "")[:120] if episodes else ""),
                    "global_characters": [],
                    "episodes": [],
                }
                reg.setdefault("series", []).append(target_series)
                reg["active_series_id"] = new_sid

        if not target_series and series_id:
            for s in reg.get("series", []):
                if s.get("id") == series_id:
                    target_series = s
                    break

        if not target_series:
            active_id = reg.get("active_series_id")
            for s in reg.get("series", []):
                if s.get("id") == active_id:
                    target_series = s
                    break
            if not target_series and reg.get("series"):
                target_series = reg["series"][0]

        saved_eps: List[Dict[str, Any]] = []
        base_num = len(target_series.get("episodes", []))
        for idx, ep in enumerate(episodes, start=1):
            ep_num = base_num + idx
            ep_id = f"ep_{uuid.uuid4().hex[:6]}"
            raw_title = (ep.get("title") or f"第 {ep_num} 集").strip()
            if not raw_title.startswith("第"):
                raw_title = f"第 {ep_num} 集：{raw_title}"
            new_ep = {
                "id": ep_id,
                "episode_num": ep_num,
                "title": raw_title,
                "status": "DRAFT",
                "duration": 0.0,
                "shots_count": 0,
                "story_text": (ep.get("content") or "").strip(),
                "video_url": "",
                "live_actor_video": "",
            }
            target_series.setdefault("episodes", []).append(new_ep)
            saved_eps.append(new_ep)

        reg["active_series_id"] = target_series["id"]
        self.save_registry(reg)
        return {
            "series": target_series,
            "saved_episodes": saved_eps,
            "registry": reg,
        }

    def find_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """根据分集 ID 查找对应的剧目与分集元数据."""
        reg = self.get_registry()
        for s in reg.get("series", []):
            for ep in s.get("episodes", []):
                if ep.get("id") == episode_id:
                    return {"series": s, "episode": ep}
        return None

    def update_episode_meta(
        self,
        episode_id: str,
        shots_count: Optional[int] = None,
        duration: Optional[float] = None,
        status: Optional[str] = None,
        title: Optional[str] = None,
        story_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """同步更新指定分集的真实镜数、时长与状态."""
        reg = self.get_registry()
        for s in reg.get("series", []):
            for ep in s.get("episodes", []):
                if ep.get("id") == episode_id:
                    if shots_count is not None:
                        ep["shots_count"] = int(shots_count)
                    if duration is not None:
                        ep["duration"] = round(float(duration), 2)
                    if status is not None:
                        ep["status"] = status
                    if title is not None and title.strip():
                        ep["title"] = title.strip()
                    if story_text is not None:
                        ep["story_text"] = story_text
                    self.save_registry(reg)
                    return ep
        return None

    def get_episode_project_file(self, episode_id: str) -> Path:
        """返回分集独立工程状态 JSON 路径."""
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", episode_id or "default")
        ep_dir = self.data_dir / "episodes"
        ep_dir.mkdir(parents=True, exist_ok=True)
        return ep_dir / f"{safe_id}.json"

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
