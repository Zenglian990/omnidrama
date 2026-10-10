package com.omnidrama.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.omnidrama.app.ui.theme.*

@Composable
fun GenerateScriptDialog(
    isGenerating: Boolean,
    onGenerate: (title: String, genre: String, novelText: String) -> Unit,
    onGenerateAndProduce: (title: String, genre: String, novelText: String) -> Unit,
    onDismiss: () -> Unit
) {
    var title by remember { mutableStateOf("至尊龙王归位") }
    var genre by remember { mutableStateOf("都市战神爽文") }
    var novelText by remember {
        mutableStateOf(
            """【第一幕】
林家祖宅大堂，狂风骤雨拍打着雕花木窗。
岳母柳琴厉声呵斥：叶辰，入赘三年，今日若拿不出三千万，就立刻滚出林家！
叶辰神色淡然：三千万？当年若非我暗中相助，林家早在三年前就已灰飞烟灭！
赵公子狂妄大笑：大言不惭的废物，也不撒泡尿照照自己是个什么东西！
突然，惊雷炸裂，大门轰然破碎，十八位黑金战铠修罗战神破门而入！
修罗战神齐声高呼：恭迎龙王回归！十万修罗殿众将，随时听候调遣！
叶辰冷冽大特写：犯我逆鳞者，杀无赦！"""
        )
    }

    Dialog(onDismissRequest = onDismiss) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.92f)
                .clip(RoundedCornerShape(16.dp))
                .background(CardDark)
                .border(1.dp, BorderDark, RoundedCornerShape(16.dp))
                .padding(20.dp)
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
                                text = "创作全新 AI 短剧",
                                color = TextPrimary,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "输入小说或选取模版，一键直出好莱坞级成片",
                                color = BrandCyan,
                                fontSize = 11.sp
                            )
                        }
                    }
                    IconButton(onClick = onDismiss, enabled = !isGenerating) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // 快速题材模版库
                Text("热门题材模版 (点击一键载入):", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(6.dp))
                            .background(Color(0xFF1E2638))
                            .border(0.5.dp, Color(0xFFFFB800), RoundedCornerShape(6.dp))
                            .clickable {
                                title = "至尊龙王归位"
                                genre = "都市战神爽文"
                                novelText = "林家大堂狂风暴雨，岳母逼迫离婚。叶辰淡然冷笑，修罗战神破门而入跪迎龙王！"
                            }
                            .padding(vertical = 6.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("🔥 战神回归", color = Color(0xFFFFDF70), fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(6.dp))
                            .background(Color(0xFF1E2638))
                            .border(0.5.dp, Color(0xFF00F2FE), RoundedCornerShape(6.dp))
                            .clickable {
                                title = "真千金杀疯豪门"
                                genre = "现代豪门爽剧"
                                novelText = "林清雪冷笑撕毁婚约：陈浩宇，三年前你夺我林氏产业，今日我携千亿财阀归来！管家慌张跑入：全球前十大财团全部听从林小姐号令！"
                            }
                            .padding(vertical = 6.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("👑 豪门千金", color = Color(0xFF67E8F9), fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(6.dp))
                            .background(Color(0xFF1E2638))
                            .border(0.5.dp, Color(0xFF7928CA), RoundedCornerShape(6.dp))
                            .clickable {
                                title = "修仙万载重回都市"
                                genre = "玄幻修真爽文"
                                novelText = "萧凡负手而立：任你权倾江城，在我仙尊眼中亦不过蝼蚁！首富跪地求饶，紫气东来三万里！"
                            }
                            .padding(vertical = 6.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("⚡ 修仙仙尊", color = Color(0xFFD8B4FE), fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // 短剧标题
                Text("短剧标题:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    singleLine = true,
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
                Text("短剧题材 / 风格调性:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = genre,
                    onValueChange = { genre = it },
                    singleLine = true,
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
                Text("小说故事 / 剧本大纲:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = novelText,
                    onValueChange = { novelText = it },
                    minLines = 5,
                    maxLines = 8,
                    placeholder = { Text("粘贴任何小说或剧本片段，AI 会自动拆解台词并生成电影视频...", color = TextMuted) },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(18.dp))

                // 双按钮操作区
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // 主按钮：一键制作全片成片
                    Button(
                        onClick = {
                            if (title.isNotBlank() && novelText.isNotBlank()) {
                                onGenerateAndProduce(title.trim(), genre.trim(), novelText.trim())
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
                            Text("AI 导演正在启动机房流水线...", color = BgDark, fontWeight = FontWeight.Bold)
                        } else {
                            Icon(imageVector = Icons.Default.AutoAwesome, contentDescription = null, tint = BgDark, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("⚡ 立即一键制作短剧全片成片", color = BgDark, fontWeight = FontWeight.ExtraBold, fontSize = 13.sp)
                        }
                    }

                    // 次按钮：仅拆解分镜
                    OutlinedButton(
                        onClick = {
                            if (title.isNotBlank() && novelText.isNotBlank()) {
                                onGenerate(title.trim(), genre.trim(), novelText.trim())
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = BrandCyan),
                        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark),
                        enabled = !isGenerating && title.isNotBlank() && novelText.isNotBlank()
                    ) {
                        Text("仅拆解分镜大纲 (不立即压制视频)", color = BrandCyan, fontSize = 11.sp)
                    }
                }
            }
        }
    }
}
