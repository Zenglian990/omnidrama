"""OmniDrama Pexels 免费高清无版权视频与图片素材检索驱动 (对标 MoneyPrinterTurbo).

用户只需在 https://www.pexels.com/api/ 免费注册即可获得 API Key（0元、免绑卡），
系统可根据分镜关键词自动检索并下载 9:16 竖屏高清实拍动态视频或高清剧照。
"""
from __future__ import annotations

import os
import requests
from typing import Optional


class PexelsProvider:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or os.environ.get("PEXELS_API_KEY", "")).strip()

    def search_and_download_photo(
        self,
        query: str,
        output_path: str,
        orientation: str = "portrait"
    ) -> Optional[str]:
        """从 Pexels 检索并下载匹配的竖屏高清图片."""
        if not self.api_key:
            return None

        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": self.api_key}
        params = {
            "query": query or "cinematic dramatic portrait",
            "orientation": orientation,
            "per_page": 5,
            "size": "large"
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            if not photos:
                return None
            src_Obj = photos[0].get("src", {})
            img_url = src_Obj.get("portrait") or src_Obj.get("large2x") or src_Obj.get("large")
            if not img_url:
                return None

            img_resp = requests.get(img_url, timeout=30)
            img_resp.raise_for_status()
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(img_resp.content)
            return output_path
        except Exception:
            return None

    def search_and_download_video(
        self,
        query: str,
        output_path: str,
        orientation: str = "portrait"
    ) -> Optional[str]:
        """从 Pexels 检索并下载匹配的竖屏高清动态视频片段."""
        if not self.api_key:
            return None

        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.api_key}
        params = {
            "query": query or "cinematic city night rain",
            "orientation": orientation,
            "per_page": 5,
            "size": "medium"
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=25)
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            if not videos:
                return None

            video_files = videos[0].get("video_files", [])
            best_link = None
            for vf in video_files:
                if vf.get("file_type") == "video/mp4" and (vf.get("height", 0) >= 720):
                    best_link = vf.get("link")
                    break
            if not best_link and video_files:
                best_link = video_files[0].get("link")
            if not best_link:
                return None

            vid_resp = requests.get(best_link, timeout=60)
            vid_resp.raise_for_status()
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(vid_resp.content)
            return output_path
        except Exception:
            return None
