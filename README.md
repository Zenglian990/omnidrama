# OmniDrama (灵眸漫剧工作台) — AI 短剧与漫剧全流程生产中枢

<p align="center">
  <a href="https://omnidrama-79709693345.asia-east1.run.app"><img src="https://img.shields.io/badge/Google_Cloud_Run-亚太生产集群在线-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white" alt="Cloud Run"></a>
  <img src="https://img.shields.io/badge/Backend-FastAPI_%2B_FFmpeg-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Android-Kotlin_%2B_Compose_M3-3DDC84?style=for-the-badge&logo=android&logoColor=white" alt="Android">
  <img src="https://img.shields.io/badge/Pytest-39_Passed_(15_Modules)-2ea44f?style=for-the-badge&logo=pytest&logoColor=white" alt="Tests">
</p>

> **云端生产环境直达**：[https://omnidrama-79709693345.asia-east1.run.app](https://omnidrama-79709693345.asia-east1.run.app)  
> 面向商业短剧与动态漫剧的全流程自动化生产系统，涵盖小说/剧本结构化拆解、多角色资产锁定、分镜画面生成、三轨母带混音（台词 + SFX 拟音 + BGM 自动闪避）、口型与微表情合成，以及剪映专业版 (`draft_content.json`) 原生工程导出。

---

## 1. 系统架构与核心模块 (`core/` & `providers/`)

项目采用**插件化多模型路由架构**，既支持接入商业多模态大模型 API 生产成片，也支持零 API 成本的本地/云端离线预演合成：

### 核心引擎层 (`core/`)
| 模块文件 | 职责与技术实现 |
| :--- | :--- |
| `director.py` | **导演分镜本体引擎**：长篇小说/剧本结构化拆解、景别（特写/中景/全景）与运镜指令标注、角色外观锚点提取 |
| `series_manager.py` | **多集连续剧状态管理**：跨集角色外貌、服装、音色配对与剧情上下文持久化锁定 |
| `tts_engine.py` | **多角色配音与字幕引擎**：支持 Edge-TTS / ElevenLabs / F5-TTS 零样本克隆，同步生成毫秒级对齐 `.srt` 字幕 |
| `audio_mixer.py` | **三轨母带混音器**：人声轨 + 环境拟音轨 (SFX) + 动态配乐轨 (BGM)，内置 **-6dB 自适应闪避 (Audio Ducking)** |
| `motion_engine.py` | **2.5D 运镜与数字演员动力学**：推拉摇移关键帧插值、角色说话实时口型开合与呼吸微动合成 |
| `compositor.py` | **FFmpeg 音画多轨合成器**：1080P 竖屏 (9:16) / 横屏 (16:9) 帧率对齐、字幕烧录与 H.264 母带压制 |
| `capcut_exporter.py` | **剪映专业版工程导出器**：自动生成标准 `draft_content.json`，将视频、人声、音效、BGM、字幕分轨注入剪映草稿箱 |
| `quality_gate.py` & `cost_tracker.py` | **成片质量门禁与成本核算**：音画时长对齐校验、黑帧检测与多模型 API 调用成本实时统计 |

### 可插拔模型驱动层 (`providers/`)
系统内置 **15 个标准化 Provider 适配器**（统一继承自 `providers/base.py`）：
- **剧本与网文解析**：DeepSeek (`deepseek-chat` / `deepseek-reasoner`)、Claude 3.5 Sonnet、Gemini 2.5 Flash、番茄小说 PUA 字体反爬解码器 (`fanqie_provider.py`)
- **角色定妆与分镜生图**：FLUX.1 (`flux_provider.py`)、SiliconFlow (`siliconflow_provider.py`)、阿里通义万相 (`dashscope_provider.py`)、Pexels 实景素材库 (`pexels_provider.py`)
- **图生视频与物理运镜**：快手可灵 Kling (`kling_provider.py`)、MiniMax 海螺 (`minimax_provider.py`)、火山引擎 Seedance (`volcengine_seedance_provider.py`)、Google Colab 分布式算力池 (`colab_cluster_provider.py`)
- **口型同步与面部活化**：SyncLabs (`synclabs_provider.py`)、LivePortrait (`liveportrait_provider.py`)
- **语音克隆与配乐生成**：ElevenLabs (`elevenlabs_provider.py`)、F5-TTS (`f5_tts_provider.py`)、Suno (`suno_provider.py`)

---

## 2. 项目工程目录结构

```text
omnidrama/
├── app.py                        # 云端混合 ASGI 网关入口 (Gradio 节点监控 + FastAPI /studio 直通)
├── cli.py                        # 命令行一键导演编排与成片渲染入口
├── cloudrun.yaml                 # Google Cloud Run (asia-east1) 生产集群部署清单
├── Dockerfile                    # 生产级容器镜像定义 (Python 3.11 + FFmpeg)
├── docker-compose.yml            # Docker Compose 编排配置
├── requirements.txt              # Python 依赖清单
├── core/                         # 导演分镜、三轨混音、运镜合成、剪映导出等核心模块
├── providers/                    # 15 个多模态大模型与素材源驱动插件
├── schemas/                      # Pydantic 剧本、角色、分镜与时间轴数据契约
├── web/                          # 可视化导演工作台后端 (app.py) 与前端单页工作台 (index.html)
├── android/                      # 原生 Android 掌上导演端 (Kotlin + Jetpack Compose + Media3)
└── tests/                        # Pytest 自动化测试套件 (15 个测试文件 / 39 项测试用例)
```

---

## 3. 快速启动与部署指南

### 方式一：本地启动可视化导演工作台 (Web Studio)

```bash
# 1. 安装依赖（需确保系统已安装 FFmpeg）
pip install -r requirements.txt

# 2. 在仓库根目录启动 FastAPI 工作台服务
python -m uvicorn web.app:app --host 127.0.0.1 --port 8765
```

浏览器访问 `http://127.0.0.1:8765`：
- **左栏**：角色定妆卡资产库与三轨音频引擎状态；
- **中栏**：全景分镜流 (Storyboard Flow)，支持单镜试听、重抽与提示词微调；
- **右栏**：1080P 主监视器、多集连续剧管理与成片预览；
- **顶部**：API 密钥控制面板、剪映专业版草稿一键注入、MP4 成片导出。

### 方式二：命令行快速出片 (CLI)

```bash
python cli.py --story sample_story.txt --title "至尊龙王归位" --genre "都市战神爽文"
```

### 方式三：Docker 与 Google Cloud Run 云端部署

```bash
# 本地或云服务器 Docker Compose 一键启动 (映射 8080 端口)
docker compose up -d --build
```
生产环境已部署于 Google Cloud Run (`asia-east1`)：[https://omnidrama-79709693345.asia-east1.run.app](https://omnidrama-79709693345.asia-east1.run.app)

---

## 4. 原生安卓客户端 (`android/`)

配备基于 **Kotlin + Jetpack Compose + Media3 (ExoPlayer)** 的移动端掌上导演室（最新发布版 `v3.3.1`）：
- 支持连接 Google Cloud Run 云端后端 (`https://omnidrama-79709693345.asia-east1.run.app`) 或局域网工作站；
- 支持番茄小说链接导入（含 PUA 加密字体还原）、角色声线分配、全景分镜点播与 9:16 竖屏成片预览。

```bash
cd android
./gradlew assembleDebug
# 输出 APK: android/app/build/outputs/apk/debug/app-debug.apk
```

---

## 5. 自动化测试验证

```bash
python -m pytest tests -v
```
涵盖导演分镜拆解、番茄 PUA 解码、三轨混音闪避、2.5D 运镜、角色口型活化、连续剧状态管理、剪映草稿导出及多模型 Provider 契约校验，共 **15 个测试模块 / 39 项测试用例**全部通过。
