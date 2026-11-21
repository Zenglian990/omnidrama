"""OmniDrama 可视化导演工作台 Web 后端 (FastAPI - v1.5.0 安全加固版)."""
import asyncio
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

import types

BASE_DIR = Path(__file__).parent.parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

# 彻底根治 Docker/Cloud Run 容器中由于根目录挂载导致的 No module named 'omnidrama'：
# 注册虚拟 omnidrama 包对象，让所有 'from omnidrama.xxx' 随时随地直接解析至根工程目录
if 'omnidrama' not in sys.modules:
    _omnidrama_mod = types.ModuleType('omnidrama')
    _omnidrama_mod.__path__ = [str(BASE_DIR)]
    _omnidrama_mod.__file__ = str(BASE_DIR / '__init__.py')
    sys.modules['omnidrama'] = _omnidrama_mod
OUTPUT_DIR = BASE_DIR / "output"
WEB_DIR = BASE_DIR / "web"
ASSETS_DIR = BASE_DIR / "assets"

# 确保 Windows Winget FFmpeg 路径注入系统 PATH
FFMPEG_WINGET_BIN = r"C:\Users\Asus\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin"
if os.path.exists(FFMPEG_WINGET_BIN) and FFMPEG_WINGET_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = FFMPEG_WINGET_BIN + os.pathsep + os.environ.get("PATH", "")

from core.runtime_context import (
    MANAGED_PROVIDER_KEYS,
    get_provider_key,
    save_runtime_managed_keys,
    scoped_api_keys,
    validate_api_keys_dict,
)
from core.security import (
    _safe_resolve_under,
    _safe_slug,
    build_safe_concat_file,
    has_path_traversal_markers,
    is_public_request,
    validate_safe_path_param,
    verify_bearer_token,
)
from core.net_safety import (
    MAX_IMAGE_BYTES,
    MAX_VIDEO_BYTES,
    UnsafeURLError,
    safe_download_to_file,
    validate_fanqie_id,
    validate_safe_public_https_url,
)

app = FastAPI(title="OmniDrama 灵眸漫剧工作台", version="1.5.0")


@app.middleware("http")
async def api_auth_middleware(request: Request, call_next):
    """全站统一 Bearer Token 鉴权中间件（未配置 API_AUTH_TOKEN 时 Fail-Closed）."""
    if request.method.upper() == "OPTIONS":
        return await call_next(request)
    if is_public_request(request.method, request.url.path):
        return await call_next(request)
    if not verify_bearer_token(request.headers.get("Authorization")):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: invalid or missing Bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await call_next(request)

# 核心导演与基础工具（100% 独立引入，绝对保障可用）
try:
    from core.cost_tracker import CostTracker, DecisionLog
except Exception:
    try:
        from omnidrama.core.cost_tracker import CostTracker, DecisionLog
    except Exception:
        pass

try:
    from schemas.drama_schema import CameraMotionEnum, Shot, ShotScaleEnum
except Exception:
    try:
        from omnidrama.schemas.drama_schema import CameraMotionEnum, Shot, ShotScaleEnum
    except Exception:
        pass

try:
    from core.quality_gate import auto_optimize_storyboard, verify_rendered_video
except Exception:
    try:
        from omnidrama.core.quality_gate import auto_optimize_storyboard, verify_rendered_video
    except Exception:
        pass

try:
    from core.audio_mixer import AudioMixer
except Exception:
    try:
        from omnidrama.core.audio_mixer import AudioMixer
    except Exception:
        pass

try:
    from core.compositor import VideoCompositor
except Exception:
    try:
        from omnidrama.core.compositor import VideoCompositor
    except Exception:
        pass

try:
    from core.director import DirectorAgent
except Exception:
    try:
        from omnidrama.core.director import DirectorAgent
    except Exception:
        pass

try:
    from core.tts_engine import TTSEngine
except Exception:
    try:
        from omnidrama.core.tts_engine import TTSEngine
    except Exception:
        pass

# 可选高阶 AI 模型 Provider（独立隔离，互不影响）
try:
    from providers.elevenlabs_provider import ElevenLabsProvider
except Exception:
    try:
        from omnidrama.providers.elevenlabs_provider import ElevenLabsProvider
    except Exception:
        ElevenLabsProvider = None

try:
    from providers.siliconflow_provider import SiliconFlowProvider
except Exception:
    try:
        from omnidrama.providers.siliconflow_provider import SiliconFlowProvider
    except Exception:
        SiliconFlowProvider = None

try:
    from providers.dashscope_provider import DashScopeProvider
except Exception:
    try:
        from omnidrama.providers.dashscope_provider import DashScopeProvider
    except Exception:
        DashScopeProvider = None

try:
    from providers.liveportrait_provider import LivePortraitProvider
except Exception:
    try:
        from omnidrama.providers.liveportrait_provider import LivePortraitProvider
    except Exception:
        LivePortraitProvider = None

try:
    from providers.f5_tts_provider import F5TTSProvider
except Exception:
    try:
        from omnidrama.providers.f5_tts_provider import F5TTSProvider
    except Exception:
        F5TTSProvider = None

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

_actors_dir = ASSETS_DIR / "cinematic_actors"
_actors_dir.mkdir(parents=True, exist_ok=True)
app.mount("/assets/cinematic_actors", StaticFiles(directory=str(_actors_dir)), name="cinematic_actors")


class StoryRequest(BaseModel):
    title: str = "新短剧"
    genre: str = "都市热血"
    story_text: str


@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "omnidrama"}


@app.get("/download/apk")
@app.get("/omnidrama.apk")
async def download_apk():
    apk_path = ASSETS_DIR / "omnidrama.apk"
    if apk_path.exists():
        return FileResponse(
            str(apk_path),
            media_type="application/vnd.android.package-archive",
            filename="OmniDrama_v3.3.0.apk"
        )
    raise HTTPException(status_code=404, detail="Release APK not found on server")


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def serve_studio():
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Studio frontend not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()


PROJECT_STATE_FILE = OUTPUT_DIR / "current_project.json"

RENDER_STATE = {
    "is_rendering": False,
    "progress": 0,
    "step_index": 0,
    "total_steps": 5,
    "current_step": "就绪",
    "logs": [
        "制片机房就绪，等待下达真实 AI 导演制作指令..."
    ],
    "video_url": "/api/video/stream?mode=full",
    "error": None
}


def _now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _mask_key(val: str) -> str:
    return "已配置" if (val or "").strip() else ""


def _load_project_data() -> Dict[str, Any]:
    if PROJECT_STATE_FILE.exists():
        try:
            with open(PROJECT_STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                title = d.get("title", "").strip()
                shots_raw = d.get("shots", [])
                if shots_raw:
                    try:
                        try:
                            from omnidrama.providers.fanqie_provider import FanqieProvider
                        except ImportError:
                            from providers.fanqie_provider import FanqieProvider
                        cleaned_shots = []
                        for s in shots_raw:
                            dlg = FanqieProvider.decode_pua(str(s.get("dialogue", ""))).strip()
                            beat = FanqieProvider.decode_pua(str(s.get("action_beat", ""))).strip()
                            if dlg in ("。", "，", ".") and not beat:
                                continue
                            s["dialogue"] = dlg
                            cleaned_shots.append(s)
                        if cleaned_shots:
                            d["shots"] = cleaned_shots
                    except Exception:
                        pass
                if title:
                    safe_title = _safe_slug(title, default="untitled")
                    try:
                        final_mp4 = _safe_resolve_under(OUTPUT_DIR, safe_title, f"{safe_title}_影视级成片.mp4")
                        srt_p = _safe_resolve_under(OUTPUT_DIR, safe_title, f"{safe_title}.srt")
                    except ValueError:
                        final_mp4 = None
                        srt_p = None
                    d["video_url"] = "/api/video/stream?mode=full" if (final_mp4 and final_mp4.exists()) else ""
                    d["live_actor_video"] = "/api/video/stream?mode=live" if (final_mp4 and final_mp4.exists()) else ""
                    if srt_p and srt_p.exists():
                        d["srt_url"] = "/api/project/subtitles"
                    elif isinstance(d.get("srt_url"), str) and d["srt_url"].startswith("/output/"):
                        d["srt_url"] = "/api/project/subtitles"
                else:
                    d["video_url"] = ""
                    d["live_actor_video"] = ""
                for s in d.get("shots", []):
                    if "visual_prompt" not in s or not s["visual_prompt"]:
                        s["visual_prompt"] = f"masterpiece, 8k vertical cinema drama, {s.get('speaker', 'character')}, {s.get('dialogue', '')}, cinematic lighting"
                return d
        except Exception:
            pass

    # 默认空白工程：绝不预置任何固定小说，完全由创作者自主添加或从番茄小说导入
    empty_data = {
        "title": "",
        "genre": "",
        "video_url": "",
        "live_actor_video": "",
        "srt_url": "",
        "duration": 0.0,
        "characters": [],
        "shots": [],
        "audio_tracks": []
    }
    return empty_data


def _save_project_data(data: Dict[str, Any]):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROJECT_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.get("/api/project")
async def get_current_project():
    """获取当前最新短剧项目的完整分镜、资产与视频成片信息."""
    return _load_project_data()


def _resolve_current_video_file(mode: str = "full") -> Path:
    data = _load_project_data()
    title = data.get("title", "").strip()
    if title:
        safe_title = _safe_slug(title, default="untitled")
        if mode == "live":
            live_p = _safe_resolve_under(OUTPUT_DIR, safe_title, f"{safe_title}_真人活化版.mp4")
            if live_p.exists():
                return live_p
        p = _safe_resolve_under(OUTPUT_DIR, safe_title, f"{safe_title}_影视级成片.mp4")
        if p.exists():
            return p
        raise HTTPException(status_code=404, detail=f"作品《{safe_title}》尚未渲染生成视频成片")
    raise HTTPException(status_code=404, detail="当前作品尚未渲染生成视频成片")


@app.get("/api/video/stream")
async def stream_current_video(mode: str = "full"):
    """流式传输当前视频，支持 HTTP Range 与直接播放."""
    p = _resolve_current_video_file(mode)
    return FileResponse(str(p), media_type="video/mp4")


@app.get("/api/video/download")
async def download_current_video(mode: str = "full"):
    """供手机端或浏览器一键下载 MP4 成片到本地相册/目录."""
    data = _load_project_data()
    safe_title = _safe_slug(data.get("title", "").strip(), default="AI短剧作品")
    p = _resolve_current_video_file(mode)
    suffix = "真人活化版" if mode == "live" else "成片"
    return FileResponse(
        str(p),
        media_type="video/mp4",
        filename=f"{safe_title}_{suffix}.mp4"
    )


@app.get("/api/project/subtitles")
async def get_project_subtitles():
    """受鉴权保护：读取当前工程 SRT 字幕文件."""
    data = _load_project_data()
    raw_title = (data.get("title") or "").strip()
    if not raw_title:
        raise HTTPException(status_code=404, detail="当前工程未生成字幕文件")
    safe_title = _safe_slug(raw_title, default="untitled")
    try:
        srt_path = _safe_resolve_under(OUTPUT_DIR, safe_title, f"{safe_title}.srt")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not srt_path.exists():
        raise HTTPException(status_code=404, detail="字幕文件尚未生成")
    return FileResponse(str(srt_path), media_type="text/plain; charset=utf-8")


class ShotAudioGenerateRequest(BaseModel):
    text: Optional[str] = None
    speaker: Optional[str] = None


@app.get("/api/shots/{shot_id}/audio")
async def get_shot_audio(shot_id: int):
    """严格只读获取指定分镜已生成的配音音频（绝不创建目录或触发 TTS 合成）."""
    data = _load_project_data()
    safe_title = _safe_slug(data.get("title", ""), default="temp_preview")
    try:
        audio_path = _safe_resolve_under(OUTPUT_DIR, safe_title, "shots", f"shot_{shot_id:03d}.mp3")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise HTTPException(
            status_code=404,
            detail="Audio not generated yet. Use PUT /api/shots/{shot_id} or POST /api/shots/{shot_id}/audio.",
        )
    return FileResponse(str(audio_path), media_type="audio/mpeg")


@app.post("/api/shots/{shot_id}/audio")
async def generate_shot_audio(shot_id: int, req: Optional[ShotAudioGenerateRequest] = None):
    """显式触发指定分镜配音音频合成并落盘."""
    data = _load_project_data()
    safe_title = _safe_slug(data.get("title", ""), default="temp_preview")
    try:
        shots_dir = _safe_resolve_under(OUTPUT_DIR, safe_title, "shots")
        audio_path = _safe_resolve_under(shots_dir, f"shot_{shot_id:03d}.mp3")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    shots_dir.mkdir(parents=True, exist_ok=True)

    target_shot = None
    for s in data.get("shots", []):
        if int(s.get("id", 0)) == shot_id:
            target_shot = s
            break

    dialogue_text = ((req.text if req else None) or (target_shot.get("dialogue", "") if target_shot else "")).strip()
    speaker_name = ((req.speaker if req else None) or (target_shot.get("speaker", "旁白") if target_shot else "旁白")).strip()
    if not dialogue_text:
        raise HTTPException(status_code=400, detail="配音台词不能为空")

    try:
        from omnidrama.core.tts_engine import TTSEngine
    except ImportError:
        from core.tts_engine import TTSEngine
    tts_engine = TTSEngine()
    voice_code = _resolve_character_voice_code(speaker_name, data.get("characters", []), data.get("genre", ""))
    await tts_engine.generate_speech(
        text=dialogue_text,
        voice=voice_code,
        output_path=str(audio_path)
    )
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail=f"Failed to synthesize audio for shot {shot_id}")
    return FileResponse(str(audio_path), media_type="audio/mpeg")


@app.get("/api/shots/{shot_id}/image")
async def get_shot_image(shot_id: int):
    """严格只读获取指定分镜已生成的剧照立绘（绝不创建目录或触发 AI 生图）."""
    data = _load_project_data()
    safe_title = _safe_slug(data.get("title", ""), default="temp_preview")
    try:
        img_path = _safe_resolve_under(OUTPUT_DIR, safe_title, "shots", f"shot_{shot_id:03d}.jpg")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not img_path.exists() or img_path.stat().st_size == 0:
        raise HTTPException(
            status_code=404,
            detail="Image not generated yet. Use POST /api/project/render or POST /api/shots/{shot_id}/image.",
        )
    return FileResponse(str(img_path), media_type="image/jpeg")


