# OmniDrama (灵眸漫剧) - 工业级 AI 漫剧导演系统技术规范 (SPEC.md)

## 1. 目标与愿景 (Objective)
打造融合业界顶尖架构的下一代 AI 漫剧/短剧导演工作台：
- **借鉴 Toonflow**：无限画布 (Infinite Canvas) 节点化防废片交互，单格即时微调，彻底拒绝黑盒盲盒。
- **借鉴 BigBanana**：工业级 Script-to-Asset-to-Keyframe（剧本-资产-关键帧）导演本体，精确控制景别（特写/全景）、运镜（推拉摇移）与多角色站位。
- **借鉴 StoryDiffusion / ComfyUI**：角色面部与服装一致性算法锁定，零换脸废片。
- **独家成本杀手**：长文本低成本 LLM (Gemini/DeepSeek) + 微软免费 edge-tts + FFmpeg 2.5D 动态运镜代码渲染（单集成本控制在 0~1 元人民币以内）。

## 2. 技术栈 (Tech Stack)
- **底层与核心流水线**：Python 3.14 (AsyncIO, Pydantic v2, Subprocess/FFmpeg, edge-tts)
- **导演智能体 (Director Agent)**：Google Gemini Flash API (百万上下文、高免费配额) / DeepSeek-V3
- **多角色配音 (Audio Engine)**：微软 `edge-tts` (全角色情感预设：云希、晓晓、云健等)，零成本
- **后期合成与运镜 (Compositor)**：FFmpeg 8.1.2 硬件加速过滤链 (Ken Burns 推拉摇移、镜头震颤、转场淡入淡出、字幕自动烧录)
- **前端工作台 (Phase 3)**：Vue 3 + Vite + Vue Flow (无限画布) + TailwindCSS

## 3. 命令行规范 (Commands)
```bash
# 依赖安装
pip install -r requirements.txt

# 运行自动化测试套件
pytest omnidrama/tests -v

# 运行导演引擎（单篇小说拆解分镜）
python -m omnidrama.core.director --input sample_story.txt

# 运行完整端到端漫剧合成流水线
python -m omnidrama.core.pipeline --story sample_story.txt --output omnidrama/output/episode_1.mp4
```

## 4. 项目结构 (Project Structure)
```
omnidrama/
├── SPEC.md                  # 核心工程规范与架构
├── requirements.txt         # Python 依赖
├── config/                  # 系统与预设配置文件
│   ├── voices.json          # 角色配音音色映射表
│   └── camera_motions.json  # 影视级运镜预设库 (Ken Burns / Shake / Pan / Zoom)
├── schemas/                 # Pydantic 严格数据契约
│   ├── drama_schema.py      # 剧本、角色资产卡、分镜镜头契约
│   └── render_task.py       # 渲染作业队列定义
├── core/                    # 核心处理引擎
│   ├── director.py          # 导演智能体：结构化分镜拆解
│   ├── tts_engine.py        # 免费配音与 SRT 字幕生成器 (edge-tts)
│   ├── compositor.py        # FFmpeg 2.5D 影视运镜合成器
│   └── pipeline.py          # 端到端串联调度管线
├── assets/                  # 演示素材与占位图片
├── output/                  # 生成的成片与中间资产目录
└── tests/                   # TDD 自动化测试用例
```

## 5. 核心数据契约 (Data Contracts)
每一个分镜镜头 (Shot) 必须包含以下强类型定义：
- `shot_id`: 镜头编号 (如 1, 2, 3...)
- `scene_description`: 画面剧情描述
- `camera`: 景别（特写 Close-up、中景 Medium、全景 Wide）与运镜动作（zoom_in, zoom_out, pan_left, pan_right, shake）
- `character_assets`: 画面中出现的角色名单与状态
- `prompt`: 优化后的生图提示词（包含画风和一致性锚点）
- `dialogue`: 对白或旁白文本
- `speaker`: 说话角色（映射到 edge-tts 音色）

## 6. 测试与质量边界 (Boundaries)
- **Always do**:
  - 所有镜头数据必须经过 Pydantic 校验，拒绝空提示词或无效运镜参数。
  - 所有音视频合成任务必须捕获 FFmpeg 异常退出并记录标准错误流。
  - 核心功能遵循 TDD 测试驱动开发（先写测试，再写实现）。
- **Never do**:
  - 严禁在脚本中硬编码任何收费商业 API 的不可控调用循环。
  - 严禁盲目直接输出无字幕、无动态运镜的纯死图视频。
