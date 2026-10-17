package com.omnidrama.app.ui.components

import android.graphics.BitmapFactory
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.omnidrama.app.data.local.LocalAndroidEngine
import com.omnidrama.app.data.model.ShotItem
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.Request
import java.io.File

@Composable
fun StoryboardCard(
    projectTitle: String = "",
    projectGenre: String = "",
    shot: ShotItem,
    serverUrl: String,
    isSelected: Boolean,
    refreshVersion: Int = 0,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isPlayingAudio by remember { mutableStateOf(false) }
    var shotBitmap by remember { mutableStateOf<ImageBitmap?>(null) }
    var isRenderingShotVideo by remember { mutableStateOf(false) }
    var showVideoDialog by remember { mutableStateOf(false) }
    var currentShotVideoPath by remember { mutableStateOf("") }

    LaunchedEffect(projectTitle, shot.id, shot.speaker, shot.dialogue, shot.visual_prompt, shot.motion, serverUrl, refreshVersion) {
        LocalAndroidEngine.ensureTtsInitialized(context)
        withContext(Dispatchers.IO) {
            try {
                val effectiveTitle = projectTitle.ifBlank { "我的短剧" }
                val effectiveGenre = projectGenre.ifBlank { "热门爽剧" }

                // 1. 先检查手机本地是否已生成该分镜的最新预览图
                val localFile = LocalAndroidEngine.getLocalShotImageFile(context, effectiveTitle, shot.id)
                if (localFile.exists() && localFile.length() > 100) {
                    val bmp = BitmapFactory.decodeFile(localFile.absolutePath)
                    if (bmp != null) {
                        shotBitmap = bmp.asImageBitmap()
                        return@withContext
                    }
                }

                // 2. 尝试从远端机房加载并缓存到本地
                var loadedFromServer = false
                if (serverUrl.isNotBlank()) {
                    try {
                        val imgUrl = "${serverUrl.trimEnd('/')}/api/shots/${shot.id}/image?v=$refreshVersion&t=${shot.dialogue.hashCode()}"
                        val req = Request.Builder().url(imgUrl).build()
                        LocalAndroidEngine.directHttpClient.newBuilder()
                            .connectTimeout(3, java.util.concurrent.TimeUnit.SECONDS)
                            .readTimeout(5, java.util.concurrent.TimeUnit.SECONDS)
                            .build()
                            .newCall(req).execute().use { resp ->
                                if (resp.isSuccessful && resp.header("Content-Type")?.contains("image") == true) {
                                    val bytes = resp.body?.bytes()
                                    if (bytes != null && bytes.isNotEmpty()) {
                                        val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                                        if (bmp != null) {
                                            try {
                                                localFile.writeBytes(bytes)
                                            } catch (_: Exception) {
                                            }
                                            shotBitmap = bmp.asImageBitmap()
                                            loadedFromServer = true
                                        }
                                    }
                                }
                            }
                    } catch (_: Exception) {
                    }
                }

                // 3. 若远端未连接，直接在手机本地生成 720×1280 竖屏分镜预览帧
                if (!loadedFromServer) {
                    val generated = LocalAndroidEngine.generateShotImageOnPhone(
                        context = context,
                        title = effectiveTitle,
                        genre = effectiveGenre,
                        shot = shot
                    )
                    if (generated.exists()) {
                        val bmp = BitmapFactory.decodeFile(generated.absolutePath)
                        if (bmp != null) {
                            shotBitmap = bmp.asImageBitmap()
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            if (isPlayingAudio) {
                LocalAndroidEngine.stopAllAudio()
            }
        }
    }

    val borderColor = if (isSelected) BrandCyan else BorderDark

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(CardDark)
            .border(1.dp, borderColor, RoundedCornerShape(12.dp))
            .clickable { onClick() }
            .padding(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Top
        ) {
            // 左侧 9:16 真实分镜画面缩略图
            Box(
                modifier = Modifier
                    .width(68.dp)
                    .height(116.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(BgDark)
                    .border(1.dp, BorderDark, RoundedCornerShape(8.dp)),
                contentAlignment = Alignment.Center
            ) {
                if (shotBitmap != null) {
                    Image(
                        bitmap = shotBitmap!!,
                        contentDescription = "Shot #${shot.id}",
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize()
                    )
                } else {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.Image,
                            contentDescription = null,
                            tint = BrandCyan.copy(alpha = 0.6f),
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text("第${shot.id}镜", color = TextMuted, fontSize = 9.sp)
                    }
                }
            }

            Spacer(modifier = Modifier.width(12.dp))

            // 右侧分镜详情与操作栏
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "#%02d".format(shot.id),
                            color = BrandCyan,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(BorderDark)
                                .padding(horizontal = 5.dp, vertical = 2.dp)
                        ) {
                            Text(
                                text = shot.scale,
                                color = Color(0xFF67E8F9),
                                fontSize = 9.5.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                        Spacer(modifier = Modifier.width(5.dp))
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(Color(0xFF2E1065))
                                .padding(horizontal = 5.dp, vertical = 2.dp)
                        ) {
                            Text(
                                text = shot.motion_name,
                                color = Color(0xFFD8B4FE),
                                fontSize = 9.5.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }

                    if (shot.sfx != "无" && shot.sfx.isNotBlank()) {
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(Color(0xFF451A03))
                                .padding(horizontal = 5.dp, vertical = 2.dp)
                        ) {
                            Text(
                                text = shot.sfx,
                                color = AccentGold,
                                fontSize = 9.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = "【${shot.speaker}】",
                    color = AccentGold,
                    fontSize = 12.5.sp,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(3.dp))

                Text(
                    text = shot.dialogue,
                    color = TextPrimary,
                    fontSize = 12.5.sp,
                    lineHeight = 17.sp,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis
                )

                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 🔊 100% 必响真实试听配音按钮 (云端 + 手机系统中文 TTS 双重保障)
                    Button(
                        onClick = {
                            if (isPlayingAudio) {
                                LocalAndroidEngine.stopAllAudio()
                                isPlayingAudio = false
                            } else {
                                scope.launch {
                                    Toast.makeText(
                                        context,
                                        "🔊 正在朗读【${shot.speaker}】台词...",
                                        Toast.LENGTH_SHORT
                                    ).show()
                                    LocalAndroidEngine.playShotAudioGuaranteed(
                                        context = context,
                                        serverUrl = serverUrl,
                                        shot = shot,
                                        onStart = { isPlayingAudio = true },
                                        onComplete = { isPlayingAudio = false }
                                    )
                                }
                            }
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (isPlayingAudio) Color(0xFFF59E0B) else Color(0xFF1E283D)
                        ),
                        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 3.dp),
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier.height(27.dp)
                    ) {
                        Icon(
                            imageVector = if (isPlayingAudio) Icons.Default.Stop else Icons.Default.VolumeUp,
                            contentDescription = "TTS",
                            tint = if (isPlayingAudio) Color.Black else AccentEmerald,
                            modifier = Modifier.size(11.dp)
                        )
                        Spacer(modifier = Modifier.width(2.dp))
                        Text(
                            text = if (isPlayingAudio) "停止" else "试听配音",
                            color = if (isPlayingAudio) Color.Black else Color.White,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    // 🎬 镜片独立视频（手机原生 MediaCodec 秒级压制 / 立即播放）
                    val localVideoFile = remember(projectTitle, shot.id, isRenderingShotVideo) {
                        LocalAndroidEngine.getLocalShotVideoFile(context, projectTitle, shot.id)
                    }
                    val hasLocalVideo = localVideoFile.exists() && localVideoFile.length() > 500

                    Button(
                        onClick = {
                            if (hasLocalVideo) {
                                currentShotVideoPath = localVideoFile.absolutePath
                                showVideoDialog = true
                            } else {
                                scope.launch {
                                    isRenderingShotVideo = true
                                    Toast.makeText(context, "🎬 正在为第${shot.id}镜生成独立视频 (台词+画面+字幕)...", Toast.LENGTH_SHORT).show()
                                    val outPath = LocalAndroidEngine.renderSingleShotMp4OnPhone(
                                        context = context,
                                        projectTitle = projectTitle,
                                        projectGenre = projectGenre,
                                        shot = shot
                                    )
                                    isRenderingShotVideo = false
                                    if (!outPath.isNullOrBlank() && File(outPath).exists()) {
                                        currentShotVideoPath = outPath
                                        showVideoDialog = true
                                        Toast.makeText(context, "✅ 第${shot.id}镜视频生成完成！", Toast.LENGTH_SHORT).show()
                                    } else {
                                        Toast.makeText(context, "❌ 镜片视频压制失败，请检查存储或重试", Toast.LENGTH_SHORT).show()
                                    }
                                }
                            }
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (isRenderingShotVideo) Color(0xFFF59E0B) else if (hasLocalVideo) Color(0xFF059669) else Color(0xFF7C3AED)
                        ),
                        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 3.dp),
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier.height(27.dp),
                        enabled = !isRenderingShotVideo
                    ) {
                        if (isRenderingShotVideo) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(11.dp),
                                color = Color.White,
                                strokeWidth = 1.5.dp
                            )
                            Spacer(modifier = Modifier.width(3.dp))
                            Text("合成中...", color = Color.White, fontSize = 9.5.sp)
                        } else {
                            Icon(
                                imageVector = if (hasLocalVideo) Icons.Default.PlayArrow else Icons.Default.Movie,
                                contentDescription = "Shot Video",
                                tint = Color.White,
                                modifier = Modifier.size(11.dp)
                            )
                            Spacer(modifier = Modifier.width(2.dp))
                            Text(
                                text = if (hasLocalVideo) "播放镜片" else "镜片视频",
                                color = Color.White,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    // 精修 / 重绘按钮
                    Button(
                        onClick = onClick,
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1E293B)),
                        contentPadding = PaddingValues(horizontal = 6.dp, vertical = 3.dp),
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier.height(27.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Edit,
                            contentDescription = "Edit Shot",
                            tint = BrandCyan,
                            modifier = Modifier.size(11.dp)
                        )
                        Spacer(modifier = Modifier.width(2.dp))
                        Text(
                            text = "改词/重绘",
                            color = BrandCyan,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    }

    // 镜片独立视频播放弹窗
    if (showVideoDialog && currentShotVideoPath.isNotBlank()) {
        Dialog(onDismissRequest = { showVideoDialog = false }) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.85f)
                    .clip(RoundedCornerShape(16.dp))
                    .background(Color(0xFF0C101A))
                    .border(1.5.dp, Color(0xFF7C3AED), RoundedCornerShape(16.dp))
                    .padding(14.dp)
            ) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "🎬 第 #${shot.id} 镜 · 镜头成片预览",
                            color = Color.White,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold
                        )
                        IconButton(onClick = { showVideoDialog = false }) {
                            Icon(Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .background(Color.Black)
                    ) {
                        VideoPlayer(
                            videoUrl = currentShotVideoPath,
                            hasActiveProject = true,
                            modifier = Modifier.fillMaxSize()
                        )
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "【${shot.speaker}】${shot.dialogue}",
                            color = TextSecondary,
                            fontSize = 11.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(
                            onClick = {
                                scope.launch {
                                    isRenderingShotVideo = true
                                    showVideoDialog = false
                                    Toast.makeText(context, "🎬 正在重新压制第${shot.id}镜视频...", Toast.LENGTH_SHORT).show()
                                    val outPath = LocalAndroidEngine.renderSingleShotMp4OnPhone(
                                        context = context,
                                        projectTitle = projectTitle,
                                        projectGenre = projectGenre,
                                        shot = shot
                                    )
                                    isRenderingShotVideo = false
                                    if (!outPath.isNullOrBlank() && File(outPath).exists()) {
                                        currentShotVideoPath = outPath
                                        showVideoDialog = true
                                    }
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1E293B)),
                            shape = RoundedCornerShape(6.dp),
                            contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
                        ) {
                            Text("🔄 重新压制", color = BrandCyan, fontSize = 10.5.sp)
                        }
                    }
                }
            }
        }
    }
}
