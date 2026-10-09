# OmniDrama (灵眸漫剧工作台)

> **综合业界优秀方案的下一代 AI 漫剧/短剧工业化生产系统**  
> 融合 **Toonflow**（无限画布与防废片交互）、**BigBanana**（工业级 Script-to-Keyframe 导演本体）、**StoryDiffusion**（角色一致性锁脸）以及独创的 **2.5D 极低成本电影级动态运镜引擎**。

---

## 🌟 核心特性与优势

1. **工业级导演智能体 (Director Agent)**：
   - 自动将长篇小说/短文拆解为结构化镜头清单。
   - 包含专业景别控制（特写 Close-up、中景 Medium、全景 Wide）与运镜决策（推进、拉远、左移、右移、镜头震撼）。
2. **零成本多角色配音与字幕 (Edge-TTS)**：
   - 深度集成微软神经网络语音（云希、晓晓、云健、云扬等）。
   - 自动分配男女主角与反派音色，毫秒级对齐并导出标准 `.srt` 字幕。
3. **2.5D 电影级动态运镜与后期合成 (FFmpeg Engine)**：
   - 彻底打破“必须靠昂贵视频模型生视频”的烧钱模式。
   - 采用代码级硬件加速运镜算法（平滑推拉摇移、受击颤动），**渲染成本为 0**，几秒钟即可导出高清视频。
4. **轻量扎实，无需昂贵显卡**：
   - 核心调度与剪辑合成基于 CPU 优化，即使普通办公电脑也能高速出片。

---

## 🚀 快速上手 (Quick Start)

### 1. 安装依赖
```bash
pip install -r omnidrama/requirements.txt
```

### 2. 运行自动化测试
```bash
pytest omnidrama/tests -v
```

### 3. 一键出片 (CLI)
```bash
# 从小说文本一键生成完整带配音与动态运镜的漫剧视频
python -m omnidrama.cli --story omnidrama/sample_story.txt --title "至尊龙王归位" --genre "都市战神爽文"
```

生成后的成片、分镜素材与字幕将存放在 `omnidrama/output/` 对应项目目录下。
