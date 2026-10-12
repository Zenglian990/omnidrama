package com.omnidrama.app.ui.screens

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.omnidrama.app.data.local.LocalAndroidEngine
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.ShotItem
import com.omnidrama.app.data.model.SotaStatusResponse
import com.omnidrama.app.data.model.VoiceItem
import com.omnidrama.app.data.repository.DramaRepository
import com.omnidrama.app.ui.components.*
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.launch

fun downloadVideoToPhone(context: Context, videoPathOrUrl: String, serverUrl: String, title: String, mode: String = "full") {
    val safeTitle = title.ifBlank { "未命名短剧" }
    if (videoPathOrUrl.isBlank()) {
        Toast.makeText(context, "⚠️ 请先点击【⚡ 一键制作 / 渲染全片】生成视频后再下载", Toast.LENGTH_LONG).show()
        return
    }
    // 1. 如果是手机本地 MediaCodec 硬件压制的 MP4 文件，直接导出至系统相册 Movies
    if (videoPathOrUrl.startsWith("/")) {
        val msg = LocalAndroidEngine.exportLocalMp4ToMovies(context, videoPathOrUrl, safeTitle)
        Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
        return
    }
    // 2. 如果是远程服务器流地址，通过 DownloadManager 下载至 Movies
    try {
        val downloadUrl = if (videoPathOrUrl.startsWith("http")) {
            "$serverUrl/api/video/download?mode=$mode&t=${System.currentTimeMillis()}"
        } else {
            "$serverUrl$videoPathOrUrl"
        }
        val fileName = "${safeTitle}_曾练AI短剧成片_${System.currentTimeMillis() % 10000}.mp4"
        val request = DownloadManager.Request(Uri.parse(downloadUrl))
            .setTitle("正在下载《$safeTitle》短剧成片")
            .setDescription("保存至手机相册 Movies 目录: $fileName")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_MOVIES, fileName)
            .addRequestHeader("Bypass-Tunnel-Reminder", "true")
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(true)

        val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        dm.enqueue(request)
        Toast.makeText(context, "📥 已开始下载《$safeTitle》成片至手机相册 (Movies)！", Toast.LENGTH_LONG).show()
    } catch (e: Exception) {
        Toast.makeText(context, "下载启动失败: ${e.localizedMessage}", Toast.LENGTH_LONG).show()
    }
}

