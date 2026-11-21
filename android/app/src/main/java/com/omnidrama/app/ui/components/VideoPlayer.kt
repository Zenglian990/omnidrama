package com.omnidrama.app.ui.components

import android.net.Uri
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.annotation.OptIn
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddCircleOutline
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
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
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView
import java.io.File

@OptIn(UnstableApi::class)
@Composable
fun VideoPlayer(
    videoUrl: String,
    hasActiveProject: Boolean = false,
    onAddWorkClick: (() -> Unit)? = null,
    onProduceClick: (() -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    var isBuffering by remember { mutableStateOf(false) }
    var hasError by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }

    val exoPlayer = remember(videoUrl) {
        val httpFactory = DefaultHttpDataSource.Factory()
            .setUserAgent("OmniDrama/1.6")
            .setConnectTimeoutMs(15000)
            .setReadTimeoutMs(30000)
            .setDefaultRequestProperties(mapOf("Bypass-Tunnel-Reminder" to "true"))

        // DefaultDataSource.Factory 同时支持 file:// 本地 MP4 与 http/https 远程流！
        val dataSourceFactory = DefaultDataSource.Factory(context, httpFactory)
        val mediaSourceFactory = DefaultMediaSourceFactory(context)
            .setDataSourceFactory(dataSourceFactory)

        ExoPlayer.Builder(context)
            .setMediaSourceFactory(mediaSourceFactory)
            .build().apply {
                if (videoUrl.isNotBlank()) {
                    try {
                        hasError = false
                        val uri = if (videoUrl.startsWith("/")) {
                            Uri.fromFile(File(videoUrl))
                        } else {
                            Uri.parse(videoUrl)
                        }
                        setMediaItem(MediaItem.fromUri(uri))
                        prepare()
                        playWhenReady = true
                        repeatMode = Player.REPEAT_MODE_ONE
                    } catch (e: Exception) {
                        hasError = true
                        errorMessage = e.localizedMessage ?: "视频加载异常"
                    }
                }
                addListener(object : Player.Listener {
                    override fun onPlaybackStateChanged(state: Int) {
                        isBuffering = (state == Player.STATE_BUFFERING)
                        if (state == Player.STATE_READY) {
                            hasError = false
                        }
                    }

                    override fun onPlayerError(error: PlaybackException) {
                        isBuffering = false
                        hasError = true
                        errorMessage = "成片尚未生成，请点击下方【一键制作 / 渲染全片】"
                    }
                })
            }
    }

    DisposableEffect(exoPlayer) {
        onDispose {
            exoPlayer.release()
        }
    }

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(Color(0xFF090B10))
            .border(1.dp, Color(0xFF1E2638), RoundedCornerShape(12.dp)),
        contentAlignment = Alignment.Center
    ) {
        if (videoUrl.isNotBlank() && !hasError) {
            AndroidView(
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        player = exoPlayer
                        useController = true
                        layoutParams = FrameLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT,
                            ViewGroup.LayoutParams.MATCH_PARENT
                        )
                    }
                },
                modifier = Modifier.fillMaxSize()
            )
        }

        if (videoUrl.isBlank() || hasError) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Box(
                    modifier = Modifier
                        .size(64.dp)
                        .clip(CircleShape)
                        .background(
                            Brush.linearGradient(
                                listOf(Color(0xFFFFDF70), Color(0xFFFFB800), Color(0xFF00F2FE))
                            )
                        )
                        .padding(2.dp)
                        .clip(CircleShape)
                        .background(Color(0xFF101420)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = if (!hasActiveProject) Icons.Default.AddCircleOutline else if (hasError) Icons.Default.Refresh else Icons.Default.Movie,
                        contentDescription = null,
                        tint = if (!hasActiveProject) Color(0xFFFFDF70) else if (hasError) Color(0xFFFFB800) else Color(0xFF00F2FE),
                        modifier = Modifier.size(32.dp)
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = if (!hasActiveProject) "您的作品库暂无剧目" else if (hasError) "当前作品尚未压制视频" else "院线监视器就绪",
                    color = Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = if (!hasActiveProject) {
                        "本产品不预留任何固定小说模板。\n请点击下方按钮从【🍅 番茄小说】导入或粘贴您喜欢的作品！"
                    } else if (hasError) {
                        errorMessage
                    } else {
                        "分镜已就绪！点击下方【⚡ 一键制作 / 渲染全片】即可生成 720×1280 竖屏短剧"
                    },
                    color = Color(0xFF94A3B8),
                    fontSize = 12.sp,
                    textAlign = TextAlign.Center
                )

                if (!hasActiveProject && onAddWorkClick != null) {
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(
                        onClick = onAddWorkClick,
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFB800)),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Text(
                            text = "🍅 从番茄小说导入 / 添加第一部作品",
                            color = Color(0xFF0C101A),
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.ExtraBold
                        )
                    }
                }
            }
        }

        if (isBuffering && videoUrl.isNotBlank() && !hasError) {
            CircularProgressIndicator(
                color = Color(0xFF00F2FE),
                strokeWidth = 3.dp,
                modifier = Modifier.size(42.dp)
            )
        }
    }
}
