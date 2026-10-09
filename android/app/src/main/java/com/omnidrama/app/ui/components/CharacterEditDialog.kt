package com.omnidrama.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
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
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.VoiceItem
import com.omnidrama.app.ui.theme.*

@Composable
fun CharacterEditDialog(
    initialCharacter: CharacterItem? = null,
    availableVoices: List<VoiceItem> = emptyList(),
    onSave: (CharacterItem) -> Unit,
    onDismiss: () -> Unit
) {
    val isEdit = initialCharacter != null
    var name by remember { mutableStateOf(initialCharacter?.name ?: "") }
    var role by remember { mutableStateOf(initialCharacter?.role ?: "核心主角") }
    var selectedVoice by remember { mutableStateOf(initialCharacter?.voice ?: "云希 (磁性沉稳霸道)") }
    var traits by remember { mutableStateOf(initialCharacter?.traits ?: "") }

    val defaultVoices = if (availableVoices.isNotEmpty()) availableVoices else listOf(
        VoiceItem("云希 (磁性沉稳霸道)", "zh-CN-YunxiNeural", "男霸总/战神", "male"),
        VoiceItem("云健 (嚣张跋扈反派)", "zh-CN-YunjianNeural", "纨绔恶少/挑衅", "male"),
        VoiceItem("云扬 (热血青年男主)", "zh-CN-YunyangNeural", "少年修仙/逆袭", "male"),
        VoiceItem("晓晓 (尖酸刻薄逼迫)", "zh-CN-XiaoxiaoNeural", "刁难反派/贵妇", "female"),
        VoiceItem("晓涵 (温柔清纯甜美)", "zh-CN-XiaohanNeural", "豪门千金/白月光", "female"),
        VoiceItem("晓梦 (傲娇泼辣独立)", "zh-CN-XiaomengNeural", "冷艳师姐/女总裁", "female")
    )

    Dialog(onDismissRequest = onDismiss) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(CardDark)
                .border(1.dp, BorderDark, RoundedCornerShape(16.dp))
                .padding(20.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = if (isEdit) "编辑角色资产" else "✨ 添加自定义新角色",
                            color = TextPrimary,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "跨剧集脸型、声线与外貌全流程锁定",
                            color = BrandCyan,
                            fontSize = 11.sp
                        )
                    }
                    IconButton(onClick = onDismiss) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // 角色姓名
                Text("角色姓名:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    placeholder = { Text("例如：林清雪、萧天", color = TextMuted) },
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

                // 角色身份 / 定位
                Text("剧情身份 / 定位标签:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = role,
                    onValueChange = { role = it },
                    placeholder = { Text("例如：豪门女帝、反派幕后黑手、隐世宗主", color = TextMuted) },
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

                // 声线音色选择
                Text("专属配音音色母带:", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(6.dp))
                LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    items(defaultVoices) { v ->
                        val isSelected = selectedVoice.contains(v.name.substringBefore(" ")) || selectedVoice == v.name
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (isSelected) BrandCyan.copy(alpha = 0.2f) else BgDark)
                                .border(
                                    1.dp,
                                    if (isSelected) BrandCyan else BorderDark,
                                    RoundedCornerShape(8.dp)
                                )
                                .clickable { selectedVoice = v.name }
                                .padding(horizontal = 10.dp, vertical = 6.dp)
                        ) {
                            Column {
                                Text(
                                    text = v.name,
                                    color = if (isSelected) BrandCyan else TextPrimary,
                                    fontSize = 11.sp,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                )
                                Text(
                                    text = v.tag,
                                    color = if (isSelected) AccentGold else TextMuted,
                                    fontSize = 9.sp
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // 外貌视觉特征 / 提示词
                Text("外貌与视觉设定特征 (AI 定妆锁脸 Prompt):", color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = traits,
                    onValueChange = { traits = it },
                    placeholder = { Text("例如：银发蓝眸，冷艳绝尘，身着黑色修身风衣，气质高冷高贵", color = TextMuted) },
                    maxLines = 3,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(20.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
                ) {
                    TextButton(onClick = onDismiss) {
                        Text("取消", color = TextSecondary)
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Button(
                        onClick = {
                            if (name.isNotBlank()) {
                                onSave(
                                    CharacterItem(
                                        name = name.trim(),
                                        role = role.trim().ifEmpty { "主要角色" },
                                        voice = selectedVoice,
                                        avatar = initialCharacter?.avatar ?: "",
                                        traits = traits.trim().ifEmpty { "${name}，动漫影视级画风，特征鲜明" }
                                    )
                                )
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = BrandCyan),
                        enabled = name.isNotBlank()
                    ) {
                        Text("保存角色资产", color = BgDark, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
