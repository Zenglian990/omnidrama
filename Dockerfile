# OmniDrama 生产级轻量化云端容器镜像 (Production Cloud Backend Dockerfile)
FROM python:3.11-slim

# 仅安装生产必需的 FFmpeg 与 CJK 中文字体（剔除 git / X11 / OpenCV 等冗余系统包，加速构建与冷启动）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    fontconfig \
    curl \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 仅安装生产精简 Python 依赖（不含 pytest 测试包）
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# 复制应用代码（已通过 .dockerignore 排除 tests/、android/、*.apk、output/ 等冗余文件）
COPY . .

# 建立符号链接，确保 python -m 与常规 omnidrama.* 导入在任意工作目录均可稳定解析
RUN ln -sf /app /app/omnidrama

# 暴露端口 (Google Cloud Run 标准 8080)
EXPOSE 8080

ENV PYTHONPATH=/app:/app/omnidrama
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=Asia/Shanghai
ENV PORT=8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8080}/health || exit 1

CMD ["sh", "-c", "python -m uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