@app.post("/api/shots/{shot_id}/image")
async def generate_shot_image(shot_id: int):
    """显式触发指定分镜剧照立绘绘制并落盘."""
    data = _load_project_data()
    safe_title = _safe_slug(data.get("title", ""), default="temp_preview")
    try:
        shots_dir = _safe_resolve_under(OUTPUT_DIR, safe_title, "shots")
        img_path = _safe_resolve_under(shots_dir, f"shot_{shot_id:03d}.jpg")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    shots_dir.mkdir(parents=True, exist_ok=True)
    target_shot = None
    for s in data.get("shots", []):
        if int(s.get("id", 0)) == shot_id:
            target_shot = s
            break
    if not target_shot:
        raise HTTPException(status_code=404, detail=f"Shot {shot_id} not found")
    await _generate_single_shot_visual(target_shot, shots_dir)
    if not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Image for shot {shot_id} not found")
    return FileResponse(str(img_path), media_type="image/jpeg")


class RenderRequest(BaseModel):
    title: Optional[str] = ""
    genre: Optional[str] = ""
    novel_text: Optional[str] = ""
    shots: Optional[List[Dict[str, Any]]] = None
    characters: Optional[List[Dict[str, Any]]] = None
    api_keys: Optional[Dict[str, str]] = None


@app.get("/api/project/render-status")
async def get_render_status():
    """获取 AI 制片机房实时渲染阶段与日志进度."""
    return RENDER_STATE


def _load_cjk_font(size: int):
    """跨平台加载中文字体 (支持 Windows / Linux Docker / macOS)."""
    from PIL import ImageFont
    candidates = [
        str(ASSETS_DIR / "fonts" / "NotoSansSC-Bold.otf"),
        str(ASSETS_DIR / "fonts" / "msyh.ttc"),
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _pick_source_manga_image(speaker: str, shot_id: int, title: str = "", genre: str = "") -> Path:
    """为影视镜头精准匹配 100% 电影级真人演员剧照（角色严格锁定，杜绝换脸与跨题材串画）."""
    actors_dir = ASSETS_DIR / "cinematic_actors"

    # 仅在题材或剧名明确属于《特工易冷》或战神动作题材时，才使用特工剧照
    is_te_gong = any(k in (title + genre + speaker) for k in ["易冷", "特工", "战神", "雇佣兵", "龙王", "修罗"])

    if is_te_gong:
        if any(k in speaker for k in ["易冷", "特工", "战神", "主角", "男主"]):
            yileng = actors_dir / "actor_yileng.jpg"
            if yileng.exists():
                return yileng
        if any(k in speaker for k in ["暖暖", "女儿", "小女孩", "女孩", "小妹", "妹", "童", "女"]):
            nuannuan = actors_dir / "actor_yinuannuan.jpg"
            if nuannuan.exists():
                return nuannuan
        if any(k in speaker for k in ["恶霸", "反派", "刀疤", "打手", "混混", "泼皮", "流氓", "坏人"]):
            gangster = actors_dir / "actor_scar_gangster.jpg"
            if gangster.exists():
                return gangster
        if "旁白" in speaker or not speaker:
            if shot_id <= 2:
                scene_rain = actors_dir / "scene_rain_alley.jpg"
                if scene_rain.exists():
                    return scene_rain
            else:
                scene_fight = actors_dir / "scene_fight_action.jpg"
                if scene_fight.exists():
                    return scene_fight

    # 非特工题材：生成/获取题材匹配的纯净电影构图底图，严禁套用雨夜特工打斗图
    proc_dir = ASSETS_DIR / "procedural"
    proc_dir.mkdir(parents=True, exist_ok=True)
    slug_genre = "romance" if any(k in genre for k in ["甜宠", "言情", "现言", "古言", "恋爱", "青春"]) else "general"
    procedural_card = proc_dir / f"{slug_genre}_shot_{shot_id:02d}.jpg"
    if not procedural_card.exists():
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (720, 1280), (28, 20, 36) if slug_genre == "romance" else (14, 18, 28))
        draw = ImageDraw.Draw(im)
        draw.rectangle([(0, 0), (720, 1280)], fill=(20, 14, 28) if slug_genre == "romance" else (12, 16, 26))
        for i in range(128):
            y = int(500 + i * 4)
            draw.line([(0, y), (720, y)], fill=(35 + int(i * 0.3), 20, 45) if slug_genre == "romance" else (10, 20 + int(i * 0.3), 35))
        im.save(procedural_card, "JPEG", quality=92)
    return procedural_card


def _create_subtitle_overlay_png(
    shot_id: int,
    speaker: str,
    dialogue: str,
    motion_name: str,
    out_png_path: str
) -> str:
    """生成 720x1280 RGBA 全透明字幕与顶部徽标叠加层 (用于 FFmpeg 运镜后固定叠加，绝不放大裁切)."""
    from PIL import Image, ImageDraw
    target_w, target_h = 720, 1280

    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 底部字幕渐变黑透遮罩
    gradient_top = target_h - 245
    for y in range(gradient_top, target_h):
        alpha = int(235 * ((y - gradient_top) / (target_h - gradient_top)))
        draw.line([(0, y), (target_w, y)], fill=(8, 10, 18, alpha))

    badge_font = _load_cjk_font(20)
    speaker_font = _load_cjk_font(26)
    dialogue_font = _load_cjk_font(30)

    # 顶部镜头徽标 (固定在左上角安全区)
    badge_text = f"第 {shot_id:02d} 镜 · {motion_name}"
    draw.rounded_rectangle([20, 20, 250, 56], radius=8, fill=(10, 14, 26, 205))
    draw.text((32, 26), badge_text, font=badge_font, fill=(0, 220, 255, 255))

    # 底部角色名标签
    speaker_color = (255, 215, 0, 255) if speaker in ["叶辰", "主角"] else (
        (255, 105, 105, 255) if any(w in speaker for w in ["赵", "母", "反派"]) else (100, 220, 255, 255)
    )
    draw.text((40, target_h - 190), f"【{speaker}】", font=speaker_font, fill=speaker_color)

    # 底部描边中文字幕 (固定居中安全区)
    max_chars_per_line = 18
    dialogue_lines = [dialogue[i:i + max_chars_per_line] for i in range(0, len(dialogue), max_chars_per_line)][:3]
    line_y = target_h - 142
    for line in dialogue_lines:
        for ox, oy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((40 + ox, line_y + oy), line, font=dialogue_font, fill=(0, 0, 0, 255))
        draw.text((40, line_y), line, font=dialogue_font, fill=(255, 255, 255, 255))
        line_y += 38

    overlay.save(out_png_path, "PNG")
    return out_png_path


