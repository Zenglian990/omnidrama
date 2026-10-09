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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.ContentCut
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
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

    var selectedTab by remember { mutableIntStateOf(0) } // 0: 监视器, 1: 分镜流, 2: 角色库
    var activeVideoMode by remember { mutableStateOf("full") } // "full" or "live"
    var showSotaDialog by remember { mutableStateOf(false) }
    var showDramaSwitcherDialog by remember { mutableStateOf(false) }
    var currentEpisodeTitle by remember { mutableStateOf("第 1 集：怒拔逆鳞") }

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
                if (showToast) {
                    Toast.makeText(context, "✅ 云端已同步！当前剧目:《${p.title}》", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
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
                // Tier 1: 品牌顶栏 (Logo + 产品名 + 创作新剧 + 设置)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    BrandLogo()

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // 亮眼黄金胶囊按钮：创作新剧
                        Button(
                            onClick = { showGenerateScriptDialog = true },
                            colors = ButtonDefaults.buttonColors(containerColor = AccentGold),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                            shape = RoundedCornerShape(20.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.AutoAwesome,
                                contentDescription = null,
                                tint = BgDark,
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "创作新剧",
                                color = BgDark,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.ExtraBold
                            )
                        }

                        Spacer(modifier = Modifier.width(6.dp))

                        // 设置按钮 (带微光绿点)
                        Box(contentAlignment = Alignment.TopEnd) {
                            IconButton(onClick = { showSotaDialog = true }) {
                                Icon(
                                    imageVector = Icons.Default.Settings,
                                    contentDescription = "Settings",
                                    tint = TextSecondary,
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                            // 绿色在线指示小圆点
                            Box(
                                modifier = Modifier
                                    .padding(top = 8.dp, end = 8.dp)
                                    .size(6.dp)
                                    .clip(CircleShape)
                                    .background(AccentEmerald)
                            )
                        }
                    }
                }

                // Tier 2: 剧目调度与快捷操作卡片
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 4.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(CardDark)
                        .border(1.dp, BorderDark, RoundedCornerShape(10.dp))
                        .padding(horizontal = 12.dp, vertical = 8.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // 剧目切换按钮
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .clip(RoundedCornerShape(6.dp))
                                .clickable { showDramaSwitcherDialog = true }
                                .padding(horizontal = 6.dp, vertical = 4.dp)
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

                        // 右侧工具栏：剪映导出与刷新同步
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            // 剪映导出按钮
                            IconButton(
                                onClick = {
                                    scope.launch {
                                        Toast.makeText(context, "正在注入剪映草稿箱...", Toast.LENGTH_SHORT).show()
                                        val msg = repo.exportJianying(serverUrl)
                                        Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                                    }
                                },
                                modifier = Modifier.size(32.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.ContentCut,
                                    contentDescription = "CapCut",
                                    tint = AccentGold,
                                    modifier = Modifier.size(17.dp)
                                )
                            }

                            Spacer(modifier = Modifier.width(4.dp))

                            // 刷新按钮 (带旋转等待与明确 Toast 反馈)
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
                                        modifier = Modifier.size(17.dp)
                                    )
                                }
                            }
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
                            .padding(16.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Button(
                                onClick = { activeVideoMode = "full" },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = if (activeVideoMode == "full") BrandCyan else BorderDark
                                ),
                                modifier = Modifier.weight(1f)
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
                                modifier = Modifier.weight(1f)
                            ) {
                                Text(
                                    text = "🔥 真人演员活化",
                                    color = if (activeVideoMode == "live") Color.White else TextSecondary,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        val currentVideoPath = if (activeVideoMode == "full") project.video_url else project.live_actor_video
                        val fullVideoUrl = if (currentVideoPath.startsWith("http")) currentVideoPath else "$serverUrl$currentVideoPath"

                        VideoPlayer(
                            videoUrl = fullVideoUrl,
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f)
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("1080P · 24FPS 竖屏漫剧", color = TextMuted, fontSize = 11.sp)
                            Text("三轨合一影视级母带 (AAC)", color = AccentEmerald, fontSize = 11.sp)
                        }
                    }
                }
                1 -> {
                    // 全景分镜流
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(project.shots) { shot ->
                            StoryboardCard(
                                shot = shot,
                                isSelected = false,
                                onClick = {
                                    Toast.makeText(context, "选中分镜 #${shot.id} - ${shot.speaker}：${shot.dialogue}", Toast.LENGTH_SHORT).show()
                                }
                            )
                        }
                    }
                }
                2 -> {
                    // 角色定妆库
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        item {
                            // 打造新角色 Header
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

                        // 快速横向角色画廊
                        if (project.characters.isNotEmpty()) {
                            item {
                                LazyRow(
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    items(project.characters) { c ->
                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(8.dp))
                                                .background(CardDark)
                                                .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
                                                .clickable {
                                                    editingCharacter = c
                                                    showCharacterEditDialog = true
                                                }
                                                .padding(horizontal = 10.dp, vertical = 6.dp)
                                        ) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Box(
                                                    modifier = Modifier
                                                        .size(8.dp)
                                                        .clip(CircleShape)
                                                        .background(BrandCyan)
                                                )
                                                Spacer(modifier = Modifier.width(6.dp))
                                                Text(c.name, color = TextPrimary, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // 角色卡片详细列表
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
                            Spacer(modifier = Modifier.height(10.dp))
                            Text(
                                text = "多轨声音母带引擎",
                                color = BrandPurple,
                                fontSize = 14.sp,
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

    // AI 小说剧本拆解弹窗
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
                        Toast.makeText(context, "《${t}》全新剧目生成成功！提取了 ${newProj.characters.size} 位新角色", Toast.LENGTH_LONG).show()
                    } else {
                        Toast.makeText(context, "剧本拆解已提交，正在同步最新剧目...", Toast.LENGTH_SHORT).show()
                        refreshData(showToast = true)
                    }
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
