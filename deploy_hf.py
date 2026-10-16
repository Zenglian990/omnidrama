"""一键将 OmniDrama 全量后端同步部署至 Hugging Face Space (zenglian110110/zeng-cloud-backend)."""
import json
import os
import urllib.request
from pathlib import Path

SPACE_ID = os.getenv("HF_SPACE_ID", "zenglian110110/zeng-cloud-backend")
ROOT_DIR = Path(__file__).parent

SKIP_DIRS = {".git", ".github", "android", "output", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", "sfx", "bgm"}
SKIP_EXTS = {".pyc", ".pyo", ".mp4", ".apk", ".wav", ".mp3", ".env", ".ps1"}
SKIP_FILES = {".env", "deploy_hf.py"}

HF_README_HEADER = """---
title: 曾练AI短剧创作 (OmniDrama Studio)
emoji: 🎬
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 5.23.1
app_file: app.py
pinned: true
---

"""


def _get_hf_token() -> str:
    env_tok = os.getenv("HF_TOKEN", "").strip()
    if env_tok:
        return env_tok
    token_file = Path.home() / ".huggingface" / "token"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    raise RuntimeError("Missing HF_TOKEN environment variable or ~/.huggingface/token")


def deploy():
    token = _get_hf_token()
    lines = [
        json.dumps(
            {
                "key": "header",
                "value": {"summary": "Sync OmniDrama Studio v1.5.0 full backend to Hugging Face Space"},
            }
        )
    ]

    file_count = 0
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname in SKIP_FILES or any(fname.endswith(ext) for ext in SKIP_EXTS):
                continue
            full_path = Path(dirpath) / fname
            rel_path = full_path.relative_to(ROOT_DIR).as_posix()

            try:
                content = full_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            if rel_path == "README.md" and not content.startswith("---"):
                content = HF_README_HEADER + content

            lines.append(
                json.dumps(
                    {
                        "key": "file",
                        "value": {
                            "content": content,
                            "path": rel_path,
                            "encoding": "utf-8",
                        },
                    }
                )
            )
            file_count += 1

    body = "\n".join(lines).encode("utf-8")
    url = f"https://huggingface.co/api/spaces/{SPACE_ID}/commit/main"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-ndjson",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print(f"Deployed {file_count} files -> {result.get('commitUrl')}")


if __name__ == "__main__":
    deploy()
