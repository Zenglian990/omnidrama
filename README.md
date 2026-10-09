# OmniDrama (灵眸漫剧工作台) - 顶级影视工业级 AI 短剧生产系统

> **全球顶配影视工业标准 · 好莱坞级视听体验 · 全板块 SOTA 技术矩阵**  
> 专为商业级短剧/漫剧工业化打造，拒绝玩具级低质代餐，全面整合全球顶尖生成式 AI 大模型。

---

## 💎 行业顶配技术选型矩阵 (SOTA Suite)

遵循最高工业标准，OmniDrama 在短剧生产的全流程中均接入业界天花板级技术：

| 生产板块 | 顶配技术选型 (SOTA Standard) | 核心优势与画质/听感指标 |
| :--- | :--- | :--- |
| **编剧与总导演** | **Claude 3.5 Sonnet / DeepSeek-R1** | 好莱坞级剧情张力曲线、专业分镜机位调度与角色特征固化锚点 |
| **定妆与分镜生图** | **FLUX.1 Pro (Black Forest Labs)** | 8K 胶片级摄影质感、精准光影氛围、真实人像质感与构图 |
| **微表情视频生成** | **MiniMax 海螺 Video-01** | 全球公认最强真人微表情、毛孔级皮肤、眼神光与影视级慢动作 |
| **打斗与物理运镜** | **快手可灵 Kling 2.0 Pro** | 复杂大动作打斗、物理交互碰撞、高动态范围与精细运镜控制 |
| **神经音画对口型** | **SyncLabs Pro (Sync.so)** | 毫秒级音画同步、真实牙齿/舌位生理运动对齐，告别模糊变形 |
| **奥斯卡级情感配音**| **ElevenLabs Multilingual v2** | 人类级呼吸喘息、轻蔑冷笑、愤怒咆哮与微表情叹息，情感爆发力拉满 |
| **电影原创配乐** | **Suno v3.5 Cinematic Score** | 汉斯·季默级史诗交响配乐、悬疑低音氛围 (Drone) 与高潮战歌 |
| **后期剪辑工业打通**| **剪映 / CapCut 原生工程注入** | 自动输出 `draft_content.json`，一键无缝注入系统剪映专业版草稿箱 |

---

## 🌟 核心杀手级特性

1. **三轨合一影视级母带系统 (Triple-Track Foley Audio)**：
   - 人声台词轨 + 好莱坞拟音环境音轨 (SFX) + 动态卡点配乐轨 (BGM)。
   - 自带广播级**自适应避让 (Adaptive Audio Ducking)**，角色开口对白时配乐自动压降 -6dB，剧场感十足。

2. **角色一致性锚点 (Character Consistency Vault)**：
   - 多角色资产库严格锁定面部特征、服饰风格与固定音色配对，杜绝“一镜一人脸”的行业通病。

3. **双轨灵活驱动 (Dual-Engine Execution)**：
   - **SOTA 商业生产轨**：一键调用海螺、可灵、FLUX.1 Pro、ElevenLabs 生成顶级商业短剧。
   - **极速预演预览轨**：内置 2.5D 硬件加速动态运镜与离线预演引擎，0 成本秒级完成全片结构验证。

4. **一键注入系统剪映专业版 (CapCut Pro Native Integration)**：
   - 自动探测 Windows 剪映专业版本地工程目录，点击按钮直接将画面、音频、音效、字幕完整轨道写入剪映草稿箱，创作者打开剪映即可精修调色。

---

## 🖥️ 可视化导演工作台 (Web Studio)

本地启动专业暗黑电影风工作台：

```bash
# 启动本地工作台 (FastAPI + Vue3)
python -m uvicorn omnidrama.web.app:app --host 127.0.0.1 --port 8765
```

浏览器访问 `http://127.0.0.1:8765`：
- **左栏**：角色定妆卡资产库与三轨声音引擎状态。
- **中栏**：全景分镜流 (Storyboard Flow)，支持单镜试听与运镜标签筛选。
- **右栏**：1080P 主监视器、全片与真人活化双模式播放器。
- **顶部**：SOTA 大模型密钥控制面板、一键注入剪映草稿、1080P 成片导出。

---

## 📱 原生安卓客户端 (Native Android App)

OmniDrama 官方配备了专为移动端打造的 **原生 Android 掌上导演室**，基于 **Kotlin + Jetpack Compose + Media3 (ExoPlayer)**：

- **源码目录**：`android/`
- **核心能力**：
  - 院线级 9:16 竖屏播放器，无缝切换电影成片与真人演员活化。
  - 掌上全景分镜卡片流，随时点播任一分镜对白与镜头调度。
  - SOTA 六大顶配大模型控制台与服务地址动态切换。
  - 手机远程一键触发桌面端注入剪映草稿。
- **一键编译与安装**：
  ```bash
  cd android
  ./gradlew assembleDebug
  # 生成 APK: android/app/build/outputs/apk/debug/app-debug.apk
  ```

---

## 🚀 命令行快速出片 (CLI)

```bash
# 执行完整导演编排与成片渲染
python -m omnidrama.cli --story omnidrama/sample_story.txt --title "至尊龙王归位" --genre "都市战神爽文"
```

---

## 🧪 自动化测试套件

```bash
python -m pytest -v
```
全套 16 项单元与集成测试：涵盖导演本体拆解、三轨音频混音、2.5D 运镜合成、真人活化、剪映草稿导出以及各大 SOTA 驱动契约校验。
