package com.omnidrama.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.SotaStatusResponse
import com.omnidrama.app.data.model.VoiceItem
import com.omnidrama.app.data.repository.DramaRepository
import com.omnidrama.app.ui.components.*
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun StudioScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val repo = remember { DramaRepository() }

    var serverUrl by remember { mutableStateOf("https://omnidrama-zeng.loca.lt") }
    var project by remember { mutableStateOf(ProjectData()) }
    var sotaInfo by remember { mutableStateOf(SotaStatusResponse()) }
    var availableVoices by remember { mutableStateOf<List<VoiceItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var isOnline by remember { mutableStateOf(false) }

    var selectedTab by remember { mutableIntStateOf(0) } // 0: 监视器, 1: 分镜流, 2: 角色库
    var activeVideoMode by remember { mutableStateOf("full") } // "full" or "live"
    var showSotaDialog by remember { mutableStateOf(false) }
    var showDramaSwitcherDialog by remember { mutableStateOf(false) }
    var currentEpisodeTitle by remember { mutableStateOf("第 1 集：怒拔逆鳞") }

    var showProductionStudioDialog by remember { mutableStateOf(false) }
    var showCharacterEditDialog by remember { mutableStateOf(false) }
    var editingCharacter by remember { mutableStateOf<CharacterItem?>(null) }
    var showGenerateScriptDialog by remember { mutableStateOf(false) }
    var isGeneratingScript by remember { mutableStateOf(false) }

    fun refreshData(showToast: Boolean = false) {
        scope.launch {
            isLoading = true
            if (showToast) {
                Toast.makeText(context, "正在连接云端服务器同步...", Toast.LENGTH_SHORT).show()
            }
            try {
                val p = repo.getProject(serverUrl)
                val s = repo.getSotaStatus(serverUrl)
                val v = repo.getVoices(serverUrl)
                project = p
                sotaInfo = s
                availableVoices = v
                isOnline = true
                if (showToast) {
                    Toast.makeText(context, "✅ 云端已同步！当前剧目:《${p.title}》", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                isOnline = false
                if (showToast) {
                    Toast.makeText(context, "⚠️ 网络同步异常，已加载本地缓存", Toast.LENGTH_SHORT).show()
                }
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshData(showToast = false)
    }

    Scaffold(
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(BgDark)
                    .statusBarsPadding()
                    .border(width = 0.5.dp, color = BorderDark)
            ) {
                // Tier 1: 品牌顶栏 (高端电影Logo + 状态 + 刷新 + 设置)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    BrandLogo()

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // 在线状态指示胶囊
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(12.dp))
                                .background(if (isOnline) Color(0xFF064E3B) else Color(0xFF1E293B))
                                .border(0.5.dp, if (isOnline) Color(0xFF10B981) else Color(0xFF475569), RoundedCornerShape(12.dp))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(6.dp)
                                        .clip(CircleShape)
                                        .background(if (isOnline) Color(0xFF10B981) else Color(0xFF94A3B8))
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    text = if (isOnline) "机房在线" else "本地模式",
                                    color = if (isOnline) Color(0xFF6EE7B7) else Color(0xFFCBD5E1),
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        Spacer(modifier = Modifier.width(4.dp))

                        // 刷新按钮 (带旋转等待反馈)
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
                            onClick = { showSotaDialog = true },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Settings,
                                contentDescription = "Settings",
                                tint = TextSecondary,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                }

                // Tier 2: 剧目快捷操作条 (当前剧目 + 创作新剧 + 剪映导出)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 剧目切换按钮
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .background(CardDark)
                            .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
                            .clickable { showDramaSwitcherDialog = true }
                            .padding(horizontal = 8.dp, vertical = 6.dp)
                    ) {
                        Text(
                            text = "《${project.title}》",
                            color = BrandCyan,
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
                        Spacer(modifier = Modifier.width(4.dp))
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(BorderDark)
                                .padding(horizontal = 4.dp, vertical = 1.dp)
                        ) {
                            Text(
                                text = currentEpisodeTitle,
                                color = AccentGold,
                                fontSize = 9.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    // 右侧操作按钮组
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // 创作新剧按钮 (醒目黄金胶囊)
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
                                text = "创作新剧",
                                color = BgDark,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.ExtraBold
                            )
                        }

                        Spacer(modifier = Modifier.width(6.dp))

                        // 剪映导出按钮
                        IconButton(
                            onClick = {
                                scope.launch {
                                    Toast.makeText(context, "正在注入剪映草稿箱...", Toast.LENGTH_SHORT).show()
                                    val msg = repo.exportJianying(serverUrl)
                                    Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                                }
                            },
                            modifier = Modifier.size(30.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.ContentCut,
                                contentDescription = "CapCut",
                                tint = AccentGold,
                                modifier = Modifier.size(16.dp)
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

            // Tab 页面切换
            when (selectedTab) {
                0 -> {
                    // 院线监视器
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(14.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        // 视频模式切换
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

                        // 计算视频播放地址
                        val currentVideoPath = if (activeVideoMode == "full") project.video_url else project.live_actor_video
                        val fullVideoUrl = if (currentVideoPath.isBlank()) {
                            ""
                        } else if (currentVideoPath.startsWith("http")) {
                            currentVideoPath
                        } else {
                            "$serverUrl$currentVideoPath"
                        }

                        // 院线播放器
                        VideoPlayer(
                            videoUrl = fullVideoUrl,
                            onProduceClick = { showProductionStudioDialog = true },
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f)
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        // ⭐ 核心英雄按钮：一键开始制作短剧 / 渲染全片 ⭐
                        Button(
                            onClick = { showProductionStudioDialog = true },
                            modifier = Modifier
                                .fillMaxWidth()
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
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = "⚡ 一键开始制作短剧 / 渲染全片",
                                        color = Color(0xFF0C101A),
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Black
                                    )
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(6.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("1080P · 24FPS 竖屏漫剧", color = TextMuted, fontSize = 10.sp)
                            Text("三轨合一影视级母带 (AAC)", color = AccentEmerald, fontSize = 10.sp)
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
                        // 分镜流顶栏操作横幅
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
                            Text(
                                text = "共 ${project.shots.size} 个好莱坞分镜镜头",
                                color = BrandCyan,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold
                            )

                            Button(
                                onClick = { showProductionStudioDialog = true },
                                colors = ButtonDefaults.buttonColors(containerColor = AccentGold),
                                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                                shape = RoundedCornerShape(6.dp),
                                modifier = Modifier.height(28.dp)
                            ) {
                                Icon(Icons.Default.PlayArrow, contentDescription = null, tint = BgDark, modifier = Modifier.size(13.dp))
                                Spacer(modifier = Modifier.width(3.dp))
                                Text("启动全片制作", color = BgDark, fontSize = 11.sp, fontWeight = FontWeight.Black)
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
                                    isSelected = false,
                                    onClick = {
                                        Toast.makeText(context, "选中分镜 #${shot.id} - ${shot.speaker}", Toast.LENGTH_SHORT).show()
                                    }
                                )
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
                                        text = "支持自由增删、切换声线及外貌设定",
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

                        // 角色卡片列表
                        items(project.characters) { char ->
                            CharacterCard(
                                character = char,
                                onEdit = {
                                    editingCharacter = char
                                    showCharacterEditDialog = true
                                },
                                onDelete = {
                                    scope.launch {
                                        repo.deleteCharacter(serverUrl, char.name)
                                        project = project.copy(characters = project.characters.filter { it.name != char.name })
                                        Toast.makeText(context, "已删除角色【${char.name}】", Toast.LENGTH_SHORT).show()
                                    }
                                }
                            )
                        }

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

    // 🎬 AI 智能制片机房弹窗 (核心制作流)
    if (showProductionStudioDialog) {
        ProductionStudioDialog(
            serverUrl = serverUrl,
            title = project.title,
            genre = project.genre,
            onFinished = { newUrl ->
                selectedTab = 0
                refreshData(showToast = true)
            },
            onDismiss = { showProductionStudioDialog = false }
        )
    }

    // 剧目管理与切换弹窗
    if (showDramaSwitcherDialog) {
        DramaSwitcherDialog(
            currentTitle = project.title,
            onSelectDrama = { newProj ->
                project = newProj
                currentEpisodeTitle = "第 1 集：已载入"
                Toast.makeText(context, "已切换至剧目《${newProj.title}》！", Toast.LENGTH_SHORT).show()
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
                    repo.addCharacter(serverUrl, savedChar)
                    val updated = project.characters.toMutableList()
                    val idx = updated.indexOfFirst { it.name == savedChar.name }
                    if (idx >= 0) {
                        updated[idx] = savedChar
                    } else {
                        updated.add(savedChar)
                    }
                    project = project.copy(characters = updated)
                    Toast.makeText(context, "角色【${savedChar.name}】已成功入库！", Toast.LENGTH_SHORT).show()
                }
            },
            onDismiss = { showCharacterEditDialog = false }
        )
    }

    // AI 小说剧本拆解与制作弹窗
    if (showGenerateScriptDialog) {
        GenerateScriptDialog(
            isGenerating = isGeneratingScript,
            onGenerate = { t, g, text ->
                scope.launch {
                    isGeneratingScript = true
                    val newProj = repo.generateScript(serverUrl, t, g, text)
                    isGeneratingScript = false
                    showGenerateScriptDialog = false
                    if (newProj != null) {
                        project = newProj
                        currentEpisodeTitle = "第 1 集：分镜已就绪"
                        Toast.makeText(context, "《${t}》分镜拆解成功！", Toast.LENGTH_SHORT).show()
                    } else {
                        refreshData(showToast = true)
                    }
                }
            },
            onGenerateAndProduce = { t, g, text ->
                scope.launch {
                    isGeneratingScript = true
                    val newProj = repo.generateScript(serverUrl, t, g, text)
                    isGeneratingScript = false
                    showGenerateScriptDialog = false
                    if (newProj != null) {
                        project = newProj
                    }
                    showProductionStudioDialog = true
                }
            },
            onDismiss = { showGenerateScriptDialog = false }
        )
    }

    // SOTA 设置弹窗
    if (showSotaDialog) {
        SotaEngineDialog(
            sotaInfo = sotaInfo,
            currentServerUrl = serverUrl,
            onSaveServerUrl = {
                serverUrl = it
                refreshData(showToast = true)
            },
            onDismiss = { showSotaDialog = false }
        )
    }
}
