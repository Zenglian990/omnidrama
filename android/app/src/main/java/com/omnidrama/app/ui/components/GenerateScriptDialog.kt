package com.omnidrama.app.ui.components

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.OpenInBrowser
import androidx.compose.material.icons.filled.Whatshot
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.omnidrama.app.data.model.FanqieBookItem
import com.omnidrama.app.data.repository.DramaRepository
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun GenerateScriptDialog(
    serverUrl: String,
    isGenerating: Boolean,
    onGenerate: (title: String, genre: String, novelText: String) -> Unit,
    onGenerateAndProduce: (title: String, genre: String, novelText: String) -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val repo = remember { DramaRepository() }

    // 100% 空白起步，绝不预留任何写死的小说模板
    var title by remember { mutableStateOf("") }
    var genre by remember { mutableStateOf("") }
    var novelText by remember { mutableStateOf("") }

    // 番茄小说联动状态
    var fanqieUrl by remember { mutableStateOf("") }
    var isParsingUrl by remember { mutableStateOf(false) }
    var isLoadingRank by remember { mutableStateOf(false) }
    var rankBooks by remember { mutableStateOf<List<FanqieBookItem>>(emptyList()) }
    var showRankPanel by remember { mutableStateOf(false) }

    val fanqieGenres = listOf(
        "都市脑洞", "战神赘婿", "豪门总裁", "玄幻修仙",
        "古言宫斗", "末世求生", "悬疑惊悚", "年代重生",
        "神医下山", "科幻星际", "规则怪谈", "历史架空"
    )

    Dialog(onDismissRequest = onDismiss) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.94f)
                .clip(RoundedCornerShape(16.dp))
                .background(CardDark)
                .border(1.dp, BorderDark, RoundedCornerShape(16.dp))
                .padding(18.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.AutoAwesome,
                            contentDescription = null,
                            tint = AccentGold,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                text = "添加您喜欢的小说作品",
                                color = TextPrimary,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "直连番茄小说网 (fanqienovel.com) 或自由粘贴原创剧本",
                                color = BrandCyan,
                                fontSize = 10.5.sp
                            )
                        }
                    }
                    IconButton(onClick = onDismiss, enabled = !isGenerating) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 🍅 番茄小说实时联动卡片
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color(0xFF1A1416))
                        .border(1.dp, Color(0xFFFF5722).copy(alpha = 0.6f), RoundedCornerShape(12.dp))
                        .padding(12.dp)
                ) {
                    Column {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("🍅", fontSize = 15.sp)
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = "番茄小说实时联动提取",
                                    color = Color(0xFFFF8A65),
                                    fontSize = 12.5.sp,
                                    fontWeight = FontWeight.ExtraBold
                                )
                            }

                            // 打开番茄小说官网挑书
                            Row(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(Color(0xFF2D1E22))
                                    .border(0.5.dp, Color(0xFFFF8A65), RoundedCornerShape(6.dp))
                                    .clickable {
                                        try {
                                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://fanqienovel.com"))
                                            context.startActivity(intent)
                                        } catch (e: Exception) {
                                            Toast.makeText(context, "无法打开浏览器", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                    .padding(horizontal = 8.dp, vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.OpenInBrowser,
                                    contentDescription = null,
                                    tint = Color(0xFFFF8A65),
                                    modifier = Modifier.size(12.dp)
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("去番茄小说挑书", color = Color(0xFFFFAB91), fontSize = 10.sp, fontWeight = FontWeight.Bold)
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        // 链接粘贴 + 一键解析
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            OutlinedTextField(
                                value = fanqieUrl,
                                onValueChange = { fanqieUrl = it },
                                singleLine = true,
                                placeholder = {
                                    Text(
                                        "粘贴番茄小说链接 (如 fanqienovel.com/page/...) 或书号",
                                        color = TextMuted,
                                        fontSize = 10.sp
                                    )
                                },
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = TextPrimary,
                                    unfocusedTextColor = TextPrimary,
                                    focusedBorderColor = Color(0xFFFF5722),
                                    unfocusedBorderColor = BorderDark
                                ),
                                modifier = Modifier.weight(1f)
                            )

                            Button(
                                onClick = {
                                    if (fanqieUrl.isBlank()) {
                                        Toast.makeText(context, "请先粘贴番茄小说链接或书籍ID", Toast.LENGTH_SHORT).show()
                                        return@Button
                                    }
                                    scope.launch {
                                        isParsingUrl = true
                                        val book = com.omnidrama.app.data.local.LocalAndroidEngine.importFanqieUrlDirectly(fanqieUrl.trim(), serverUrl)
                                        isParsingUrl = false
                                        if (book != null && book.title.isNotBlank()) {
                                            title = book.title
                                            genre = book.genre.ifBlank { "番茄爆款短剧" }
                                            novelText = book.story_text.ifBlank { book.abstract }
                                            Toast.makeText(context, "✅ 成功从番茄小说导入《${book.title}》！", Toast.LENGTH_SHORT).show()
                                        } else {
                                            Toast.makeText(context, "⚠️ 链接解析未获取到正文，请检查链接或直接粘贴章节内容", Toast.LENGTH_LONG).show()
                                        }
                                    }
                                },
                                enabled = !isParsingUrl && !isGenerating,
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFF5722)),
                                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 10.dp),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                if (isParsingUrl) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(14.dp),
                                        color = Color.White,
                                        strokeWidth = 2.dp
                                    )
                                } else {
                                    Icon(Icons.Default.Link, contentDescription = null, tint = Color.White, modifier = Modifier.size(14.dp))
                                    Spacer(modifier = Modifier.width(3.dp))
                                    Text("解析导入", color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        // 一键拉取番茄实时热榜按钮
                        Button(
                            onClick = {
                                scope.launch {
                                    showRankPanel = true
                                    isLoadingRank = true
                                    rankBooks = com.omnidrama.app.data.local.LocalAndroidEngine.fetchFanqieRankDirectly(serverUrl)
                                    isLoadingRank = false
                                    if (rankBooks.isEmpty()) {
                                        Toast.makeText(context, "⚠️ 暂未获取到榜单，可点击右上角【去番茄小说挑书】复制链接", Toast.LENGTH_SHORT).show()
                                    }
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2D1E22)),
                            shape = RoundedCornerShape(8.dp),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            if (isLoadingRank) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(14.dp),
                                    color = Color(0xFFFF8A65),
                                    strokeWidth = 2.dp
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("正在同步 fanqienovel.com 实时热榜...", color = Color(0xFFFFAB91), fontSize = 11.sp)
                            } else {
                                Icon(Icons.Default.Whatshot, contentDescription = null, tint = Color(0xFFFF5722), modifier = Modifier.size(15.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = if (rankBooks.isEmpty()) "🔥 获取番茄小说实时热榜 (点击挑选喜欢的小说)" else "🔥 刷新番茄小说实时热榜 (已加载 ${rankBooks.size} 部)",
                                    color = Color(0xFFFFAB91),
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        // 实时榜单展示区
                        if (showRankPanel && rankBooks.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(Color(0xFF110E10))
                                    .padding(8.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                Text(
                                    text = "点击任意作品即可自动抓取简介与首章内容：",
                                    color = Color(0xFFFFAB91),
                                    fontSize = 10.sp
                                )
                                rankBooks.take(8).forEach { item ->
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clip(RoundedCornerShape(6.dp))
                                            .background(Color(0xFF1E191B))
                                            .clickable {
                                                scope.launch {
                                                    isParsingUrl = true
                                                    val fullBook = if (item.url.isNotBlank() && item.story_text.isBlank()) {
                                                        com.omnidrama.app.data.local.LocalAndroidEngine.importFanqieUrlDirectly(item.url, serverUrl) ?: item
                                                    } else item
                                                    isParsingUrl = false
                                                    title = fullBook.title
                                                    genre = fullBook.genre.ifBlank { "番茄热榜爽剧" }
                                                    novelText = fullBook.story_text.ifBlank { fullBook.abstract }
                                                    showRankPanel = false
                                                    Toast.makeText(context, "✅ 已载入《${fullBook.title}》，可继续自由修改内容！", Toast.LENGTH_SHORT).show()
                                                }
                                            }
                                            .padding(8.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Text(
                                                    text = "《${item.title}》",
                                                    color = Color.White,
                                                    fontSize = 12.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    maxLines = 1,
                                                    overflow = TextOverflow.Ellipsis
                                                )
                                                Spacer(modifier = Modifier.width(6.dp))
                                                Text(
                                                    text = item.genre,
                                                    color = Color(0xFFFF8A65),
                                                    fontSize = 9.5.sp
                                                )
                                            }
                                            if (item.abstract.isNotBlank()) {
                                                Text(
                                                    text = item.abstract,
                                                    color = TextMuted,
                                                    fontSize = 10.sp,
                                                    maxLines = 2,
                                                    overflow = TextOverflow.Ellipsis
                                                )
                                            }
                                        }
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(6.dp))
                                                .background(Color(0xFFFF5722))
                                                .padding(horizontal = 8.dp, vertical = 4.dp)
                                        ) {
                                            Text("导入", color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 番茄全品类题材标签（仅填充题材分类，绝不覆盖用户小说正文）
                Text(
                    text = "番茄热门题材分类 (点击填入题材标签):",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    fanqieGenres.forEach { tag ->
                        val selected = genre == tag
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(14.dp))
                                .background(if (selected) BrandCyan else Color(0xFF1E2638))
                                .border(
                                    0.5.dp,
                                    if (selected) BrandCyan else BorderDark,
                                    RoundedCornerShape(14.dp)
                                )
                                .clickable { genre = tag }
                                .padding(horizontal = 10.dp, vertical = 5.dp)
                        ) {
                            Text(
                                text = tag,
                                color = if (selected) BgDark else TextPrimary,
                                fontSize = 10.5.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 作品标题
                Text("作品名称 / 短剧标题:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    singleLine = true,
                    placeholder = { Text("输入您喜欢的作品名称（或从上方番茄小说一键导入）", color = TextMuted, fontSize = 11.sp) },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(10.dp))

                // 题材类型
                Text("短剧题材 / 视觉风格:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = genre,
                    onValueChange = { genre = it },
                    singleLine = true,
                    placeholder = { Text("例如：都市脑洞 / 末世求生 / 古言宫斗 / 悬疑惊悚...", color = TextMuted, fontSize = 11.sp) },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(10.dp))

                // 小说文本
                Text("小说章节正文 / 剧本内容:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = novelText,
                    onValueChange = { novelText = it },
                    minLines = 5,
                    maxLines = 9,
                    placeholder = {
                        Text(
                            "粘贴您喜欢的任意小说段落、番茄小说章节内容或您自己创作的故事，AI 导演将自动拆解角色、台词与分镜画面...",
                            color = TextMuted,
                            fontSize = 11.sp
                        )
                    },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(16.dp))

                // 双按钮操作区
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // 主按钮：一键制作全片成片
                    Button(
                        onClick = {
                            if (title.isNotBlank() && novelText.isNotBlank()) {
                                onGenerateAndProduce(
                                    title.trim(),
                                    genre.trim().ifBlank { "精品短剧" },
                                    novelText.trim()
                                )
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = AccentGold),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        enabled = !isGenerating && title.isNotBlank() && novelText.isNotBlank()
                    ) {
                        if (isGenerating) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(18.dp),
                                color = BgDark,
                                strokeWidth = 2.dp
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("正在拆解剧本并创建您的专属作品...", color = BgDark, fontWeight = FontWeight.Bold)
                        } else {
                            Icon(imageVector = Icons.Default.AutoAwesome, contentDescription = null, tint = BgDark, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("⚡ 添加至我的作品库并立即制作成片", color = BgDark, fontWeight = FontWeight.ExtraBold, fontSize = 13.sp)
                        }
                    }

                    // 次按钮：仅拆解分镜
                    OutlinedButton(
                        onClick = {
                            if (title.isNotBlank() && novelText.isNotBlank()) {
                                onGenerate(
                                    title.trim(),
                                    genre.trim().ifBlank { "精品短剧" },
                                    novelText.trim()
                                )
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = BrandCyan),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark),
                        enabled = !isGenerating && title.isNotBlank() && novelText.isNotBlank()
                    ) {
                        Text("仅添加作品并拆解分镜 (稍后压制视频)", color = BrandCyan, fontSize = 11.sp)
                    }
                }
            }
        }
    }
}
