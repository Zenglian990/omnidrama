# OmniDrama Android (灵眸漫剧掌上导演室)

OmniDrama 官方原生 Android 客户端，基于 **Kotlin + Jetpack Compose + Media3 (ExoPlayer)** 打造，专为 9:16 竖屏短剧创作与主监视器设计。

---

## 🌟 核心特性

1. **院线级 9:16 掌上主监视器 (Master Vertical Player)**：
   - 基于 AndroidX Media3 / ExoPlayer 深度定制，支持 1080P/24FPS 竖屏无缝循环播放与秒开缓冲。
   - 双播放模式随时切换：**全片电影级成片** 与 **真人演员活化 (微表情+口型)**。
2. **全景分镜流与单镜检查 (Storyboard Flow)**：
   - 包含景别（特写、中景、全景）、运镜轨迹（推进、拉远、横移、震撼）与对白字幕。
   - 点击任意分镜卡片可直接定位或试听对白。
3. **角色定妆与多轨母带 (Character & Audio Vault)**：
   - 角色人设、服饰特征与配音音色预设卡片。
   - 人声台词轨、好莱坞拟音环境音效 (SFX) 与电影交响配乐 (BGM) 状态监视。
4. **SOTA 行业顶配大模型控制台 (Engine Control Drawer)**：
   - 支持移动端查看 MiniMax 海螺、快手可灵、FLUX.1 Pro、ElevenLabs、SyncLabs、Suno 六大顶配大模型引擎就绪状态。
   - 支持随时动态配置与切换局域网/公网后端服务地址。
5. **一键注入系统剪映专业版草稿**：
   - 手机端远程一键触发桌面端将当前漫剧工程写入剪映草稿箱。
6. **离线弹性高可用 (Offline Resilient Mode)**：
   - 内置离线回退数据包，在离线或弱网环境下依然可流畅完整体验。

---

## 🚀 编译与运行 (Build & Run)

### 方式一：Android Studio 一键导入
1. 打开 **Android Studio** (推荐 Ladybug / 2024.2+)。
2. 选择 **Open Project** -> 选择 `omnidrama/android` 目录。
3. 等待 Gradle 同步完成，连接手机或启动模拟器，点击 **Run** (绿色三角箭头) 即可运行。

### 方式二：命令行编译 APK (Gradle)
```bash
cd android
./gradlew assembleDebug
```
生成的 APK 路径为：
`android/app/build/outputs/apk/debug/app-debug.apk`

### 方式三：ADB 一键安装到连接手机
```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```
