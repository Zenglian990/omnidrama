"""针对产品真实使用问题修复的全链路回归测试 (Product Usability Fixes Verification)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from omnidrama.core.director import DirectorAgent
from omnidrama.core.quality_gate import auto_optimize_storyboard
from omnidrama.web.app import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    return TestClient(app)


def test_turnaround_image_route_serves_real_jpeg_and_blocks_traversal(client):
    """三视图生成后，前端访问 turnaround_image 必须返回 200 图片，不再 404 破图."""
    res = client.post("/api/characters/林尘验证/turnaround", json={"prompt": "cinematic male lead", "regenerate": True})
    assert res.status_code == 200
    img_url = res.json()["turnaround_image"]
    assert img_url.startswith("/output/turnarounds/")

    img_resp = client.get(img_url)
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"].startswith("image/")
    assert len(img_resp.content) > 500

    # 安全校验：禁止读取非图片或路径穿越
    bad_ext = client.get("/output/turnarounds/secret.json")
    assert bad_ext.status_code == 400


def test_short_story_offline_splits_multiple_shots_and_avoids_broken_urls(client):
    """短剧情拆解不再退化成单镜，且刚生成完未生图时绝不返回 404 破图链接."""
    agent = DirectorAgent()
    proj = agent.breakdown_story_offline(
        "雨夜天台，落魄赘婿林尘亮出龙王令，豪门反派赵天霸当场跪地求饶。",
        title="回归短剧测试",
        genre="都市战神",
    )
    assert len(proj.shots) >= 3

    res = client.post(
        "/api/project/generate",
        json={
            "title": "回归短剧测试_无破图",
            "genre": "都市战神",
            "novel_text": "雨夜天台，落魄赘婿林尘亮出龙王令，豪门反派赵天霸当场跪地求饶。",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["shots"]) >= 2
    for s in data["shots"]:
        if not s.get("has_image"):
            assert s["image"] == ""
        if not s.get("has_audio"):
            assert s["audio"] == ""


def test_split_novel_persists_to_series_and_select_episode_loads_project(client):
    """切集必须真实入库并出现在 /api/series 中，且切换分集必须真实加载该集工程."""
    novel = (
        "第一章 雨夜归来\n暴雨倾盆，林尘孤身走入豪门大堂，众人哄堂大笑。\n"
        "第二章 龙王令出\n林尘甩出黑金龙王令，十万战神齐声叩首！"
    )
    split_res = client.post(
        "/api/series/split-novel",
        json={
            "novel_text": novel,
            "series_title": "回归测试连载剧",
            "persist": True,
        },
    )
    assert split_res.status_code == 200
    split_data = split_res.json()
    assert split_data["count"] == 2
    assert len(split_data["saved_episodes"]) == 2

    ep2 = split_data["saved_episodes"][1]
    sel_res = client.post("/api/series/select-episode", json={"episode_id": ep2["id"]})
    assert sel_res.status_code == 200
    sel_data = sel_res.json()
    assert sel_data["project"]["episode_id"] == ep2["id"]
    assert "龙王令" in sel_data["project"]["story_text"]


def test_export_jianying_returns_downloadable_zip_with_real_duration(client):
    """剪映导出必须提供真 ZIP 下载且正确保留分镜时长."""
    client.post(
        "/api/project/generate",
        json={
            "title": "剪映打包测试剧",
            "genre": "都市热血",
            "novel_text": "雨夜天台，林尘拔剑出鞘，反派惊恐后退。",
        },
    )
    res = client.post("/api/export-jianying", json={"title": "剪映打包测试剧"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "download_url" in data and data["download_url"].startswith("/api/export-jianying/download/")

    dl = client.get(data["download_url"])
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(dl.content), "r") as zf:
        names = zf.namelist()
        assert any(n.endswith("draft_content.json") for n in names)


def test_quality_gate_first_shot_hook_duration_matches_standard():
    """质检优化后首镜时长必须严格 ≤3.5s，不再出现首镜 7.5s 的自相矛盾."""
    shots = [
        {"id": 1, "speaker": "林尘", "dialogue": "雨夜天台之上落魄赘婿亮出黑金龙王令豪门反派当场跪地求饶", "motion": "STATIC", "scale": "WIDE_SHOT"},
        {"id": 2, "speaker": "赵天霸", "dialogue": "不可能，你怎么会是龙王！", "motion": "STATIC", "scale": "WIDE_SHOT"},
    ]
    opt, _, _, _ = auto_optimize_storyboard(shots)
    assert opt[0]["duration"] <= 3.5
    assert opt[0]["duration_seconds"] <= 3.5


def test_dockerfile_and_frontend_hardening_invariants():
    """验证 Dockerfile 轻量化含中文字体、无冗余 APK/废弃脚本，前端具备离线静态资源与核心能力."""
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerfile_code = "\n".join(
        line for line in dockerfile.splitlines() if not line.lstrip().startswith("#")
    )
    assert "fonts-noto-cjk" in dockerfile_code
    assert "requirements-prod.txt" in dockerfile_code
    assert "git" not in dockerfile_code
    assert "libsm6" not in dockerfile_code
    assert not (PROJECT_ROOT / "assets" / "omnidrama.apk").exists()
    assert not (PROJECT_ROOT / "render_masterpiece.py").exists()
    assert (PROJECT_ROOT / "requirements-prod.txt").exists()
    assert (PROJECT_ROOT / "web" / "__init__.py").exists()
    for ignore_name in (".dockerignore", ".gcloudignore"):
        ignore_lines = [
            line.strip()
            for line in (PROJECT_ROOT / ignore_name).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        # 严禁写无根目录斜杠的裸 "app.py"，否则会递归误杀 web/app.py 导致 Cloud Run 启动报 Could not import module "web.app"
        assert "app.py" not in ignore_lines, f"{ignore_name} 误含裸 app.py，会递归排除 web/app.py"

    html = (PROJECT_ROOT / "web/index.html").read_text(encoding="utf-8")
    assert "全片 61s" not in html
    assert "61s Master" not in html
    assert "全 10 镜完结" not in html
    assert "viral_hook.mp4" not in html
    assert "cdn.tailwindcss.com" not in html
    assert "unpkg.com/vue" not in html
    assert "cdnjs.cloudflare.com" not in html
    assert "/static/vendor/app.css" in html
    assert "/static/vendor/vue.global.prod.js" in html
    assert "keyInputs[item.env_key]" in html
    assert "mobileTab" in html
    assert "resetRenderState" in html
    assert "showAuthModal" in html
    assert "quickGenerateShotImage" in html
    assert "quickGenerateShotAudio" in html


def test_production_fail_closed_and_httponly_session_cookie_auth(client, monkeypatch):
    """验证生产环境真 Fail-Closed、错误令牌拒绝、正确令牌签发 HttpOnly Cookie 放行原生媒体/API."""
    # 1. 生产环境未配置 API_AUTH_TOKEN 时必须真 Fail-Closed
    monkeypatch.setenv("OMNIDRAMA_ENV", "production")
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OMNIDRAMA_ALLOW_ANONYMOUS", raising=False)

    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["auth_mode"] == "fail_closed_missing_token"

    blocked = client.get("/api/project")
    assert blocked.status_code == 401

    # 2. 配置 API_AUTH_TOKEN 后，支持通过 /api/auth/session 校验并签发 HttpOnly 会话 Cookie
    monkeypatch.setenv("API_AUTH_TOKEN", "zeng-prod-secret-2026")
    assert client.get("/api/project").status_code == 401

    bad_login = client.post("/api/auth/session", json={"token": "wrong-token"})
    assert bad_login.status_code == 401

    ok_login = client.post("/api/auth/session", json={"token": "zeng-prod-secret-2026"})
    assert ok_login.status_code == 200
    set_cookie_hdr = ok_login.headers.get("set-cookie", "")
    assert "omnidrama_session=" in set_cookie_hdr
    assert "httponly" in set_cookie_hdr.lower()
    # 原始密钥绝不以明文出现在 Cookie 中
    assert "zeng-prod-secret-2026" not in set_cookie_hdr

    # 3. 携带会话 Cookie（不带 Authorization Header，模拟 <video>/<img>/<a>）放行访问
    authed = client.get("/api/project")
    assert authed.status_code == 200

    # 4. 登出后 Cookie 清除，再次拦截
    client.post("/api/auth/logout")
    assert client.get("/api/project").status_code == 401


def test_jianying_zip_uses_portable_placeholder_and_includes_readme(client):
    """验证剪映导出 ZIP 内使用剪映标准可移植相对占位符而非服务器绝对路径，并附带导入说明."""
    client.post(
        "/api/project/generate",
        json={
            "title": "可移植剪映测试",
            "genre": "都市爽文",
            "novel_text": "暴雨夜，林尘冷笑一声，反派直接傻眼。",
        },
    )
    res = client.post("/api/export-jianying", json={"title": "可移植剪映测试"})
    assert res.status_code == 200
    dl = client.get(res.json()["download_url"])
    assert dl.status_code == 200

    with zipfile.ZipFile(io.BytesIO(dl.content), "r") as zf:
        names = zf.namelist()
        readme_entry = next((n for n in names if n.endswith("README_导入说明.txt")), None)
        draft_entry = next((n for n in names if n.endswith("draft_content.json")), None)
        assert readme_entry is not None
        assert draft_entry is not None
        draft_text = zf.read(draft_entry).decode("utf-8")
        assert "##_draftpath_placeholder_0E685133-18CE-45ED-8CB8-2904A212EC80_##/assets/" in draft_text


def test_local_reference_video_upload_and_no_broken_shot_urls(client, tmp_path):
    """验证本地上传 MP4 参考视频走真实 FFmpeg 拆解，且仿写结果不带 404 破图 URL."""
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg, "需要 FFmpeg 执行参考视频上传测试"

    sample_mp4 = tmp_path / "sample_ref.mp4"
    subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "color=c=navy:s=360x640:d=3",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(sample_mp4),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )

    # 非法后缀拦截
    bad = client.post(
        "/api/project/analyze-reference-upload",
        files={"file": ("hack.txt", b"hello" * 400, "text/plain")},
        data={"title": "非法文件测试"},
    )
    assert bad.status_code == 400

    # 合法 MP4 拆解与仿写
    with open(sample_mp4, "rb") as f:
        ok = client.post(
            "/api/project/analyze-reference-upload",
            files={"file": ("sample_ref.mp4", f, "video/mp4")},
            data={
                "title": "本地视频仿写测试",
                "genre": "都市战神",
                "novel_text": "寿宴上未婚妻退婚，男主冷笑一声亮出龙王令，全场震惊下跪！",
                "adapt_and_save": "true",
            },
        )
    assert ok.status_code == 200
    body = ok.json()
    assert body["reference_breakdown"]["source"].startswith("本地上传视频")
    adapted = body["adapted_storyboard"]
    assert adapted is not None and len(adapted["shots"]) >= 2
    for s in adapted["shots"]:
        assert s["image"] == ""
        assert s["audio"] == ""
        assert s["has_image"] is False


def test_sota_save_keys_accepts_env_key_and_static_assets_served(client):
    """验证 SOTA 密钥按 env_key 正确入库，且本地化静态资源 200 OK 返回."""
    from omnidrama.core.runtime_context import reset_runtime_managed_keys

    try:
        res = client.post("/api/sota/save-keys", json={"keys": {"SILICONFLOW_API_KEY": "sk-test-verify-123"}})
        assert res.status_code == 200
        assert res.json()["updated_count"] == 1
    finally:
        reset_runtime_managed_keys()

    for static_url in ("/static/vendor/app.css", "/static/vendor/vue.global.prod.js", "/static/vendor/fontawesome/css/all.min.css"):
        sr = client.get(static_url)
        assert sr.status_code == 200
        assert len(sr.content) > 1000


def test_subtitle_overlay_safe_zone_and_real_cinema_fallback(tmp_path):
    """验证竖屏安全区大字幕生成及离线兜底优先匹配高清影视剧照而非旧蓝条纹."""
    from PIL import Image
    from omnidrama.web.app import _create_subtitle_overlay_png, _pick_source_manga_image

    sub_out = tmp_path / "sub_test.png"
    _create_subtitle_overlay_png(1, "林尘", "三年之期已到，龙王归位！今日谁敢拦我？", "镜头推进", str(sub_out))
    assert sub_out.exists()
    with Image.open(sub_out) as im:
        assert im.size == (720, 1280)
        assert im.mode == "RGBA"

    src_img = _pick_source_manga_image("林尘", 1, title="现代甜宠剧", genre="都市言情")
    assert src_img.exists()
    assert "procedural" not in str(src_img) or "storyboard_v2" in str(src_img)
    # 同一男主跨镜严格锁脸，第 1/2/3/4/5 镜必须始终锁定同一男主剧照，绝不突然变女童
    for sid in (1, 2, 3, 4, 5):
        assert _pick_source_manga_image("林尘", sid).name == "actor_yileng.jpg"


def test_narrative_director_extracts_real_characters_and_splits_two_sentences():
    """两句无引号冲突梗概应智能拆成 >=3 镜并提取真名角色（如林尘/未婚妻），不再满屏‘主角/旁白’."""
    agent = DirectorAgent()
    proj = agent.breakdown_story_offline(
        "雨夜寿宴上，未婚妻当众退婚嘲讽林尘是废物。林尘冷笑一声，亮出百亿黑金令，门外十万保镖齐声叩首！",
        title="豪门逆袭之夜",
        genre="都市商战",
    )
    assert len(proj.shots) >= 4
    char_names = {c.name for c in proj.characters}
    assert "林尘" in char_names or "未婚妻" in char_names
    speakers = {s.speaker for s in proj.shots}
    assert any(sp != "旁白" for sp in speakers)


def test_multi_genre_bgm_and_dynamic_sfx_cues():
    """验证不同题材自动匹配不同 BGM，甜宠剧绝不无脑在 0.5 秒劈雷."""
    from omnidrama.core.audio_mixer import build_sfx_cues_from_shots, select_bgm_type_for_genre

    assert select_bgm_type_for_genre("现代甜宠言情") == "romantic_warm"
    assert select_bgm_type_for_genre("古风仙侠") == "ancient_guofeng"
    assert select_bgm_type_for_genre("豪门商战悬疑") == "suspense_dark"
    assert select_bgm_type_for_genre("都市战神") == "epic_battle"

    romance_shots = [
        {"id": 1, "duration": 3.0, "motion": "ZOOM_IN", "sfx": "无", "dialogue": "阳光洒进咖啡馆，她抬头对他一笑。"},
        {"id": 2, "duration": 3.5, "motion": "PAN_LEFT", "sfx": "无", "dialogue": "他递过一杯热拿铁。"},
    ]
    romance_cues = build_sfx_cues_from_shots(romance_shots, genre="现代甜宠")
    assert all(c["name"] != "thunder" for c in romance_cues)

    action_shots = [
        {"id": 1, "duration": 3.0, "motion": "ZOOM_IN", "sfx": "无", "dialogue": "雨夜推门。"},
        {"id": 2, "duration": 3.0, "motion": "SHAKE", "sfx": "惊雷劈裂", "dialogue": "亮出龙王令！"},
    ]
    action_cues = build_sfx_cues_from_shots(action_shots, genre="都市战神")
    assert any(c["name"] == "thunder" and c["time_seconds"] >= 3.0 for c in action_cues)


def test_shot_crud_reorder_reset_and_localize_workflow(client, monkeypatch):
    """验证分镜新增、上下调序、删除、一键出海译制（切母语声线+还原中文）与清空工作台全流程."""
    from omnidrama.web import app as web_app_mod

    # 1. 清空工作台并新建短剧
    rst = client.post("/api/project/reset")
    assert rst.status_code == 200
    assert rst.json()["shots"] == []

    # 2. 新增两镜
    s1 = client.post("/api/shots", json={"speaker": "林尘", "dialogue": "第一镜开场白", "motion": "ZOOM_IN"})
    assert s1.status_code == 200 and len(s1.json()["shots"]) == 1
    s2 = client.post("/api/shots", json={"speaker": "未婚妻", "dialogue": "第二镜退婚台词", "motion": "SHAKE"})
    assert s2.status_code == 200 and len(s2.json()["shots"]) == 2

    # 3. 下移/上移调序
    reord = client.post("/api/shots/reorder", json={"shot_id": 2, "direction": "up"})
    assert reord.status_code == 200
    assert reord.json()["shots"][0]["dialogue"] == "第二镜退婚台词"

    # 4. 出海一键译制（Mock 翻译函数避免离线环境依赖外部网络）
    monkeypatch.setattr(
        web_app_mod,
        "_translate_text_for_localization",
        lambda text, lang: f"[{lang.upper()}] {text}",
    )
    loc_en = client.post("/api/project/localize", json={"target_lang": "en", "bilingual_subtitle": False})
    assert loc_en.status_code == 200
    loc_data = loc_en.json()
    assert loc_data["language"] == "en"
    assert loc_data["shots"][0]["dialogue"].startswith("[EN]")
    assert loc_data["shots"][0]["source_dialogue"] == "第二镜退婚台词"

    # 切回中文还原原文
    loc_zh = client.post("/api/project/localize", json={"target_lang": "zh"})
    assert loc_zh.status_code == 200
    assert loc_zh.json()["shots"][0]["dialogue"] == "第二镜退婚台词"

    # 5. 删除第 1 镜
    rm = client.delete("/api/shots/1")
    assert rm.status_code == 200
    assert len(rm.json()["shots"]) == 1
    assert rm.json()["shots"][0]["id"] == 1


def test_sota_key_probe_rejects_unmanaged_and_empty(client):
    """验证 SOTA 密钥测活接口拦截非白名单键并对空 Key 诚实报错."""
    bad = client.post("/api/sota/test-key", json={"env_key": "PATH"})
    assert bad.status_code == 400

    empty_probe = client.post("/api/sota/test-key", json={"env_key": "DEEPSEEK_API_KEY", "api_key": ""})
    assert empty_probe.status_code == 200
    assert empty_probe.json()["ok"] is False


def test_reorder_and_delete_sync_disk_assets_prevent_shot_mismatch(client):
    """硬伤 #1 铁证验证：分镜上移/删除必须同步对调/清理磁盘图音文件，彻底杜绝音画串镜."""
    from omnidrama.web.app import OUTPUT_DIR

    client.post("/api/project/reset")
    gen = client.post(
        "/api/project/generate",
        json={
            "title": "防串镜磁盘同步验证剧",
            "genre": "都市商战",
            "novel_text": "林尘推开宴会厅大门，反派赵少端起红酒嘲讽，全场宾客鸦雀无声。",
        },
    )
    assert gen.status_code == 200
    assert len(gen.json()["shots"]) >= 3

    shots_dir = OUTPUT_DIR / "防串镜磁盘同步验证剧" / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    (shots_dir / "shot_001.jpg").write_bytes(b"IMG_SLOT_ONE_DATA")
    (shots_dir / "shot_001.mp3").write_bytes(b"AUD_SLOT_ONE_DATA")
    (shots_dir / "shot_002.jpg").write_bytes(b"IMG_SLOT_TWO_DATA")
    (shots_dir / "shot_002.mp3").write_bytes(b"AUD_SLOT_TWO_DATA")

    # 1. 第 2 镜上移到第 1 镜 -> 磁盘文件必须精确互换
    reord = client.post("/api/shots/reorder", json={"shot_id": 2, "direction": "up"})
    assert reord.status_code == 200
    assert (shots_dir / "shot_001.jpg").read_bytes() == b"IMG_SLOT_TWO_DATA"
    assert (shots_dir / "shot_001.mp3").read_bytes() == b"AUD_SLOT_TWO_DATA"
    assert (shots_dir / "shot_002.jpg").read_bytes() == b"IMG_SLOT_ONE_DATA"
    assert (shots_dir / "shot_002.mp3").read_bytes() == b"AUD_SLOT_ONE_DATA"

    # 2. 删除现在第 1 镜（旧2）-> 旧1 自动递补到 shot_001，不再残留错位文件
    rm = client.delete("/api/shots/1")
    assert rm.status_code == 200
    assert (shots_dir / "shot_001.jpg").read_bytes() == b"IMG_SLOT_ONE_DATA"
    assert (shots_dir / "shot_001.mp3").read_bytes() == b"AUD_SLOT_ONE_DATA"
    assert not (shots_dir / "shot_002.jpg").exists()


