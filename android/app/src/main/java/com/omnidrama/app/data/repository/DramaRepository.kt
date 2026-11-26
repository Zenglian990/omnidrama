package com.omnidrama.app.data.repository

import android.content.Context
import com.google.gson.Gson
import com.omnidrama.app.data.local.LocalAndroidEngine
import com.omnidrama.app.data.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class DramaRepository {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val orig = chain.request()
            val builder = orig.newBuilder()
                .addHeader("Bypass-Tunnel-Reminder", "true")
            val token = LocalAndroidEngine.activeServerAuthToken.trim()
            if (token.isNotEmpty() && orig.header("Authorization") == null) {
                builder.addHeader("Authorization", "Bearer $token")
            }
            chain.proceed(builder.build())
        }
        .build()

    /**
     * 校验云端服务器锁门密钥（API_AUTH_TOKEN），验证通过返回 true.
     */
    suspend fun verifyServerAuthToken(baseUrl: String, token: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val cleanUrl = baseUrl.trim().removeSuffix("/")
        if (cleanUrl.isBlank()) return@withContext Pair(false, "服务器地址为空")
        try {
            val payload = gson.toJson(mapOf("token" to token.trim()))
            val req = Request.Builder()
                .url("$cleanUrl/api/auth/session")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    return@withContext Pair(true, "鉴权校验通过")
                }
                val code = resp.code
                return@withContext Pair(false, if (code == 401) "访问密钥错误 (401)" else "服务器返回 HTTP $code")
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "无法连接云端: ${e.localizedMessage ?: "网络异常"}")
        }
    }

    /**
     * 实时测活单个 SOTA 模型 API Key（直连后端 /api/sota/test-key）.
     */
    suspend fun testSotaApiKey(baseUrl: String, envKey: String, apiKey: String = ""): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val cleanUrl = baseUrl.trim().removeSuffix("/")
        if (cleanUrl.isBlank()) return@withContext Pair(false, "未配置云端机房地址")
        try {
            val payload = gson.toJson(mapOf("env_key" to envKey, "api_key" to apiKey.trim()))
            val req = Request.Builder()
                .url("$cleanUrl/api/sota/test-key")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                val body = resp.body?.string() ?: ""
                if (resp.code == 401) {
                    return@withContext Pair(false, "未通过服务器鉴权 (401)，请先填写云端访问密钥")
                }
                if (body.trim().startsWith("{")) {
                    val obj = com.google.gson.JsonParser.parseString(body).asJsonObject
                    val ok = obj.get("ok")?.asBoolean == true
                    val msg = obj.get("message")?.asString ?: obj.get("detail")?.asString ?: if (ok) "密钥可用" else "测活失败"
                    return@withContext Pair(ok, msg)
                }
                return@withContext Pair(resp.isSuccessful, "HTTP ${resp.code}")
            }
        } catch (e: Exception) {
            return@withContext Pair(false, "测活请求异常: ${e.localizedMessage ?: "网络超时"}")
        }
    }

    /**
     * 一键出海译制（调用后端 /api/project/localize，支持 en/ja/ko/zh）.
     */
    suspend fun localizeProject(
        context: Context,
        baseUrl: String,
        targetLang: String
    ): Pair<ProjectData?, String> = withContext(Dispatchers.IO) {
        val cleanUrl = baseUrl.trim().removeSuffix("/")
        if (cleanUrl.isBlank()) return@withContext Pair(null, "请先配置并连接云端机房后再使用出海译制")
        try {
            val payload = gson.toJson(mapOf("target_lang" to targetLang, "auto_switch_voices" to true))
            val req = Request.Builder()
                .url("$cleanUrl/api/project/localize")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                val body = resp.body?.string() ?: ""
                if (resp.code == 401) {
                    return@withContext Pair(null, "服务器鉴权失败 (401)，请在设置中填写正确的云端访问密钥")
                }
                if (resp.isSuccessful) {
                    val updated = getProject(context, cleanUrl)
                    val msg = try {
                        val obj = com.google.gson.JsonParser.parseString(body).asJsonObject
                        obj.get("message")?.asString ?: "出海译制完成"
                    } catch (_: Exception) {
                        "出海译制完成"
                    }
                    return@withContext Pair(updated, msg)
                }
                val errDetail = try {
                    com.google.gson.JsonParser.parseString(body).asJsonObject.get("detail")?.asString
                } catch (_: Exception) {
                    null
                }
                return@withContext Pair(null, errDetail ?: "出海译制失败 (HTTP ${resp.code})")
            }
        } catch (e: Exception) {
            return@withContext Pair(null, "出海译制网络异常: ${e.localizedMessage ?: "连接超时"}")
        }
    }

    /**
     * 云端同步新增分镜（失败时返回 null 由调用方降级本地保存）.
     */
    suspend fun addShotOnServer(context: Context, baseUrl: String, shot: ShotItem): ProjectData? = withContext(Dispatchers.IO) {
        val cleanUrl = baseUrl.trim().removeSuffix("/")
        if (cleanUrl.isBlank()) return@withContext null
        try {
            val payload = gson.toJson(
                mapOf(
                    "speaker" to shot.speaker,
                    "dialogue" to shot.dialogue,
                    "visual_prompt" to shot.visual_prompt,
                    "motion" to shot.motion,
                    "scale" to shot.scale,
                    "sfx" to shot.sfx
                )
            )
            val req = Request.Builder()
                .url("$cleanUrl/api/shots")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    return@withContext getProject(context, cleanUrl)
                }
            }
        } catch (_: Exception) {
        }
        return@withContext null
    }

    /**
     * 云端同步删除分镜（防串镜、自动顺延磁盘资产编号）.
     */
    suspend fun deleteShotOnServer(context: Context, baseUrl: String, shotId: Int): ProjectData? = withContext(Dispatchers.IO) {
        val cleanUrl = baseUrl.trim().removeSuffix("/")
        if (cleanUrl.isBlank()) return@withContext null
        try {
            val req = Request.Builder()
                .url("$cleanUrl/api/shots/$shotId")
                .delete()
                .build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    return@withContext getProject(context, cleanUrl)
                }
            }
        } catch (_: Exception) {
        }
        return@withContext null
    }

    /**
     * 云端同步重排分镜顺序（三阶段同步对调磁盘图音视频，杜绝串镜）.
     */
    suspend fun reorderShotsOnServer(context: Context, baseUrl: String, orderedIds: List<Int>): ProjectData? = withContext(Dispatchers.IO) {
        val cleanUrl = baseUrl.trim().removeSuffix("/")
        if (cleanUrl.isBlank()) return@withContext null
        try {
            val payload = gson.toJson(mapOf("ordered_ids" to orderedIds))
            val req = Request.Builder()
                .url("$cleanUrl/api/shots/reorder")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    return@withContext getProject(context, cleanUrl)
                }
            }
        } catch (_: Exception) {
        }
        return@withContext null
    }

    private val gson = Gson()

    suspend fun getProject(context: Context, baseUrl: String): ProjectData = withContext(Dispatchers.IO) {
        val localCurrent = LocalAndroidEngine.getCurrentWork(context)
        val cleanUrl = baseUrl.trim().removeSuffix("/")
        if (cleanUrl.isNotBlank()) {
            try {
                val req = Request.Builder().url("$cleanUrl/api/project").build()
                client.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val body = resp.body?.string()
                        if (!body.isNullOrBlank() && body.trim().startsWith("{")) {
                            val remoteProj = gson.fromJson(body, ProjectData::class.java)
                            if (remoteProj != null && remoteProj.title.isNotBlank()) {
                                LocalAndroidEngine.saveCreatorWork(context, remoteProj)
                                return@withContext remoteProj
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }
        return@withContext localCurrent
    }

    suspend fun getSotaStatus(context: Context, baseUrl: String): SotaStatusResponse = withContext(Dispatchers.IO) {
        val localKeys = LocalAndroidEngine.getSavedApiKeys(context)
        val cleanUrl = baseUrl.trim().removeSuffix("/")
        if (cleanUrl.isNotBlank()) {
            try {
                val req = Request.Builder().url("$cleanUrl/api/sota/status").build()
                client.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val body = resp.body?.string()
                        if (!body.isNullOrBlank() && body.trim().startsWith("{") && body.contains("\"providers\"")) {
                            val remote = gson.fromJson(body, SotaStatusResponse::class.java)
                            if (remote != null && remote.providers.isNotEmpty()) {
                                val mergedProviders = remote.providers.mapValues { (_, item) ->
                                    val localVal = localKeys[item.env_key]
                                    if (!item.configured && !localVal.isNullOrBlank()) {
                                        item.copy(
                                            configured = true,
                                            masked_key = LocalAndroidEngine.maskKey(localVal)
                                        )
                                    } else {
                                        item
                                    }
                                }
                                return@withContext remote.copy(providers = mergedProviders)
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }
        return@withContext buildLocalSotaStatus(localKeys)
    }

    suspend fun saveApiKeys(context: Context, baseUrl: String, keys: Map<String, String>): Boolean = withContext(Dispatchers.IO) {
        // 1. 始终先保存到手机本地加密/持久化存储，确保即使未连接电脑机房也 100% 生效
        LocalAndroidEngine.saveApiKeysLocally(context, keys)

        // 2. 如果配置了远端机房地址，同步推送至远端
        if (baseUrl.isNotBlank()) {
            try {
                val payload = mapOf("keys" to keys)
                val json = gson.toJson(payload)
                val req = Request.Builder()
                    .url("$baseUrl/api/sota/save-keys")
                    .post(json.toRequestBody("application/json".toMediaType()))
                    .build()
                client.newCall(req).execute().use { resp ->
                    return@withContext resp.isSuccessful
                }
            } catch (_: Exception) {
            }
        }
        return@withContext true
    }

    suspend fun updateAndRegenerateShot(
        context: Context,
        baseUrl: String,
        title: String,
        genre: String,
        shotId: Int,
        speaker: String,
        dialogue: String,
        visualPrompt: String,
        motion: String,
        regenerateImage: Boolean,
        regenerateAudio: Boolean
    ): ProjectData = withContext(Dispatchers.IO) {
        val effectiveTitle = title.ifBlank { "我的短剧" }
        val effectiveGenre = genre.ifBlank { "热门爽剧" }
        val mVal = motion.uppercase()
        val mName = when {
            mVal.contains("SHAKE") -> "镜头震撼"
            mVal.contains("OUT") -> "镜头拉远"
            mVal.contains("PAN") -> "向左横移"
            else -> "镜头推进"
        }

        if (regenerateAudio) {
            LocalAndroidEngine.clearCachedShotAudio(context, shotId)
        }

        // 1. 先尝试远程机房更新
        if (baseUrl.isNotBlank()) {
            try {
                val payload = mapOf(
                    "speaker" to speaker,
                    "dialogue" to dialogue,
                    "visual_prompt" to visualPrompt,
                    "motion" to mVal,
                    "regenerate_image" to regenerateImage,
                    "regenerate_audio" to regenerateAudio
                )
                val json = gson.toJson(payload)
                val req = Request.Builder()
                    .url("${baseUrl.trimEnd('/')}/api/shots/$shotId")
                    .put(json.toRequestBody("application/json".toMediaType()))
                    .build()
                client.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        // 删除本地旧预览缓存，以便分镜卡片从远端拉取重绘后的新图
                        try {
                            LocalAndroidEngine.getLocalShotImageFile(context, effectiveTitle, shotId).delete()
                        } catch (_: Exception) {
                        }
                        val updated = getProject(context, baseUrl)
                        if (updated.title.isNotBlank()) {
                            return@withContext updated
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }

        // 2. 手机本地直接更新并重绘该镜头画面与字幕层
        val cur = LocalAndroidEngine.getCurrentWork(context)
        val newShots = cur.shots.map { s ->
            if (s.id == shotId) {
                val updatedShot = s.copy(
                    speaker = speaker,
                    dialogue = dialogue,
                    visual_prompt = visualPrompt,
                    motion = mVal,
                    motion_name = mName
                )
                val file = LocalAndroidEngine.generateShotImageOnPhone(
                    context = context,
                    title = effectiveTitle,
                    genre = effectiveGenre,
                    shot = updatedShot,
                    forceRegenerateBg = regenerateImage
                )
                updatedShot.copy(image = file.absolutePath)
            } else {
                s
            }
        }
        val updatedWork = cur.copy(shots = newShots)
        LocalAndroidEngine.saveCreatorWork(context, updatedWork)
        return@withContext updatedWork
    }

    suspend fun exportJianying(baseUrl: String): String = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder()
                .url("$baseUrl/api/export-jianying")
                .post("{}".toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    return@withContext "已成功导出剪映草稿工程！"
                }
            }
        } catch (_: Exception) {
        }
        return@withContext "当前为手机独立算力模式，请直接点击【📥 下载成片】保存 MP4 到手机相册后导入剪映 App"
    }

    suspend fun addCharacter(context: Context, baseUrl: String, character: CharacterItem): Boolean = withContext(Dispatchers.IO) {
        val cur = LocalAndroidEngine.getCurrentWork(context)
        if (cur.title.isNotBlank()) {
            val list = cur.characters.toMutableList()
            val idx = list.indexOfFirst { it.name == character.name }
            if (idx >= 0) list[idx] = character else list.add(character)
            LocalAndroidEngine.saveCreatorWork(context, cur.copy(characters = list))
        }
        try {
            val json = gson.toJson(character)
            val req = Request.Builder()
                .url("$baseUrl/api/characters")
                .post(json.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                return@withContext resp.isSuccessful
            }
        } catch (_: Exception) {
            return@withContext true
        }
    }

    suspend fun deleteCharacter(context: Context, baseUrl: String, name: String): Boolean = withContext(Dispatchers.IO) {
        val cur = LocalAndroidEngine.getCurrentWork(context)
        if (cur.title.isNotBlank()) {
            LocalAndroidEngine.saveCreatorWork(
                context,
                cur.copy(characters = cur.characters.filter { it.name != name })
            )
        }
        try {
            val encodedName = java.net.URLEncoder.encode(name, "UTF-8")
            val req = Request.Builder()
                .url("$baseUrl/api/characters/$encodedName")
                .delete()
                .build()
            client.newCall(req).execute().use { resp ->
                return@withContext resp.isSuccessful
            }
        } catch (_: Exception) {
            return@withContext true
        }
    }

    suspend fun generateScript(
        context: Context,
        baseUrl: String,
        title: String,
        genre: String,
        novelText: String
    ): ProjectData = withContext(Dispatchers.IO) {
        // 1. 尝试远端算力机房拆解
        if (baseUrl.isNotBlank()) {
            try {
                val payload = mapOf(
                    "title" to title,
                    "genre" to genre,
                    "novel_text" to novelText
                )
                val json = gson.toJson(payload)
                val req = Request.Builder()
                    .url("$baseUrl/api/project/generate")
                    .post(json.toRequestBody("application/json".toMediaType()))
                    .build()
                client.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val body = resp.body?.string()
                        if (!body.isNullOrBlank() && body.trim().startsWith("{")) {
                            val remoteWork = gson.fromJson(body, ProjectData::class.java)
                            if (remoteWork != null && remoteWork.title.isNotBlank()) {
                                LocalAndroidEngine.saveCreatorWork(context, remoteWork)
                                return@withContext remoteWork
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }

        // 2. 手机独立算力引擎直接拆解 (直连云端大模型 API 或智能分镜解析)
        return@withContext LocalAndroidEngine.breakdownStoryOnPhone(context, title, genre, novelText)
    }

    suspend fun triggerRender(context: Context, baseUrl: String, project: ProjectData): Boolean = withContext(Dispatchers.IO) {
        if (baseUrl.isBlank()) return@withContext false
        try {
            val localKeys = LocalAndroidEngine.getSavedApiKeys(context)
            val payload = mapOf(
                "title" to project.title,
                "genre" to project.genre,
                "shots" to project.shots,
                "characters" to project.characters,
                "api_keys" to localKeys
            )
            val json = gson.toJson(payload)
            val req = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/api/project/render")
                .post(json.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                val body = resp.body?.string() ?: ""
                return@withContext resp.isSuccessful && body.trim().startsWith("{")
            }
        } catch (_: Exception) {
            return@withContext false
        }
    }

    suspend fun triggerRender(context: Context, baseUrl: String, title: String, genre: String): Boolean =
        triggerRender(context, baseUrl, ProjectData(title = title, genre = genre))

    suspend fun triggerRender(baseUrl: String, project: ProjectData): Boolean = withContext(Dispatchers.IO) {
        if (baseUrl.isBlank()) return@withContext false
        try {
            val payload = mapOf(
                "title" to project.title,
                "genre" to project.genre,
                "shots" to project.shots,
                "characters" to project.characters
            )
            val json = gson.toJson(payload)
            val req = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/api/project/render")
                .post(json.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                val body = resp.body?.string() ?: ""
                return@withContext resp.isSuccessful && body.trim().startsWith("{")
            }
        } catch (_: Exception) {
            return@withContext false
        }
    }

    suspend fun getRenderStatus(baseUrl: String): RenderStatusResponse? = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/api/project/render-status").build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    val body = resp.body?.string()
                    if (!body.isNullOrBlank() && body.trim().startsWith("{")) {
                        return@withContext gson.fromJson(body, RenderStatusResponse::class.java)
                    }
                }
            }
        } catch (_: Exception) {
        }
        return@withContext null
    }

    suspend fun getVoices(baseUrl: String): List<VoiceItem> = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/api/voices").build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    val body = resp.body?.string()
                    if (!body.isNullOrBlank() && body.trim().startsWith("[")) {
                        val type = object : com.google.gson.reflect.TypeToken<List<VoiceItem>>() {}.type
                        return@withContext gson.fromJson(body, type)
                    }
                }
            }
        } catch (_: Exception) {
        }
        return@withContext listOf(
            VoiceItem("云希 (磁性沉稳霸道)", "zh-CN-YunxiNeural", "男霸总/战神", "male"),
            VoiceItem("云健 (嚣张跋扈反派)", "zh-CN-YunjianNeural", "纨绔恶少/挑衅", "male"),
            VoiceItem("云扬 (热血青年男主)", "zh-CN-YunyangNeural", "少年修仙/逆袭", "male"),
            VoiceItem("晓晓 (尖酸刻薄逼迫)", "zh-CN-XiaoxiaoNeural", "刁难反派/贵妇", "female"),
            VoiceItem("晓涵 (温柔清纯甜美)", "zh-CN-XiaohanNeural", "豪门千金/白月光", "female"),
            VoiceItem("晓梦 (傲娇泼辣独立)", "zh-CN-XiaomengNeural", "冷艳师姐/女总裁", "female")
        )
    }

    private fun buildLocalSotaStatus(localKeys: Map<String, String>): SotaStatusResponse {
        fun entry(name: String, role: String, envKey: String, tier: String): ProviderItem {
            val v = localKeys[envKey]?.trim() ?: ""
            return ProviderItem(
                name = name,
                role = role,
                env_key = envKey,
                configured = v.isNotEmpty(),
                masked_key = LocalAndroidEngine.maskKey(v),
                tier = tier
            )
        }

        val providers = mapOf(
            "colab_cluster" to entry("⚡ Google Colab 三号联开 48GB 算力池", "1号机 Qwen3.8-27B 破甲导演 + 2号机 Qwen-Image 4K 生图 + 3号机 Breeze-TTS/Whisper (输入 4/0A... 授权码即可激活)", "COLAB_CLUSTER_TOKEN", "免费 3×T4 (48GB VRAM)"),
            "siliconflow" to entry("🔥 硅基流动 SiliconFlow (国内免绑卡首选)", "手机直连：免费 FLUX.1 逐镜生图 + DeepSeek/Qwen 导演拆解 + CosyVoice 配音", "SILICONFLOW_API_KEY", "国内免费生图+导演"),
            "dashscope" to entry("🌟 阿里云百炼 DashScope (通义万相2.1 + Qwen配音)", "新用户送百万Token+百张免费生图：Wan2.1 竖屏短剧剧照 + 超拟真配音", "DASHSCOPE_API_KEY", "国内大厂顶配 (推荐)"),
            "seedance" to entry("🎬 字节火山方舟 Seedance 2.0 (豆包视频大模型)", "50万免费Token体验：图生视频 I2V 电影级物理运镜与人物微表情", "ARK_API_KEY", "SOTA 动态视频"),
            "deepseek" to entry("DeepSeek-V3 / R1 (深度求索官方)", "手机直连：好莱坞编剧与分镜剧本拆解总导演", "DEEPSEEK_API_KEY", "主力导演 (国内直连)"),
            "pexels" to entry("Pexels 免费高清视频/图片素材库", "手机直连：0元免绑卡自动匹配下载 9:16 竖屏高清实拍剧照", "PEXELS_API_KEY", "免费高清素材"),
            "kimi" to entry("Kimi (月之暗面 Moonshot AI)", "手机直连：长篇网文理解、剧本台词打磨与镜头关键词提炼", "MOONSHOT_API_KEY", "国内直连 (SOTA)"),
            "gemini" to entry("Google Gemini 2.0 Flash", "多模态剧本拆解与分镜视觉提示词引擎", "GEMINI_API_KEY", "高速导演"),
            "image" to entry("FLUX.1 Pro (Black Forest Labs)", "8K 胶片级定妆与分镜剧照生图 (海外官方)", "BFL_API_KEY", "行业顶级 (SOTA)"),
            "voice" to entry("ElevenLabs Multilingual v2", "人类级呼吸感情绪配音 (未配则用内置中文语音合成)", "ELEVENLABS_API_KEY", "行业顶级 (SOTA)")
        )
        return SotaStatusResponse(
            system = SystemStatus("未连接远程电脑机房 (已启用手机本地独立算力引擎)", true, false, ""),
            providers = providers
        )
    }

    suspend fun optimizeAndAuditProject(
        context: Context,
        baseUrl: String,
        project: ProjectData
    ): ProjectData = withContext(Dispatchers.IO) {
        if (baseUrl.isNotBlank()) {
            try {
                val payload = mapOf("auto_fix" to true, "budget_limit_usd" to 2.0)
                val req = Request.Builder()
                    .url("${baseUrl.trimEnd('/')}/api/project/quality-check")
                    .post(gson.toJson(payload).toRequestBody("application/json".toMediaType()))
                    .build()
                client.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val updated = getProject(context, baseUrl)
                        if (updated.title.isNotBlank()) {
                            return@withContext updated
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }
        val optimized = LocalAndroidEngine.scoreAndOptimizeStoryboardOnPhone(project)
        LocalAndroidEngine.saveCreatorWork(context, optimized)
        return@withContext optimized
    }

    suspend fun analyzeAndAdaptReference(
        context: Context,
        baseUrl: String,
        title: String,
        genre: String,
        novelText: String
    ): ProjectData = withContext(Dispatchers.IO) {
        if (baseUrl.isNotBlank()) {
            try {
                val payload = mapOf(
                    "video_source" to "",
                    "title" to title,
                    "novel_text" to novelText,
                    "adapt_and_save" to true
                )
                val req = Request.Builder()
                    .url("${baseUrl.trimEnd('/')}/api/project/analyze-reference")
                    .post(gson.toJson(payload).toRequestBody("application/json".toMediaType()))
                    .build()
                client.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val updated = getProject(context, baseUrl)
                        if (updated.title.isNotBlank()) {
                            return@withContext updated
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }
        return@withContext LocalAndroidEngine.adaptReferenceRhythmOnPhone(context, title, genre, novelText)
    }
}