def _prepare_clean_background_and_preview(
    source_img_path: Path,
    shot_id: int,
    speaker: str,
    dialogue: str,
    motion_name: str,
    raw_bg_path: str,
    sub_png_path: str,
    preview_jpg_path: str,
    is_fallback_portrait: bool = False
):
    """生成纯净无字 720x1280 背景图 (raw_bg_path)、透明字幕层 (sub_png_path) 以及卡片预览图 (preview_jpg_path)."""
    from PIL import Image, ImageDraw, ImageEnhance
    target_w, target_h = 720, 1280
    os.makedirs(os.path.dirname(os.path.abspath(raw_bg_path)), exist_ok=True)

    with Image.open(source_img_path) as im:
        im = im.convert("RGB")
        # 若使用的是本地基础立绘兜底，根据 shot_id 进行差异化景别裁剪与电影色调滤镜，避免每镜画面雷同
        zoom_boost = 1.0 + ((shot_id % 4) * 0.08) if is_fallback_portrait else 1.0
        scale = max(target_w / im.width, target_h / im.height) * zoom_boost
        new_w = int(im.width * scale)
        new_h = int(im.height * scale)
        im_resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)

        offset_x = ((shot_id * 37) % max(1, new_w - target_w)) if is_fallback_portrait and new_w > target_w else (new_w - target_w) // 2
        offset_y = ((shot_id * 23) % max(1, (new_h - target_h) // 2)) if is_fallback_portrait and new_h > target_h else (new_h - target_h) // 2
        frame = im_resized.crop((offset_x, offset_y, offset_x + target_w, offset_y + target_h))

    if is_fallback_portrait:
        # 注入温和的电影级色调滤镜，不绘制突兀的放射线条
        tint_palettes = [
            (15, 30, 65, 35),   # 冷峻夜雨蓝
            (55, 15, 25, 35),   # 压迫猩红
            (50, 38, 10, 30),   # 帝王黑金
            (15, 45, 45, 30),   # 寒芒青灰
            (40, 15, 55, 35),   # 雷霆紫电
        ]
        tint_rgba = tint_palettes[(shot_id - 1) % len(tint_palettes)]
        tint_layer = Image.new("RGBA", (target_w, target_h), tint_rgba)
        frame_rgba = frame.convert("RGBA")
        frame_rgba = Image.alpha_composite(frame_rgba, tint_layer)
        frame = frame_rgba.convert("RGB")
        frame = ImageEnhance.Contrast(frame).enhance(1.06)

    # 1. 保存纯净无字的背景图供 FFmpeg 2.5D 运镜使用
    frame.save(raw_bg_path, quality=95)

    # 2. 生成全透明 RGBA 字幕层供 FFmpeg 顶层固定叠加
    _create_subtitle_overlay_png(shot_id, speaker, dialogue, motion_name, sub_png_path)

    # 3. 合成带字幕的预览卡片图供前端分镜列表展示
    with Image.open(sub_png_path) as sub_im:
        preview = frame.convert("RGBA")
        preview.alpha_composite(sub_im)
        preview.convert("RGB").save(preview_jpg_path, quality=92)


def _resolve_character_voice_code(speaker: str, characters: List[Dict[str, Any]], genre: str = "") -> str:
    """根据角色列表中绑定的音色名解析对应的微软神经网络音色代码."""
    voice_name_to_code = {
        "云希": "zh-CN-YunxiNeural",
        "云健": "zh-CN-YunjianNeural",
        "云扬": "zh-CN-YunyangNeural",
        "云浩": "zh-CN-YunxiNeural",
        "晓晓": "zh-CN-XiaoxiaoNeural",
        "晓涵": "zh-CN-XiaohanNeural",
        "晓梦": "zh-CN-XiaomengNeural",
        "东北晓贝": "zh-CN-liaoning-XiaobeiNeural",
        "陕西晓妮": "zh-CN-shaanxi-XiaoniNeural",
        "Christopher": "en-US-ChristopherNeural",
        "Jenny": "en-US-JennyNeural",
    }
    for c in characters:
        c_name = c.get("name", "")
        if speaker and (speaker in c_name or c_name in speaker):
            v_label = c.get("voice", "")
            for k, code in voice_name_to_code.items():
                if k in v_label:
                    return code

    # 女性角色关键词（涵盖常见女主名、称谓及别称）
    if any(w in speaker for w in ["女", "妹", "妻", "小姐", "姐", "母", "琴", "雪", "涵", "妃", "婉", "瑶", "虞", "梨", "娇", "儿", "娘", "姑娘", "女孩", "少女"]):
        return "zh-CN-XiaohanNeural"

    # 反派 / 霸道人物
    if any(w in speaker for w in ["赵", "少", "反派", "恶霸", "恶", "混混"]):
        return "zh-CN-YunjianNeural"

    # 旁白根据题材定制
    if speaker in ["旁白", "叙事旁白", "Scene", "环境"]:
        if any(k in genre for k in ["甜宠", "言情", "现言", "古言", "恋爱", "青春", "校园"]):
            return "zh-CN-XiaoxiaoNeural"
        return "zh-CN-YunxiNeural"

    # 青年男主默认阳光清朗男声
    return "zh-CN-YunyangNeural"


async def _generate_single_shot_visual(
    shot: Dict[str, Any],
    shots_dir: Path,
    logs_list: Optional[List[str]] = None
) -> Optional[str]:
    """为单个分镜生成真实画面 (支持 SiliconFlow 免费 FLUX / BFL FLUX / Pexels 视频或图片 / 本地差异化合成).
    返回动态视频片段路径 (若使用了 Pexels 视频) 或 None (使用图片运镜).
    """
    import asyncio
    try:
        from omnidrama.providers.siliconflow_provider import SiliconFlowProvider
        from omnidrama.providers.dashscope_provider import DashScopeProvider
        from omnidrama.providers.liveportrait_provider import LivePortraitProvider
        from omnidrama.providers.f5_tts_provider import F5TTSProvider
        from omnidrama.providers.flux_provider import FluxProProvider
        from omnidrama.providers.pexels_provider import PexelsProvider
    except ImportError:
        from providers.siliconflow_provider import SiliconFlowProvider
        from providers.dashscope_provider import DashScopeProvider
        from providers.liveportrait_provider import LivePortraitProvider
        from providers.f5_tts_provider import F5TTSProvider
        from providers.flux_provider import FluxProProvider
        from providers.pexels_provider import PexelsProvider

    sid = int(shot["id"])
    speaker = shot.get("speaker", "旁白")
    dialogue = shot.get("dialogue", "")
    motion_name = shot.get("motion_name", "镜头推进")
    visual_prompt = shot.get(
        "visual_prompt",
        f"masterpiece, 8k vertical anime drama frame, {speaker}, {dialogue}, dramatic lighting"
    )

    raw_bg_path = str(shots_dir / f"shot_{sid:03d}_raw.jpg")
    sub_png_path = str(shots_dir / f"shot_{sid:03d}_sub.png")
    preview_jpg_path = str(shots_dir / f"shot_{sid:03d}.jpg")
    ai_gen_source_path = str(shots_dir / f"ai_src_{sid:03d}.jpg")

    sf_key = get_provider_key("SILICONFLOW_API_KEY")
    ds_img_key = get_provider_key("DASHSCOPE_API_KEY")
    bfl_key = get_provider_key("BFL_API_KEY") or get_provider_key("FLUX_API_KEY")
    pexels_key = get_provider_key("PEXELS_API_KEY")
    char_seed = (abs(hash(speaker)) % 900000) + 100000

    generated_ai_img = False

    # 0. 优先尝试 Google Colab T4 2号机 (Qwen-Image-2.1-Turbo-Q8_0.gguf + Real-ESRGAN 免费 4K 电影定妆生图)
    try:
        try:
            from omnidrama.providers.colab_cluster_provider import ColabClusterManager
        except ImportError:
            from providers.colab_cluster_provider import ColabClusterManager
        colab_mgr = ColabClusterManager.get_instance()
        allow_cold = logs_list is not None
        await asyncio.to_thread(
            colab_mgr.run_qwen_image_esrgan,
            visual_prompt,
            ai_gen_source_path,
            char_seed,
            allow_cold,
            55,
        )
        if os.path.exists(ai_gen_source_path) and os.path.getsize(ai_gen_source_path) > 3000:
            generated_ai_img = True
            if logs_list is not None:
                logs_list.append(
                    f"🎨 [{_now_str()}] 第 {sid:02d} 镜：Colab T4 (Qwen-Image-2.1-Turbo + Real-ESRGAN) 4K 定妆生图成功 (Seed:{char_seed})！"
                )
    except Exception as colab_img_err:
        if logs_list is not None and "正在后台预热" not in str(colab_img_err):
            logs_list.append(f"ℹ️ [{_now_str()}] 第 {sid:02d} 镜 Colab T4 路由切换: {str(colab_img_err)[:55]}")

    # 1. 优先使用硅基流动 SiliconFlow (国内免绑卡·免费 FLUX.1-schnell，固定角色 seed 锁定风格)
    if not generated_ai_img and sf_key:
        try:
            sf_provider = SiliconFlowProvider(api_key=sf_key)
            await asyncio.to_thread(
                sf_provider.generate_shot_image,
                visual_prompt,
                ai_gen_source_path,
                "black-forest-labs/FLUX.1-schnell",
                "768x1024",
                char_seed
            )
            generated_ai_img = True
            if logs_list is not None:
                logs_list.append(f"🎨 [{_now_str()}] 第 {sid:02d} 镜：SiliconFlow FLUX 真实生图成功 (Seed:{char_seed})！")
        except Exception as sf_err:
            if logs_list is not None:
                logs_list.append(f"⚠️ [{_now_str()}] 第 {sid:02d} 镜 SiliconFlow 生图异常 ({str(sf_err)[:55]})")

    # 1B. 尝试阿里云百炼 DashScope 通义万相 2.1 / Qwen-Image (含 job_path 断点续传)
    if not generated_ai_img and ds_img_key:
        try:
            ds_provider = DashScopeProvider(api_key=ds_img_key)
            ds_job_path = shots_dir / f"shot_{sid:03d}_dashscope_job.json"
            await asyncio.to_thread(
                ds_provider.generate_shot_image,
                visual_prompt,
                ai_gen_source_path,
                "720*1280",
                char_seed,
                "wanx2.1-t2i-turbo",
                ds_job_path
            )
            generated_ai_img = True
            if logs_list is not None:
                logs_list.append(f"🎨 [{_now_str()}] 第 {sid:02d} 镜：阿里百炼通义万相真实生图成功 (Seed:{char_seed})！")
        except Exception as ds_err:
            if logs_list is not None:
                logs_list.append(f"⚠️ [{_now_str()}] 第 {sid:02d} 镜 阿里百炼生图异常 ({str(ds_err)[:55]})")

    # 2. 尝试官方 Black Forest Labs FLUX.1 Pro
    if not generated_ai_img and bfl_key:
        try:
            flux_provider = FluxProProvider(api_key=bfl_key)
            await asyncio.to_thread(
                flux_provider.generate_cinematic_frame,
                visual_prompt,
                "9:16",
                ai_gen_source_path
            )
            generated_ai_img = True
            if logs_list is not None:
                logs_list.append(f"🎨 [{_now_str()}] 第 {sid:02d} 镜：FLUX.1 Pro 真实生图成功！")
        except Exception as bfl_err:
            if logs_list is not None:
                logs_list.append(f"⚠️ [{_now_str()}] 第 {sid:02d} 镜 FLUX.1 Pro 异常 ({str(bfl_err)[:55]})")

    # 3. 尝试字节跳动火山方舟 Seedance 2.0/2.5 或 快手可灵 Kling 2.0 图生视频 (支持 resume_job 防重复扣费)
    pexels_video_clip: Optional[str] = None
    ark_key = get_provider_key("ARK_API_KEY")
    kling_key = get_provider_key("KLING_ACCESS_KEY") or get_provider_key("KLING_API_KEY")

    if (generated_ai_img or os.path.exists(ai_gen_source_path)) and ark_key:
        try:
            try:
                from omnidrama.providers.volcengine_seedance_provider import VolcengineSeedanceProvider
            except ImportError:
                from providers.volcengine_seedance_provider import VolcengineSeedanceProvider
            sp = VolcengineSeedanceProvider(api_key=ark_key)
            seedance_job = shots_dir / f"shot_{sid:03d}_seedance_job.json"
            seedance_out = shots_dir / f"seedance_vid_{sid:03d}.mp4"
            seedance_input_prompt = shot.get("seedance_prompt") or visual_prompt
            tid = await asyncio.to_thread(
                sp.create_generation_task,
                seedance_input_prompt,
                ai_gen_source_path,
                "9:16",
                "720p",
                5,
                True,
                seedance_job
            )
            if tid:
                vid_path = await asyncio.to_thread(sp.poll_and_download, tid, seedance_out, seedance_job, 120)
                if vid_path and os.path.exists(vid_path):
                    pexels_video_clip = vid_path
                    if logs_list is not None:
                        logs_list.append(f"🎬 [{_now_str()}] 第 {sid:02d} 镜：字节火山方舟 Seedance 2.0 图生视频成功！")
        except Exception:
            pass

    if not pexels_video_clip and (generated_ai_img or os.path.exists(ai_gen_source_path)) and kling_key:
        try:
            import base64
            try:
                from omnidrama.providers.kling_provider import KlingVideoProvider
            except ImportError:
                from providers.kling_provider import KlingVideoProvider
            with open(ai_gen_source_path, "rb") as bf:
                b64_img = base64.b64encode(bf.read()).decode("utf-8")
            kp = KlingVideoProvider(access_key=kling_key)
            kling_job = shots_dir / f"shot_{sid:03d}_kling_job.json"
            tid = await asyncio.to_thread(
                kp.create_image_to_video_task, b64_img, visual_prompt, 5, "zoom_in", "pro", kling_job
            )
            if tid:
                v_url = await asyncio.to_thread(kp.poll_kling_task, tid, 90, kling_job)
                if v_url:
                    kling_target = str(shots_dir / f"kling_vid_{sid:03d}.mp4")
                    await asyncio.to_thread(
                        safe_download_to_file,
                        v_url,
                        kling_target,
                        max_bytes=MAX_VIDEO_BYTES,
                        timeout=45.0,
                    )
                    pexels_video_clip = kling_target
                    if logs_list is not None:
                        logs_list.append(f"🎬 [{_now_str()}] 第 {sid:02d} 镜：可灵 Kling 2.0 图生视频成功！")
        except Exception:
            pass

    # 3.5 自动使用完全免费且免 Key 的官方 Pollinations FLUX.1 生成 8K 真实电影剧照
    if not generated_ai_img:
        try:
            raw_p = visual_prompt or "8k cinematic vertical movie still, ARRI Alexa 65, dramatic lighting, photorealistic, no cartoon"
            ascii_p = re.sub(r"[^a-zA-Z0-9, .-]", " ", raw_p)
            ascii_p = re.sub(r"\s+", " ", ascii_p).strip()[:160] or "8k cinematic live action movie still, dramatic lighting, photorealistic, vertical 9:16"
            poll_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(ascii_p)}?width=720&height=1280&model=flux&nologo=true&seed={char_seed + sid}"
            await asyncio.to_thread(
                safe_download_to_file,
                poll_url,
                ai_gen_source_path,
                max_bytes=MAX_IMAGE_BYTES,
                timeout=35.0,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"},
                allowed_hosts=("image.pollinations.ai",),
                min_bytes=5000,
            )
            generated_ai_img = True
            if logs_list is not None:
                logs_list.append(f"🎨 [{_now_str()}] 第 {sid:02d} 镜：FLUX.1 真实电影剧照生成成功 (Seed:{char_seed + sid})！")
        except Exception as p_err:
            if logs_list is not None:
                logs_list.append(f"⚠️ [{_now_str()}] 第 {sid:02d} 镜 FLUX.1 备用获取提示: {str(p_err)[:40]}")

    # 4. 尝试 Pexels 免费高清图库/视频库 (对标 MoneyPrinterTurbo)
    if not generated_ai_img and pexels_key:
        try:
            px = PexelsProvider(api_key=pexels_key)
            photo_res = await asyncio.to_thread(
                px.search_and_download_photo,
                visual_prompt,
                ai_gen_source_path
            )
            if photo_res:
                generated_ai_img = True
                if logs_list is not None:
                    logs_list.append(f"📸 [{_now_str()}] 第 {sid:02d} 镜：Pexels 高清剧照匹配下载成功！")
            vid_target = str(shots_dir / f"pexels_vid_{sid:03d}.mp4")
            vid_res = await asyncio.to_thread(
                px.search_and_download_video,
                visual_prompt,
                vid_target
            )
            if vid_res:
                pexels_video_clip = vid_res
        except Exception:
            pass

    proj_data = _load_project_data()
    src_img_for_bg = Path(ai_gen_source_path) if generated_ai_img and os.path.exists(ai_gen_source_path) else _pick_source_manga_image(speaker, sid, proj_data.get("title", ""), proj_data.get("genre", ""))

    await asyncio.to_thread(
        _prepare_clean_background_and_preview,
        src_img_for_bg,
        sid,
        speaker,
        dialogue,
        motion_name,
        raw_bg_path,
        sub_png_path,
        preview_jpg_path,
        not generated_ai_img
    )
    shot["image"] = f"/api/shots/{sid}/image"
    return pexels_video_clip


async def _run_production_pipeline(req: Optional[RenderRequest]):
    """100% 真实执行的短剧制作与渲染流水线 (集成 OpenMontage 质检门禁 + CostTracker + DecisionLog)."""
    import asyncio
    global RENDER_STATE
    key_scope = scoped_api_keys(req.api_keys if req else None)
    key_scope.__enter__()
    try:
        RENDER_STATE["is_rendering"] = True

        # 本地函数作用域安全导入核心制片引擎
        try:
            from core.cost_tracker import CostTracker, DecisionLog
        except Exception:
            from omnidrama.core.cost_tracker import CostTracker, DecisionLog

        try:
            from schemas.drama_schema import CameraMotionEnum, Shot, ShotScaleEnum
        except Exception:
            from omnidrama.schemas.drama_schema import CameraMotionEnum, Shot, ShotScaleEnum

        try:
            from core.quality_gate import auto_optimize_storyboard, verify_rendered_video
        except Exception:
            from omnidrama.core.quality_gate import auto_optimize_storyboard, verify_rendered_video

        try:
            from core.director import DirectorAgent
        except Exception:
            from omnidrama.core.director import DirectorAgent

        try:
            from core.tts_engine import TTSEngine
        except Exception:
            from omnidrama.core.tts_engine import TTSEngine

        try:
            from core.audio_mixer import AudioMixer
        except Exception:
            from omnidrama.core.audio_mixer import AudioMixer

        try:
            from core.compositor import VideoCompositor
        except Exception:
            from omnidrama.core.compositor import VideoCompositor
        RENDER_STATE["error"] = None
        RENDER_STATE["progress"] = 5
        RENDER_STATE["step_index"] = 1
        RENDER_STATE["current_step"] = "阶段 1/5：AI 总导演剧本拆解与反 PPT 感节奏调优"
        RENDER_STATE["logs"] = [
            f"🚀 [{_now_str()}] 曾练AI短剧创作 v1.8.0 (融合 OpenMontage 制片内核) · 真实制片流水线启动！"
        ]


        data = _load_project_data()
        raw_title = (req.title if req and req.title else data.get("title", "至尊龙王归位")).strip()
        title = validate_safe_path_param(raw_title, field_name="title", default="至尊龙王归位")
        genre = (req.genre if req and req.genre else data.get("genre", "都市战神爽文")).strip()
        novel_text = (req.novel_text if req and req.novel_text else "").strip()

        proj_dir = _safe_resolve_under(OUTPUT_DIR, title)
        shots_dir = _safe_resolve_under(proj_dir, "shots")
        shots_dir.mkdir(parents=True, exist_ok=True)

        cost_tracker = CostTracker(budget_total_usd=5.0, cost_log_path=proj_dir / "cost_log.json")
        decision_log = DecisionLog(log_path=proj_dir / "decision_log.json")

        if novel_text:
            RENDER_STATE["logs"].append(f"🎬 [{_now_str()}] 正在调用 AI 导演引擎拆解小说《{title}》...")
            agent = DirectorAgent()
            proj = await asyncio.to_thread(agent.breakdown_story, novel_text, title, genre, None, None, "deepseek-chat", True)
            RENDER_STATE["logs"].append(
                f"✅ [{_now_str()}] 剧本拆解完成！使用引擎：{agent.last_used_engine}，共生成 {len(proj.shots)} 个分镜、{len(proj.characters)} 位角色。"
            )
            decision_log.record(
                category="script_director",
                subject="AI 导演剧本拆解引擎",
                chosen=agent.last_used_engine,
                reason=f"自动拆解《{title}》生成 {len(proj.shots)} 个分镜",
            )
            chars_list = []
            for idx, c in enumerate(proj.characters):
                card_data = c.consistency_card.model_dump() if (hasattr(c, "consistency_card") and c.consistency_card and hasattr(c.consistency_card, "model_dump")) else (c.consistency_card.dict() if (hasattr(c, "consistency_card") and c.consistency_card and hasattr(c.consistency_card, "dict")) else getattr(c, "consistency_card", None))
                chars_list.append({
                    "name": c.name,
                    "role": "核心主角" if idx == 0 else "重要角色",
                    "voice": getattr(c, "voice_name", None) or ("云希 (磁性沉稳霸道)" if c.gender == "male" else "晓晓 (尖酸刻薄逼迫)"),
                    "avatar": getattr(c, "turnaround_image", "") or f"/api/shots/{min(idx + 1, len(proj.shots))}/image",
                    "traits": c.visual_tags,
                    "archetype": getattr(c, "archetype", "") or "",
                    "turnaround_prompt": getattr(c, "turnaround_prompt", "") or "",
                    "turnaround_image": getattr(c, "turnaround_image", "") or "",
                    "consistency_card": card_data,
                })
            shots_list = []
            for s in proj.shots:
                m_val = s.camera_motion.value.upper()
                m_name = "镜头震撼" if "SHAKE" in m_val else (
                    "镜头拉远" if "OUT" in m_val else ("向左横移" if "PAN" in m_val else "镜头推进")
                )
                shots_list.append({
                    "id": s.shot_id,
                    "speaker": s.speaker,
                    "scale": s.shot_scale.value.upper(),
                    "motion": m_val,
                    "motion_name": m_name,
                    "dialogue": s.dialogue,
                    "visual_prompt": s.visual_prompt,
                    "image": f"/api/shots/{s.shot_id}/image",
                    "audio": f"/api/shots/{s.shot_id}/audio",
                    "sfx": getattr(s, "sfx", "") or ("惊雷劈裂 (Thunder)" if "SHAKE" in m_val else "无"),
                    "action_beat": getattr(s, "action_beat", ""),
                    "seedance_prompt": getattr(s, "seedance_prompt", ""),
                    "duration": getattr(s, "duration_seconds", None)
                })
        elif req and req.shots and len(req.shots) > 0:
            shots_list = req.shots
            chars_list = req.characters if req.characters else data.get("characters", [])
            RENDER_STATE["logs"].append(
                f"🎬 [{_now_str()}] 接收到移动端传入的《{title}》完整剧本分镜（共 {len(shots_list)} 镜）。"
            )
        else:
            shots_list = data.get("shots", [])
            chars_list = data.get("characters", [])
            if not shots_list:
                RENDER_STATE["logs"].append(f"🎬 [{_now_str()}] 未检测到分镜数据，正在调用 AI 导演引擎自动生成《{title}》初始分镜...")
                agent = DirectorAgent()
                proj = await asyncio.to_thread(agent.breakdown_story, f"《{title}》精彩短剧开篇，矛盾冲突激烈，悬念迭起。", title, genre)
                chars_list = []
                for idx, c in enumerate(proj.characters):
                    card_data = c.consistency_card.model_dump() if (hasattr(c, "consistency_card") and c.consistency_card and hasattr(c.consistency_card, "model_dump")) else (c.consistency_card.dict() if (hasattr(c, "consistency_card") and c.consistency_card and hasattr(c.consistency_card, "dict")) else getattr(c, "consistency_card", None))
                    chars_list.append({
                        "name": c.name,
                        "role": "核心主角" if idx == 0 else "重要角色",
                        "voice": getattr(c, "voice_name", None) or ("云希 (磁性沉稳霸道)" if c.gender == "male" else "晓晓 (尖酸刻薄逼迫)"),
                        "avatar": getattr(c, "turnaround_image", "") or f"/api/shots/{min(idx + 1, len(proj.shots))}/image",
                        "traits": c.visual_tags,
                        "archetype": getattr(c, "archetype", "") or "",
                        "turnaround_prompt": getattr(c, "turnaround_prompt", "") or "",
                        "turnaround_image": getattr(c, "turnaround_image", "") or "",
                        "consistency_card": card_data,
                    })
                shots_list = []
                for s in proj.shots:
                    m_val = s.camera_motion.value.upper()
                    m_name = "镜头震撼" if "SHAKE" in m_val else (
                        "镜头拉远" if "OUT" in m_val else ("向左横移" if "PAN" in m_val else "镜头推进")
                    )
                    shots_list.append({
                        "id": s.shot_id,
                        "speaker": s.speaker,
                        "scale": s.shot_scale.value.upper(),
                        "motion": m_val,
                        "motion_name": m_name,
                        "dialogue": s.dialogue,
                        "visual_prompt": s.visual_prompt,
                        "image": f"/api/shots/{s.shot_id}/image",
                        "audio": f"/api/shots/{s.shot_id}/audio",
                        "sfx": "惊雷劈裂 (Thunder)" if "SHAKE" in m_val else "无"
                    })
            else:
                RENDER_STATE["logs"].append(
                    f"🎬 [{_now_str()}] 读取当前工程《{title}》分镜脚本（共 {len(shots_list)} 镜，{len(chars_list)} 位角色）。"
                )

        # OpenMontage 质量门禁 1：渲染前反 PPT 感 6 维风险评分与自动调优
        shots_list, risk_before, risk_after, q_fixes = auto_optimize_storyboard(shots_list, genre=genre)
        data["title"] = title
        data["genre"] = genre
        data["characters"] = chars_list
        data["shots"] = shots_list
        data["slideshow_risk"] = risk_after
        _save_project_data(data)
        RENDER_STATE["logs"].append(
            f"🛡️ [{_now_str()}] 反PPT感导演质检通过：风险指数 {risk_before['average']} -> {risk_after['average']} ({risk_after['verdict_cn']}，自动调优 {len(q_fixes)} 项)"
        )

        # 阶段 2：真实分镜画面与独立透明字幕层生成
        RENDER_STATE["progress"] = 30
        RENDER_STATE["step_index"] = 2
        sf_key = get_provider_key("SILICONFLOW_API_KEY")
        ds_key = get_provider_key("DASHSCOPE_API_KEY")
        bfl_key = get_provider_key("BFL_API_KEY") or get_provider_key("FLUX_API_KEY")
        pexels_key = get_provider_key("PEXELS_API_KEY")

        img_tool_name = (
            "siliconflow_flux" if sf_key else (
                "dashscope_image" if ds_key else (
                    "bfl_flux_pro" if bfl_key else "pollinations_flux"
                )
            )
        )
        decision_log.record(
            category="image_generation",
            subject="9:16 分镜视觉生成引擎",
            chosen=img_tool_name,
            reason="根据已配置环境变量自动路由最高优先级生图通道",
        )

        if sf_key:
            RENDER_STATE["current_step"] = "阶段 2/5：硅基流动 FLUX.1 正在逐镜生成专属分镜画面"
            RENDER_STATE["logs"].append(f"🎨 [{_now_str()}] 已启用 SILICONFLOW_API_KEY ({_mask_key(sf_key)}) 逐镜生成原画...")
        elif ds_key:
            RENDER_STATE["current_step"] = "阶段 2/5：阿里云百炼通义万相 2.1 正在逐镜生成专属分镜画面"
            RENDER_STATE["logs"].append(f"🎨 [{_now_str()}] 已启用 DASHSCOPE_API_KEY ({_mask_key(ds_key)}) 逐镜生成原画...")
        elif bfl_key:
            RENDER_STATE["current_step"] = "阶段 2/5：FLUX.1 Pro 正在逐镜生成专属分镜画面"
            RENDER_STATE["logs"].append(f"🎨 [{_now_str()}] 已启用 BFL_API_KEY ({_mask_key(bfl_key)}) 逐镜生成原画...")
        elif pexels_key:
            RENDER_STATE["current_step"] = "阶段 2/5：Pexels 高清视频/图片库正在逐镜匹配素材"
            RENDER_STATE["logs"].append(f"📸 [{_now_str()}] 已启用 PEXELS_API_KEY ({_mask_key(pexels_key)}) 检索匹配高清素材...")
        else:
            RENDER_STATE["current_step"] = "阶段 2/5：本地漫剧特效引擎逐镜绘制背景层与独立透明字幕层"
            RENDER_STATE["logs"].append(f"🎨 [{_now_str()}] 正在分离绘制《{title}》无字背景原画层与 RGBA 固定字幕层...")

        shot_video_clips: Dict[int, str] = {}
        for s in shots_list:
            sid = int(s["id"])
            c_id = cost_tracker.estimate(img_tool_name, f"生成第 {sid} 镜画面", shot_id=sid)
            cost_tracker.reserve(c_id)
            vid_clip = await _generate_single_shot_visual(s, shots_dir, RENDER_STATE["logs"])
            cost_tracker.reconcile(c_id, succeeded=True)
            if vid_clip:
                shot_video_clips[sid] = vid_clip

        RENDER_STATE["logs"].append(f"✅ [{_now_str()}] 全部 {len(shots_list)} 镜的无字背景原画与独立透明字幕层已准备完毕！")

        # 阶段 3：真实角色配音合成 (ElevenLabs API / 阿里百炼 Qwen-TTS / SiliconFlow CosyVoice2 / 微软 Edge-TTS)
        RENDER_STATE["progress"] = 55
        RENDER_STATE["step_index"] = 3
        eleven_key = get_provider_key("ELEVENLABS_API_KEY")
        tts_engine = TTSEngine()
        eleven_provider = ElevenLabsProvider(api_key=eleven_key) if eleven_key else None
        ds_tts_provider = DashScopeProvider(api_key=ds_key) if ds_key else None
        sf_tts_provider = SiliconFlowProvider(api_key=sf_key) if sf_key else None
        f5_provider = F5TTSProvider() if F5TTSProvider is not None else None

        tts_tool_name = "elevenlabs_tts" if eleven_key else ("edge_tts")
        decision_log.record(
            category="voice_selection",
            subject="多角色语音合成引擎",
            chosen=tts_tool_name,
            reason="支持按角色性别与人设自动匹配戏剧化声线",
        )

        if eleven_key:
            RENDER_STATE["current_step"] = "阶段 3/5：ElevenLabs Multilingual v2 真实合成角色配音"
            RENDER_STATE["logs"].append(f"🎙️ [{_now_str()}] 检测到 ELEVENLABS_API_KEY ({_mask_key(eleven_key)})，启动 ElevenLabs 语音合成...")
        else:
            RENDER_STATE["current_step"] = "阶段 3/5：微软 Edge-TTS / CosyVoice2 神经网络多角色真实配音"
            RENDER_STATE["logs"].append(f"🎙️ [{_now_str()}] 启动多角色神经网络语音引擎，逐句合成男女角色 MP3 音频...")

        schema_shots_for_srt: List[Shot] = []
        voice_mp3_list: List[str] = []
        total_dur = 0.0

        for s in shots_list:
            sid = int(s["id"])
            speaker = s.get("speaker", "旁白")
            dialogue = s.get("dialogue", "")
            audio_out = str(shots_dir / f"shot_{sid:03d}.mp3")
            voice_code = _resolve_character_voice_code(speaker, chars_list, genre)
            c_tts = cost_tracker.estimate(tts_tool_name, f"合成第 {sid} 镜【{speaker}】配音", shot_id=sid)
            cost_tracker.reserve(c_tts)

            synthesized = False
            # 0. 优先尝试 Google Colab T4 3号机 (Breeze-TTS / Ming-3.0-TTS + Faster-Whisper 情感配音与字幕对齐)
            if not synthesized and dialogue.strip():
                try:
                    try:
                        from omnidrama.providers.colab_cluster_provider import ColabClusterManager
                    except ImportError:
                        from providers.colab_cluster_provider import ColabClusterManager
                    colab_mgr = ColabClusterManager.get_instance()
                    colab_aud_out, _ = await asyncio.to_thread(
                        colab_mgr.run_breeze_tts_and_whisper,
                        dialogue,
                        speaker,
                        audio_out,
                        True,
                        45,
                    )
                    if colab_aud_out and os.path.exists(colab_aud_out) and os.path.getsize(colab_aud_out) > 200:
                        synthesized = True
                        RENDER_STATE["logs"].append(
                            f"🎙️ [{_now_str()}] 第 {sid:02d} 镜【{speaker}】Colab T4 (Breeze/Ming-3.0-TTS + Whisper) 情感配音与对齐完成！"
                        )
                except Exception:
                    pass

            if not synthesized and f5_provider and speaker not in ["旁白", "Scene", "环境"]:
                try:
                    cloned_out = await asyncio.to_thread(
                        f5_provider.synthesize_character_voice,
                        dialogue,
                        speaker,
                        audio_out
                    )
                    if cloned_out and os.path.exists(cloned_out):
                        synthesized = True
                        RENDER_STATE["logs"].append(f"🎙️ [{_now_str()}] 第 {sid:02d} 镜【{speaker}】F5-TTS ZeroGPU A10G 专属声音克隆完成！")
                except Exception:
                    pass

            if not synthesized and eleven_provider:
                try:
                    el_voice_id = "pNInz6obpgDQGcFmaJgB" if "Xiaoxiao" not in voice_code and "Xiaohan" not in voice_code else "21m00Tcm4TlvDq8ikWAM"
                    await asyncio.to_thread(
                        eleven_provider.synthesize_emotional_speech,
                        dialogue,
                        el_voice_id,
                        audio_out
                    )
                    synthesized = True
                except Exception as el_err:
                    RENDER_STATE["logs"].append(f"⚠️ [{_now_str()}] ElevenLabs 第 {sid:02d} 镜回退至 Edge-TTS ({str(el_err)[:50]})")

            if not synthesized:
                try:
                    await tts_engine.generate_speech(
                        text=dialogue,
                        voice=voice_code,
                        output_path=audio_out
                    )
                    synthesized = True
                except Exception:
                    if ds_tts_provider:
                        try:
                            await asyncio.to_thread(
                                ds_tts_provider.synthesize_speech,
                                dialogue,
                                audio_out,
                                speaker
                            )
                            synthesized = True
                        except Exception:
                            pass
                    if not synthesized and sf_tts_provider:
                        try:
                            await asyncio.to_thread(
                                sf_tts_provider.synthesize_speech,
                                dialogue,
                                speaker,
                                audio_out
                            )
                            synthesized = True
                        except Exception:
                            pass

            cost_tracker.reconcile(c_tts, succeeded=synthesized)
            dur = tts_engine.get_audio_duration(audio_out)
            total_dur += dur
            voice_mp3_list.append(audio_out)
            s["audio"] = f"/api/shots/{sid}/audio"
            s["duration_seconds"] = round(dur, 2)

            schema_shots_for_srt.append(
                Shot(
                    shot_id=sid,
                    shot_scale=ShotScaleEnum.MEDIUM_SHOT,
                    camera_motion=CameraMotionEnum.ZOOM_IN,
                    visual_prompt=s.get("visual_prompt", "cinematic shot"),
                    speaker=speaker,
                    dialogue=dialogue,
                    duration_seconds=dur
                )
            )
            RENDER_STATE["logs"].append(
                f"🔊 [{_now_str()}] 第 {sid:02d} 镜【{speaker}】配音已生成 ({voice_code}, {dur:.2f}s)"
            )

        srt_path = str(_safe_resolve_under(proj_dir, f"{title}.srt"))
        tts_engine.generate_srt(schema_shots_for_srt, srt_path)
        data["srt_url"] = "/api/project/subtitles"
        data["duration"] = round(total_dur, 2)

        # 阶段 4：真实三轨合一影视级母带混音 (FFmpeg + AudioMixer 含自动避让 Ducking)
        RENDER_STATE["progress"] = 75
        RENDER_STATE["step_index"] = 4
        RENDER_STATE["current_step"] = "阶段 4/5：FFmpeg 三轨合一母带混音 (人声 + 拟音 + 交响和声 BGM 避让)"
        RENDER_STATE["logs"].append(f"🎚️ [{_now_str()}] 正在将 {len(voice_mp3_list)} 段人声、雷雨音效与和声 BGM 进行侧链避让混音...")

        mixer = AudioMixer()
        combined_voice_wav = str(proj_dir / "combined_voice.wav")
        master_wav = str(proj_dir / "master_soundtrack.wav")

        def _concat_and_mix():
            norm_wavs = []
            for idx_w, mp3_p in enumerate(voice_mp3_list):
                norm_w = str(proj_dir / f"_norm_voice_{idx_w:03d}.wav")
                subprocess.run(
                    ["ffmpeg", "-y", "-i", mp3_p, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", norm_w],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
                )
                if os.path.exists(norm_w):
                    norm_wavs.append(norm_w)
            if len(norm_wavs) == 1:
                shutil.copyfile(norm_wavs[0], combined_voice_wav)
            elif len(norm_wavs) > 1:
                concat_list, tmp_dir = build_safe_concat_file(norm_wavs, proj_dir)
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-f", "concat", "-i", str(concat_list), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", combined_voice_wav],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                    )
                finally:
                    if concat_list.exists():
                        try:
                            concat_list.unlink()
                        except OSError:
                            pass
                    if tmp_dir and tmp_dir.exists():
                        shutil.rmtree(tmp_dir, ignore_errors=True)
            for nw in norm_wavs:
                try:
                    os.remove(nw)
                except OSError:
                    pass
            if os.path.exists(combined_voice_wav):
                try:
                    mixer.mix_soundtrack(
                        voice_track=combined_voice_wav,
                        total_duration=max(1.0, total_dur),
                        sfx_cues=[{"name": "thunder", "time_seconds": 0.5, "volume": 0.35}],
                        bgm_type="epic_battle",
                        output_path=master_wav,
                    )
                except Exception:
                    shutil.copyfile(combined_voice_wav, master_wav)
        await asyncio.to_thread(_concat_and_mix)
        RENDER_STATE["logs"].append(f"✅ [{_now_str()}] 母带混音完成：{master_wav} (总时长 {total_dur:.2f} 秒)")

        # 阶段 5：FFmpeg 双层合成 (背景 2.5D 动态运镜 + 顶层固定透明字幕层 overlay + 真人活化特写版)
        RENDER_STATE["progress"] = 90
        RENDER_STATE["step_index"] = 5
        RENDER_STATE["current_step"] = "阶段 5/5：FFmpeg 双层压制与 OpenMontage 成片多维质检门禁"
        RENDER_STATE["logs"].append(f"🎞️ [{_now_str()}] 启动 FFmpeg 双层视频合成器，同步渲染标准成片与真人活化版...")

        compositor = VideoCompositor(width=720, height=1280, fps=24)
        clip_paths: List[str] = []
        live_clip_paths: List[str] = []

        for idx, s in enumerate(shots_list):
            sid = int(s["id"])
            raw_bg_p = str(shots_dir / f"shot_{sid:03d}_raw.jpg")
            sub_png_p = str(shots_dir / f"shot_{sid:03d}_sub.png")
            fallback_img_p = str(shots_dir / f"shot_{sid:03d}.jpg")
            bg_to_use = raw_bg_p if os.path.exists(raw_bg_p) else fallback_img_p
            sub_to_use = sub_png_p if os.path.exists(raw_bg_p) and os.path.exists(sub_png_p) else None

            aud_p = str(shots_dir / f"shot_{sid:03d}.mp3")
            clip_p = str(shots_dir / f"shot_{sid:03d}.mp4")
            live_clip_p = str(shots_dir / f"shot_{sid:03d}_live.mp4")
            m_str = s.get("motion", "ZOOM_IN").upper()

            if "SHAKE" in m_str:
                cm = CameraMotionEnum.SHAKE
            elif "OUT" in m_str:
                cm = CameraMotionEnum.ZOOM_OUT
            elif "LEFT" in m_str:
                cm = CameraMotionEnum.PAN_LEFT
            elif "RIGHT" in m_str:
                cm = CameraMotionEnum.PAN_RIGHT
            else:
                cm = CameraMotionEnum.ZOOM_IN

            if sid in shot_video_clips and os.path.exists(shot_video_clips[sid]):
                await asyncio.to_thread(
                    compositor.render_video_shot,
                    shot_video_clips[sid],
                    aud_p,
                    clip_p,
                    sub_to_use
                )
                shutil.copyfile(clip_p, live_clip_p)
            else:
                await asyncio.to_thread(
                    compositor.render_shot,
                    bg_to_use,
                    aud_p,
                    cm,
                    clip_p,
                    sub_to_use
                )
                await asyncio.to_thread(
                    compositor.render_live_actor_shot,
                    bg_to_use,
                    aud_p,
                    live_clip_p,
                    sub_to_use
                )
            clip_paths.append(clip_p)
            live_clip_paths.append(live_clip_p)
            RENDER_STATE["progress"] = min(98, 90 + int(((idx + 1) / max(1, len(shots_list))) * 8))

        raw_concat_mp4 = str(proj_dir / f"{title}_concat_raw.mp4")
        raw_live_concat_mp4 = str(proj_dir / f"{title}_live_concat_raw.mp4")
        final_video_mp4 = str(proj_dir / f"{title}_影视级成片.mp4")
        final_live_mp4 = str(proj_dir / f"{title}_真人活化版.mp4")

        def _finalize_video():
            compositor.concatenate_clips(clip_paths, raw_concat_mp4)
            compositor.concatenate_clips(live_clip_paths, raw_live_concat_mp4)
            if os.path.exists(master_wav):
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", raw_concat_mp4,
                        "-i", master_wav,
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-shortest",
                        final_video_mp4
                    ],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                )
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", raw_live_concat_mp4,
                        "-i", master_wav,
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-shortest",
                        final_live_mp4
                    ],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
                )
            else:
                shutil.copyfile(raw_concat_mp4, final_video_mp4)
                shutil.copyfile(raw_live_concat_mp4, final_live_mp4)

        await asyncio.to_thread(_finalize_video)

        # OpenMontage 质量门禁 2：成片 ffprobe + 响度检测
        render_report = await asyncio.to_thread(verify_rendered_video, final_video_mp4)
        cost_snap = cost_tracker.cost_snapshot()
        decision_log.record(
            category="render_runtime_selection",
            subject="成片合成与质检引擎",
            chosen="FFmpeg Dual-Layer + Volumedetect QA",
            reason=render_report.get("summary", "质检完成"),
        )

        data["video_url"] = "/api/video/stream?mode=full"
        data["live_actor_video"] = "/api/video/stream?mode=live"
        data["render_report"] = render_report
        data["cost_snapshot"] = cost_snap
        data["decision_log"] = decision_log.current_decisions()
        data["audio_tracks"] = [
            {"track": "人声对白轨", "status": "已真实合成", "source": "ElevenLabs / Edge-TTS 神经网络配音"},
            {"track": "拟音音效轨 (SFX)", "status": "已真实混音", "source": "FFmpeg 暴雨 + 惊雷 + 破门轰鸣"},
            {"track": "电影配乐轨 (BGM)", "status": "已真实合成", "source": "FFmpeg 弦乐和声 + 自动避让 Ducking"}
        ]
        _save_project_data(data)

        RENDER_STATE["progress"] = 100
        RENDER_STATE["step_index"] = 5
        RENDER_STATE["is_rendering"] = False
        RENDER_STATE["current_step"] = f"《{title}》真实渲染与质检完成！({render_report.get('summary', '')})"
        RENDER_STATE["logs"].append(
            f"🛡️ [{_now_str()}] {render_report.get('summary', '成片质检通过')} | 本集算力账单：¥{cost_snap['total_spent_cny']} (${cost_snap['total_spent_usd']})"
        )
        RENDER_STATE["logs"].append(
            f"🏆 [{_now_str()}] 真实渲染全部完成！成片文件：{final_video_mp4} (时长 {total_dur:.2f}s)"
        )
    except Exception as e:
        RENDER_STATE["is_rendering"] = False
        RENDER_STATE["error"] = str(e)
        RENDER_STATE["logs"].append(f"❌ [{_now_str()}] 渲染发生异常: {str(e)}")
    finally:
        key_scope.__exit__(None, None, None)
        # 自动释放 Colab T4 显卡看门狗，防止挂机消耗每日免费 GPU 配额
        try:
            try:
                from omnidrama.providers.colab_cluster_provider import ColabClusterManager
            except ImportError:
                from providers.colab_cluster_provider import ColabClusterManager
            released = await asyncio.to_thread(ColabClusterManager.get_instance().release_all_runtimes)
            if any(released.values()):
                RENDER_STATE["logs"].append(
                    f"🛑 [{_now_str()}] [Colab 算力看门狗] 已自动归还空闲 T4 显卡实例，0 浪费保护每日免费配额！"
                )
        except Exception:
            pass


