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
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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
    onDismiss: () -> Unit
) {
    var title by remember { mutableStateOf("重生之千金霸气归来") }
    var genre by remember { mutableStateOf("豪门打脸爽剧") }
    var novelText by remember {
        mutableStateOf(
            """【第一幕】
林清雪冷笑着将婚约撕得粉碎：陈浩宇，三年前你夺我林氏产业，今日我携千亿财阀归来，定让你陈家万劫不复！
陈浩宇脸色铁青：林清雪，凭你也敢在我面前放肆？
突然，门外传来一阵轰鸣，千辆劳斯莱斯封锁整条街道！
秘书高声通报：恭迎林董归位！"""
        )
    }

    Dialog(onDismissRequest = onDismiss) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.9f)
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
                                text = "AI 智能拆解小说剧本",
                                color = TextPrimary,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "自动识别提取全新角色、声线与分镜镜头",
                                color = BrandCyan,
                                fontSize = 11.sp
                            )
                        }
                    }
                    IconButton(onClick = onDismiss, enabled = !isGenerating) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

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

                Spacer(modifier = Modifier.height(12.dp))

                // 题材类型
                Text("短剧题材 / 调性:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
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

                Spacer(modifier = Modifier.height(12.dp))

                // 快速模版
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("小说文本 / 剧本大纲:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(BorderDark)
                                .clickable {
                                    title = "真千金杀疯豪门"
                                    genre = "现代豪门爽剧"
                                    novelText = "林清雪冷笑：陈浩宇，三年前你夺我林氏产业，今日我携千亿财阀归来！\n陈浩宇大怒：一个弃女也敢大放厥词！\n管家慌张跑入：少爷不好了，全球前十大财团全部听从林小姐号令！"
                                }
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text("真千金", color = BrandCyan, fontSize = 10.sp)
                        }
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(BorderDark)
                                .clickable {
                                    title = "修仙万载重回都市"
                                    genre = "玄幻修真爽文"
                                    novelText = "萧凡负手而立：任你权倾江城，在我仙尊眼中亦不过蝼蚁！\n江城首富跪倒在地：仙尊饶命！老朽有眼不识泰山！\n天地骤然变色，紫气东来三万里！"
                                }
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text("修仙仙尊", color = AccentGold, fontSize = 10.sp)
                        }
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = novelText,
                    onValueChange = { novelText = it },
                    minLines = 6,
                    maxLines = 10,
                    placeholder = { Text("粘贴任何爽文片段，角色与动作会自动智能提取...", color = TextMuted) },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(20.dp))

                Button(
                    onClick = {
                        if (title.isNotBlank() && novelText.isNotBlank()) {
                            onGenerate(title.trim(), genre.trim(), novelText.trim())
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = AccentGold),
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !isGenerating && title.isNotBlank() && novelText.isNotBlank()
                ) {
                    if (isGenerating) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            color = BgDark,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("AI 导演正在拆解镜头与角色...", color = BgDark, fontWeight = FontWeight.Bold)
                    } else {
                        Icon(imageVector = Icons.Default.AutoAwesome, contentDescription = null, tint = BgDark, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text("⚡ 立即拆解并生成全新剧目", color = BgDark, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