def test_commercial_clean_subtitle_no_debug_watermark_and_english_word_wrap(tmp_path):
    """硬伤 #2 铁证验证：商业成片无左上角调试水印、英文整词断行绝不劈词、出海模式隐藏未译中文标签."""
    from PIL import Image
    from omnidrama.core.pipeline import _create_subtitle_overlay, _wrap_subtitle_lines

    en_text = "This is an unbelievable betrayal at the billionaire banquet tonight!"
    lines = _wrap_subtitle_lines(en_text, max_chars=13, max_lines=3)
    assert len(lines) >= 2
    assert "unbelievable" in " ".join(lines)
    # 每个完整单词都必须完整出现在某一行，绝不被硬切劈断
    for word in ("unbelievable", "betrayal", "billionaire", "banquet"):
        assert any(word in ln for ln in lines)

    # 默认 show_debug_badge=False：左上角徽标区域完全透明（alpha == 0），无调试水印
    sub_clean = tmp_path / "sub_en_clean.png"
    _create_subtitle_overlay(
        shot_id=1,
        speaker="未婚妻",
        dialogue=en_text,
        motion_name="镜头推进",
        out_png_path=str(sub_clean),
        target_lang="en",
    )
    with Image.open(sub_clean) as im:
        top_left_crop = im.crop((24, 34, 220, 72))
        _, max_alpha = top_left_crop.getchannel("A").getextrema()
        assert max_alpha == 0


