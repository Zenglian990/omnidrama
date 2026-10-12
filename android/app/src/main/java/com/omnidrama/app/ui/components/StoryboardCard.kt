package com.omnidrama.app.ui.components

import android.graphics.BitmapFactory
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
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
import com.omnidrama.app.data.model.ShotItem
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

private val thumbHttpClient = OkHttpClient.Builder()
    .connectTimeout(10, TimeUnit.SECONDS)
    .readTimeout(15, TimeUnit.SECONDS)
    .addInterceptor { chain ->
        val req = chain.request().newBuilder()
            .addHeader("Bypass-Tunnel-Reminder", "true")
            .build()
        chain.proceed(req)
    }
    .build()

@Composable
fun StoryboardCard(
    shot: ShotItem,
    serverUrl: String,
    isSelected: Boolean,
    refreshVersion: Int = 0,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    var isPlayingAudio by remember { mutableStateOf(false) }
    var mediaPlayer by remember { mutableStateOf<MediaPlayer?>(null) }
    var shotBitmap by remember { mutableStateOf<ImageBitmap?>(null) }

    LaunchedEffect(shot.id, shot.dialogue, shot.visual_prompt, serverUrl, refreshVersion) {
        withContext(Dispatchers.IO) {
            try {
                val imgUrl = "$serverUrl/api/shots/${shot.id}/image?v=$refreshVersion&t=${shot.dialogue.hashCode()}"
                val req = Request.Builder().url(imgUrl).build()
                thumbHttpClient.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val bytes = resp.body?.bytes()
                        if (bytes != null && bytes.isNotEmpty()) {
                            val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                            if (bmp != null) {
                                shotBitmap = bmp.asImageBitmap()
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            mediaPlayer?.release()
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
                // Header Row: 镜头编号 + 景别 + 运镜 + 拟音
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

                    if (shot.sfx != "无") {
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

                // 角色说话人
                Text(
                    text = "【${shot.speaker}】",
                    color = AccentGold,
                    fontSize = 12.5.sp,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(3.dp))

                // 台词正文
                Text(
                    text = shot.dialogue,
                    color = TextPrimary,
                    fontSize = 12.5.sp,
                    lineHeight = 17.sp,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis
                )

                Spacer(modifier = Modifier.height(8.dp))

                // 底部操作按钮：试听配音 + 精修/重绘
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 试听配音按钮
                    Button(
                        onClick = {
                            if (isPlayingAudio) {
                                mediaPlayer?.stop()
                                mediaPlayer?.release()
                                mediaPlayer = null
                                isPlayingAudio = false
                            } else {
                                try {
                                    val audioEndpoint = "$serverUrl/api/shots/${shot.id}/audio?v=$refreshVersion&t=${System.currentTimeMillis()}"
                                    val player = MediaPlayer().apply {
                                        setAudioAttributes(
                                            AudioAttributes.Builder()
                                                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                                                .setUsage(AudioAttributes.USAGE_MEDIA)
                                                .build()
                                        )
                                        setDataSource(audioEndpoint)
                                        setOnPreparedListener {
                                            start()
                                            isPlayingAudio = true
                                        }
                                        setOnCompletionListener {
                                            isPlayingAudio = false
                                            release()
                                        }
                                        setOnErrorListener { _, _, _ ->
                                            isPlayingAudio = false
                                            Toast.makeText(context, "配音准备中，可先点击重绘/重录", Toast.LENGTH_SHORT).show()
                                            true
                                        }
                                        prepareAsync()
                                    }
                                    mediaPlayer = player
                                } catch (e: Exception) {
                                    isPlayingAudio = false
                                    Toast.makeText(context, "播放失败: ${e.message}", Toast.LENGTH_SHORT).show()
                                }
                            }
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (isPlayingAudio) Color(0xFFF59E0B) else Color(0xFF1E283D)
                        ),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 3.dp),
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier.height(27.dp)
                    ) {
                        Icon(
                            imageVector = if (isPlayingAudio) Icons.Default.Stop else Icons.Default.VolumeUp,
                            contentDescription = "TTS",
                            tint = if (isPlayingAudio) Color.Black else AccentEmerald,
                            modifier = Modifier.size(12.dp)
                        )
                        Spacer(modifier = Modifier.width(3.dp))
                        Text(
                            text = if (isPlayingAudio) "停止" else "试听配音",
                            color = if (isPlayingAudio) Color.Black else Color.White,
                            fontSize = 10.5.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    // 精修 / 重绘按钮
                    Button(
                        onClick = onClick,
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1E293B)),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 3.dp),
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier.height(27.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Edit,
                            contentDescription = "Edit Shot",
                            tint = BrandCyan,
                            modifier = Modifier.size(12.dp)
                        )
                        Spacer(modifier = Modifier.width(3.dp))
                        Text(
                            text = "改词 / 重绘画面",
                            color = BrandCyan,
                            fontSize = 10.5.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    }
}