@app.post("/api/project/render-reset")
async def reset_render_pipeline():
    """强制重置制片机房渲染状态."""
    global RENDER_STATE
    RENDER_STATE["is_rendering"] = False
    RENDER_STATE["progress"] = 0
    RENDER_STATE["step_index"] = 0
    RENDER_STATE["error"] = None
    RENDER_STATE["current_step"] = "空闲待命"
    RENDER_STATE["logs"] = [f"🔄 [{_now_str()}] 制片机房状态已手动重置就绪。"]
    return {"status": "ok", "message": "渲染状态已重置", "state": RENDER_STATE}


@app.post("/api/project/render")
async def trigger_render_pipeline(req: Optional[RenderRequest] = None):
    """一键触发全链路短剧真实制作与渲染流水线 (即刻后台启动并快速返回 200，保证移动端握手不超时)."""
    import asyncio
    global RENDER_STATE
    if req:
        if req.title and has_path_traversal_markers(req.title):
            raise HTTPException(status_code=400, detail="非法的 title 参数：禁止包含路径分隔符或目录穿越序列")
        if req.api_keys:
            try:
                validate_api_keys_dict(req.api_keys)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    if RENDER_STATE["is_rendering"]:
        return {"status": "already_running", "message": "制片机房正在全负荷真实渲染中...", "state": RENDER_STATE}

    RENDER_STATE["is_rendering"] = True
    RENDER_STATE["error"] = None
    RENDER_STATE["progress"] = 5
    RENDER_STATE["step_index"] = 1
    RENDER_STATE["current_step"] = "正在启动云端制片流水线..."
    RENDER_STATE["logs"] = [f"🚀 [{_now_str()}] 接收到移动端渲染指令，启动云端真实制片机房..."]

    asyncio.create_task(_run_production_pipeline(req))
    return {"status": "started", "message": "真实短剧制作与 FFmpeg 渲染流水线已在后台启动！", "state": RENDER_STATE}