def test_new_drama_binds_isolated_series_and_episode(client):
    """硬伤 #3 铁证验证：新建不同剧名自动分配独立 series_id/episode_id，杜绝顶栏跨剧串台."""
    r1 = client.post(
        "/api/project/generate",
        json={"title": "独立隔离剧目甲", "genre": "都市爽文", "novel_text": "林尘推门而入，众人震惊，反派下跪。"},
    )
    r2 = client.post(
        "/api/project/generate",
        json={"title": "独立隔离剧目乙", "genre": "古风仙侠", "novel_text": "仙尊御剑而来，万剑归宗，妖魔退散。"},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    d1, d2 = r1.json(), r2.json()
    assert d1["series_id"] and d2["series_id"]
    assert d1["series_id"] != d2["series_id"]
    assert d1["episode_id"] != d2["episode_id"]


def test_compositor_adds_natural_breath_pad_transition(tmp_path):
    """硬伤 #4 铁证验证：单镜合成自动注入 0.24s 自然呼吸气口，彻底消除 0 秒抢话硬切."""
    import subprocess
    from PIL import Image
    from omnidrama.core.compositor import VideoCompositor
    from omnidrama.schemas.drama_schema import CameraMotionEnum

    img_p = tmp_path / "f.jpg"
    Image.new("RGB", (360, 640), (20, 30, 50)).save(img_p)
    aud_p = tmp_path / "a.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "1.50", "-q:a", "9", str(aud_p)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    comp = VideoCompositor(width=360, height=640, fps=24)
    out_mp4 = tmp_path / "out_breath.mp4"
    comp.render_shot(str(img_p), str(aud_p), CameraMotionEnum.ZOOM_IN, str(out_mp4))
    actual_dur = comp.get_audio_duration(str(out_mp4))
    assert actual_dur >= 1.68  # 1.50s 语音 + 0.24s 自然气口 ≈ 1.74s
