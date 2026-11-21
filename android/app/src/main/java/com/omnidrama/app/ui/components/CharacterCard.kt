package com.omnidrama.app.ui.components

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.omnidrama.app.data.local.LocalAndroidEngine
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

@Composable
fun CharacterCard(
    character: CharacterItem,
    projectTitle: String = "",
    serverUrl: String = "",
    modifier: Modifier = Modifier,
    onEdit: () -> Unit = {},
    onDelete: () -> Unit = {},
    onViewTurnaround: ((CharacterItem) -> Unit)? = null
) {
    val context = LocalContext.current
    var turnaroundBitmap by remember { mutableStateOf<ImageBitmap?>(null) }

    // 加载角色 16:9 三视图定妆照缓存
    LaunchedEffect(character.name, character.turnaround_image, projectTitle) {
        withContext(Dispatchers.IO) {
            if (character.turnaround_image.isNotBlank()) {
                val f = File(character.turnaround_image)
                if (f.exists() && f.length() > 100) {
                    val bmp = BitmapFactory.decodeFile(f.absolutePath)
                    if (bmp != null) {
                        turnaroundBitmap = bmp.asImageBitmap()
                        return@withContext
                    }
                }
            }
            val localFile = LocalAndroidEngine.getLocalCharacterTurnaroundFile(context, projectTitle, character.name)
            if (localFile.exists() && localFile.length() > 100) {
                val bmp = BitmapFactory.decodeFile(localFile.absolutePath)
                if (bmp != null) {
                    turnaroundBitmap = bmp.asImageBitmap()
                }
            }
        }
    }

    val archetypeBadgeText = when (character.archetype) {
        "04_modern_female_urban", "04" -> "都市丽人"
        "05_modern_male_boss", "05" -> "霸总"
        "06_ancient_male_noble", "06" -> "清冷世子"
        "08_antagonist_female_greentea", "08" -> "绿茶千金"
        else -> if (character.archetype.isNotBlank()) {
            character.archetype.substringAfter("-").ifEmpty { character.archetype }
        } else null
    }

    val card = character.safe_consistency_card
    val hasFaceLock = card.facial_lock.isNotBlank()
    val hasHairLock = card.hair_lock.isNotBlank()
    val hasCostumeLock = card.costume_lock.isNotBlank()
    val hasAnyLock = hasFaceLock || hasHairLock || hasCostumeLock

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(CardDark)
            .border(1.dp, BorderDark, RoundedCornerShape(12.dp))
            .padding(12.dp)
    ) {
        Column {
            Row(verticalAlignment = Alignment.Top) {
                // 角色头像基座
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(BorderDark)
                        .border(1.dp, BrandCyan, CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Person,
                        contentDescription = null,
                        tint = BrandCyan,
                        modifier = Modifier.size(24.dp)
                    )
                }

                Spacer(modifier = Modifier.width(12.dp))

                Column(modifier = Modifier.weight(1f)) {
                    // 姓名 + 角色定位 + 母版 Badge + 操作按钮
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.weight(1f, fill = false)
                        ) {
                            Text(
                                text = character.name,
                                color = TextPrimary,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            // 身份定位 Badge
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(BorderDark)
                                    .padding(horizontal = 5.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = character.role,
                                    color = AccentGold,
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                            // 爆款人设母版 Chip
                            if (archetypeBadgeText != null) {
                                Spacer(modifier = Modifier.width(5.dp))
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(BrandPurple.copy(alpha = 0.2f))
                                        .border(1.dp, BrandPurple.copy(alpha = 0.6f), RoundedCornerShape(4.dp))
                                        .padding(horizontal = 5.dp, vertical = 2.dp)
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(
                                            imageVector = Icons.Default.AutoAwesome,
                                            contentDescription = null,
                                            tint = BrandCyan,
                                            modifier = Modifier.size(10.dp)
                                        )
                                        Spacer(modifier = Modifier.width(2.dp))
                                        Text(
                                            text = archetypeBadgeText,
                                            color = Color(0xFFC084FC),
                                            fontSize = 9.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                }
                            }
                        }

                        Row(verticalAlignment = Alignment.CenterVertically) {
                            IconButton(onClick = onEdit, modifier = Modifier.size(24.dp)) {
                                Icon(imageVector = Icons.Default.Edit, contentDescription = "Edit", tint = BrandCyan, modifier = Modifier.size(14.dp))
                            }
                            IconButton(onClick = onDelete, modifier = Modifier.size(24.dp)) {
                                Icon(imageVector = Icons.Default.DeleteOutline, contentDescription = "Delete", tint = AccentRose, modifier = Modifier.size(14.dp))
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    // 配音声线
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Mic,
                            contentDescription = null,
                            tint = BrandCyan,
                            modifier = Modifier.size(12.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = character.voice,
                            color = BrandCyan,
                            fontSize = 11.sp
                        )
                    }

                    Spacer(modifier = Modifier.height(4.dp))

                    // 一致性特征锁指示标签 (五官锁 / 发型锁 / 服饰锁)
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        if (hasFaceLock) LockIndicatorBadge(label = "五官锁", icon = Icons.Default.Face)
                        if (hasHairLock) LockIndicatorBadge(label = "发型锁", icon = Icons.Default.Lock)
                        if (hasCostumeLock) LockIndicatorBadge(label = "服饰锁", icon = Icons.Default.Checkroom)
                        if (!hasAnyLock) {
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(3.dp))
                                    .background(BorderDark)
                                    .padding(horizontal = 4.dp, vertical = 1.dp)
                            ) {
                                Text(text = "未配置特征锁", color = TextMuted, fontSize = 9.sp)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(6.dp))

                    // 外貌特征描述
                    Text(
                        text = character.traits,
                        color = TextSecondary,
                        fontSize = 11.sp,
                        lineHeight = 15.sp,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            // 16:9 三视图定妆照预览层
            if (turnaroundBitmap != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(88.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .border(1.dp, BorderDark, RoundedCornerShape(8.dp))
                        .clickable { onViewTurnaround?.invoke(character) }
                ) {
                    Image(
                        bitmap = turnaroundBitmap!!,
                        contentDescription = "三视图定妆照",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop
                    )
                    Box(
                        modifier = Modifier
                            .align(Alignment.BottomEnd)
                            .background(Color(0xCC080A0F), RoundedCornerShape(topStart = 6.dp))
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Visibility,
                                contentDescription = null,
                                tint = BrandCyan,
                                modifier = Modifier.size(10.dp)
                            )
                            Spacer(modifier = Modifier.width(3.dp))
                            Text("16:9 三视图定妆", color = BrandCyan, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            } else if (character.turnaround_prompt.isNotBlank()) {
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(6.dp))
                        .background(CardDark)
                        .border(0.5.dp, BorderDark, RoundedCornerShape(6.dp))
                        .clickable { onEdit() }
                        .padding(horizontal = 8.dp, vertical = 5.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(imageVector = Icons.Default.AutoAwesome, contentDescription = null, tint = AccentGold, modifier = Modifier.size(11.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(text = "三视图Prompt已就绪", color = TextSecondary, fontSize = 10.sp)
                    }
                    Text(text = "点击定妆 ➔", color = BrandCyan, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun LockIndicatorBadge(label: String, icon: ImageVector) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(3.dp))
            .background(AccentEmerald.copy(alpha = 0.12f))
            .border(0.5.dp, AccentEmerald.copy(alpha = 0.5f), RoundedCornerShape(3.dp))
            .padding(horizontal = 4.dp, vertical = 1.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(imageVector = icon, contentDescription = null, tint = AccentEmerald, modifier = Modifier.size(9.dp))
            Spacer(modifier = Modifier.width(2.dp))
            Text(text = label, color = AccentEmerald, fontSize = 9.sp, fontWeight = FontWeight.Medium)
        }
    }
}
