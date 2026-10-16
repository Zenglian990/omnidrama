package com.omnidrama.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.RadioButtonUnchecked
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.omnidrama.app.data.model.SotaStatusResponse
import com.omnidrama.app.ui.theme.*

@Composable
fun SotaEngineDialog(
    sotaInfo: SotaStatusResponse,
    currentServerUrl: String,
    isSaving: Boolean = false,
    onSaveConfig: (serverUrl: String, apiKeys: Map<String, String>) -> Unit,
    onDismiss: () -> Unit
) {
    var serverUrl by remember { mutableStateOf(currentServerUrl) }
    val keyInputs = remember { mutableStateMapOf<String, String>() }

    val configuredCount = sotaInfo.providers.values.count { it.configured }
    val totalCount = sotaInfo.providers.size

    Dialog(onDismissRequest = onDismiss) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.90f)
                .clip(RoundedCornerShape(16.dp))
                .background(CardDark)
                .border(1.dp, BorderDark, RoundedCornerShape(16.dp))
                .padding(16.dp)
        ) {
            Column {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "真实 API 密钥与引擎配置中心",
                            color = TextPrimary,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "拒绝虚假状态 · 已配置 $configuredCount / $totalCount 项商业 Key",
                            color = if (configuredCount > 0) AccentEmerald else AccentGold,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    IconButton(onClick = onDismiss) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // 后端服务地址输入
                Text(
                    text = "后端算力机房地址 (FastAPI Engine):",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = serverUrl,
                    onValueChange = { serverUrl = it },
                    singleLine = true,
                    textStyle = LocalTextStyle.current.copy(fontSize = 12.sp, fontFamily = FontFamily.Monospace),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedButton(
                    onClick = { serverUrl = "https://omnidrama-79709693345.asia-east1.run.app" },
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text("⚡ 填入谷歌云官方制片机房 (asia-east1)", fontSize = 11.5.sp, color = BrandCyan)
                }

                Spacer(modifier = Modifier.height(10.dp))

                // 内置免费真实引擎提示卡
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(Color(0xFF062C24))
                        .border(0.8.dp, AccentEmerald.copy(alpha = 0.5f), RoundedCornerShape(8.dp))
                        .padding(8.dp)
                ) {
                    Column {
                        Text(
                            text = "✅ 内置免费引擎已真实激活：微软 Edge-TTS + FFmpeg 2.5D 运镜",
                            color = AccentEmerald,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "未填下方商业 Key 时，系统使用内置免费引擎真实生成语音与 MP4；填入真实 Key 保存后，立即切换为对应商业大模型！",
                            color = Color(0xFFA7F3D0),
                            fontSize = 9.5.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(sotaInfo.providers.values.toList()) { provider ->
                        val currentInput = keyInputs[provider.env_key] ?: ""
                        val isMarkedClear = currentInput == "__CLEAR__"
                        val effectivelyConfigured = provider.configured && !isMarkedClear

                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(10.dp))
                                .background(BgDark)
                                .border(
                                    width = 1.dp,
                                    color = if (effectivelyConfigured) AccentEmerald.copy(alpha = 0.6f) else BorderDark,
                                    shape = RoundedCornerShape(10.dp)
                                )
                                .padding(10.dp)
                        ) {
                            Column {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = provider.name,
                                        color = TextPrimary,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.weight(1f)
                                    )

                                    // 真实状态徽标 (绝不伪造)
                                    if (effectivelyConfigured) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Icon(
                                                imageVector = Icons.Default.CheckCircle,
                                                contentDescription = null,
                                                tint = AccentEmerald,
                                                modifier = Modifier.size(13.dp)
                                            )
                                            Spacer(modifier = Modifier.width(3.dp))
                                            Text(
                                                text = "已配置 (${provider.masked_key})",
                                                color = AccentEmerald,
                                                fontSize = 10.sp,
                                                fontWeight = FontWeight.Bold
                                            )
                                            Spacer(modifier = Modifier.width(6.dp))
                                            Text(
                                                text = "清除",
                                                color = Color(0xFFF87171),
                                                fontSize = 10.sp,
                                                fontWeight = FontWeight.Bold,
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(4.dp))
                                                    .background(Color(0xFF3B1219))
                                                    .clickable {
                                                        keyInputs[provider.env_key] = "__CLEAR__"
                                                    }
                                                    .padding(horizontal = 5.dp, vertical = 2.dp)
                                            )
                                        }
                                    } else {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Icon(
                                                imageVector = Icons.Default.RadioButtonUnchecked,
                                                contentDescription = null,
                                                tint = TextMuted,
                                                modifier = Modifier.size(12.dp)
                                            )
                                            Spacer(modifier = Modifier.width(3.dp))
                                            Text(
                                                text = if (isMarkedClear) "待清除 (点击保存生效)" else "未配置 Key",
                                                color = if (isMarkedClear) Color(0xFFF87171) else TextMuted,
                                                fontSize = 10.sp,
                                                fontWeight = FontWeight.Medium
                                            )
                                        }
                                    }
                                }

                                Spacer(modifier = Modifier.height(3.dp))
                                Text(
                                    text = "${provider.role} · 变量名: ${provider.env_key}",
                                    color = TextMuted,
                                    fontSize = 9.5.sp
                                )

                                Spacer(modifier = Modifier.height(6.dp))

                                // 真实 API Key 输入框
                                OutlinedTextField(
                                    value = if (isMarkedClear) "" else currentInput,
                                    onValueChange = { keyInputs[provider.env_key] = it },
                                    singleLine = true,
                                    placeholder = {
                                        Text(
                                            text = if (effectivelyConfigured) "已存密钥 ${provider.masked_key}，输入新 Key 可覆盖..."
                                            else "在此输入或粘贴真实 ${provider.env_key}...",
                                            color = TextMuted,
                                            fontSize = 10.5.sp
                                        )
                                    },
                                    leadingIcon = {
                                        Icon(
                                            imageVector = Icons.Default.Key,
                                            contentDescription = null,
                                            tint = if (currentInput.isNotBlank() && !isMarkedClear) AccentGold else TextMuted,
                                            modifier = Modifier.size(14.dp)
                                        )
                                    },
                                    textStyle = LocalTextStyle.current.copy(
                                        fontSize = 11.5.sp,
                                        fontFamily = FontFamily.Monospace
                                    ),
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedTextColor = TextPrimary,
                                        unfocusedTextColor = TextPrimary,
                                        focusedBorderColor = AccentGold,
                                        unfocusedBorderColor = BorderDark
                                    ),
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                Button(
                    onClick = {
                        val cleanKeys = keyInputs.filterValues { it.isNotBlank() }
                        onSaveConfig(serverUrl.trim(), cleanKeys)
                    },
                    enabled = !isSaving,
                    colors = ButtonDefaults.buttonColors(containerColor = BrandCyan),
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
                        Text("正在保存密钥至服务器...", color = BgDark, fontWeight = FontWeight.Bold)
                    } else {
                        Text(
                            text = "💾 保存真实 API 密钥并同步连接",
                            color = BgDark,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.ExtraBold
                        )
                    }
                }
            }
        }
    }
}
