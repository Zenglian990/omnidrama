"""OmniDrama 可视化导演工作台 Web 后端 (FastAPI)."""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

app = FastAPI(title="OmniDrama Studio (灵眸漫剧工作台)", version="1.0.0")

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
WEB_DIR = BASE_DIR / "web"
ASSETS_DIR = BASE_DIR / "assets"

# 挂载静态资源
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


class StoryRequest(BaseModel):
    title: str = "新短剧"
    genre: str = "都市热血"
    story_text: str


@app.get("/", response_class=HTMLResponse)
async def serve_studio():
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Studio frontend not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/project")
async def get_current_project():
    """获取当前最新短剧项目的完整分镜、资产与视频成片信息."""
    project_dir = OUTPUT_DIR / "至尊龙王归位"
    shots_dir = project_dir / "shots"

    shots = [
        {
            "id": 1,
            "speaker": "旁白",
            "scale": "WIDE_SHOT",
            "motion": "ZOOM_IN",
            "motion_name": "镜头推进",
            "dialogue": "林家祖宅大堂，狂风骤雨拍打着雕花木窗。",
            "image": "/output/至尊龙王归位/shots/shot_001.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_001.mp3",
            "sfx": "暴雨环境音"
        },
        {
            "id": 2,
            "speaker": "岳母柳琴",
            "scale": "MEDIUM_SHOT",
            "motion": "PAN_LEFT",
            "motion_name": "向左横移",
            "dialogue": "叶辰，入赘三年，今日若拿不出三千万，就立刻滚出林家！",
            "image": "/output/至尊龙王归位/shots/shot_002.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_002.mp3",
            "sfx": "无"
        },
        {
            "id": 3,
            "speaker": "旁白",
            "scale": "CLOSE_UP",
            "motion": "ZOOM_IN",
            "motion_name": "镜头推进",
            "dialogue": "叶辰神色淡然，深邃的双眸中隐现寒光。",
            "image": "/output/至尊龙王归位/shots/shot_003.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_003.mp3",
            "sfx": "无"
        },
        {
            "id": 4,
            "speaker": "叶辰",
            "scale": "CLOSE_UP",
            "motion": "ZOOM_IN",
            "motion_name": "镜头推进",
            "dialogue": "三千万？当年若非我暗中相助，林家早在三年前就已灰飞烟灭！",
            "image": "/output/至尊龙王归位/shots/shot_004.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_004.mp3",
            "sfx": "疾风起势 (Whoosh)"
        },
        {
            "id": 5,
            "speaker": "赵公子",
            "scale": "MEDIUM_SHOT",
            "motion": "ZOOM_OUT",
            "motion_name": "镜头拉远",
            "dialogue": "哈哈哈！大言不惭的废物，也不撒泡尿照照自己是个什么东西！",
            "image": "/output/至尊龙王归位/shots/shot_005.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_005.mp3",
            "sfx": "无"
        },
        {
            "id": 6,
            "speaker": "旁白",
            "scale": "FULL_SHOT",
            "motion": "SHAKE",
            "motion_name": "镜头震撼",
            "dialogue": "突然，天地间惊雷滚滚，整座大堂剧烈震颤！",
            "image": "/output/至尊龙王归位/shots/shot_006.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_006.mp3",
            "sfx": "惊雷劈裂 (Thunder)"
        },
        {
            "id": 7,
            "speaker": "旁白",
            "scale": "FULL_SHOT",
            "motion": "ZOOM_OUT",
            "motion_name": "镜头拉远",
            "dialogue": "大门轰然破碎，十八位身披黑金战铠的修罗战神破门而入！",
            "image": "/output/至尊龙王归位/shots/shot_007.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_007.mp3",
            "sfx": "重低音轰鸣 (Impact)"
        },
        {
            "id": 8,
            "speaker": "修罗战神",
            "scale": "CLOSE_UP",
            "motion": "ZOOM_IN",
            "motion_name": "镜头推进",
            "dialogue": "恭迎龙王回归！十万修罗殿众将，随时听候调遣！",
            "image": "/output/至尊龙王归位/shots/shot_008.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_008.mp3",
            "sfx": "金铁下跪 (Armor)"
        },
        {
            "id": 9,
            "speaker": "岳母与赵公子",
            "scale": "MEDIUM_SHOT",
            "motion": "SHAKE",
            "motion_name": "镜头震撼",
            "dialogue": "龙……龙王？！你竟然是那位镇守北境的至尊龙王！",
            "image": "/output/至尊龙王归位/shots/shot_009.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_009.mp3",
            "sfx": "无"
        },
        {
            "id": 10,
            "speaker": "叶辰",
            "scale": "EXTREME_CLOSE_UP",
            "motion": "ZOOM_IN",
            "motion_name": "镜头推进",
            "dialogue": "犯我逆鳞者，杀无赦！",
            "image": "/output/至尊龙王归位/shots/shot_010.jpg",
            "audio": "/output/至尊龙王归位/shots/shot_010.mp3",
            "sfx": "终极大爆炸 (Impact)"
        }
    ]

    characters = [
        {
            "name": "叶辰 (主角)",
            "role": "至尊龙王",
            "voice": "云希 (磁性沉稳霸道)",
            "avatar": "/output/至尊龙王归位/shots/shot_004.jpg",
            "traits": "黑发冷眸，修罗战神之主，隐藏滔天权势"
        },
        {
            "name": "岳母柳琴",
            "role": "刁难反派",
            "voice": "晓晓 (尖酸刻薄逼迫)",
            "avatar": "/output/至尊龙王归位/shots/shot_002.jpg",
            "traits": "翡翠旗袍，拜金势力，豪门大堂"
        },
        {
            "name": "赵公子",
            "role": "狂妄对手",
            "voice": "云健 (嚣张跋扈)",
            "avatar": "/output/至尊龙王归位/shots/shot_005.jpg",
            "traits": "定制西装，手持红酒，自傲恶少"
        }
    ]

    return {
        "title": "至尊龙王归位",
        "genre": "都市战神爽文",
        "video_url": "/output/至尊龙王归位/至尊龙王归位_影视级成片.mp4",
        "live_actor_video": "/output/至尊龙王归位/真人演员_叶辰_会说话.mp4",
        "srt_url": "/output/至尊龙王归位/至尊龙王归位.srt",
        "duration": 61.61,
        "characters": characters,
        "shots": shots,
        "audio_tracks": [
            {"track": "人声对白轨", "status": "已对齐", "source": "Edge-TTS 神经网络多音色"},
            {"track": "拟音音效轨 (SFX)", "status": "已注入", "source": "暴雨 + 惊雷 + 破门轰鸣 + 金铁下跪"},
            {"track": "电影配乐轨 (BGM)", "status": "已卡点", "source": "战神觉醒史诗管弦交响"}
        ]
    }