@Composable
fun StudioScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val repo = remember { DramaRepository() }

    val prefs = remember { context.getSharedPreferences("omnidrama_prefs", Context.MODE_PRIVATE) }
    var serverUrl by remember {
        mutableStateOf(prefs.getString("server_url", "https://omnidrama-zeng.loca.lt") ?: "https://omnidrama-zeng.loca.lt")
    }
    var project by remember { mutableStateOf(ProjectData()) }
    var creatorWorks by remember { mutableStateOf<List<ProjectData>>(emptyList()) }
    var sotaInfo by remember { mutableStateOf(SotaStatusResponse()) }
    var availableVoices by remember { mutableStateOf<List<VoiceItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var isOnline by remember { mutableStateOf(false) }
    var isSavingKeys by remember { mutableStateOf(false) }

    var selectedTab by remember { mutableIntStateOf(0) } // 0: 监视器, 1: 分镜流, 2: 角色库
    var activeVideoMode by remember { mutableStateOf("full") } // "full" or "live"
    var showSotaDialog by remember { mutableStateOf(false) }
    var showDramaSwitcherDialog by remember { mutableStateOf(false) }

    var showProductionStudioDialog by remember { mutableStateOf(false) }
    var showCharacterEditDialog by remember { mutableStateOf(false) }
    var editingCharacter by remember { mutableStateOf<CharacterItem?>(null) }
    var showGenerateScriptDialog by remember { mutableStateOf(false) }
    var isGeneratingScript by remember { mutableStateOf(false) }

    var editingShot by remember { mutableStateOf<ShotItem?>(null) }
    var isSavingShot by remember { mutableStateOf(false) }
    var shotRefreshVersion by remember { mutableIntStateOf(0) }

    fun refreshData(showToast: Boolean = false) {
        scope.launch {
            isLoading = true
            try {
                // 清理旧版残留预置小说（仅首次执行一次）
                if (!prefs.getBoolean("v160_cleaned_presets", false)) {
                    val existing = LocalAndroidEngine.getCreatorWorks(context)
                    val presetTitles = setOf("至尊龙王归位", "真千金归来杀疯豪门", "真千金杀疯豪门", "修仙万载重回都市")
                    existing.filter { it.title in presetTitles }.forEach {
                        LocalAndroidEngine.deleteCreatorWork(context, it.title)
                    }
                    prefs.edit().putBoolean("v160_cleaned_presets", true).apply()
                }

                val p = repo.getProject(context, serverUrl)
                val s = repo.getSotaStatus(context, serverUrl)
                val v = repo.getVoices(serverUrl)
                project = p
                creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                sotaInfo = s
                availableVoices = v
                // 100% 真实检测：只有真正连上远程服务器才显示 isOnline = true
                isOnline = !s.system.os.startsWith("手机独立算力模式") && !s.system.os.startsWith("离线") && !s.system.os.startsWith("未连接")
                if (showToast) {
                    val confCount = s.providers.values.count { it.configured }
                    if (isOnline) {
                        val titleDesc = if (p.title.isNotBlank()) "当前作品《${p.title}》" else "作品库为空"
                        Toast.makeText(context, "✅ 远程机房已连接！$titleDesc，已配置 $confCount 项 API Key", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(context, "📱 当前为【手机独立算力模式】（支持番茄小说直连、手机TTS配音与本地MP4硬件压制）", Toast.LENGTH_LONG).show()
                    }
                }
            } catch (e: Exception) {
                isOnline = false
                creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                if (showToast) {
                    Toast.makeText(context, "📱 已切换至手机独立算力模式", Toast.LENGTH_SHORT).show()
                }
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshData(showToast = false)
    }

    val hasActiveProject = project.title.isNotBlank() && project.shots.isNotEmpty()

    Scaffold(
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(BgDark)
                    .statusBarsPadding()
                    .border(width = 0.5.dp, color = BorderDark)
            ) {
                // Tier 1: 品牌顶栏 (高端电影Logo + 真实状态胶囊 + 刷新 + 设置)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    BrandLogo()

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // 100% 真实算力状态胶囊（绝不虚标机房在线）
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(12.dp))
                                .background(if (isOnline) Color(0xFF064E3B) else Color(0xFF1E293B))
                                .border(0.5.dp, if (isOnline) Color(0xFF10B981) else Color(0xFF38BDF8), RoundedCornerShape(12.dp))
                                .clickable { refreshData(showToast = true) }
                                .padding(horizontal = 7.dp, vertical = 3.dp)
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(6.dp)
                                        .clip(CircleShape)
                                        .background(if (isOnline) Color(0xFF10B981) else Color(0xFF38BDF8))
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    text = if (isOnline) "远程机房已连" else "手机独立算力",
                                    color = if (isOnline) Color(0xFF6EE7B7) else Color(0xFF7DD3FC),
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        Spacer(modifier = Modifier.width(4.dp))

                        // 刷新按钮
                        IconButton(
                            onClick = { refreshData(showToast = true) },
                            modifier = Modifier.size(32.dp),
                            enabled = !isLoading
                        ) {
                            if (isLoading) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(15.dp),
                                    color = BrandCyan,
                                    strokeWidth = 2.dp
                                )
                            } else {
                                Icon(
                                    imageVector = Icons.Default.Refresh,
                                    contentDescription = "Refresh",
                                    tint = BrandCyan,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        }

                        // 设置按钮
                        IconButton(
                            onClick = {
                                refreshData(showToast = false)
                                showSotaDialog = true
                            },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Settings,
                                contentDescription = "Settings",
                                tint = AccentGold,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                }

                // Tier 2: 创作者作品库切换条 + 番茄小说添加新剧
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 我的作品库切换按钮
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .background(CardDark)
                            .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
                            .clickable {
                                creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                                showDramaSwitcherDialog = true
                            }
                            .padding(horizontal = 8.dp, vertical = 6.dp)
                    ) {
                        Text(
                            text = if (project.title.isNotBlank()) "《${project.title}》" else "📚 我的作品库 (${creatorWorks.size})",
                            color = if (project.title.isNotBlank()) BrandCyan else AccentGold,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.width(2.dp))
                        Icon(
                            imageVector = Icons.Default.ArrowDropDown,
                            contentDescription = "Switch",
                            tint = BrandCyan,
                            modifier = Modifier.size(16.dp)
                        )
                        if (project.genre.isNotBlank()) {
                            Spacer(modifier = Modifier.width(4.dp))
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(BorderDark)
                                    .padding(horizontal = 5.dp, vertical = 1.dp)
                            ) {
                                Text(
                                    text = project.genre,
                                    color = AccentGold,
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }

                    // 右侧操作按钮组
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Button(
                            onClick = { showGenerateScriptDialog = true },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGold),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 5.dp),
                            shape = RoundedCornerShape(16.dp),
                            modifier = Modifier.height(30.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.AutoAwesome,
                                contentDescription = null,
                                tint = BgDark,
                                modifier = Modifier.size(13.dp)
                            )
                            Spacer(modifier = Modifier.width(3.dp))
                            Text(
                                text = "🍅 添加作品 / 创作新剧",
                                color = BgDark,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.ExtraBold
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(4.dp))
            }
        },
        containerColor = BgDark
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // Tab 导航栏
            TabRow(
                selectedTabIndex = selectedTab,
                containerColor = CardDark,
                contentColor = BrandCyan
            ) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text("院线监视器", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text("全景分镜流 (${project.shots.size})", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                )
                Tab(
                    selected = selectedTab == 2,
                    onClick = { selectedTab = 2 },
                    text = { Text("角色定妆库 (${project.characters.size})", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                )
            }

            when (selectedTab) {
                0 -> {
                    // 院线监视器
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(14.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Button(
                                onClick = { activeVideoMode = "full" },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = if (activeVideoMode == "full") BrandCyan else BorderDark
                                ),
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Text(
                                    text = "全片电影级成片",
                                    color = if (activeVideoMode == "full") BgDark else TextSecondary,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            Button(
                                onClick = { activeVideoMode = "live" },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = if (activeVideoMode == "live") BrandPurple else BorderDark
                                ),
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Text(
                                    text = "🔥 真人演员活化",
                                    color = if (activeVideoMode == "live") Color.White else TextSecondary,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(10.dp))

                        val currentVideoPath = if (activeVideoMode == "full") project.video_url else project.live_actor_video.ifBlank { project.video_url }
                        val fullVideoUrl = when {
                            currentVideoPath.isBlank() -> ""
                            currentVideoPath.startsWith("http") || currentVideoPath.startsWith("/") -> currentVideoPath
                            else -> "$serverUrl$currentVideoPath"
                        }

                        VideoPlayer(
                            videoUrl = fullVideoUrl,
                            hasActiveProject = hasActiveProject,
                            onAddWorkClick = { showGenerateScriptDialog = true },
                            onProduceClick = {
                                if (hasActiveProject) {
                                    showProductionStudioDialog = true
                                } else {
                                    showGenerateScriptDialog = true
                                }
                            },
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f)
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Button(
                                onClick = {
                                    if (!hasActiveProject) {
                                        showGenerateScriptDialog = true
                                    } else {
                                        showProductionStudioDialog = true
                                    }
                                },
                                modifier = Modifier
                                    .weight(1f)
                                    .height(48.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent),
                                contentPadding = PaddingValues(0.dp),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .background(
                                            Brush.horizontalGradient(
                                                listOf(Color(0xFFFFDF70), Color(0xFFFFB800), Color(0xFF00F2FE))
                                            )
                                        ),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(
                                            imageVector = Icons.Default.AutoAwesome,
                                            contentDescription = null,
                                            tint = Color(0xFF0C101A),
                                            modifier = Modifier.size(18.dp)
                                        )
                                        Spacer(modifier = Modifier.width(6.dp))
                                        Text(
                                            text = if (hasActiveProject) "⚡ 一键制作 / 渲染全片" else "🍅 添加小说作品并制作短剧",
                                            color = Color(0xFF0C101A),
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.Black
                                        )
                                    }
                                }
                            }

                            Button(
                                onClick = {
                                    downloadVideoToPhone(context, fullVideoUrl, serverUrl, project.title, activeVideoMode)
                                },
                                modifier = Modifier.height(48.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = AccentEmerald),
                                contentPadding = PaddingValues(horizontal = 14.dp),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Text(
                                    text = "📥 下载成片",
                                    color = BgDark,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Black
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(6.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("720×1280 · 竖屏防变形双层字幕轨", color = TextMuted, fontSize = 10.sp)
                            Text("支持远程机房与手机独立硬件压制 MP4", color = AccentEmerald, fontSize = 10.sp)
                        }
                    }
                }
                1 -> {
                    // 全景分镜流
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 14.dp, vertical = 10.dp)
                    ) {
                        if (!hasActiveProject) {
                            Box(
                                modifier = Modifier.fillMaxSize(),
                                contentAlignment = Alignment.Center
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text("暂无分镜镜头", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Bold)
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        "请先点击右上角【🍅 添加作品 / 创作新剧】导入您喜欢的小说，AI 将自动拆解好莱坞分镜！",
                                        color = TextMuted,
                                        fontSize = 12.sp,
                                        textAlign = TextAlign.Center
                                    )
                                    Spacer(modifier = Modifier.height(14.dp))
                                    Button(
                                        onClick = { showGenerateScriptDialog = true },
                                        colors = ButtonDefaults.buttonColors(containerColor = AccentGold)
                                    ) {
                                        Text("🍅 立即添加作品", color = BgDark, fontWeight = FontWeight.Bold)
                                    }
                                }
                            }
                        } else {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(CardDark)
                                    .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
                                    .padding(horizontal = 12.dp, vertical = 8.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "《${project.title}》共 ${project.shots.size} 个分镜",
                                        color = BrandCyan,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        text = "点击【🔊 试听配音】可播放真实语音，点击卡片可改词重绘",
                                        color = TextMuted,
                                        fontSize = 9.5.sp
                                    )
                                }

                                Button(
                                    onClick = { showProductionStudioDialog = true },
                                    colors = ButtonDefaults.buttonColors(containerColor = AccentGold),
                                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                                    shape = RoundedCornerShape(6.dp),
                                    modifier = Modifier.height(28.dp)
                                ) {
                                    Icon(Icons.Default.PlayArrow, contentDescription = null, tint = BgDark, modifier = Modifier.size(13.dp))
                                    Spacer(modifier = Modifier.width(3.dp))
                                    Text("合成全片", color = BgDark, fontSize = 11.sp, fontWeight = FontWeight.Black)
                                }
                            }

                            Spacer(modifier = Modifier.height(10.dp))

                            LazyColumn(
                                modifier = Modifier.fillMaxSize(),
                                verticalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                items(project.shots) { shot ->
                                    StoryboardCard(
                                        shot = shot,
                                        serverUrl = serverUrl,
                                        isSelected = editingShot?.id == shot.id,
                                        refreshVersion = shotRefreshVersion,
                                        onClick = {
                                            editingShot = shot
                                        }
                                    )
                                }
                            }
                        }
                    }
                }
                2 -> {
                    // 角色定妆库
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        item {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(
                                        text = "角色定妆资产库 (${project.characters.size})",
                                        color = BrandCyan,
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        text = "支持自由增删角色、切换声线及外貌设定",
                                        color = TextMuted,
                                        fontSize = 10.sp
                                    )
                                }
                                Button(
                                    onClick = {
                                        editingCharacter = null
                                        showCharacterEditDialog = true
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = BrandCyan),
                                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 5.dp),
                                    shape = RoundedCornerShape(8.dp)
                                ) {
                                    Icon(imageVector = Icons.Default.Add, contentDescription = null, tint = BgDark, modifier = Modifier.size(14.dp))
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text("添加角色", color = BgDark, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                }
                            }
                        }

                        items(project.characters) { char ->
                            CharacterCard(
                                character = char,
                                onEdit = {
                                    editingCharacter = char
                                    showCharacterEditDialog = true
                                },
                                onDelete = {
                                    scope.launch {
                                        repo.deleteCharacter(context, serverUrl, char.name)
                                        project = project.copy(characters = project.characters.filter { it.name != char.name })
                                        creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                                        Toast.makeText(context, "已删除角色【${char.name}】", Toast.LENGTH_SHORT).show()
                                    }
                                }
                            )
                        }

                        if (project.audio_tracks.isNotEmpty()) {
                            item {
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = "多轨声音母带引擎",
                                    color = BrandPurple,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            items(project.audio_tracks) { track ->
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(CardDark)
                                        .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
                                        .padding(10.dp)
                                ) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column {
                                            Text(track.track, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                            Text(track.source, color = TextMuted, fontSize = 10.sp)
                                        }
                                        Text(track.status, color = AccentEmerald, fontSize = 11.sp)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // 🎬 AI 真实制片弹窗（自动协同远程服务器与手机原生硬件压制）
    if (showProductionStudioDialog) {
        ProductionStudioDialog(
            serverUrl = serverUrl,
            project = project,
            title = project.title,
            genre = project.genre,
            onFinished = { newUrl ->
                selectedTab = 0
                val updated = project.copy(video_url = newUrl, live_actor_video = newUrl)
                project = updated
                LocalAndroidEngine.saveCreatorWork(context, updated)
                creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
            },
            onDismiss = { showProductionStudioDialog = false }
        )
    }

    // 创作者作品库切换与管理弹窗（无任何预留固定小说）
    if (showDramaSwitcherDialog) {
        DramaSwitcherDialog(
            currentTitle = project.title,
            creatorWorks = creatorWorks,
            onSelectDrama = { selectedWork ->
                project = selectedWork
                LocalAndroidEngine.setCurrentWorkTitle(context, selectedWork.title)
                Toast.makeText(context, "已切换至作品《${selectedWork.title}》！", Toast.LENGTH_SHORT).show()
            },
            onDeleteDrama = { delTitle ->
                LocalAndroidEngine.deleteCreatorWork(context, delTitle)
                creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                project = LocalAndroidEngine.getCurrentWork(context)
                Toast.makeText(context, "已从作品库删除《$delTitle》", Toast.LENGTH_SHORT).show()
            },
            onCreateNew = { showGenerateScriptDialog = true },
            onDismiss = { showDramaSwitcherDialog = false }
        )
    }

    // 角色添加与编辑弹窗
    if (showCharacterEditDialog) {
        CharacterEditDialog(
            initialCharacter = editingCharacter,
            availableVoices = availableVoices,
            onSave = { savedChar ->
                scope.launch {
                    showCharacterEditDialog = false
                    repo.addCharacter(context, serverUrl, savedChar)
                    val updated = project.characters.toMutableList()
                    val idx = updated.indexOfFirst { it.name == savedChar.name }
                    if (idx >= 0) {
                        updated[idx] = savedChar
                    } else {
                        updated.add(savedChar)
                    }
                    project = project.copy(characters = updated)
                    creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                    Toast.makeText(context, "角色【${savedChar.name}】已保存！", Toast.LENGTH_SHORT).show()
                }
            },
            onDismiss = { showCharacterEditDialog = false }
        )
    }

    // 🍅 番茄小说联动与新作品创建弹窗
    if (showGenerateScriptDialog) {
        GenerateScriptDialog(
            serverUrl = serverUrl,
            isGenerating = isGeneratingScript,
            onGenerate = { t, g, text ->
                scope.launch {
                    isGeneratingScript = true
                    val newProj = repo.generateScript(context, serverUrl, t, g, text)
                    isGeneratingScript = false
                    showGenerateScriptDialog = false
                    project = newProj
                    creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                    selectedTab = 1
                    Toast.makeText(context, "✅ 作品《${t}》已加入作品库并完成分镜拆解！", Toast.LENGTH_LONG).show()
                }
            },
            onGenerateAndProduce = { t, g, text ->
                scope.launch {
                    isGeneratingScript = true
                    val newProj = repo.generateScript(context, serverUrl, t, g, text)
                    isGeneratingScript = false
                    showGenerateScriptDialog = false
                    project = newProj
                    creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                    showProductionStudioDialog = true
                }
            },
            onDismiss = { showGenerateScriptDialog = false }
        )
    }

    // 真实 API 密钥与引擎设置弹窗
    if (showSotaDialog) {
        SotaEngineDialog(
            sotaInfo = sotaInfo,
            currentServerUrl = serverUrl,
            isSaving = isSavingKeys,
            onSaveConfig = { newUrl, apiKeys ->
                scope.launch {
                    isSavingKeys = true
                    serverUrl = newUrl
                    prefs.edit().putString("server_url", newUrl).apply()

                    if (apiKeys.isNotEmpty()) {
                        repo.saveApiKeys(context, newUrl, apiKeys)
                    }
                    val s = repo.getSotaStatus(context, newUrl)
                    val p = repo.getProject(context, newUrl)
                    sotaInfo = s
                    project = p
                    isOnline = !s.system.os.startsWith("手机独立算力模式") && !s.system.os.startsWith("离线") && !s.system.os.startsWith("未连接")
                    isSavingKeys = false

                    if (apiKeys.isNotEmpty()) {
                        Toast.makeText(
                            context,
                            if (isOnline) "✅ 已成功保存 ${apiKeys.size} 项真实 API 密钥至服务器与手机本地！"
                            else "✅ 已保存 ${apiKeys.size} 项 API 密钥至手机本地直连引擎！",
                            Toast.LENGTH_LONG
                        ).show()
                    } else {
                        showSotaDialog = false
                        refreshData(showToast = true)
                    }
                }
            },
            onDismiss = { showSotaDialog = false }
        )
    }

    // 🎬 单镜头精细修改与重绘弹窗
    editingShot?.let { targetShot ->
        ShotEditDialog(
            shot = targetShot,
            isSaving = isSavingShot,
            onSaveAndRegenerate = { speaker, dialogue, visualPrompt, motion, regenImg, regenTts ->
                scope.launch {
                    isSavingShot = true
                    val updatedProj = repo.updateAndRegenerateShot(
                        context = context,
                        baseUrl = serverUrl,
                        title = project.title,
                        genre = project.genre,
                        shotId = targetShot.id,
                        speaker = speaker,
                        dialogue = dialogue,
                        visualPrompt = visualPrompt,
                        motion = motion,
                        regenerateImage = regenImg,
                        regenerateAudio = regenTts
                    )
                    isSavingShot = false
                    project = updatedProj
                    creatorWorks = LocalAndroidEngine.getCreatorWorks(context)
                    shotRefreshVersion += 1
                    editingShot = null
                    Toast.makeText(
                        context,
                        "✅ 镜头 #${targetShot.id} 已更新完成！点击【合成全片】即可生成最新视频",
                        Toast.LENGTH_LONG
                    ).show()
                }
            },
            onDismiss = {
                if (!isSavingShot) {
                    editingShot = null
                }
            }
        )
    }
}
