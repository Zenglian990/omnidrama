"""Hugging Face Spaces (ZeroGPU + FastAPI) 启动入口 — OmniDrama 云端后端."""
import os
import platform
import shutil
import subprocess
from pathlib import Path

# 1. 启动前同步 Hugging Face Space Secrets 到本地 .env（若存在）
BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"
MANAGED_KEYS = [
    "SILICONFLOW_API_KEY",
    "DEEPSEEK_API_KEY",
    "PEXELS_API_KEY",
    "MOONSHOT_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "BFL_API_KEY",
    "ELEVENLABS_API_KEY",
    "MINIMAX_API_KEY",
    "KLING_ACCESS_KEY",
    "SYNCLABS_API_KEY",
    "SUNO_API_KEY",
]

if not ENV_FILE.exists():
    initial_lines = []
    for k in MANAGED_KEYS:
        val = os.environ.get(k, "").strip()
        if val:
            initial_lines.append(f"{k}={val}")
    if initial_lines:
        ENV_FILE.write_text("\n".join(initial_lines) + "\n", encoding="utf-8")

import spaces
import gradio as gr
import gradio.routes
from fastapi.responses import JSONResponse
from web.app import app as omnidrama_app


def get_cloud_node_info():
    total_disk, used_disk, free_disk = shutil.disk_usage("/")
    mem_bytes = (
        os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        if hasattr(os, "sysconf")
        else 0
    )
    return {
        "status": "online",
        "service": "OmniDrama Studio Cloud Backend (v1.5.0)",
        "owner": "曾先生 (zenglian110110)",
        "space_host": os.getenv("SPACE_HOST", "zenglian110110-zeng-cloud-backend.hf.space"),
        "cpu_cores": os.cpu_count(),
        "memory_gb": round(mem_bytes / (1024**3), 2),
        "disk_free_gb": round(free_disk / (1024**3), 2),
        "python_version": platform.python_version(),
        "accelerator": os.getenv("ACCELERATOR", "ZeroGPU"),
    }


@spaces.GPU(duration=20)
def wake_zerogpu():
    try:
        out = (
            subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]
            )
            .decode()
            .strip()
        )
        return f"✅ ZeroGPU 显卡已激活: {out}"
    except Exception as e:
        return f"GPU 状态: {e}"


@omnidrama_app.get("/api/cloud/health")
async def cloud_health_endpoint():
    """云端节点健康检查与硬件状态接口."""
    return JSONResponse(get_cloud_node_info())


# 2. 在 ASGI 入口层直接分流：/studio、/api/*、/output/*、/assets/* 直通 OmniDrama FastAPI，其余走 Gradio
_orig_asgi_call = gradio.routes.App.__call__


async def _hybrid_asgi_call(self, scope, receive, send):
    if scope["type"] == "http":
        path = scope.get("path", "")
        if path == "/studio" or path == "/studio/":
            new_scope = dict(scope)
            new_scope["path"] = "/"
            new_scope["raw_path"] = b"/"
            return await omnidrama_app(new_scope, receive, send)
        if path.startswith(("/api/", "/output", "/assets")):
            return await omnidrama_app(scope, receive, send)
    return await _orig_asgi_call(self, scope, receive, send)


gradio.routes.App.__call__ = _hybrid_asgi_call


with gr.Blocks(title="曾练AI短剧创作 (OmniDrama Studio)") as demo:
    gr.Markdown("## 🎬 曾先生 OmniDrama 短剧云端后端 (ZeroGPU + FastAPI)")
    gr.HTML(
        '<div style="margin:12px 0;padding:14px;border-radius:10px;background:#1e1b4b;color:#fff;">'
        '🚀 <b>OmniDrama 可视化导演工作台已就绪：</b> '
        '<a href="/studio" target="_blank" style="color:#38bdf8;font-weight:bold;text-decoration:underline;">'
        '点击打开全屏导演工作台 (/studio)</a> ｜ '
        '安卓 App 服务地址请填：<code>https://zenglian110110-zeng-cloud-backend.hf.space</code>'
        '</div>'
    )
    with gr.Row():
        btn_info = gr.Button("📊 刷新云端节点配置", variant="primary")
        btn_gpu = gr.Button("⚡ 唤醒免费 48GB 显卡 (ZeroGPU)")
    json_out = gr.JSON(label="云端节点实时指标", value=get_cloud_node_info)
    gpu_out = gr.Textbox(label="ZeroGPU 显卡状态")
    btn_info.click(fn=get_cloud_node_info, outputs=json_out)
    btn_gpu.click(fn=wake_zerogpu, outputs=gpu_out)


if __name__ == "__main__":
    demo.launch()
