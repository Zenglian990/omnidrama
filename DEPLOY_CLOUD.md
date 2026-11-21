# OmniDrama 云端后端部署与移动端公网直连指南

> **核心原则**：短剧创作涉及 1080P/24FPS 视频合成、三轨母带音频压降、大模型 API 调度与微表情渲染，这些重型算力必须由**云端后端 (Cloud Backend)** 统一处理，而**安卓手机端 (Android App)** 作为掌上监视器和控制终端。

---

## 🏗️ 架构分工模型 (Client-Server Architecture)

```
[ 安卓手机端 (Android App) ] 
       │  (HTTPS/WSS API 交互，随时随地监看、点播、控制)
       ▼
[ 云端后端服务 (FastAPI Cloud Server) ] ◄──► [ 6大顶级模型集群 (SOTA APIs) ]
       │  (1080P FFmpeg 运镜渲染 / 三轨影视母带 / 剪映草稿生成)
       ▼
[ 媒体对象存储 / 本地磁盘持久化 ]
```

---

## 🚀 三种云端部署方案 (根据场景自由选择)

### 方案一：公网云服务器一键部署 (推荐生产商业化，7×24小时在线)
适用场景：短剧工作室、出海分发、多人远程协同。

1. **准备一台云服务器** (腾讯云、阿里云、华为云或海外 VPS，推荐 2核4G 或以上，系统 Ubuntu 22.04+)。
2. **克隆代码并一键启动 Docker**：
   ```bash
   git clone https://github.com/Zenglian990/omnidrama.git
   cd omnidrama
   docker compose up -d --build
   ```
3. **在手机端连接**：
   打开安卓手机 OmniDrama App -> 点击右上角设置 -> 将服务地址修改为：
   `http://你的云服务器IP:8765`（或绑定域名 `https://api.yourdomain.com`）。

---

### 方案二：本地电脑免费 Cloudflare Tunnel 穿透 (0 成本，当前电脑秒变云端)
适用场景：不想购买云服务器，直接用自己当前的电脑作为“算力母机”，人在外面用手机 5G 随时连回家中电脑。

1. **下载并安装 Cloudflare Tunnel (cloudflared)**：
   ```bash
   winget install Cloudflare.cloudflared
   ```
2. **启动对本地 8765 端口的免费公网映射**：
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8765
   ```
3. 终端会即时生成一个全球可访问的免费 HTTPS 临时域名（例如 `https://xyz-random.trycloudflare.com`）。
4. **在手机端连接**：
   直接将该 HTTPS 域名填入安卓手机 App 的服务地址栏，在户外手机 5G 网络下即可随时随地出片！

---

### 方案三：工作室局域网 WiFi 直连 (零网络延迟)
适用场景：手机与电脑连接同一个办公室/家里的 WiFi 路由器。

1. **查询电脑在局域网的 IP 地址**：
   在电脑 PowerShell 运行 `ipconfig`，找到形如 `192.168.1.100` 或 `192.168.31.25` 的 IPv4 地址。
2. **在手机端连接**：
   打开手机 App 设置 -> 填入 `http://192.168.1.100:8765` 即可实时连通电脑后台。

---

## 🛡️ 离线弹性保障 (Offline Resilience)
即使在未连上云端后端的弱网/断网状态下，手机 App 依然内置了完整的《至尊龙王归位》首发工程离线资产，支持 100% 离线预览与分镜检查，绝不会崩溃或黑屏。