class UpdateShotRequest(BaseModel):
    speaker: str
    dialogue: str
    visual_prompt: Optional[str] = ""
    motion: Optional[str] = "ZOOM_IN"
    regenerate_image: bool = True
    regenerate_audio: bool = True
    regenerate_tts: Optional[bool] = None


@app.put("/api/shots/{shot_id}")
async def update_and_regenerate_shot(shot_id: int, req: UpdateShotRequest):
    """单分镜精修工作台：修改指定分镜的台词、画面提示词、运镜，并立即真实重绘画面、重录配音及同步更新单镜头与全片 MP4."""
    import asyncio
    try:
        from omnidrama.core.tts_engine import TTSEngine
        from omnidrama.core.compositor import VideoCompositor
        from omnidrama.schemas.drama_schema import CameraMotionEnum
    except ImportError:
        from core.tts_engine import TTSEngine
        from core.compositor import VideoCompositor
        from schemas.drama_schema import CameraMotionEnum

    data = _load_project_data()
    raw_title = data.get("title", "至尊龙王归位").strip() or "至尊龙王归位"
    title = _safe_slug(raw_title, default="至尊龙王归位")
    proj_dir = _safe_resolve_under(OUTPUT_DIR, title)
    shots_dir = _safe_resolve_under(proj_dir, "shots")
    shots_dir.mkdir(parents=True, exist_ok=True)

    target_shot = None
    for s in data.get("shots", []):
        if int(s["id"]) == shot_id:
            target_shot = s
            break

    if not target_shot:
        raise HTTPException(status_code=404, detail=f"Shot {shot_id} not found")

    m_val = (req.motion or "ZOOM_IN").upper()
    m_name = "镜头震撼" if "SHAKE" in m_val else (
        "镜头拉远" if "OUT" in m_val else ("向左横移" if "PAN" in m_val else "镜头推进")
    )

    target_shot["speaker"] = req.speaker.strip() or "旁白"
    target_shot["dialogue"] = req.dialogue.strip()
    target_shot["motion"] = m_val
    target_shot["motion_name"] = m_name
    if req.visual_prompt and req.visual_prompt.strip():
        target_shot["visual_prompt"] = req.visual_prompt.strip()

    if req.regenerate_image:
        await _generate_single_shot_visual(target_shot, shots_dir)
    else:
        # 即使不重绘底图，如果改了台词也更新双层透明字幕层和预览缩略图 (严格传递 8 个完整参数)
        raw_img = shots_dir / f"shot_{shot_id:03d}_raw.jpg"
        preview_img = shots_dir / f"shot_{shot_id:03d}.jpg"
        sub_png = shots_dir / f"shot_{shot_id:03d}_sub.png"
        src_img = raw_img if raw_img.exists() else _pick_source_manga_image(target_shot["speaker"], shot_id, data.get("title", ""), data.get("genre", ""))
        await asyncio.to_thread(
            _prepare_clean_background_and_preview,
            src_img,
            shot_id,
            target_shot["speaker"],
            target_shot["dialogue"],
            target_shot["motion_name"],
            str(raw_img),
            str(sub_png),
            str(preview_img),
            not raw_img.exists()
        )

    do_tts = req.regenerate_tts if req.regenerate_tts is not None else req.regenerate_audio
    tts_engine = TTSEngine()
    audio_out = str(shots_dir / f"shot_{shot_id:03d}.mp3")
    if do_tts or not os.path.exists(audio_out):
        voice_code = _resolve_character_voice_code(target_shot["speaker"], data.get("characters", []), data.get("genre", ""))
        await tts_engine.generate_speech(
            text=target_shot["dialogue"],
            voice=voice_code,
            output_path=audio_out
        )
        target_shot["audio"] = f"/api/shots/{shot_id}/audio"

    # 立即使用双层防变形技术重压该单镜头 MP4 片段，并同步重拼接全片 MP4
    raw_img = shots_dir / f"shot_{shot_id:03d}_raw.jpg"
    preview_img = shots_dir / f"shot_{shot_id:03d}.jpg"
    sub_png = shots_dir / f"shot_{shot_id:03d}_sub.png"
    bg_to_use = raw_img if raw_img.exists() else preview_img
    if bg_to_use.exists() and Path(audio_out).exists():
        compositor = VideoCompositor(width=720, height=1280, fps=24)
        motion_enum = CameraMotionEnum.ZOOM_IN
        if "OUT" in m_val:
            motion_enum = CameraMotionEnum.ZOOM_OUT
        elif "PAN" in m_val:
            motion_enum = CameraMotionEnum.PAN_LEFT
        elif "SHAKE" in m_val:
            motion_enum = CameraMotionEnum.SHAKE

        await asyncio.to_thread(
            compositor.render_shot,
            str(bg_to_use),
            audio_out,
            motion_enum,
            str(shots_dir / f"shot_{shot_id:03d}.mp4"),
            str(sub_png) if sub_png.exists() else None
        )
        # 如果工程已有全片 MP4，自动快速重拼各分镜切片以保持全片与单镜同步
        all_shot_clips = [str(shots_dir / f"shot_{int(s['id']):03d}.mp4") for s in data.get("shots", [])]
        if all_shot_clips and all(os.path.exists(cp) for cp in all_shot_clips):
            final_video_mp4 = str(proj_dir / f"{title}_影视级成片.mp4")
            await asyncio.to_thread(compositor.concatenate_clips, all_shot_clips, final_video_mp4)
            data["video_url"] = "/api/video/stream?mode=full"

    _save_project_data(data)
    return {**data, "status": "success", "shot": target_shot}



