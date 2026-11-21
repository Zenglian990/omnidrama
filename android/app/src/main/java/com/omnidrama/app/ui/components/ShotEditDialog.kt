package com.omnidrama.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
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
import com.omnidrama.app.data.model.ShotItem
import com.omnidrama.app.ui.theme.*

@Composable
fun ShotEditDialog(
    shot: ShotItem,
    isSaving: Boolean,
    onSaveAndRegenerate: (
        speaker: String,
        dialogue: String,
        visualPrompt: String,
        motion: String,
        regenImage: Boolean,
        regenAudio: Boolean
    ) -> Unit,
    onDeleteShot: ((shotId: Int) -> Unit)? = null,
    onDismiss: () -> Unit
) {
    var speaker by remember { mutableStateOf(shot.speaker) }
    var dialogue by remember { mutableStateOf(shot.dialogue) }
    var visualPrompt by remember {
        mutableStateOf(
            shot.visual_prompt.ifBlank {
                "masterpiece, 8k anime vertical drama, ${shot.speaker}, ${shot.dialogue}, cinematic lighting"
            }
        )
    }
    var selectedMotion by remember { mutableStateOf(shot.motion.uppercase()) }
    var regenImage by remember { mutableStateOf(true) }
    var regenAudio by remember { mutableStateOf(true) }

    val motionOptions = listOf(
        "ZOOM_IN" to "镜头推进",
        "ZOOM_OUT" to "镜头拉远",
        "PAN_LEFT" to "向左横移",
        "SHAKE" to "镜头震撼"
    )

    Dialog(onDismissRequest = { if (!isSaving) onDismiss() }) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(CardDark)
                .border(1.dp, BrandCyan.copy(alpha = 0.5f), RoundedCornerShape(16.dp))
                .padding(16.dp)
        ) {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState())
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "第 %02d 镜 · 分镜精修与单镜重绘".format(shot.id),
                            color = TextPrimary,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "修改台词或画面提示词后，可单独重绘本镜画面与配音",
                            color = BrandCyan,
                            fontSize = 10.5.sp
                        )
                    }
                    IconButton(onClick = { if (!isSaving) onDismiss() }) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                Text("说话角色 (Speaker):", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = speaker,
                    onValueChange = { speaker = it },
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

                Text("本镜台词 / 旁白 (Dialogue):", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = dialogue,
                    onValueChange = { dialogue = it },
                    minLines = 2,
                    maxLines = 4,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(10.dp))

                Text("AI 画面生成提示词 / Pexels 搜索词 (Visual Prompt):", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = visualPrompt,
                    onValueChange = { visualPrompt = it },
                    minLines = 2,
                    maxLines = 4,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = AccentGold,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(10.dp))

                Text("镜头运动方式 (Camera Motion):", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    motionOptions.forEach { (code, label) ->
                        val isSel = selectedMotion.contains(code) || (code == "ZOOM_IN" && selectedMotion !in listOf("ZOOM_OUT", "PAN_LEFT", "SHAKE"))
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(6.dp))
                                .background(if (isSel) BrandCyan else BgDark)
                                .border(1.dp, if (isSel) BrandCyan else BorderDark, RoundedCornerShape(6.dp))
                                .clickable { selectedMotion = code }
                                .padding(vertical = 6.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = label,
                                color = if (isSel) BgDark else TextSecondary,
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Checkbox(
                        checked = regenImage,
                        onCheckedChange = { regenImage = it },
                        colors = CheckboxDefaults.colors(checkedColor = BrandCyan)
                    )
                    Text("重绘本镜画面", color = TextPrimary, fontSize = 11.5.sp)
                    Spacer(modifier = Modifier.width(12.dp))
                    Checkbox(
                        checked = regenAudio,
                        onCheckedChange = { regenAudio = it },
                        colors = CheckboxDefaults.colors(checkedColor = AccentEmerald)
                    )
                    Text("重录本镜配音", color = TextPrimary, fontSize = 11.5.sp)
                }

                Spacer(modifier = Modifier.height(10.dp))

                Button(
                    onClick = {
                        onSaveAndRegenerate(
                            speaker,
                            dialogue,
                            visualPrompt,
                            selectedMotion,
                            regenImage,
                            regenAudio
                        )
                    },
                    enabled = !isSaving,
                    colors = ButtonDefaults.buttonColors(containerColor = AccentGold),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(44.dp),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    if (isSaving) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = BgDark,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("正在真实重绘画面与合成配音...", color = BgDark, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                    } else {
                        Text(
                            text = "🎨 保存修改并立即重绘本镜",
                            color = BgDark,
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 13.sp
                        )
                    }
                }

                if (onDeleteShot != null) {
                    Spacer(modifier = Modifier.height(10.dp))
                    OutlinedButton(
                        onClick = {
                            onDeleteShot(shot.id)
                            onDismiss()
                        },
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFF87171)),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF7F1D1D)),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier.fillMaxWidth().height(40.dp)
                    ) {
                        Text("🗑️ 删除本镜头 (自动重排分镜编号)", color = Color(0xFFF87171), fontSize = 11.5.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
