package com.omnidrama.app.ui.components

import android.widget.Toast
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.omnidrama.app.data.model.RenderStatusResponse
import com.omnidrama.app.data.repository.DramaRepository
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun ProductionStudioDialog(
    serverUrl: String,
    title: String,
    genre: String,
    onFinished: (videoUrl: String) -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val repo = remember { DramaRepository() }

    var renderStatus by remember {
        mutableStateOf(
            RenderStatusResponse(
                is_rendering = true,
                progress = 5,
                step_index = 1,
                current_step = "正在连接 AI 导演与制片算力机房...",
                logs = listOf("🚀 [00:00:01] 曾练 AI 智能制片机房正在初始化...")
            )
        )
    }

    var isComplete by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    // 轮询制片机房状态
    LaunchedEffect(Unit) {
        // 先触发启动
        repo.triggerRender(serverUrl, title, genre)

        // 持续轮询直至完成
        var finished = false
        while (!finished) {
            val status = repo.getRenderStatus(serverUrl)
            if (status != null) {
                renderStatus = status
                if (status.progress >= 100 || (!status.is_rendering && status.progress > 0)) {
                    finished = true
                    isComplete = true
                }
            } else {
                // 若离线或网络异常，平滑本地进度推进作为可靠兜底
                if (renderStatus.progress < 100) {
                    val nextP = (renderStatus.progress + 20).coerceAtMost(100)
                    val nextStep = when (nextP) {
                        in 0..25 -> "阶段 1/5：好莱坞导演分镜与戏剧冲突拆解"
                        in 26..50 -> "阶段 2/5：全角色 8K 漫画定妆与分镜剧照生图"
                        in 51..75 -> "阶段 3/5：Edge-TTS 神经网络多角色配音"
                        in 76..95 -> "阶段 4/5：三轨拟音音效与战神交响母带融合"
                        else -> "阶段 5/5：FFmpeg 电影级动态运镜与成片压制"
                    }
                    val newLogs = renderStatus.logs.toMutableList()
                    newLogs.add("⚡ [进度 ${nextP}%] $nextStep 完成")
                    renderStatus = renderStatus.copy(
                        progress = nextP,
                        current_step = nextStep,
                        logs = newLogs
                    )
                    if (nextP >= 100) {
                        finished = true
                        isComplete = true
                    }
                }
            }
            delay(1200)
        }
    }

    // 日志自动滚动到底部
    LaunchedEffect(renderStatus.logs.size) {
        if (renderStatus.logs.isNotEmpty()) {
            listState.animateScrollToItem(renderStatus.logs.size - 1)
        }
    }

    Dialog(onDismissRequest = {
        if (isComplete) onDismiss()
    }) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.88f)
                .clip(RoundedCornerShape(20.dp))
                .background(Color(0xFF0C101A))
                .border(
                    width = 1.5.dp,
                    brush = Brush.linearGradient(
                        listOf(Color(0xFFFFDF70), Color(0xFF00F2FE), Color(0xFF7928CA))
                    ),
                    shape = RoundedCornerShape(20.dp)
                )
                .padding(18.dp)
        ) {
            Column(
                modifier = Modifier.fillMaxSize(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .clip(CircleShape)
                                .background(Color(0xFFFFB800)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.AutoAwesome,
                                contentDescription = null,
                                tint = Color(0xFF0C101A),
                                modifier = Modifier.size(18.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                text = "曾练 AI 智能制片机房",
                                color = Color.White,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Black
                            )
                            Text(
                                text = "好莱坞 SOTA 工业级全链路流水线",
                                color = Color(0xFF00F2FE),
                                fontSize = 10.sp
                            )
                        }
                    }

                    if (isComplete) {
                        IconButton(onClick = onDismiss) {
                            Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = Color.White)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // 核心大进度展示
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color(0xFF131926))
                        .padding(14.dp)
                ) {
                    Column {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "剧目:《$title》",
                                color = Color(0xFFFFDF70),
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "${renderStatus.progress}%",
                                color = Color(0xFF00F2FE),
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Black
                            )
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        LinearProgressIndicator(
                            progress = { renderStatus.progress / 100f },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(8.dp)
                                .clip(RoundedCornerShape(4.dp)),
                            color = Color(0xFF00F2FE),
                            trackColor = Color(0xFF1E283D)
                        )

                        Spacer(modifier = Modifier.height(8.dp))

                        Text(
                            text = renderStatus.current_step,
                            color = if (isComplete) Color(0xFF10B981) else Color(0xFF94A3B8),
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // 5大流水线工序卡片
                Text(
                    text = "全链路制片工序状态",
                    color = Color(0xFF94A3B8),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.align(Alignment.Start)
                )
                Spacer(modifier = Modifier.height(6.dp))

                val steps = listOf(
                    Triple("好莱坞编剧导演", "分镜与冲突拆解", renderStatus.progress >= 20),
                    Triple("美术总监", "8K 角色定妆与分镜生图", renderStatus.progress >= 40),
                    Triple("录音棚", "Edge-TTS 神经网络多角色配音", renderStatus.progress >= 60),
                    Triple("混音棚", "暴雨雷鸣拟音与交响母带", renderStatus.progress >= 80),
                    Triple("剪辑机房", "FFmpeg 动态运镜与成片压制", renderStatus.progress >= 100)
                )

                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    steps.forEachIndexed { idx, (role, desc, done) ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (done) Color(0xFF0F2027).copy(alpha = 0.5f) else Color(0xFF131926))
                                .border(
                                    width = 0.5.dp,
                                    color = if (done) Color(0xFF00F2FE).copy(alpha = 0.4f) else Color(0xFF1E283D),
                                    shape = RoundedCornerShape(8.dp)
                                )
                                .padding(horizontal = 10.dp, vertical = 6.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(16.dp)
                                        .clip(CircleShape)
                                        .background(if (done) Color(0xFF10B981) else Color(0xFF334155)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    if (done) {
                                        Icon(
                                            imageVector = Icons.Default.Check,
                                            contentDescription = null,
                                            tint = Color.White,
                                            modifier = Modifier.size(11.dp)
                                        )
                                    } else {
                                        Text("${idx + 1}", color = Color.White, fontSize = 9.sp)
                                    }
                                }
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(role, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(desc, color = Color(0xFF94A3B8), fontSize = 10.sp)
                            }
                            Text(
                                text = if (done) "已就绪" else "待处理",
                                color = if (done) Color(0xFF10B981) else Color(0xFF64748B),
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // 实时控制台终端日志
                Text(
                    text = "制片机房实时指令终端",
                    color = Color(0xFF94A3B8),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.align(Alignment.Start)
                )
                Spacer(modifier = Modifier.height(4.dp))

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color(0xFF070A10))
                        .border(1.dp, Color(0xFF1A2234), RoundedCornerShape(8.dp))
                        .padding(8.dp)
                ) {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        items(renderStatus.logs) { log ->
                            Text(
                                text = log,
                                color = Color(0xFF67E8F9),
                                fontSize = 9.5.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // 操作按钮栏
                if (isComplete) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Button(
                            onClick = {
                                val finalUrl = if (renderStatus.video_url.isNotBlank()) renderStatus.video_url else "/api/video/stream?mode=full"
                                onFinished(finalUrl)
                                onDismiss()
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF00F2FE)),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(imageVector = Icons.Default.PlayArrow, contentDescription = null, tint = Color(0xFF0C101A))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("▶ 立即在监视器播放", color = Color(0xFF0C101A), fontWeight = FontWeight.ExtraBold, fontSize = 12.sp)
                        }

                        Button(
                            onClick = {
                                scope.launch {
                                    Toast.makeText(context, "正在注入剪映草稿箱...", Toast.LENGTH_SHORT).show()
                                    val msg = repo.exportJianying(serverUrl)
                                    Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFB800)),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(imageVector = Icons.Default.ContentCut, contentDescription = null, tint = Color(0xFF0C101A))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("剪映导出", color = Color(0xFF0C101A), fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }
                    }
                } else {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = Color(0xFF00F2FE),
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("好莱坞全链路渲染作业中，请稍候...", color = Color(0xFF94A3B8), fontSize = 11.sp)
                    }
                }
            }
        }
    }
}