class CharacterModel(BaseModel):
    name: str
    role: str = "重要角色"
    voice: str = "云希 (磁性沉稳霸道)"
    avatar: Optional[str] = ""
    traits: Optional[str] = ""
    archetype: Optional[str] = ""
    turnaround_prompt: Optional[str] = ""
    turnaround_image: Optional[str] = ""
    consistency_card: Optional[Dict[str, Any]] = None


class ApplyArchetypeRequest(BaseModel):
    character_name: str
    archetype_id: str
    custom_role: Optional[str] = None


class TurnaroundGenerateRequest(BaseModel):
    prompt: Optional[str] = None
    regenerate: bool = True


class GenerateScriptRequest(BaseModel):
    title: str = "新短剧"
    genre: str = "都市爽文"
    novel_text: str
    api_keys: Optional[Dict[str, str]] = None


@app.post("/api/project/generate")
async def generate_script_endpoint(req: GenerateScriptRequest):
    """根据输入小说文本调用真实大模型 (或智能规则引擎) 拆解全新剧本与角色资产."""
    import asyncio
    if has_path_traversal_markers(req.title):
        raise HTTPException(status_code=400, detail="非法的 title 参数：禁止包含路径分隔符或目录穿越序列")
    safe_title = validate_safe_path_param(req.title, field_name="title", default="新短剧")
    if req.api_keys:
        try:
            validate_api_keys_dict(req.api_keys)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    try:
        from omnidrama.core.director import DirectorAgent
    except ImportError:
        from core.director import DirectorAgent

    with scoped_api_keys(req.api_keys):
        agent = DirectorAgent()
        proj = await asyncio.to_thread(agent.breakdown_story, req.novel_text, safe_title, req.genre)

    chars_list = []
    for idx, c in enumerate(proj.characters):
        is_first = (idx == 0)
        card_data = c.consistency_card.model_dump() if (hasattr(c, "consistency_card") and c.consistency_card and hasattr(c.consistency_card, "model_dump")) else (c.consistency_card.dict() if (hasattr(c, "consistency_card") and c.consistency_card and hasattr(c.consistency_card, "dict")) else getattr(c, "consistency_card", None))
        chars_list.append({
            "name": c.name,
            "role": "男一号 / 核心主角" if is_first else "主要人物",
            "voice": getattr(c, "voice_name", None) or ("云希 (磁性沉稳霸道)" if c.gender == "male" else "晓晓 (尖酸刻薄/成熟女主)"),
            "avatar": getattr(c, "turnaround_image", "") or f"/api/shots/{min(idx + 1, max(1, len(proj.shots)))}/image",
            "traits": f"{c.visual_tags} [引擎: {agent.last_used_engine}]",
            "archetype": getattr(c, "archetype", "") or "",
            "turnaround_prompt": getattr(c, "turnaround_prompt", "") or "",
            "turnaround_image": getattr(c, "turnaround_image", "") or "",
            "consistency_card": card_data,
        })

    if not chars_list:
        chars_list = [
            {"name": "主角", "role": "男主", "voice": "云希 (磁性沉稳霸道)", "avatar": "/api/shots/1/image", "traits": "冷峻青年，身手不凡"}
        ]

    shots_list = []
    for s in proj.shots:
        m_val = s.camera_motion.value.upper()
        m_name = "镜头震撼" if "SHAKE" in m_val else (
            "镜头拉远" if "OUT" in m_val else ("向左横移" if "PAN" in m_val else "镜头推进")
        )
        shots_list.append({
            "id": s.shot_id,
            "speaker": s.speaker,
            "scale": s.shot_scale.value.upper(),
            "motion": m_val,
            "motion_name": m_name,
            "dialogue": s.dialogue,
            "visual_prompt": s.visual_prompt,
            "image": f"/api/shots/{s.shot_id}/image",
            "audio": f"/api/shots/{s.shot_id}/audio",
            "sfx": getattr(s, "sfx", "") or ("惊雷劈裂 (Thunder)" if "SHAKE" in m_val else "无"),
            "action_beat": getattr(s, "action_beat", ""),
            "seedance_prompt": getattr(s, "seedance_prompt", ""),
            "duration": getattr(s, "duration_seconds", None)
        })

    final_mp4 = _safe_resolve_under(OUTPUT_DIR, safe_title, f"{safe_title}_影视级成片.mp4")
    has_video = final_mp4.exists()

    new_data = {
        "title": safe_title,
        "genre": req.genre,
        "video_url": "/api/video/stream?mode=full" if has_video else "",
        "live_actor_video": "/api/video/stream?mode=live" if has_video else "",
        "srt_url": "/api/project/subtitles",
        "duration": float(len(shots_list) * 5.0),
        "characters": chars_list,
        "shots": shots_list,
        "audio_tracks": [
            {"track": f"剧本导演引擎 ({agent.last_used_engine})", "status": "已拆解", "source": f"生成 {len(shots_list)} 镜分镜脚本"},
            {"track": "人声对白轨", "status": "待合成", "source": f"Edge-TTS / ElevenLabs ({len(chars_list)} 位声线)"},
            {"track": "电影配乐轨 (BGM)", "status": "待混音", "source": f"{req.genre}交响配乐"}
        ]
    }
    _save_project_data(new_data)
    return new_data


@app.post("/api/characters")
async def add_character_endpoint(char: CharacterModel):
    """新增或修改角色."""
    data = _load_project_data()
    existing = False
    char_payload = char.model_dump() if hasattr(char, "model_dump") else char.dict()
    for c in data["characters"]:
        if c["name"] == char.name:
            c.update(char_payload)
            existing = True
            break
    if not existing:
        data["characters"].append(char_payload)
    _save_project_data(data)
    return {"status": "success", "message": f"角色【{char.name}】已成功入库", "characters": data["characters"]}


@app.put("/api/characters/{name}")
async def update_character_endpoint(name: str, char: CharacterModel):
    """修改指定角色信息."""
    data = _load_project_data()
    updated = False
    char_payload = char.model_dump() if hasattr(char, "model_dump") else char.dict()
    for i, c in enumerate(data["characters"]):
        if c["name"] == name:
            data["characters"][i] = char_payload
            updated = True
            break
    if not updated:
        data["characters"].append(char_payload)
    _save_project_data(data)
    return {"status": "success", "characters": data["characters"]}


@app.delete("/api/characters/{name}")
async def delete_character_endpoint(name: str):
    """删除指定角色."""
    data = _load_project_data()
    data["characters"] = [c for c in data["characters"] if c["name"] != name]
    _save_project_data(data)
    return {"status": "success", "message": f"角色【{name}】已删除", "characters": data["characters"]}


@app.get("/api/archetypes")
async def get_archetypes_endpoint():
    """获取所有 4 款行业标准电影级爆款短剧母版列表 (含一致性控制卡与 16:9 三视图定妆规范)."""
    try:
        from omnidrama.config.archetypes import BUILTIN_ARCHETYPES
    except ImportError:
        from config.archetypes import BUILTIN_ARCHETYPES

    results = []
    for arch in sorted(BUILTIN_ARCHETYPES.values(), key=lambda a: a.code):
        results.append({
            "id": arch.id,
            "code": arch.code,
            "name": arch.name,
            "genre_category": arch.genre_category,
            "gender": arch.gender,
            "role_type": arch.role_type,
            "summary": arch.summary,
            "description": arch.description or arch.summary,
            "voice_name": arch.voice_name,
            "voice_rate": arch.voice_rate,
            "voice_pitch": arch.voice_pitch,
            "voice_display": arch.voice_binding.get("name", arch.voice_name),
            "voice_prompt": arch.voice_prompt,
            "visual_anchor": arch.visual_anchor,
            "visual_tags": arch.visual_tags,
            "turnaround_prompt": arch.turnaround_prompt,
            "consistency_card": arch.consistency_card.model_dump() if hasattr(arch.consistency_card, "model_dump") else arch.consistency_card.dict(),
            "generation_params": arch.generation_params,
        })
    return results


@app.post("/api/archetypes/apply")
async def apply_archetype_endpoint(req: ApplyArchetypeRequest):
    """一键套用指定爆款人设母版至指定角色 (自动绑定骨相锁/发型锁/服饰锁/专属负向词/Edge-TTS/三视图提示词)."""
    try:
        from omnidrama.config.archetypes import get_archetype
    except ImportError:
        from config.archetypes import get_archetype

    arch = get_archetype(req.archetype_id)
    if not arch:
        raise HTTPException(status_code=404, detail=f"未找到人设母版: {req.archetype_id}")

    data = _load_project_data()
    target_char = None
    for c in data.get("characters", []):
        if c.get("name") == req.character_name:
            target_char = c
            break

    card_dict = arch.consistency_card.model_dump() if hasattr(arch.consistency_card, "model_dump") else arch.consistency_card.dict()

    if target_char:
        target_char["archetype"] = arch.id
        target_char["voice"] = arch.voice_binding.get("name", arch.voice_name)
        target_char["traits"] = arch.visual_anchor or arch.visual_tags
        target_char["turnaround_prompt"] = arch.turnaround_prompt
        target_char["consistency_card"] = card_dict
        if req.custom_role:
            target_char["role"] = req.custom_role
        char_dict = target_char
    else:
        char_dict = {
            "name": req.character_name,
            "role": req.custom_role or (arch.name.split("-")[-1] if "-" in arch.name else arch.name),
            "voice": arch.voice_binding.get("name", arch.voice_name),
            "avatar": "",
            "traits": arch.visual_anchor or arch.visual_tags,
            "archetype": arch.id,
            "turnaround_prompt": arch.turnaround_prompt,
            "turnaround_image": "",
            "consistency_card": card_dict
        }
        data.setdefault("characters", []).append(char_dict)

    _save_project_data(data)
    return {
        "status": "success",
        "message": f"角色【{req.character_name}】已成功套用母版【{arch.name}】",
        "character": char_dict,
        "characters": data["characters"]
    }


@app.post("/api/characters/{name}/turnaround")
async def generate_character_turnaround_endpoint(
    name: str,
    req: Optional[TurnaroundGenerateRequest] = None
):
    """为指定角色生成电影级 16:9 标准三视图定妆 (纯白底正面/侧面/背面 + 胸像特写)."""
    import urllib.parse
    import asyncio
    import re
    import requests as _req
    try:
        from omnidrama.core.director import build_character_turnaround_prompt
        from omnidrama.schemas.drama_schema import CharacterAsset, CharacterConsistencyCard
        from omnidrama.providers.siliconflow_provider import SiliconFlowProvider
    except ImportError:
        from core.director import build_character_turnaround_prompt
        from schemas.drama_schema import CharacterAsset, CharacterConsistencyCard
        from providers.siliconflow_provider import SiliconFlowProvider

    data = _load_project_data()
    target_char = None
    for c in data.get("characters", []):
        if c.get("name") == name:
            target_char = c
            break

    if not target_char:
        target_char = {
            "name": name,
            "role": "主要角色",
            "voice": "云希 (磁性沉稳霸道)",
            "avatar": "",
            "traits": "",
            "archetype": "",
            "turnaround_prompt": "",
            "turnaround_image": "",
            "consistency_card": None
        }
        data.setdefault("characters", []).append(target_char)

    # 1. 确定 16:9 三视图提示词
    turnaround_p = (req.prompt.strip() if req and req.prompt and req.prompt.strip() else "")
    if not turnaround_p:
        if target_char.get("turnaround_prompt"):
            turnaround_p = target_char["turnaround_prompt"]
        else:
            card_obj = None
            if target_char.get("consistency_card"):
                card_obj = CharacterConsistencyCard(**target_char["consistency_card"])
            char_asset = CharacterAsset(
                name=name,
                gender="female" if "女" in target_char.get("role", "") else "male",
                visual_tags=target_char.get("traits", ""),
                visual_anchor=target_char.get("traits", ""),
                archetype=target_char.get("archetype", ""),
                consistency_card=card_obj
            )
            turnaround_p = build_character_turnaround_prompt(char_asset)

    # 2. 准备输出文件目录
    turnarounds_dir = _safe_resolve_under(OUTPUT_DIR, "turnarounds")
    turnarounds_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-_]", "_", name)
    turnaround_file = _safe_resolve_under(turnarounds_dir, f"turnaround_{safe_name}.jpg")
    turnaround_url = f"/output/turnarounds/turnaround_{safe_name}.jpg"

    # 3. 触发图像渲染生成流水线 (16:9 比例)
    char_seed = (abs(hash(name)) % 900000) + 100000
    generated = False

    # 3.1 尝试 SiliconFlow FLUX (1024x576)
    sf_key = get_provider_key("SILICONFLOW_API_KEY")
    if sf_key:
        try:
            sf = SiliconFlowProvider(api_key=sf_key)
            await asyncio.to_thread(
                sf.generate_shot_image,
                turnaround_p,
                str(turnaround_file),
                "black-forest-labs/FLUX.1-schnell",
                "1024x576",
                char_seed
            )
            if turnaround_file.exists() and turnaround_file.stat().st_size > 3000:
                generated = True
        except Exception:
            pass

    # 3.2 备用官方免费免 Key Pollinations FLUX (1280x720)
    if not generated:
        try:
            clean_prompt = re.sub(r"[^a-zA-Z0-9, .\-]", " ", turnaround_p)
            clean_prompt = re.sub(r"\s+", " ", clean_prompt).strip()[:240] or "character turnaround sheet, 3 views, 16:9, white background, ARRI Alexa"
            poll_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(clean_prompt)}?width=1280&height=720&model=flux&nologo=true&seed={char_seed}"
            p_resp = await asyncio.to_thread(
                _req.get,
                poll_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"},
                timeout=15
            )
            if p_resp.status_code == 200 and len(p_resp.content) > 3000:
                with open(turnaround_file, "wb") as pf:
                    pf.write(p_resp.content)
                generated = True
        except Exception:
            pass

    # 3.3 离线/降级安全垫：本地生成 16:9 纯白底预览图
    if not generated and not turnaround_file.exists():
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (1280, 720), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.text((640, 360), f"【{name}】16:9 三视图定妆\n{turnaround_p[:60]}...", fill=(60, 60, 60), anchor="mm")
            img.save(str(turnaround_file), "JPEG")
            generated = True
        except Exception:
            pass

    # 4. 更新角色状态
    target_char["turnaround_prompt"] = turnaround_p
    target_char["turnaround_image"] = turnaround_url
    if not target_char.get("avatar") or target_char["avatar"].startswith("/api/shots"):
        target_char["avatar"] = turnaround_url
    _save_project_data(data)

    return {
        "status": "success",
        "message": f"角色【{name}】16:9 三视图定妆生成成功！",
        "turnaround_image": turnaround_url,
        "turnaround_prompt": turnaround_p,
        "character": target_char,
        "characters": data["characters"]
    }


