package com.omnidrama.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCut
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.SotaStatusResponse
import com.omnidrama.app.data.repository.DramaRepository
import com.omnidrama.app.ui.components.*
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun StudioScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val repo = remember { DramaRepository() }

    var serverUrl by remember { mutableStateOf("http://10.0.2.2:8765") }
    var project by remember { mutableStateOf(ProjectData()) }
    var sotaInfo by remember { mutableStateOf(SotaStatusResponse()) }
    var isLoading by remember { mutableStateOf(false) }

    var selectedTab by remember { mutableIntStateOf(0) } // 0: 监视器, 1: 分镜流, 2: 角色库
    var activeVideoMode by remember { mutableStateOf("full") } // "full" or "live"
    var showSotaDialog by remember { mutableStateOf(false) }

    fun refreshData() {
        scope.launch {
            isLoading = true
            project = repo.getProject(serverUrl)
            sotaInfo = repo.getSotaStatus(serverUrl)
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        refreshData()
    }

    Scaffold(
        topBar = {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(BgDark)
                    .border(width = 0.5.dp, color = BorderDark)
                    .padding(horizontal = 16.dp, vertical = 10.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(28.dp)
                                .clip(RoundedCornerShape(6.dp))
                                .background(BrandCyan),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("Ω", color = BgDark, fontWeight = FontWeight.Black, fontSize = 16.sp)
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                text = "OmniDrama",
                                color = BrandCyan,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "《${project.title}》",
                                color = TextSecondary,
                                fontSize = 10.sp
                            )
                        }
                    }

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = {
                            scope.launch {
                                val msg = repo.exportJianying(serverUrl)
                                Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                            }
                        }) {
                            Icon(
                                imageVector = Icons.Default.ContentCut,
                                contentDescription = "CapCut",
                                tint = AccentGold
                            )
                        }

                        IconButton(onClick = { showSotaDialog = true }) {
                            Icon(
                                imageVector = Icons.Default.Settings,
                                contentDescription = "SOTA",
                                tint = BrandPurple
                            )
                        }

                        IconButton(onClick = { refreshData() }) {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = "Refresh",
                                tint = TextSecondary
                            )
                        }
                    }
                }
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
                    text = { Text("角色与声音 (${project.characters.size})", fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                )
            }

            // 内容视图
            when (selectedTab) {
                0 -> {
                    // 监视器模式
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp)
                    ) {
                        // 模式切换条
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(CardDark)
                                .padding(4.dp),
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            Button(
                                onClick = { activeVideoMode = "full" },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = if (activeVideoMode == "full") BrandCyan else Color.Transparent
                                ),
                                modifier = Modifier.weight(1f)
                            ) {
                                Text(
                                    text = "全片电影级成片",
                                    color = if (activeVideoMode == "full") BgDark else TextSecondary,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                            Button(
                                onClick = { activeVideoMode = "live" },
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = if (activeVideoMode == "live") BrandPurple else Color.Transparent
                                ),
                                modifier = Modifier.weight(1f)
                            ) {
                                Text(
                                    text = "🔥 真人演员活化",
                                    color = if (activeVideoMode == "live") TextPrimary else TextSecondary,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        // 竖屏视频播放器
                        val currentVideoPath = if (activeVideoMode == "full") project.video_url else project.live_actor_video
                        val videoFullUrl = if (currentVideoPath.startsWith("http")) {
                            currentVideoPath
                        } else if (currentVideoPath.isNotBlank()) {
                            "$serverUrl$currentVideoPath"
                        } else {
                            ""
                        }

                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f)
                                .clip(RoundedCornerShape(16.dp))
                                .background(Color.Black)
                                .border(1.dp, BorderDark, RoundedCornerShape(16.dp))
                        ) {
                            VideoPlayer(videoUrl = videoFullUrl)
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        // 影视规格标签
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
                    // 分镜流模式
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
                                    Toast.makeText(context, "选中分镜 #${shot.id} - ${shot.speaker}", Toast.LENGTH_SHORT).show()
                                }
                            )
                        }
                    }
                }
                2 -> {
                    // 角色与配音
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        item {
                            Text(
                                text = "角色定妆资产库",
                                color = BrandCyan,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        items(project.characters) { char ->
                            CharacterCard(character = char)
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

    if (showSotaDialog) {
        SotaEngineDialog(
            sotaInfo = sotaInfo,
            currentServerUrl = serverUrl,
            onSaveServerUrl = {
                serverUrl = it
                refreshData()
            },
            onDismiss = { showSotaDialog = false }
        )
    }
}
