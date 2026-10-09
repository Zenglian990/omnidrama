# OmniDrama 生产级云端后端容器镜像 (Production Cloud Backend Dockerfile)
FROM python:3.11-slim

# 安装 FFmpeg 及必要系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 生产依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8765

ENV PYTHONPATH=/app:/app/omnidrama
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "python -m uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8765}"]