@app.get("/api/characters/{name}/turnaround")
async def get_character_turnaround_endpoint(name: str):
    """查询指定角色的 16:9 三视图定妆信息与图像链接."""
    data = _load_project_data()
    for c in data.get("characters", []):
        if c.get("name") == name:
            return {
                "status": "success",
                "name": name,
                "archetype": c.get("archetype", ""),
                "turnaround_prompt": c.get("turnaround_prompt", ""),
                "turnaround_image": c.get("turnaround_image", ""),
                "consistency_card": c.get("consistency_card")
            }
    raise HTTPException(status_code=404, detail=f"未找到角色: {name}")


@app.get("/api/projects/{project_id}")
async def get_project_by_id_endpoint(project_id: str):
    """获取指定工程数据 (兼容移动端与多工程 REST 契约)."""
    return _load_project_data()


@app.get("/api/voices")
async def get_available_voices():
    """获取系统支持的配音音色母带字典 (优先置顶曾先生 HuggingFace A10G 专属 F5-TTS 声音克隆)."""
    return [
        {
            "name": "🔥 HuggingFace F5-TTS 专属声音克隆",
            "code": "hf-f5-tts-clone",
            "tag": "曾先生ZeroGPU A10G · 真实演员原声克隆",
            "gender": "custom"
        },
        {"name": "云希 (磁性沉稳霸道)", "code": "zh-CN-YunxiNeural", "tag": "男霸总/战神", "gender": "male"},
        {"name": "云健 (嚣张跋扈反派)", "code": "zh-CN-YunjianNeural", "tag": "纨绔恶少/挑衅", "gender": "male"},
        {"name": "云扬 (热血青年男主)", "code": "zh-CN-YunyangNeural", "tag": "少年修仙/逆袭", "gender": "male"},
        {"name": "云浩 (沉稳长辈/正剧)", "code": "zh-CN-YunxiNeural", "tag": "长辈宗师/掌门", "gender": "male"},
        {"name": "晓晓 (尖酸刻薄逼迫)", "code": "zh-CN-XiaoxiaoNeural", "tag": "刁难反派/贵妇", "gender": "female"},
        {"name": "晓涵 (温柔清纯甜美)", "code": "zh-CN-XiaohanNeural", "tag": "豪门千金/白月光", "gender": "female"},
        {"name": "晓梦 (傲娇泼辣独立)", "code": "zh-CN-XiaomengNeural", "tag": "冷艳师姐/女总裁", "gender": "female"},
        {"name": "东北晓贝 (爽快大姐)", "code": "zh-CN-liaoning-XiaobeiNeural", "tag": "方言喜剧/生活", "gender": "female"},
        {"name": "陕西晓妮 (豪爽淳朴)", "code": "zh-CN-shaanxi-XiaoniNeural", "tag": "西北风情/豪迈", "gender": "female"},
        {"name": "Christopher (美语男主)", "code": "en-US-ChristopherNeural", "tag": "海外出海男主角", "gender": "male"},
        {"name": "Jenny (美语女主)", "code": "en-US-JennyNeural", "tag": "海外出海女主角", "gender": "female"}
    ]


@app.get("/api/voices/preview")
async def preview_voice(voice: str = "zh-CN-YunxiNeural", text: str = ""):
    """真实试听指定音色母带样例音频 (微软 Edge-TTS / SiliconFlow CosyVoice2 / ElevenLabs 真实发音)."""
    try:
        from omnidrama.core.tts_engine import TTSEngine
    except ImportError:
        from core.tts_engine import TTSEngine

    tts_engine = TTSEngine()

    voice_name_to_code = {
        "云希": "zh-CN-YunxiNeural",
        "云健": "zh-CN-YunjianNeural",
        "云扬": "zh-CN-YunyangNeural",
        "云浩": "zh-CN-YunxiNeural",
        "晓晓": "zh-CN-XiaoxiaoNeural",
        "晓涵": "zh-CN-XiaohanNeural",
        "晓梦": "zh-CN-XiaomengNeural",
        "东北晓贝": "zh-CN-liaoning-XiaobeiNeural",
        "陕西晓妮": "zh-CN-shaanxi-XiaoniNeural",
        "Christopher": "en-US-ChristopherNeural",
        "Jenny": "en-US-JennyNeural"
    }
    voice_code = voice
    for k, code in voice_name_to_code.items():
        if k in voice:
            voice_code = code
            break

    sample_text = text.strip()
    if not sample_text:
        if "Xiaoxiao" in voice_code:
            sample_text = "哼，凭你也配跟我平起平坐？别做梦了！"
        elif "Xiaohan" in voice_code:
            sample_text = "既然命运让我们相遇，我便绝不负你。"
        elif "Xiaomeng" in voice_code:
            sample_text = "今天这件事，必须给我一个交代！"
        elif "Yunjian" in voice_code:
            sample_text = "在江城，还没有人敢这么跟我说话！"
        elif "Yunyang" in voice_code:
            sample_text = "今日之辱，来日我必十倍奉还！"
        elif "Yunhao" in voice_code:
            sample_text = "老夫纵横一生，岂容小辈放肆！"
        elif "en-US" in voice_code:
            sample_text = "I will reclaim everything that once belonged to me."
        else:
            sample_text = "天凉了，该让王氏集团彻底破产了。"

    preview_dir = OUTPUT_DIR / "voice_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    if "hf-f5" in voice.lower() or "f5-tts" in voice.lower():
        try:
            try:
                from omnidrama.providers.f5_tts_provider import F5TTSProvider
            except ImportError:
                from providers.f5_tts_provider import F5TTSProvider
            f5 = F5TTSProvider()
            sample_text = sample_text or "三年了，我终于回来了。欠我的，今夜一并还清！"
            out_wav = preview_dir / f"hf_f5_preview_{abs(hash(sample_text))}.wav"
            res = await asyncio.to_thread(f5.synthesize_character_voice, text=sample_text, role="男主角", output_path=str(out_wav))
            if res and os.path.exists(res):
                return FileResponse(str(res), media_type="audio/wav")
        except Exception as e:
            print(f"[app.py] F5-TTS preview failed: {e}")

    out_file = preview_dir / f"{voice_code}_{abs(hash(sample_text))}.mp3"

    if not out_file.exists():
        await tts_engine.generate_speech(text=sample_text, voice=voice_code, output_path=str(out_file))

    return FileResponse(str(out_file), media_type="audio/mpeg")


@app.get("/api/sota/status")
async def get_sota_status():
    """获取所有行业顶配大模型引擎的【真实】配置就绪状态与本地系统环境 (绝不伪造状态)."""
    try:
        jianying_path = None
        try:
            from core.capcut_exporter import CapCutExporter
            jianying_path = CapCutExporter.get_system_jianying_draft_path()
        except Exception:
            pass

        def _entry(name: str, role: str, env_key: str, tier: str) -> Dict[str, Any]:
            raw_val = get_provider_key(env_key)
            is_conf = bool(raw_val)
            return {
                "name": name,
                "role": role,
                "env_key": env_key,
                "configured": is_conf,
                "masked_key": _mask_key(raw_val),
                "tier": tier
            }

        colab_summary = {"configured_nodes": 0, "runtime_ready_nodes": 0, "total_vram_gb": 48}
        try:
            try:
                from omnidrama.providers.colab_cluster_provider import ColabClusterManager
            except ImportError:
                from providers.colab_cluster_provider import ColabClusterManager
            cmgr = ColabClusterManager.get_instance()
            colab_summary = cmgr.get_cluster_summary()
        except Exception:
            pass

        has_colab = colab_summary.get("configured_nodes", 0) > 0
        providers_status = {
            "colab_cluster": {
                "name": f"⚡ Google Colab 三号联开 48GB 算力池 ({colab_summary.get('runtime_ready_nodes', 0)}/3 全权就绪)",
                "role": "1号机 Qwen3.8-27B破甲导演 · 2号机 Qwen-Image-2.1+ESRGAN 4K生图 · 3号机 Breeze/Ming-3.0-TTS+Whisper",
                "env_key": "COLAB_CLUSTER_TOKEN",
                "configured": has_colab,
                "masked_key": "已配置" if has_colab else "",
                "tier": "3×T4 (48GB 免费显卡池)"
            },
            "siliconflow": _entry(
                "🔥 硅基流动 SiliconFlow (国内免绑卡首选)",
                "一个Key同时开启：免费 FLUX.1 逐镜真实生图 + DeepSeek/Qwen 导演剧本拆解 + CosyVoice2 配音",
                "SILICONFLOW_API_KEY",
                "国内免费生图+导演"
            ),
            "dashscope": _entry(
                "🌟 阿里云百炼 DashScope (通义万相 2.1 + Qwen3-TTS)",
                "新用户送百万Token+百张免费生图额度：Wan2.1 竖屏短剧剧照 + Qwen3-TTS 超拟真配音",
                "DASHSCOPE_API_KEY",
                "国内大厂顶配 (推荐)"
            ),
            "seedance": _entry(
                "🎬 字节火山方舟 Seedance 2.0 (豆包视频大模型)",
                "50万免费Token体验：图生视频 I2V 电影级物理运镜与人物微表情生成",
                "ARK_API_KEY",
                "SOTA 动态视频"
            ),
            "deepseek": _entry(
                "DeepSeek-V3 / R1 (深度求索官方)",
                "好莱坞编剧与十镜分镜剧本拆解总导演",
                "DEEPSEEK_API_KEY",
                "主力导演 (国内直连)"
            ),
            "pexels": _entry(
                "Pexels 免费高清视频/图片素材库",
                "对标 MoneyPrinterTurbo：0元免绑卡自动匹配下载 9:16 竖屏高清实拍素材",
                "PEXELS_API_KEY",
                "免费动态视频素材"
            ),
            "kimi": _entry(
                "Kimi (月之暗面 Moonshot AI)",
                "长篇网文理解、剧本台词打磨与镜头关键词提炼",
                "MOONSHOT_API_KEY",
                "国内直连 (SOTA)"
            ),
            "gemini": _entry(
                "Google Gemini 2.0 Flash",
                "多模态剧本拆解与分镜视觉提示词引擎",
                "GEMINI_API_KEY",
                "高速导演"
            ),
            "image": _entry(
                "FLUX.1 Pro (Black Forest Labs)",
                "8K 胶片级定妆与分镜剧照生图 (海外官方)",
                "BFL_API_KEY",
                "行业顶级 (SOTA)"
            ),
            "liveportrait": {
                "name": "🎭 LivePortrait 专属演员动效工坊 (ZeroGPU A10G)",
                "role": "角色定妆照一键转电影级眼神流转、眨眼、挑眉与自然微表情动效 (zenglian110110/liveportrait-studio)",
                "env_key": "HF_TOKEN",
                "configured": bool(get_provider_key("HF_TOKEN")),
                "masked_key": _mask_key(get_provider_key("HF_TOKEN")),
                "tier": "A10G 专属算力"
            },
            "f5_tts": {
                "name": "🎙️ F5-TTS 专属声音克隆与配音工坊 (ZeroGPU A10G)",
                "role": "男女主角零样本音色克隆、自带呼吸声与电影级情绪爆发配音 (zenglian110110/f5-tts-studio)",
                "env_key": "HF_TOKEN",
                "configured": bool(get_provider_key("HF_TOKEN")),
                "masked_key": _mask_key(get_provider_key("HF_TOKEN")),
                "tier": "A10G 专属算力"
            },
            "voice": _entry(
                "ElevenLabs Multilingual v2",
                "人类级呼吸感情绪配音 (未配则用内置免费微软 Edge-TTS)",
                "ELEVENLABS_API_KEY",
                "行业顶级 (SOTA)"
            ),
        }

        sys_name = platform.system() if "platform" in globals() else "Linux"
        return {
            "system": {
                "os": f"云端算力机房 (Google Cloud Run · {sys_name} · Edge-TTS + FFmpeg 算力就绪)",
                "ffmpeg": bool(shutil.which("ffmpeg")),
                "jianying_installed": bool(jianying_path),
                "jianying_draft_path": jianying_path or "云端机房运行环境"
            },
            "providers": providers_status,
            "colab_cluster": colab_summary
        }
    except Exception:
        return {
            "system": {
                "os": "云端算力机房 (Google Cloud Run · 备用防熔断模式)",
                "ffmpeg": bool(shutil.which("ffmpeg")),
                "jianying_installed": False,
                "jianying_draft_path": "云端机房"
            },
            "providers": {}
        }


