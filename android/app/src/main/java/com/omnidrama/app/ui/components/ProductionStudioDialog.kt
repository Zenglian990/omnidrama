package com.omnidrama.app.ui.components

import android.widget.Toast
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
import com.omnidrama.app.data.local.LocalAndroidEngine
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.RenderStatusResponse
import com.omnidrama.app.data.repository.DramaRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun ProductionStudioDialog(
    serverUrl: String,
    project: ProjectData,
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
                current_step = "正在检测远程算力机房与手机独立硬件编码器...",
                logs = listOf("🚀 启动《$title》全链路真实成片渲染引擎...")
            )
        )
    }

    var isComplete by remember { mutableStateOf(false) }
    var hasError by remember { mutableStateOf(false) }
    var usingLocalEngine by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    suspend fun runPhoneHardwareRender() {
        usingLocalEngine = true
        val logsList = renderStatus.logs.toMutableList()
        logsList.add("📱 远程隧道未连接，已自动切换至【手机原生 MediaCodec H.264 硬件制片引擎】！")
        renderStatus = renderStatus.copy(
            is_rendering = true,
            progress = 10,
            current_step = "📱 手机原生硬件引擎：正在准备分镜与API直连...",
            logs = logsList.toList()
        )
        val mp4Path = LocalAndroidEngine.renderFullMp4OnPhone(
            context = context,
            project = project,
            onProgress = { prog, stepText, newLog ->
                logsList.add(newLog)
                renderStatus = renderStatus.copy(
                    is_rendering = prog < 100,
                    progress = prog,
                    current_step = stepText,
                    logs = logsList.toList()
                )
            }
        )
        if (mp4Path != null) {
            renderStatus = renderStatus.copy(
                is_rendering = false,
                progress = 100,
                current_step = "✅ 手机端 720×1280 H.264 MP4 成片压制完成！",
                video_url = mp4Path,
                logs = logsList.toList()
            )
            isComplete = true
        } else {
            hasError = true
            renderStatus = renderStatus.copy(
                is_rendering = false,
                current_step = "❌ 视频硬件编码失败，请先添加作品分镜后重试",
                logs = logsList + "❌ 未检测到有效分镜，请先添加小说作品并拆解分镜。"
            )
        }
    }

    LaunchedEffect(Unit) {
        val started = repo.triggerRender(serverUrl, title, genre)
        if (!started) {
            // 无缝切换至手机原生 MediaCodec 硬件渲染，绝不卡死在 2%！
            runPhoneHardwareRender()
            return@LaunchedEffect
        }

        var failCount = 0
        var finished = false
        while (!finished) {
            delay(1500)
            val status = repo.getRenderStatus(serverUrl)
            if (status != null) {
                failCount = 0
                renderStatus = status
                if (status.error != null) {
                    // 如果远程渲染异常，自动由手机硬件引擎兜底完成
                    runPhoneHardwareRender()
                    finished = true
                } else if (status.progress >= 100 || (!status.is_rendering && status.progress > 0)) {
                    finished = true
                    isComplete = true
                }
            } else {
                failCount++
                if (failCount >= 3) {
                    // 远程轮询中断时立即切换手机本地硬件编码完成制作
                    runPhoneHardwareRender()
                    finished = true
                }
            }
        }
    }

    LaunchedEffect(renderStatus.logs.size) {
        if (renderStatus.logs.isNotEmpty()) {
            listState.animateScrollToItem(renderStatus.logs.size - 1)
        }
    }

    Dialog(onDismissRequest = { onDismiss() }) {
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
                                text = if (usingLocalEngine) "手机原生 H.264 制片引擎" else "曾练 AI 真实制片机房",
                                color = Color.White,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Black
                            )
                            Text(
                                text = if (usingLocalEngine) "手机直连 SiliconFlow / Pexels + MediaCodec 硬件压制" else "实时同步远程 FFmpeg / Edge-TTS 真实进度",
                                color = Color(0xFF00F2FE),
                                fontSize = 10.sp
                            )
                        }
                    }

                    IconButton(onClick = onDismiss) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = Color.White)
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

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
                                text = "作品:《${title.ifBlank { "未命名作品" }}》",
                                color = Color(0xFFFFDF70),
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "${renderStatus.progress}%",
                                color = if (hasError) Color(0xFFF87171) else Color(0xFF00F2FE),
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
                            color = if (hasError) Color(0xFFF87171) else Color(0xFF00F2FE),
                            trackColor = Color(0xFF1E283D)
                        )

                        Spacer(modifier = Modifier.height(8.dp))

                        Text(
                            text = renderStatus.current_step,
                            color = when {
                                hasError -> Color(0xFFF87171)
                                isComplete -> Color(0xFF10B981)
                                else -> Color(0xFF94A3B8)
                            },
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 5大流水线工序卡片
                Text(
                    text = "全链路真实渲染工序状态",
                    color = Color(0xFF94A3B8),
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.align(Alignment.Start)
                )
                Spacer(modifier = Modifier.height(6.dp))

                val steps = listOf(
                    Triple("导演分镜引擎", "DeepSeek / 硅基流动 / 剧本智能拆解", renderStatus.progress >= 20),
                    Triple("分镜画面合成", "硅基流动 FLUX.1 / Pexels / 720P 高清帧绘制", renderStatus.progress >= 45),
                    Triple("多角色配音", "云端神经语音 / Android 原生中文 TTS 引擎", renderStatus.progress >= 70),
                    Triple("2.5D 运镜合成", "推镜/拉镜/摇镜动态帧序列与防变形双层字幕", renderStatus.progress >= 85),
                    Triple("H.264 视频压制", "720×1280 竖屏成片 MP4 封装入库", renderStatus.progress >= 100)
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
                            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.weight(1f)) {
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
                                Text(desc, color = Color(0xFF94A3B8), fontSize = 9.sp, maxLines = 1)
                            }
                            Text(
                                text = if (done) "已完成" else "进行中",
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
                    text = "制片引擎实时执行日志",
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
                                color = if (log.startsWith("❌")) Color(0xFFF87171) else Color(0xFF67E8F9),
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
                                    if (usingLocalEngine && renderStatus.video_url.startsWith("/")) {
                                        val msg = LocalAndroidEngine.exportLocalMp4ToMovies(context, renderStatus.video_url, title)
                                        Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                                    } else {
                                        Toast.makeText(context, "正在注入剪映草稿箱...", Toast.LENGTH_SHORT).show()
                                        val msg = repo.exportJianying(serverUrl)
                                        Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                                    }
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFB800)),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(imageVector = Icons.Default.Download, contentDescription = null, tint = Color(0xFF0C101A))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(if (usingLocalEngine) "保存至相册" else "剪映导出", color = Color(0xFF0C101A), fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }
                    }
                } else if (hasError) {
                    Button(
                        onClick = onDismiss,
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF334155)),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Text("关闭窗口", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
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
                        Text("真实渲染压制中，请稍候...", color = Color(0xFF94A3B8), fontSize = 11.sp)
                    }
                }
            }
        }
    }
}
