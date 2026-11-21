package com.omnidrama.app.ui.components

import android.graphics.BitmapFactory
import android.widget.Toast
import androidx.compose.foundation.Image
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
import androidx.compose.material.icons.filled.*
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.omnidrama.app.data.local.CanonicalArchetypePreset
import com.omnidrama.app.data.local.LocalAndroidEngine
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ConsistencyCardItem
import com.omnidrama.app.data.model.VoiceItem
import com.omnidrama.app.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@Composable
fun CharacterEditDialog(
    initialCharacter: CharacterItem? = null,
    projectTitle: String = "",
    availableVoices: List<VoiceItem> = emptyList(),
    serverUrl: String = "",
    onSave: (CharacterItem) -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val isEdit = initialCharacter != null

    var name by remember { mutableStateOf(initialCharacter?.name ?: "") }
    var role by remember { mutableStateOf(initialCharacter?.role ?: "核心主角") }
    var selectedVoice by remember { mutableStateOf(initialCharacter?.voice ?: "云希 (磁性霸总男声)") }
    var traits by remember { mutableStateOf(initialCharacter?.traits ?: "") }
    var selectedArchetype by remember { mutableStateOf(initialCharacter?.archetype ?: "") }

    // 一致性控制卡字段
    val initialCard = initialCharacter?.safe_consistency_card ?: ConsistencyCardItem()
    var facialLock by remember { mutableStateOf(initialCard.facial_lock) }
    var hairLock by remember { mutableStateOf(initialCard.hair_lock) }
    var costumeLock by remember { mutableStateOf(initialCard.costume_lock) }
    var negativePrompt by remember { mutableStateOf(initialCard.exclusive_negative_prompt) }

    // 三视图字段
    var turnaroundPrompt by remember { mutableStateOf(initialCharacter?.turnaround_prompt ?: "") }
    var turnaroundImage by remember { mutableStateOf(initialCharacter?.turnaround_image ?: "") }
    var turnaroundBitmap by remember { mutableStateOf<ImageBitmap?>(null) }
    var isGeneratingTurnaround by remember { mutableStateOf(false) }

    var isConsistencyCardExpanded by remember { mutableStateOf(false) }
    var isPlayingVoice by remember { mutableStateOf(false) }

    // 初始化加载本地定妆照
    LaunchedEffect(turnaroundImage, name, projectTitle) {
        withContext(Dispatchers.IO) {
            if (turnaroundImage.isNotBlank()) {
                val f = File(turnaroundImage)
                if (f.exists() && f.length() > 100) {
                    val bmp = BitmapFactory.decodeFile(f.absolutePath)
                    if (bmp != null) {
                        turnaroundBitmap = bmp.asImageBitmap()
                        return@withContext
                    }
                }
            }
            if (name.isNotBlank()) {
                val localFile = LocalAndroidEngine.getLocalCharacterTurnaroundFile(context, projectTitle, name)
                if (localFile.exists() && localFile.length() > 100) {
                    val bmp = BitmapFactory.decodeFile(localFile.absolutePath)
                    if (bmp != null) {
                        turnaroundBitmap = bmp.asImageBitmap()
                    }
                }
            }
        }
    }

    val defaultVoices = if (availableVoices.isNotEmpty()) availableVoices else listOf(
        VoiceItem("云希 (磁性霸总男声)", "zh-CN-YunxiNeural", "男霸总/战神", "male"),
        VoiceItem("云健 (清冷孤傲男声)", "zh-CN-YunjianNeural", "世子/清冷权谋", "male"),
        VoiceItem("云扬 (热血青年男主)", "zh-CN-YunyangNeural", "少年修仙/逆袭", "male"),
        VoiceItem("晓晓 (知性独立女声)", "zh-CN-XiaoxiaoNeural", "都市丽人/大女主", "female"),
        VoiceItem("晓涵 (温柔清纯甜美)", "zh-CN-XiaohanNeural", "白月光/千金女二", "female"),
        VoiceItem("晓梦 (傲娇冷艳御姐)", "zh-CN-XiaomengNeural", "女总裁/反派贵妇", "female")
    )

    Dialog(onDismissRequest = onDismiss) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(CardDark)
                .border(1.dp, BorderDark, RoundedCornerShape(16.dp))
                .padding(18.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
            ) {
                // 弹窗头部
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = if (isEdit) "编辑角色资产与定妆" else "✨ 添加短剧角色资产",
                            color = TextPrimary,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "爆款母版 · 一致性控制卡 · 16:9 三视图定妆",
                            color = BrandCyan,
                            fontSize = 11.sp
                        )
                    }
                    IconButton(onClick = onDismiss) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = "Close", tint = TextSecondary)
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // ==================== 1. 爆款人设母版快速套用 ====================
                Text("🌟 快速套用爆款人设母版 (一键填充锁脸/声线/三视图):", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(6.dp))
                LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    items(LocalAndroidEngine.ARCHETYPE_PRESETS) { preset ->
                        val isSelected = selectedArchetype == preset.id || selectedArchetype == preset.code
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (isSelected) BrandCyan.copy(alpha = 0.2f) else BgDark)
                                .border(
                                    1.dp,
                                    if (isSelected) BrandCyan else BorderDark,
                                    RoundedCornerShape(8.dp)
                                )
                                .clickable {
                                    selectedArchetype = preset.id
                                    role = preset.defaultRole
                                    selectedVoice = preset.voiceDisplay
                                    traits = preset.traits
                                    facialLock = preset.consistencyCard.facial_lock
                                    hairLock = preset.consistencyCard.hair_lock
                                    costumeLock = preset.consistencyCard.costume_lock
                                    negativePrompt = preset.consistencyCard.exclusive_negative_prompt
                                    turnaroundPrompt = preset.turnaroundPrompt
                                    if (name.isBlank()) {
                                        name = preset.name.split("-").lastOrNull() ?: preset.name
                                    }
                                    Toast.makeText(context, "已套用母版【${preset.name}】", Toast.LENGTH_SHORT).show()
                                }
                                .padding(horizontal = 10.dp, vertical = 7.dp)
                        ) {
                            Column {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = Icons.Default.AutoAwesome,
                                        contentDescription = null,
                                        tint = if (isSelected) BrandCyan else AccentGold,
                                        modifier = Modifier.size(11.dp)
                                    )
                                    Spacer(modifier = Modifier.width(3.dp))
                                    Text(
                                        text = preset.name,
                                        color = if (isSelected) BrandCyan else TextPrimary,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                                Spacer(modifier = Modifier.height(2.dp))
                                Text(
                                    text = preset.voiceDisplay,
                                    color = if (isSelected) AccentGold else TextMuted,
                                    fontSize = 9.sp
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // ==================== 2. 基本属性 (姓名、定位) ====================
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("角色姓名:", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                        Spacer(modifier = Modifier.height(4.dp))
                        OutlinedTextField(
                            value = name,
                            onValueChange = { name = it },
                            placeholder = { Text("林清雪 / 萧天", color = TextMuted, fontSize = 11.sp) },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedBorderColor = BrandCyan,
                                unfocusedBorderColor = BorderDark
                            ),
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                    Column(modifier = Modifier.weight(1f)) {
                        Text("定位标签:", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                        Spacer(modifier = Modifier.height(4.dp))
                        OutlinedTextField(
                            value = role,
                            onValueChange = { role = it },
                            placeholder = { Text("女主角 / 霸总", color = TextMuted, fontSize = 11.sp) },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedBorderColor = BrandCyan,
                                unfocusedBorderColor = BorderDark
                            ),
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // ==================== 3. 声线音色选择与试听 ====================
                Text("专属配音音色母带:", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Medium)
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
                                .padding(horizontal = 8.dp, vertical = 5.dp)
                        ) {
                            Column {
                                Text(
                                    text = v.name,
                                    color = if (isSelected) BrandCyan else TextPrimary,
                                    fontSize = 10.sp,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                )
                                Text(
                                    text = v.tag,
                                    color = if (isSelected) AccentGold else TextMuted,
                                    fontSize = 8.sp
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "已选音色：${selectedVoice.substringBefore(" ")}",
                        color = AccentGold,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium
                    )

                    Button(
                        onClick = {
                            if (isPlayingVoice) {
                                LocalAndroidEngine.stopAllAudio()
                                isPlayingVoice = false
                            } else {
                                scope.launch {
                                    val sampleSentence = when {
                                        selectedVoice.contains("晓晓") -> "哼，凭你也配跟我平起平坐？别做梦了！"
                                        selectedVoice.contains("晓涵") -> "既然命运让我们相遇，我便绝不负你。"
                                        selectedVoice.contains("晓梦") -> "今天这件事，必须给我一个交代！"
                                        selectedVoice.contains("云健") -> "在江城，还没有人敢这么跟我说话！"
                                        selectedVoice.contains("云扬") -> "今日之辱，来日我必十倍奉还！"
                                        selectedVoice.contains("云浩") -> "老夫纵横一生，岂容小辈放肆！"
                                        else -> "天凉了，该让王氏集团彻底破产了。"
                                    }
                                    Toast.makeText(context, "🔊 正在试听【$selectedVoice】...", Toast.LENGTH_SHORT).show()
                                    LocalAndroidEngine.playVoiceSampleGuaranteed(
                                        context = context,
                                        serverUrl = serverUrl,
                                        voiceName = selectedVoice,
                                        sampleText = sampleSentence,
                                        onStart = { isPlayingVoice = true },
                                        onComplete = { isPlayingVoice = false }
                                    )
                                }
                            }
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (isPlayingVoice) Color(0xFFF59E0B) else Color(0xFF1E283D)
                        ),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier.height(26.dp)
                    ) {
                        Icon(
                            imageVector = if (isPlayingVoice) Icons.Default.Stop else Icons.Default.VolumeUp,
                            contentDescription = null,
                            tint = if (isPlayingVoice) Color.Black else AccentEmerald,
                            modifier = Modifier.size(12.dp)
                        )
                        Spacer(modifier = Modifier.width(3.dp))
                        Text(
                            text = if (isPlayingVoice) "停止试听" else "🔊 试听配音",
                            color = if (isPlayingVoice) Color.Black else Color.White,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 外貌视觉特征
                Text("外貌与视觉设定特征 (AI Visual Anchor):", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                Spacer(modifier = Modifier.height(4.dp))
                OutlinedTextField(
                    value = traits,
                    onValueChange = { traits = it },
                    placeholder = { Text("例如：鹅蛋骨相脸，清澈坚定的杏仁明眸，身着燕麦白西装", color = TextMuted, fontSize = 11.sp) },
                    maxLines = 2,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(12.dp))

                // ==================== 4. 角色物理一致性控制卡 (折叠展开) ====================
                val lockCount = listOf(facialLock, hairLock, costumeLock).count { it.isNotBlank() }
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .background(BgDark)
                        .border(1.dp, if (lockCount > 0) AccentEmerald.copy(alpha = 0.5f) else BorderDark, RoundedCornerShape(10.dp))
                        .clickable { isConsistencyCardExpanded = !isConsistencyCardExpanded }
                        .padding(horizontal = 12.dp, vertical = 9.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Lock,
                                contentDescription = null,
                                tint = if (lockCount > 0) AccentEmerald else TextSecondary,
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "🔒 角色物理一致性控制卡 (已锁定 $lockCount 项)",
                                color = if (lockCount > 0) AccentEmerald else TextPrimary,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        Icon(
                            imageVector = if (isConsistencyCardExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                            contentDescription = null,
                            tint = TextSecondary,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }

                if (isConsistencyCardExpanded) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color(0xFF0F1420))
                            .border(0.5.dp, BorderDark, RoundedCornerShape(8.dp))
                            .padding(10.dp)
                    ) {
                        Text("骨相五官锁 (Facial Bone Lock):", color = TextSecondary, fontSize = 10.sp)
                        Spacer(modifier = Modifier.height(2.dp))
                        OutlinedTextField(
                            value = facialLock,
                            onValueChange = { facialLock = it },
                            placeholder = { Text("亚洲鹅蛋脸型、下颌线轮廓、眼型、鼻梁等五官特征...", color = TextMuted, fontSize = 10.sp) },
                            maxLines = 2,
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedBorderColor = AccentEmerald,
                                unfocusedBorderColor = BorderDark
                            )
                        )

                        Spacer(modifier = Modifier.height(6.dp))

                        Text("发型发色锁 (Hair Lock):", color = TextSecondary, fontSize = 10.sp)
                        Spacer(modifier = Modifier.height(2.dp))
                        OutlinedTextField(
                            value = hairLock,
                            onValueChange = { hairLock = it },
                            placeholder = { Text("法式及肩微卷、深冷茶棕发色、发丝质感...", color = TextMuted, fontSize = 10.sp) },
                            maxLines = 2,
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedBorderColor = AccentEmerald,
                                unfocusedBorderColor = BorderDark
                            )
                        )

                        Spacer(modifier = Modifier.height(6.dp))

                        Text("服饰装束锁 (Costume Lock):", color = TextSecondary, fontSize = 10.sp)
                        Spacer(modifier = Modifier.height(2.dp))
                        OutlinedTextField(
                            value = costumeLock,
                            onValueChange = { costumeLock = it },
                            placeholder = { Text("定制燕麦白双排扣西装、香槟真丝吊带、配饰细节...", color = TextMuted, fontSize = 10.sp) },
                            maxLines = 2,
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedBorderColor = AccentEmerald,
                                unfocusedBorderColor = BorderDark
                            )
                        )

                        Spacer(modifier = Modifier.height(6.dp))

                        Text("专属防崩负向词 (Exclusive Negative):", color = TextSecondary, fontSize = 10.sp)
                        Spacer(modifier = Modifier.height(2.dp))
                        OutlinedTextField(
                            value = negativePrompt,
                            onValueChange = { negativePrompt = it },
                            placeholder = { Text("避免走形、幼态娃娃脸、劣质假睫毛、廉价反光面料...", color = TextMuted, fontSize = 10.sp) },
                            maxLines = 2,
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary,
                                focusedBorderColor = AccentEmerald,
                                unfocusedBorderColor = BorderDark
                            )
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                // ==================== 5. 16:9 角色三视图定妆预览与生成 ====================
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("📐 16:9 电影级三视图定妆 (Turnaround Sheet):", color = TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    Button(
                        onClick = {
                            if (name.isBlank()) {
                                Toast.makeText(context, "请先填写角色姓名", Toast.LENGTH_SHORT).show()
                                return@Button
                            }
                            scope.launch {
                                isGeneratingTurnaround = true
                                Toast.makeText(context, "🎨 正在生成【$name】16:9 三视图定妆...", Toast.LENGTH_SHORT).show()
                                val currentChar = CharacterItem(
                                    name = name.trim(),
                                    role = role.trim().ifEmpty { "核心主角" },
                                    voice = selectedVoice,
                                    avatar = turnaroundImage,
                                    traits = traits.trim(),
                                    archetype = selectedArchetype,
                                    turnaround_prompt = turnaroundPrompt.trim(),
                                    turnaround_image = turnaroundImage,
                                    consistency_card = ConsistencyCardItem(
                                        facial_lock = facialLock.trim(),
                                        hair_lock = hairLock.trim(),
                                        costume_lock = costumeLock.trim(),
                                        exclusive_negative_prompt = negativePrompt.trim()
                                    )
                                )
                                val res = LocalAndroidEngine.generateCharacterTurnaroundOnPhone(context, projectTitle, currentChar)
                                res.onSuccess { path ->
                                    turnaroundImage = path
                                    withContext(Dispatchers.IO) {
                                        val bmp = BitmapFactory.decodeFile(path)
                                        if (bmp != null) {
                                            turnaroundBitmap = bmp.asImageBitmap()
                                        }
                                    }
                                    Toast.makeText(context, "✨【$name】三视图定妆完成！", Toast.LENGTH_SHORT).show()
                                }.onFailure { err ->
                                    Toast.makeText(context, "生成失败: ${err.message}", Toast.LENGTH_SHORT).show()
                                }
                                isGeneratingTurnaround = false
                            }
                        },
                        enabled = !isGeneratingTurnaround && name.isNotBlank(),
                        colors = ButtonDefaults.buttonColors(containerColor = AccentEmerald),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
                        shape = RoundedCornerShape(6.dp),
                        modifier = Modifier.height(26.dp)
                    ) {
                        if (isGeneratingTurnaround) {
                            CircularProgressIndicator(color = Color.Black, modifier = Modifier.size(12.dp), strokeWidth = 1.5.dp)
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("生成中...", color = Color.Black, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        } else {
                            Icon(imageVector = Icons.Default.AutoAwesome, contentDescription = null, tint = Color.Black, modifier = Modifier.size(12.dp))
                            Spacer(modifier = Modifier.width(3.dp))
                            Text("🎨 生成三视图定妆", color = Color.Black, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(6.dp))

                // 16:9 预览画布容器
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(110.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(BgDark)
                        .border(1.dp, BorderDark, RoundedCornerShape(8.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    if (turnaroundBitmap != null) {
                        Image(
                            bitmap = turnaroundBitmap!!,
                            contentDescription = "三视图定妆预览",
                            modifier = Modifier.fillMaxSize(),
                            contentScale = ContentScale.Crop
                        )
                        Box(
                            modifier = Modifier
                                .align(Alignment.BottomEnd)
                                .background(Color(0xCC000000), RoundedCornerShape(topStart = 6.dp))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text("16:9 纯白底三视图已就绪", color = AccentEmerald, fontSize = 8.sp, fontWeight = FontWeight.Bold)
                        }
                    } else {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(imageVector = Icons.Default.Image, contentDescription = null, tint = TextMuted, modifier = Modifier.size(24.dp))
                            Spacer(modifier = Modifier.height(4.dp))
                            Text("尚未生成 16:9 正/侧/背纯白底三视图，点击上方【生成三视图定妆】触发", color = TextMuted, fontSize = 9.sp)
                        }
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                Text("三视图提示词 (Turnaround Prompt):", color = TextSecondary, fontSize = 10.sp)
                Spacer(modifier = Modifier.height(2.dp))
                OutlinedTextField(
                    value = turnaroundPrompt,
                    onValueChange = { turnaroundPrompt = it },
                    placeholder = { Text("自动由导演一致性引擎编译，或点击母版自动填入...", color = TextMuted, fontSize = 10.sp) },
                    maxLines = 2,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = BrandCyan,
                        unfocusedBorderColor = BorderDark
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(18.dp))

                // ==================== 底部操作按钮 ====================
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
                                        role = role.trim().ifEmpty { "核心主角" },
                                        voice = selectedVoice,
                                        avatar = initialCharacter?.avatar ?: "",
                                        traits = traits.trim().ifEmpty { "${name}，动漫影视级画风，特征鲜明" },
                                        visual_anchor = traits.trim(),
                                        archetype = selectedArchetype,
                                        turnaround_prompt = turnaroundPrompt.trim(),
                                        turnaround_image = turnaroundImage,
                                        consistency_card = ConsistencyCardItem(
                                            facial_lock = facialLock.trim(),
                                            hair_lock = hairLock.trim(),
                                            costume_lock = costumeLock.trim(),
                                            exclusive_negative_prompt = negativePrompt.trim()
                                        )
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