@app.post("/api/sota/save-keys")
@app.post("/api/settings/apikey")
async def save_api_keys(request: Request):
    """受控白名单保存模型服务商 API Key 至进程内安全上下文（严禁写入 os.environ 或 .env，拦截 LD_PRELOAD/PATH 等系统变量）."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 JSON 请求体")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="请求体必须为 JSON 对象")

    raw_keys: Dict[str, str] = {}
    if isinstance(payload.get("keys"), dict):
        raw_keys.update({str(k): "" if v is None else str(v) for k, v in payload["keys"].items()})
    elif "key" in payload or "env_key" in payload or "name" in payload:
        k_name = str(payload.get("key") or payload.get("env_key") or payload.get("name") or "").strip()
        v_val = payload.get("value") if "value" in payload else payload.get("api_key", "")
        raw_keys[k_name] = "" if v_val is None else str(v_val)
    else:
        for k, v in payload.items():
            if not isinstance(v, (dict, list)):
                raw_keys[str(k)] = "" if v is None else str(v)

    if not raw_keys:
        raise HTTPException(status_code=400, detail="未提供任何 API Key 键值")

    try:
        updated_count = save_runtime_managed_keys(raw_keys)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "success",
        "updated_count": updated_count,
        "message": f"已通过安全白名单校验并保存 {updated_count} 项受管模型 API 密钥！"
    }


class ExportJianyingRequest(BaseModel):
    title: Optional[str] = None


@app.post("/api/export-jianying")
async def export_jianying_project(req: Optional[ExportJianyingRequest] = None):
    """将当前项目一键导出为系统剪映专业版原生草稿工程（带路径遍历防护）."""
    try:
        from omnidrama.core.capcut_exporter import CapCutExporter
    except ImportError:
        from core.capcut_exporter import CapCutExporter

    if req and req.title and has_path_traversal_markers(req.title):
        raise HTTPException(status_code=400, detail="非法的 title 参数：禁止包含路径分隔符或目录穿越序列")

    project_data = await get_current_project()
    exporter = CapCutExporter(fps=24)
    raw_title = (req.title if req and req.title else project_data.get("title", "AI短剧")) or "AI短剧"
    if has_path_traversal_markers(raw_title):
        raise HTTPException(status_code=400, detail="非法的 title 参数：禁止包含路径分隔符或目录穿越序列")
    safe_title = _safe_slug(raw_title, default="AI短剧")
    shots_dir = _safe_resolve_under(OUTPUT_DIR, safe_title, "shots")

    shots_for_draft = []
    for idx, s in enumerate(project_data.get("shots", []), start=1):
        sid = int(s.get("id", idx))
        shots_for_draft.append({
            "duration": float(s.get("duration_seconds", 4.0) or 4.0),
            "motion": s.get("motion", "zoom_in").lower(),
            "speaker": s.get("speaker", "旁白"),
            "dialogue": s.get("dialogue", ""),
            "video_path": str(_safe_resolve_under(shots_dir, f"shot_{sid:03d}.mp4")),
            "audio_path": str(_safe_resolve_under(shots_dir, f"shot_{sid:03d}.mp3"))
        })

    draft_path = exporter.export_to_system_jianying(
        project_title=safe_title,
        shots=shots_for_draft
    )

    return {
        "status": "success",
        "draft_path": draft_path,
        "message": f"成功导出！请直接在剪映中打开工程：{draft_path}"
    }


class AddEpisodeRequest(BaseModel):
    series_id: str
    title: str
    text: Optional[str] = ""


class SplitNovelRequest(BaseModel):
    novel_text: str
    chars_per_episode: Optional[int] = 600


def _get_series_manager():
    try:
        from omnidrama.core.series_manager import SeriesManager
    except ImportError:
        from core.series_manager import SeriesManager
    return SeriesManager()


@app.get("/api/series")
async def get_series_list():
    """获取所有剧目及分集连载信息."""
    mgr = _get_series_manager()
    return mgr.get_registry()


@app.post("/api/series/episodes")
async def add_episode_endpoint(req: AddEpisodeRequest):
    """向指定剧目新增一集分镜."""
    mgr = _get_series_manager()
    new_ep = mgr.add_episode(req.series_id, req.title, req.text or "")
    return {"status": "success", "episode": new_ep}


@app.post("/api/series/split-novel")
async def split_novel_endpoint(req: SplitNovelRequest):
    """智能长篇小说切集算法：自动分割为连续短剧集."""
    mgr = _get_series_manager()
    episodes = mgr.auto_split_novel(req.novel_text, req.chars_per_episode or 600)
    return {"status": "success", "count": len(episodes), "episodes": episodes}


class FanqieImportRequest(BaseModel):
    url_or_id: Optional[str] = ""
    url: Optional[str] = ""

    def get_target(self) -> str:
        return (self.url_or_id or self.url or "").strip()


@app.get("/api/fanqie/rank")
async def get_fanqie_rank(limit: int = 8):
    """实时抓取番茄小说 (fanqienovel.com) 热门排行榜单."""
    import asyncio
    try:
        from omnidrama.providers.fanqie_provider import FanqieProvider
    except ImportError:
        from providers.fanqie_provider import FanqieProvider
    try:
        books = await asyncio.to_thread(FanqieProvider.fetch_rank_books, limit)
        return {"status": "success", "books": books}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取番茄小说热榜失败: {str(e)}")


@app.post("/api/fanqie/import")
async def import_fanqie_book(req: FanqieImportRequest):
    """解析用户输入的番茄小说链接或 book_id 提取书名、题材标签、简介及首章正文."""
    import asyncio
    try:
        from omnidrama.providers.fanqie_provider import FanqieProvider
    except ImportError:
        from providers.fanqie_provider import FanqieProvider
    try:
        target = req.get_target()
        if not target:
            raise ValueError("请提供番茄小说链接或作品 ID")
        book = await asyncio.to_thread(FanqieProvider.fetch_book_by_url_or_id, target)
        return {"status": "success", "book": book}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/fanqie/chapter/{item_id}")
async def get_fanqie_chapter_content(item_id: str):
    """直接抓取并解码番茄小说指定章节 (item_id) 的真实完整中文正文."""
    import asyncio
    try:
        from omnidrama.providers.fanqie_provider import FanqieProvider
    except ImportError:
        from providers.fanqie_provider import FanqieProvider
    try:
        data = await asyncio.to_thread(FanqieProvider.fetch_chapter_content, item_id.strip())
        return {"status": "success", **data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class AnalyzeReferenceRequest(BaseModel):
    video_source: Optional[str] = ""
    novel_text: Optional[str] = ""
    title: Optional[str] = "爆款节奏仿写短剧"
    genre: Optional[str] = "都市战神爽文"
    adapt_and_save: Optional[bool] = True


@app.post("/api/project/analyze-reference")
async def analyze_reference_video_endpoint(req: AnalyzeReferenceRequest):
    """对标 OpenMontage Reference Video Analyst：拆解爆款视频剪辑节奏并 1:1 仿写新剧本（带 SSRF 与本地文件探测拦截）."""
    import asyncio
    try:
        from omnidrama.core.reference_analyzer import ReferenceVideoAnalyzer
    except ImportError:
        from core.reference_analyzer import ReferenceVideoAnalyzer

    if req.title and has_path_traversal_markers(req.title):
        raise HTTPException(status_code=400, detail="非法的 title 参数：禁止包含路径分隔符或目录穿越序列")
    safe_title = _safe_slug(req.title or "爆款节奏仿写短剧", default="爆款节奏仿写短剧")

    analyzer = ReferenceVideoAnalyzer(workspace_dir=_safe_resolve_under(OUTPUT_DIR, "_reference_analysis"))
    src = (req.video_source or "").strip()

    try:
        brief = await asyncio.to_thread(analyzer.analyze_reference, src)
    except (UnsafeURLError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    pacing = brief.get("pacing_profile", {})
    breakdown = {
        **brief,
        "source": brief.get("source", {}).get("input") or "黄金短剧卡点模板",
        "cuts_per_minute": pacing.get("cuts_per_minute", 17.6),
        "pacing_profile": pacing.get("pacing_style", "fast_intense"),
        "narrative_arc": " → ".join(brief.get("what_makes_it_work", [])[:2]) or pacing.get("hook_technique", ""),
        "hook_mechanics": {
            "first_shot_duration": brief.get("scenes", [{}])[0].get("duration", 2.8) if brief.get("scenes") else 2.8,
            "retention_trigger": pacing.get("hook_technique", "前3秒高密度特写推镜"),
        },
        "shots": [
            {
                "shot_id": sc.get("scene_id", i + 1),
                "duration_seconds": sc.get("duration", 3.5),
                "suggested_motion": sc.get("recommended_motion_name", sc.get("recommended_motion", "ZOOM_IN")),
                "scale": sc.get("recommended_scale", "MEDIUM_SHOT"),
            }
            for i, sc in enumerate(brief.get("scenes", []))
        ],
    }

    adapted_storyboard = None
    if req.novel_text and req.novel_text.strip():
        adapted_storyboard = await asyncio.to_thread(
            analyzer.adapt_reference_to_novel,
            brief,
            req.novel_text.strip(),
            safe_title,
            req.genre or "都市战神爽文",
        )
        if req.adapt_and_save:
            current_data = _load_project_data()
            current_data["title"] = adapted_storyboard["title"]
            current_data["genre"] = adapted_storyboard["genre"]
            current_data["characters"] = adapted_storyboard["characters"]
            current_data["shots"] = adapted_storyboard["shots"]
            current_data["slideshow_risk"] = adapted_storyboard["slideshow_risk_after"]
            _save_project_data(current_data)

    return {
        "status": "success",
        "reference_breakdown": breakdown,
        "adapted_storyboard": adapted_storyboard,
    }


class QualityCheckRequest(BaseModel):
    auto_fix: Optional[bool] = True
    budget_limit_usd: Optional[float] = 5.0


@app.post("/api/project/quality-check")
async def project_quality_check_endpoint(req: QualityCheckRequest):
    """对当前分镜工程执行反 PPT 幻灯片感 6 维诊断、自动节奏调优与算力成本预估."""
    try:
        from omnidrama.core.quality_gate import score_slideshow_risk, auto_optimize_storyboard
        from omnidrama.core.cost_tracker import CostTracker, DecisionLog
    except ImportError:
        from core.quality_gate import score_slideshow_risk, auto_optimize_storyboard
        from core.cost_tracker import CostTracker, DecisionLog

    project_data = await get_current_project()
    shots = project_data.get("shots", [])
    genre = project_data.get("genre", "都市爽文") or "都市爽文"
    before_raw = score_slideshow_risk(shots)

    after_raw = before_raw
    fixes: List[str] = []
    if req.auto_fix:
        opt_shots, before_raw, after_raw, fixes = auto_optimize_storyboard(shots, genre=genre)
        project_data["shots"] = opt_shots
        project_data["slideshow_risk"] = after_raw
        _save_project_data(project_data)

    def _enrich_quality(rep: Dict[str, Any], shot_list: List[Dict[str, Any]], fix_list: List[str]) -> Dict[str, Any]:
        risk_100 = max(0, min(100, int(round(rep.get("average", 0.0) * 20))))
        durs = [float(s.get("duration") or s.get("duration_seconds") or 3.8) for s in shot_list] or [3.8]
        return {
            **rep,
            "risk_score": risk_100,
            "verdict": rep.get("verdict_cn", rep.get("verdict", "")),
            "metrics": {
                "motion_diversity_ratio": 1.0 if rep.get("dimensions", {}).get("weak_motion", {}).get("score", 0) < 2.0 else 0.75,
                "avg_duration_sec": round(sum(durs) / len(durs), 2),
                "first_shot_duration_sec": round(durs[0], 2),
            },
            "issues": [
                {"dimension": k, "detail": v.get("reason", "")}
                for k, v in rep.get("dimensions", {}).items()
                if v.get("score", 0) >= 1.5
            ] or [{"dimension": "自动调优", "detail": f} for f in fix_list],
        }

    title = _safe_slug(project_data.get("title", "AI短剧") or "AI短剧", default="AI短剧")
    proj_dir = _safe_resolve_under(OUTPUT_DIR, title)
    tracker = CostTracker(budget_total_usd=req.budget_limit_usd or 5.0, cost_log_path=proj_dir / "cost_log.json")
    snap = tracker.cost_snapshot()
    n_shots = max(1, len(project_data.get("shots", [])))
    est_usd = round(snap["total_spent_usd"] if snap["total_spent_usd"] > 0 else n_shots * 0.02, 3)
    cost_estimate = {
        **snap,
        "estimated_total_usd": est_usd,
        "estimated_total_cny": round(est_usd * 7.2, 2),
        "budget_limit_usd": round(tracker.budget_total_usd, 2),
    }

    dlog = DecisionLog(log_path=proj_dir / "decision_log.json")
    if fixes:
        dlog.record(
            category="quality_gate",
            subject="反PPT幻灯片感6维调优",
            chosen="auto_optimize_storyboard",
            reason=f"执行 {len(fixes)} 项镜头语言优化，风险均值 {before_raw.get('average')} -> {after_raw.get('average')}",
        )
    decisions = [
        {
            "stage": d.get("category", "director"),
            "action": d.get("chosen", ""),
            "reason": d.get("reason", ""),
        }
        for d in dlog.current_decisions()
    ]

    return {
        "status": "success",
        "before_quality": _enrich_quality(before_raw, shots, fixes),
        "after_quality": _enrich_quality(after_raw, project_data.get("shots", []), fixes),
        "cost_estimate": cost_estimate,
        "decisions": decisions,
        "project": project_data,
    }


@app.get("/api/system/capabilities")
async def system_capabilities_endpoint():
    """对标 OpenMontage get_capability_envelope：返回全量工具链与大模型就绪包络矩阵."""
    try:
        from omnidrama.core.cost_tracker import get_capability_envelope
    except ImportError:
        from core.cost_tracker import get_capability_envelope
    return get_capability_envelope()


class ColabOAuthExchangeRequest(BaseModel):
    node_id: str = "node_2_image"
    code: str
    state: Optional[str] = None


@app.get("/api/colab/status")
async def get_colab_cluster_status(probe: bool = False):
    """获取 Google Colab 三号联开 (3 × T4 = 48GB VRAM) 算力池实时状态."""
    import asyncio
    try:
        from omnidrama.providers.colab_cluster_provider import ColabClusterManager
    except ImportError:
        from providers.colab_cluster_provider import ColabClusterManager
    mgr = ColabClusterManager.get_instance()
    if probe:
        return await asyncio.to_thread(mgr.probe_all_nodes, True)
    return mgr.get_cluster_summary()


@app.post("/api/colab/warmup")
async def warmup_colab_cluster_endpoint():
    """手机端一键并发预热三号 Colab T4 免费显卡池."""
    import asyncio
    try:
        from omnidrama.providers.colab_cluster_provider import ColabClusterManager
    except ImportError:
        from providers.colab_cluster_provider import ColabClusterManager
    mgr = ColabClusterManager.get_instance()
    res = await asyncio.to_thread(mgr.warmup_cluster)
    return {"status": "success", "message": "已下发 Colab T4 算力池并发预热指令！", **res}


@app.post("/api/colab/release")
async def release_colab_cluster_endpoint():
    """手机端一键释放全部 Colab T4 实例以保护每日免费配额."""
    import asyncio
    try:
        from omnidrama.providers.colab_cluster_provider import ColabClusterManager
    except ImportError:
        from providers.colab_cluster_provider import ColabClusterManager
    mgr = ColabClusterManager.get_instance()
    released = await asyncio.to_thread(mgr.release_all_runtimes)
    return {
        "status": "success",
        "released": released,
        "message": "已安全释放全部 Colab T4 显卡实例，免费额度已锁定保护！",
        "cluster": mgr.get_cluster_summary(),
    }


@app.get("/api/colab/oauth-url")
async def get_colab_mobile_oauth_url(node_id: str = "node_2_image"):
    """生成指定 Colab 节点 (1号机/2号机/3号机) 的 PKCE 完整权限授权链接."""
    try:
        from omnidrama.providers.colab_cluster_provider import ColabClusterManager
    except ImportError:
        from providers.colab_cluster_provider import ColabClusterManager
    mgr = ColabClusterManager.get_instance()
    return mgr.generate_mobile_oauth_url(node_id=node_id)


@app.post("/api/colab/oauth-exchange")
async def exchange_colab_mobile_oauth(req: ColabOAuthExchangeRequest):
    """将手机或电脑端获取的 4/0A... 授权码兑换为完整 colaboratory T4 权限并落盘."""
    import asyncio
    try:
        from omnidrama.providers.colab_cluster_provider import ColabClusterManager
    except ImportError:
        from providers.colab_cluster_provider import ColabClusterManager
    mgr = ColabClusterManager.get_instance()
    try:
        node_dict = await asyncio.to_thread(
            mgr.exchange_mobile_oauth_code,
            req.node_id,
            req.code,
            req.state,
        )
        return {
            "status": "success",
            "message": f"节点 {node_dict.get('node_id', req.node_id)} 已成功开通完整 Colab T4 权限！",
            "node": node_dict,
            "cluster": mgr.get_cluster_summary(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




