package com.omnidrama.app.data.local

import android.content.Context
import android.graphics.*
import android.media.*
import android.os.Bundle
import android.os.Environment
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import com.google.gson.Gson
import com.google.gson.JsonParser
import com.google.gson.reflect.TypeToken
import com.omnidrama.app.data.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.util.Locale
import java.util.concurrent.TimeUnit
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

object LocalAndroidEngine {
    private const val PREFS_NAME = "omnidrama_creator_v16"
    private const val KEY_WORKS_LIST = "creator_works_json"
    private const val KEY_CURRENT_TITLE = "current_work_title"
    private const val KEY_API_KEYS_MAP = "saved_api_keys_json"

    // 严禁预留任何假小说名字：启动时若发现旧版本遗留的预设剧名则自动清理
    private val BANNED_PRESET_TITLES = setOf(
        "至尊龙王归位",
        "真千金归来杀疯豪门",
        "修仙万载重回都市",
        "九天太古剑尊",
        "重生1990商业帝国"
    )

    private val gson = Gson()

    val directHttpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(45, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val req = chain.request().newBuilder()
                .addHeader("Bypass-Tunnel-Reminder", "true")
                .addHeader(
                    "User-Agent",
                    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
                )
                .build()
            chain.proceed(req)
        }
        .build()

    // ===================== 1. 创作者个人作品库管理 (0 预设小说) =====================

    fun getCreatorWorks(context: Context): List<ProjectData> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_WORKS_LIST, null) ?: return emptyList()
        return try {
            val type = object : TypeToken<List<ProjectData>>() {}.type
            val list: List<ProjectData> = gson.fromJson(raw, type) ?: emptyList()
            list.filter { it.title.isNotBlank() && it.title !in BANNED_PRESET_TITLES }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun saveCreatorWork(context: Context, work: ProjectData) {
        if (work.title.isBlank()) return
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val current = getCreatorWorks(context).toMutableList()
        val idx = current.indexOfFirst { it.title == work.title }
        if (idx >= 0) {
            current[idx] = work
        } else {
            current.add(0, work)
        }
        prefs.edit()
            .putString(KEY_WORKS_LIST, gson.toJson(current))
            .putString(KEY_CURRENT_TITLE, work.title)
            .apply()
    }

    fun deleteCreatorWork(context: Context, title: String): List<ProjectData> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val updated = getCreatorWorks(context).filter { it.title != title }
        val nextTitle = updated.firstOrNull()?.title ?: ""
        prefs.edit()
            .putString(KEY_WORKS_LIST, gson.toJson(updated))
            .putString(KEY_CURRENT_TITLE, nextTitle)
            .apply()
        return updated
    }

    fun getCurrentWork(context: Context): ProjectData {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val works = getCreatorWorks(context)
        if (works.isEmpty()) return ProjectData()
        val curTitle = prefs.getString(KEY_CURRENT_TITLE, "") ?: ""
        return works.find { it.title == curTitle } ?: works.first()
    }

    fun setCurrentWorkTitle(context: Context, title: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_CURRENT_TITLE, title).apply()
    }

    // ===================== 2. 本地真实 API Key 持久化存储 =====================

    fun getSavedApiKeys(context: Context): MutableMap<String, String> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_API_KEYS_MAP, null) ?: return mutableMapOf()
        return try {
            val type = object : TypeToken<MutableMap<String, String>>() {}.type
            gson.fromJson(raw, type) ?: mutableMapOf()
        } catch (_: Exception) {
            mutableMapOf()
        }
    }

    fun saveApiKeysLocally(context: Context, newKeys: Map<String, String>) {
        val current = getSavedApiKeys(context)
        for ((k, v) in newKeys) {
            val cleanV = v.trim()
            if (cleanV == "__CLEAR__") {
                current.remove(k)
            } else if (cleanV.isNotEmpty()) {
                current[k] = cleanV
            }
        }
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_API_KEYS_MAP, gson.toJson(current)).apply()
    }

    fun maskKey(raw: String?): String {
        val v = (raw ?: "").trim()
        if (v.isEmpty()) return ""
        if (v.length <= 8) return v.take(2) + "****"
        return "${v.take(4)}****${v.takeLast(4)}"
    }

    // ===================== 3. 100% 真实配音试听引擎 (解决图一无法试听问题) =====================

    private var ttsInstance: TextToSpeech? = null
    private var ttsReady = false
    private var activeMediaPlayer: MediaPlayer? = null

    fun ensureTtsInitialized(context: Context, onReady: (() -> Unit)? = null) {
        if (ttsInstance != null && ttsReady) {
            onReady?.invoke()
            return
        }
        ttsInstance = TextToSpeech(context.applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val res = ttsInstance?.setLanguage(Locale.SIMPLIFIED_CHINESE)
                if (res == TextToSpeech.LANG_MISSING_DATA || res == TextToSpeech.LANG_NOT_SUPPORTED) {
                    ttsInstance?.setLanguage(Locale.CHINESE)
                }
                ttsReady = true
                onReady?.invoke()
            }
        }
    }

    fun stopAllAudio() {
        try {
            activeMediaPlayer?.stop()
            activeMediaPlayer?.release()
        } catch (_: Exception) {
        }
        activeMediaPlayer = null
        try {
            ttsInstance?.stop()
        } catch (_: Exception) {
        }
    }

    private fun applyVoiceCharacteristics(speaker: String) {
        val tts = ttsInstance ?: return
        when {
            speaker.contains("女") || speaker.contains("姐") || speaker.contains("母") ||
                speaker.contains("妻") || speaker.contains("雪") || speaker.contains("薇") ||
                speaker.contains("妃") -> {
                tts.setPitch(1.22f)
                tts.setSpeechRate(1.05f)
            }
            speaker.contains("旁白") -> {
                tts.setPitch(0.95f)
                tts.setSpeechRate(1.02f)
            }
            speaker.contains("老") || speaker.contains("爷") || speaker.contains("长") -> {
                tts.setPitch(0.75f)
                tts.setSpeechRate(0.92f)
            }
            else -> {
                // 男主 / 霸总 / 战神
                tts.setPitch(0.84f)
                tts.setSpeechRate(1.0f)
            }
        }
    }

    suspend fun playShotAudioGuaranteed(
        context: Context,
        serverUrl: String,
        shot: ShotItem,
        onStart: () -> Unit,
        onComplete: () -> Unit
    ) {
        stopAllAudio()

        // 1. 先检查本地是否已有合成好的音频文件
        val localDir = File(context.filesDir, "shot_audio")
        localDir.mkdirs()
        val cachedMp3 = File(localDir, "shot_${shot.id}_${shot.dialogue.hashCode()}.mp3")

        // 2. 如果配置了硅基流动 Key，优先尝试直接调用 SiliconFlow 真实语音合成接口 (CosyVoice2)
        val keys = getSavedApiKeys(context)
        val sfKey = keys["SILICONFLOW_API_KEY"] ?: ""
        if (!cachedMp3.exists() && sfKey.isNotBlank()) {
            withContext(Dispatchers.IO) {
                try {
                    val payload = mapOf(
                        "model" to "FunAudioLLM/CosyVoice2-0.5B",
                        "input" to shot.dialogue,
                        "voice" to "FunAudioLLM/CosyVoice2-0.5B:alex",
                        "response_format" to "mp3"
                    )
                    val req = Request.Builder()
                        .url("https://api.siliconflow.cn/v1/audio/speech")
                        .addHeader("Authorization", "Bearer $sfKey")
                        .post(gson.toJson(payload).toRequestBody("application/json".toMediaType()))
                        .build()
                    directHttpClient.newCall(req).execute().use { resp ->
                        if (resp.isSuccessful) {
                            val bytes = resp.body?.bytes()
                            if (bytes != null && bytes.size > 200) {
                                cachedMp3.writeBytes(bytes)
                            }
                        }
                    }
                } catch (_: Exception) {
                }
            }
        }

        // 3. 尝试从远端算力机房实时拉取 Edge-TTS 音频 (限时 3.5 秒，绝不卡死)
        if (!cachedMp3.exists() && serverUrl.isNotBlank()) {
            withContext(Dispatchers.IO) {
                try {
                    val fastClient = directHttpClient.newBuilder()
                        .connectTimeout(3, TimeUnit.SECONDS)
                        .readTimeout(5, TimeUnit.SECONDS)
                        .build()
                    val encText = java.net.URLEncoder.encode(shot.dialogue, "UTF-8")
                    val encSpeaker = java.net.URLEncoder.encode(shot.speaker, "UTF-8")
                    val url = "$serverUrl/api/shots/${shot.id}/audio?text=$encText&speaker=$encSpeaker"
                    val req = Request.Builder().url(url).build()
                    fastClient.newCall(req).execute().use { resp ->
                        if (resp.isSuccessful && resp.header("Content-Type")?.contains("audio") == true) {
                            val bytes = resp.body?.bytes()
                            if (bytes != null && bytes.size > 200) {
                                cachedMp3.writeBytes(bytes)
                            }
                        }
                    }
                } catch (_: Exception) {
                }
            }
        }

        // 4. 若成功获取到 MP3 音频文件，使用 MediaPlayer 播放
        if (cachedMp3.exists() && cachedMp3.length() > 200) {
            try {
                val mp = MediaPlayer().apply {
                    setAudioAttributes(
                        AudioAttributes.Builder()
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .setUsage(AudioAttributes.USAGE_MEDIA)
                            .build()
                    )
                    setDataSource(cachedMp3.absolutePath)
                    setOnPreparedListener {
                        onStart()
                        start()
                    }
                    setOnCompletionListener {
                        onComplete()
                        release()
                        activeMediaPlayer = null
                    }
                    setOnErrorListener { _, _, _ ->
                        release()
                        activeMediaPlayer = null
                        speakWithSystemTts(context, shot.speaker, shot.dialogue, onStart, onComplete)
                        true
                    }
                    prepareAsync()
                }
                activeMediaPlayer = mp
                return
            } catch (_: Exception) {
            }
        }

        // 5. 保底直连：调用手机系统原生中文语音合成引擎 (Android TextToSpeech)，100% 必响！
        speakWithSystemTts(context, shot.speaker, shot.dialogue, onStart, onComplete)
    }

    private fun speakWithSystemTts(
        context: Context,
        speaker: String,
        dialogue: String,
        onStart: () -> Unit,
        onComplete: () -> Unit
    ) {
        ensureTtsInitialized(context) {
            val tts = ttsInstance ?: return@ensureTtsInitialized
            applyVoiceCharacteristics(speaker)
            val utteranceId = "utt_${System.currentTimeMillis()}"
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(id: String?) {
                    onStart()
                }

                override fun onDone(id: String?) {
                    onComplete()
                }

                @Deprecated("Deprecated in Java")
                override fun onError(id: String?) {
                    onComplete()
                }
            })
            onStart()
            tts.speak(dialogue, TextToSpeech.QUEUE_FLUSH, Bundle(), utteranceId)
        }
    }

    // ===================== 4. 番茄小说 (fanqienovel.com) 手机端直连抓取与链接解析 =====================

    suspend fun fetchFanqieRankDirectly(serverUrl: String = ""): List<FanqieBookItem> = withContext(Dispatchers.IO) {
        // 先尝试通过后端拉取（若后端在线）
        if (serverUrl.isNotBlank()) {
            try {
                val fast = directHttpClient.newBuilder().connectTimeout(3, TimeUnit.SECONDS).readTimeout(8, TimeUnit.SECONDS).build()
                val req = Request.Builder().url("$serverUrl/api/fanqie/rank?limit=6").build()
                fast.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val body = resp.body?.string()
                        if (!body.isNullOrBlank() && body.trim().startsWith("{")) {
                            val root = JsonParser.parseString(body).asJsonObject
                            val arr = root.getAsJsonArray("books")
                            if (arr != null && arr.size() > 0) {
                                val type = object : TypeToken<List<FanqieBookItem>>() {}.type
                                return@withContext gson.fromJson(arr, type)
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }

        // 手机端直接请求 https://fanqienovel.com/rank 抓取实时热榜
        val results = mutableListOf<FanqieBookItem>()
        try {
            val req = Request.Builder().url("https://fanqienovel.com/rank").build()
            val html = directHttpClient.newCall(req).execute().use { it.body?.string() ?: "" }
            val idRegex = Regex("/page/(\\d{15,22})")
            val bookIds = idRegex.findAll(html).map { it.groupValues[1] }.distinct().take(6).toList()
            for (bid in bookIds) {
                val book = fetchFanqieBookByIdDirectly(bid)
                if (book != null && book.title.isNotBlank()) {
                    results.add(book)
                }
            }
        } catch (_: Exception) {
        }
        return@withContext results
    }

    suspend fun importFanqieUrlDirectly(urlOrId: String, serverUrl: String = ""): FanqieBookItem? = withContext(Dispatchers.IO) {
        val text = urlOrId.trim()
        val pageMatch = Regex("/page/(\\d{15,22})").find(text)
        if (pageMatch != null) {
            return@withContext fetchFanqieBookByIdDirectly(pageMatch.groupValues[1])
        }
        val readerMatch = Regex("/reader/(\\d{15,22})").find(text)
        if (readerMatch != null) {
            return@withContext fetchFanqieChapterDirectly(readerMatch.groupValues[1])
        }
        val rawIdMatch = Regex("\\b(\\d{15,22})\\b").find(text)
        if (rawIdMatch != null) {
            return@withContext fetchFanqieBookByIdDirectly(rawIdMatch.groupValues[1])
        }
        return@withContext null
    }

    private fun stripHtmlTags(html: String): String {
        return html
            .replace(Regex("<script[^>]*>[\\s\\S]*?</script>"), "")
            .replace(Regex("<style[^>]*>[\\s\\S]*?</style>"), "")
            .replace(Regex("</p>|</div>|<br\\s*/?>"), "\n")
            .replace(Regex("<[^>]+>"), "")
            .replace(Regex("[\\uE000-\\uF8FF]"), "")
            .replace("&nbsp;", " ")
            .replace("&quot;", "\"")
            .replace("&amp;", "&")
            .lines()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .joinToString("\n")
    }

    private fun fetchFanqieBookByIdDirectly(bookId: String): FanqieBookItem? {
        return try {
            val url = "https://fanqienovel.com/page/$bookId"
            val req = Request.Builder().url(url).build()
            val html = directHttpClient.newCall(req).execute().use { it.body?.string() ?: "" }
            if (html.isBlank()) return null

            val title = stripHtmlTags(Regex("<h1[^>]*>([^<]+)</h1>").find(html)?.groupValues?.get(1) ?: "")
            val author = stripHtmlTags(Regex("class=\"author-name-text\"[^>]*>([^<]+)<").find(html)?.groupValues?.get(1) ?: "番茄作者")
            val labels = Regex("class=\"info-label-[^\"]*\"[^>]*>([^<]+)<")
                .findAll(html)
                .map { stripHtmlTags(it.groupValues[1]) }
                .filter { it.isNotEmpty() }
                .toList()
            val genre = if (labels.isNotEmpty()) labels.take(3).joinToString(" · ") else "番茄热门连载"

            val abstractBlock = Regex("class=\"page-abstract-content\"[^>]*>([\\s\\S]*?)</div>").find(html)?.groupValues?.get(1) ?: ""
            val abstractText = stripHtmlTags(abstractBlock)

            val chapTitles = Regex("class=\"chapter-item\"[\\s\\S]*?href=\"/reader/\\d+\"[^>]*>([^<]+)</a>")
                .findAll(html)
                .map { stripHtmlTags(it.groupValues[1]) }
                .filter { it.isNotEmpty() }
                .take(6)
                .toList()
            val firstChapTitle = chapTitles.firstOrNull() ?: "第1章"

            val fullStory = buildString {
                if (abstractText.isNotBlank()) {
                    append("【作品核心剧情】\n").append(abstractText)
                }
                if (chapTitles.isNotEmpty()) {
                    append("\n\n【开篇主线脉络】\n").append(chapTitles.joinToString(" -> "))
                }
            }.trim()

            FanqieBookItem(
                book_id = bookId,
                title = title,
                author = author,
                genre = genre,
                abstract = abstractText,
                first_chapter_title = firstChapTitle,
                story_text = if (fullStory.isNotBlank()) fullStory else abstractText,
                url = url
            )
        } catch (_: Exception) {
            null
        }
    }

    private fun fetchFanqieChapterDirectly(itemId: String): FanqieBookItem? {
        return try {
            val url = "https://fanqienovel.com/reader/$itemId"
            val req = Request.Builder().url(url).build()
            val html = directHttpClient.newCall(req).execute().use { it.body?.string() ?: "" }
            if (html.isBlank()) return null

            val pageBid = Regex("href=\"/page/(\\d+)\"").find(html)?.groupValues?.get(1)
            if (!pageBid.isNullOrBlank()) {
                val bookInfo = fetchFanqieBookByIdDirectly(pageBid)
                if (bookInfo != null && bookInfo.title.isNotBlank()) {
                    return bookInfo
                }
            }

            val chapTitle = stripHtmlTags(Regex("<h1[^>]*>([^<]+)</h1>").find(html)?.groupValues?.get(1) ?: "第1章")
            val bookTitle = stripHtmlTags(Regex("href=\"/page/\\d+\"[^>]*>([^<]+)</a>").find(html)?.groupValues?.get(1) ?: chapTitle)
            val paragraphs = Regex("<p>([\\s\\S]*?)</p>")
                .findAll(html)
                .map { stripHtmlTags(it.groupValues[1]) }
                .filter { it.length > 4 }
                .take(16)
                .toList()
            val text = paragraphs.joinToString("\n")
            FanqieBookItem(
                book_id = itemId,
                title = bookTitle,
                author = "番茄小说",
                genre = "番茄热门连载",
                abstract = text.take(120),
                first_chapter_title = chapTitle,
                story_text = text,
                url = url
            )
        } catch (_: Exception) {
            null
        }
    }

    // ===================== 5. 手机端独立 AI 导演拆解引擎 (直连大模型或本地拆解) =====================

    suspend fun breakdownStoryOnPhone(
        context: Context,
        title: String,
        genre: String,
        novelText: String
    ): ProjectData = withContext(Dispatchers.IO) {
        val keys = getSavedApiKeys(context)
        val sfKey = keys["SILICONFLOW_API_KEY"] ?: ""
        val dsKey = keys["DEEPSEEK_API_KEY"] ?: ""
        val kimiKey = keys["MOONSHOT_API_KEY"] ?: ""

        // 1. 若手机上配置了真实大模型 Key，从手机直接调用云端大模型 API 拆解剧本
        val apiEndpointAndKey: Triple<String, String, String>? = when {
            sfKey.isNotBlank() -> Triple("https://api.siliconflow.cn/v1/chat/completions", sfKey, "Qwen/Qwen2.5-7B-Instruct")
            dsKey.isNotBlank() -> Triple("https://api.deepseek.com/chat/completions", dsKey, "deepseek-chat")
            kimiKey.isNotBlank() -> Triple("https://api.moonshot.cn/v1/chat/completions", kimiKey, "moonshot-v1-8k")
            else -> null
        }

        if (apiEndpointAndKey != null) {
            try {
                val (apiUrl, apiKey, modelName) = apiEndpointAndKey
                val sysPrompt = """
                    你是一位好莱坞级竖屏短剧总导演。请将用户输入的小说文本拆解为6到8个分镜镜头及角色列表，严格输出纯JSON对象（不要markdown代码块），格式如下：
                    {
                      "characters": [{"name":"角色名","role":"身份定位","voice":"云希 (磁性沉稳霸道)","traits":"外貌与性格特征"}],
                      "shots": [{"id":1,"speaker":"说话人或旁白","scale":"MEDIUM_SHOT","motion":"ZOOM_IN","dialogue":"台词或旁白","visual_prompt":"9:16 vertical anime cinematic frame prompt"}]
                    }
                """.trimIndent()
                val reqBody = mapOf(
                    "model" to modelName,
                    "messages" to listOf(
                        mapOf("role" to "system", "content" to sysPrompt),
                        mapOf("role" to "user", "content" to "剧名：《$title》\n题材：$genre\n小说内容：\n${novelText.take(2500)}")
                    ),
                    "temperature" to 0.4
                )
                val req = Request.Builder()
                    .url(apiUrl)
                    .addHeader("Authorization", "Bearer $apiKey")
                    .post(gson.toJson(reqBody).toRequestBody("application/json".toMediaType()))
                    .build()
                directHttpClient.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val raw = resp.body?.string() ?: ""
                        val root = JsonParser.parseString(raw).asJsonObject
                        var content = root.getAsJsonArray("choices")
                            ?.get(0)?.asJsonObject
                            ?.getAsJsonObject("message")
                            ?.get("content")?.asString ?: ""
                        content = content.replace("```json", "").replace("```", "").trim()
                        val jsonStart = content.indexOf('{')
                        val jsonEnd = content.lastIndexOf('}')
                        if (jsonStart >= 0 && jsonEnd > jsonStart) {
                            val parsed = JsonParser.parseString(content.substring(jsonStart, jsonEnd + 1)).asJsonObject
                            val charsArr = parsed.getAsJsonArray("characters")
                            val shotsArr = parsed.getAsJsonArray("shots")
                            val chars = mutableListOf<CharacterItem>()
                            charsArr?.forEach { el ->
                                val o = el.asJsonObject
                                chars.add(
                                    CharacterItem(
                                        name = o.get("name")?.asString ?: "主角",
                                        role = o.get("role")?.asString ?: "主要角色",
                                        voice = o.get("voice")?.asString ?: "云希 (磁性沉稳霸道)",
                                        avatar = "",
                                        traits = o.get("traits")?.asString ?: "气质出众"
                                    )
                                )
                            }
                            val shots = mutableListOf<ShotItem>()
                            shotsArr?.forEachIndexed { idx, el ->
                                val o = el.asJsonObject
                                val sid = idx + 1
                                val m = (o.get("motion")?.asString ?: "ZOOM_IN").uppercase()
                                val mName = when {
                                    m.contains("SHAKE") -> "镜头震撼"
                                    m.contains("OUT") -> "镜头拉远"
                                    m.contains("PAN") -> "向左横移"
                                    else -> "镜头推进"
                                }
                                shots.add(
                                    ShotItem(
                                        id = sid,
                                        speaker = o.get("speaker")?.asString ?: "旁白",
                                        scale = o.get("scale")?.asString ?: "MEDIUM_SHOT",
                                        motion = m,
                                        motion_name = mName,
                                        dialogue = o.get("dialogue")?.asString ?: "",
                                        image = "",
                                        audio = "",
                                        sfx = if (m.contains("SHAKE")) "重低音轰鸣" else "无",
                                        visual_prompt = o.get("visual_prompt")?.asString ?: "9:16 vertical cinematic drama, $title, $genre"
                                    )
                                )
                            }
                            if (shots.isNotEmpty()) {
                                val work = ProjectData(
                                    title = title,
                                    genre = genre,
                                    duration = shots.size * 4.5,
                                    characters = if (chars.isNotEmpty()) chars else extractCharactersFromShots(shots),
                                    shots = shots,
                                    audio_tracks = listOf(
                                        AudioTrackItem("AI 导演剧本引擎 ($modelName)", "已拆解", "共生成 ${shots.size} 个分镜镜头"),
                                        AudioTrackItem("人声对白轨", "可随时试听", "支持逐镜真实语音试听与重录"),
                                        AudioTrackItem("双层防变形字幕轨", "已就绪", "720×1280 竖屏独立字幕图层")
                                    )
                                )
                                saveCreatorWork(context, work)
                                return@withContext work
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }

        // 2. 智能段落与对白规则拆解（100% 基于创作者输入的真实小说文本）
        val rawLines = novelText
            .split(Regex("[\\r\\n]+|(?<=[。！？!?])"))
            .map { it.trim() }
            .filter { it.length >= 4 && !it.startsWith("【第") && !it.startsWith("【作品简介】") }
            .take(10)

        val effectiveLines = if (rawLines.isNotEmpty()) rawLines else listOf(novelText.trim().ifEmpty { "《$title》第一幕开启。" })
        val motions = listOf(
            "ZOOM_IN" to "镜头推进",
            "PAN_LEFT" to "向左横移",
            "ZOOM_IN" to "镜头推进",
            "ZOOM_OUT" to "镜头拉远",
            "SHAKE" to "镜头震撼"
        )
        val scales = listOf("WIDE_SHOT", "MEDIUM_SHOT", "CLOSE_UP", "MEDIUM_SHOT", "FULL_SHOT")

        val shots = effectiveLines.mapIndexed { idx, line ->
            val sid = idx + 1
            var speaker = "旁白"
            var dialogue = line

            val colonMatch = Regex("^([\\u4e00-\\u9fa5A-Za-z0-9]{1,8}?)(?:说道|冷笑|怒喝|大喊|低声道|道|说)?[：:]\\s*(.+)$").find(line)
            val quoteMatch = Regex("^([\\u4e00-\\u9fa5]{2,5})[^“\"：:]{0,6}[“\"]([^”\"]+)[”\"]").find(line)
            if (colonMatch != null) {
                speaker = colonMatch.groupValues[1]
                dialogue = colonMatch.groupValues[2].trim('“', '”', '"')
            } else if (quoteMatch != null) {
                speaker = quoteMatch.groupValues[1]
                dialogue = quoteMatch.groupValues[2]
            }

            val (mCode, mName) = motions[idx % motions.size]
            ShotItem(
                id = sid,
                speaker = speaker,
                scale = scales[idx % scales.size],
                motion = mCode,
                motion_name = mName,
                dialogue = dialogue,
                image = "",
                audio = "",
                sfx = if (mCode == "SHAKE") "惊雷轰鸣" else "环境音效",
                visual_prompt = "9:16 vertical cinematic drama, $genre, $speaker, $dialogue"
            )
        }

        val chars = extractCharactersFromShots(shots)
        val work = ProjectData(
            title = title,
            genre = genre,
            duration = shots.size * 4.5,
            characters = chars,
            shots = shots,
            audio_tracks = listOf(
                AudioTrackItem("剧本分镜拆解引擎", "已就绪", "根据《$title》生成 ${shots.size} 个镜头"),
                AudioTrackItem("多角色语音合成轨", "可试听", "点击分镜【试听配音】即可发声"),
                AudioTrackItem("双层防变形字幕轨", "已就绪", "720×1280 竖屏独立字幕层")
            )
        )
        saveCreatorWork(context, work)
        return@withContext work
    }

    private fun extractCharactersFromShots(shots: List<ShotItem>): List<CharacterItem> {
        val speakers = shots.map { it.speaker }.filter { it != "旁白" && it.isNotBlank() }.distinct()
        if (speakers.isEmpty()) {
            return listOf(
                CharacterItem("叙事旁白", "全剧讲述者", "云希 (磁性沉稳霸道)", "", "沉浸式电影感叙事声线")
            )
        }
        return speakers.mapIndexed { idx, name ->
            val isFemale = name.any { it in "女姐母妻雪薇妃瑶琴妹娘" }
            CharacterItem(
                name = name,
                role = if (idx == 0) "核心主角" else "主要角色",
                voice = if (isFemale) "晓涵 (温柔清纯甜美)" else "云希 (磁性沉稳霸道)",
                avatar = "",
                traits = "来自创作者剧本《${name}》角色设定"
            )
        }
    }

    // ===================== 6. 手机端分镜画面生成 + 硬件 H.264 MP4 成片合成引擎 =====================

    fun getLocalShotImageFile(context: Context, title: String, shotId: Int): File {
        val safeTitle = title.replace(Regex("[^\\u4e00-\\u9fa5a-zA-Z0-9_-]"), "_").ifEmpty { "default_work" }
        val dir = File(context.filesDir, "projects/$safeTitle/shots")
        dir.mkdirs()
        return File(dir, "shot_${shotId}_preview.jpg")
    }

    private fun getLocalShotRawBgFile(context: Context, title: String, shotId: Int): File {
        val safeTitle = title.replace(Regex("[^\\u4e00-\\u9fa5a-zA-Z0-9_-]"), "_").ifEmpty { "default_work" }
        val dir = File(context.filesDir, "projects/$safeTitle/shots")
        dir.mkdirs()
        return File(dir, "shot_${shotId}_raw.jpg")
    }

    suspend fun generateShotImageOnPhone(
        context: Context,
        title: String,
        genre: String,
        shot: ShotItem
    ): File = withContext(Dispatchers.IO) {
        val rawFile = getLocalShotRawBgFile(context, title, shot.id)
        val previewFile = getLocalShotImageFile(context, title, shot.id)
        val keys = getSavedApiKeys(context)
        val sfKey = keys["SILICONFLOW_API_KEY"] ?: ""
        val pexelsKey = keys["PEXELS_API_KEY"] ?: ""

        var bgBitmap: Bitmap? = null

        // 1. 若手机上配置了硅基流动 SILICONFLOW_API_KEY，直接调用免费 FLUX.1-schnell 生成真实 9:16 分镜图
        if (sfKey.isNotBlank()) {
            try {
                val payload = mapOf(
                    "model" to "black-forest-labs/FLUX.1-schnell",
                    "prompt" to "${shot.visual_prompt}, vertical 9:16 portrait, cinematic lighting, high detail, no text",
                    "image_size" to "720x1280",
                    "num_inference_steps" to 4
                )
                val req = Request.Builder()
                    .url("https://api.siliconflow.cn/v1/images/generations")
                    .addHeader("Authorization", "Bearer $sfKey")
                    .post(gson.toJson(payload).toRequestBody("application/json".toMediaType()))
                    .build()
                directHttpClient.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val body = resp.body?.string() ?: ""
                        val imgUrl = JsonParser.parseString(body).asJsonObject
                            .getAsJsonArray("images")?.get(0)?.asJsonObject
                            ?.get("url")?.asString ?: ""
                        if (imgUrl.isNotBlank()) {
                            val imgReq = Request.Builder().url(imgUrl).build()
                            directHttpClient.newCall(imgReq).execute().use { imgResp ->
                                val bytes = imgResp.body?.bytes()
                                if (bytes != null && bytes.isNotEmpty()) {
                                    bgBitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                                }
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }

        // 2. 若配置了 PEXELS_API_KEY，直接从手机调用 Pexels 9:16 竖屏高清图库
        if (bgBitmap == null && pexelsKey.isNotBlank()) {
            try {
                val q = java.net.URLEncoder.encode(genre.ifBlank { "cinematic portrait" }, "UTF-8")
                val req = Request.Builder()
                    .url("https://api.pexels.com/v1/search?query=$q&orientation=portrait&per_page=5")
                    .addHeader("Authorization", pexelsKey)
                    .build()
                directHttpClient.newCall(req).execute().use { resp ->
                    if (resp.isSuccessful) {
                        val body = resp.body?.string() ?: ""
                        val photos = JsonParser.parseString(body).asJsonObject.getAsJsonArray("photos")
                        if (photos != null && photos.size() > 0) {
                            val pick = photos.get((shot.id - 1) % photos.size()).asJsonObject
                            val imgUrl = pick.getAsJsonObject("src")?.get("large2x")?.asString
                                ?: pick.getAsJsonObject("src")?.get("portrait")?.asString ?: ""
                            if (imgUrl.isNotBlank()) {
                                directHttpClient.newCall(Request.Builder().url(imgUrl).build()).execute().use { r2 ->
                                    val bytes = r2.body?.bytes()
                                    if (bytes != null && bytes.isNotEmpty()) {
                                        bgBitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                                    }
                                }
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }

        // 3. 若未配置生图 Key，使用 Android Canvas 绘制高质感 720×1280 电影级分镜底图
        val finalBg = if (bgBitmap != null) {
            Bitmap.createScaledBitmap(bgBitmap!!, 720, 1280, true)
        } else {
            drawProceduralCinematicBg(title, genre, shot)
        }

        FileOutputStream(rawFile).use { out ->
            finalBg.compress(Bitmap.CompressFormat.JPEG, 90, out)
        }

        val previewBmp = finalBg.copy(Bitmap.Config.ARGB_8888, true)
        val canvas = Canvas(previewBmp)
        drawStationarySubtitleOverlay(canvas, 720, 1280, shot)
        FileOutputStream(previewFile).use { out ->
            previewBmp.compress(Bitmap.CompressFormat.JPEG, 90, out)
        }
        return@withContext previewFile
    }

    private fun drawProceduralCinematicBg(title: String, genre: String, shot: ShotItem): Bitmap {
        val w = 720
        val h = 1280
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)

        val palettes = listOf(
            intArrayOf(Color.parseColor("#0B132B"), Color.parseColor("#1C2541"), Color.parseColor("#0F172A")),
            intArrayOf(Color.parseColor("#1A0B2E"), Color.parseColor("#2E1065"), Color.parseColor("#090D16")),
            intArrayOf(Color.parseColor("#06283D"), Color.parseColor("#1363DF"), Color.parseColor("#071018")),
            intArrayOf(Color.parseColor("#2C0703"), Color.parseColor("#590D22"), Color.parseColor("#0B090A"))
        )
        val pal = palettes[(shot.id - 1) % palettes.size]
        val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = LinearGradient(0f, 0f, w.toFloat(), h.toFloat(), pal, null, Shader.TileMode.CLAMP)
        }
        canvas.drawRect(0f, 0f, w.toFloat(), h.toFloat(), bgPaint)

        // 绘制电影灯光晕与戏剧构图线条
        val glowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = RadialGradient(
                w * 0.5f,
                h * 0.38f,
                340f,
                Color.argb(95, 0, 242, 254),
                Color.TRANSPARENT,
                Shader.TileMode.CLAMP
            )
        }
        canvas.drawCircle(w * 0.5f, h * 0.38f, 340f, glowPaint)

        // 绘制中心戏剧剪影与分镜景别信息
        val titlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(70, 255, 255, 255)
            textSize = 42f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("《$title》", w / 2f, h * 0.32f, titlePaint)

        val rolePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#FFD166")
            textSize = 54f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText(shot.speaker, w / 2f, h * 0.42f, rolePaint)

        val metaPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#67E8F9")
            textSize = 26f
            textAlign = Paint.Align.CENTER
        }
        canvas.drawText("镜头 #0${shot.id} · ${shot.scale} · ${shot.motion_name}", w / 2f, h * 0.48f, metaPaint)

        return bmp
    }

    fun drawStationarySubtitleOverlay(canvas: Canvas, w: Int, h: Int, shot: ShotItem) {
        // 顶部镜头角标
        val topBadgePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(175, 10, 15, 28)
        }
        canvas.drawRoundRect(RectF(28f, 36f, 340f, 88f), 14f, 14f, topBadgePaint)
        val badgeTextPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#00F2FE")
            textSize = 22f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        }
        canvas.drawText("SHOT #0${shot.id} · ${shot.motion_name}", 46f, 70f, badgeTextPaint)

        // 底部固定字幕底栏 (完全独立于底层运镜，永不裁切变形)
        val subBoxTop = h - 320f
        val subBgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = LinearGradient(
                0f,
                subBoxTop - 60f,
                0f,
                h.toFloat(),
                intArrayOf(Color.TRANSPARENT, Color.argb(215, 6, 10, 20), Color.argb(245, 6, 10, 20)),
                floatArrayOf(0f, 0.3f, 1f),
                Shader.TileMode.CLAMP
            )
        }
        canvas.drawRect(0f, subBoxTop - 60f, w.toFloat(), h.toFloat(), subBgPaint)

        // 说话人金色名牌
        val speakerTagPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#FFB800")
        }
        canvas.drawRoundRect(RectF(44f, subBoxTop, 240f, subBoxTop + 46f), 10f, 10f, speakerTagPaint)
        val speakerTextPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#0C101A")
            textSize = 24f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
        }
        canvas.drawText(shot.speaker.take(6), 62f, subBoxTop + 32f, speakerTextPaint)

        // 自动换行高对比度台词字幕
        val textPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 32f
            typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
            setShadowLayer(6f, 0f, 2f, Color.BLACK)
        }
        val contentWidth = w - 88
        val staticLayout = StaticLayout.Builder
            .obtain(shot.dialogue, 0, shot.dialogue.length, textPaint, contentWidth)
            .setAlignment(Layout.Alignment.ALIGN_NORMAL)
            .setLineSpacing(6f, 1.0f)
            .setMaxLines(4)
            .build()

        canvas.save()
        canvas.translate(44f, subBoxTop + 66f)
        staticLayout.draw(canvas)
        canvas.restore()
    }

    /**
     * 手机端本地硬件 H.264 MP4 视频合成引擎 (解决图四无法连接机房时无法生成视频的问题)
     */
    suspend fun renderFullMp4OnPhone(
        context: Context,
        project: ProjectData,
        onProgress: (progress: Int, step: String, log: String) -> Unit
    ): String = withContext(Dispatchers.IO) {
        val safeTitle = project.title.replace(Regex("[^\\u4e00-\\u9fa5a-zA-Z0-9_-]"), "_").ifEmpty { "creator_drama" }
        val outDir = File(context.filesDir, "projects/$safeTitle")
        outDir.mkdirs()
        val outMp4 = File(outDir, "${safeTitle}_成片.mp4")
        if (outMp4.exists()) outMp4.delete()

        val shots = project.shots
        val totalShots = max(1, shots.size)

        onProgress(15, "阶段 1/4：分镜剧本与角色声线校验", "🎬 已载入《${project.title}》共 $totalShots 个分镜镜头")

        // 1. 生成每个镜头的分镜画面 (若配置了硅基流动/Pexels 则真实云端生图，否则绘制高清竖屏帧)
        val rawBitmaps = mutableListOf<Bitmap>()
        for ((idx, shot) in shots.withIndex()) {
            val pct = 20 + ((idx + 1) * 30 / totalShots)
            onProgress(
                pct,
                "阶段 2/4：正在绘制第 ${shot.id}/$totalShots 镜画面",
                "🎨 正在生成镜头 #0${shot.id} (${shot.speaker}) 9:16 竖屏画面..."
            )
            generateShotImageOnPhone(context, project.title, project.genre, shot)
            val rawFile = getLocalShotRawBgFile(context, project.title, shot.id)
            val bmp = BitmapFactory.decodeFile(rawFile.absolutePath)
                ?: drawProceduralCinematicBg(project.title, project.genre, shot)
            rawBitmaps.add(bmp)
        }

        onProgress(60, "阶段 3/4：硬件 H.264 双层防变形运镜编码", "🎞️ 启动 Android MediaCodec 720×1280 竖屏硬件编码器...")

        val width = 720
        val height = 1280
        val fps = 15
        val secondsPerShot = 3
        val framesPerShot = fps * secondsPerShot

        val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height).apply {
            setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
            setInteger(MediaFormat.KEY_BIT_RATE, 2_500_000)
            setInteger(MediaFormat.KEY_FRAME_RATE, fps)
            setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1)
        }

        val encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
        encoder.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
        encoder.start()

        val muxer = MediaMuxer(outMp4.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
        val bufferInfo = MediaCodec.BufferInfo()
        var trackIndex = -1
        var muxerStarted = false
        var frameIndex = 0L

        val frameBitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val frameCanvas = Canvas(frameBitmap)
        val matrix = Matrix()
        val paint = Paint(Paint.FILTER_BITMAP_FLAG)
        val argbPixels = IntArray(width * height)
        val yuvBytes = ByteArray(width * height * 3 / 2)

        fun drainEncoder(endOfStream: Boolean) {
            if (endOfStream) {
                try {
                    encoder.signalEndOfInputStream()
                } catch (_: Exception) {
                }
            }
            while (true) {
                val outIndex = encoder.dequeueOutputBuffer(bufferInfo, 10_000)
                if (outIndex == MediaCodec.INFO_TRY_AGAIN_LATER) {
                    if (!endOfStream) break
                } else if (outIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    if (!muxerStarted) {
                        trackIndex = muxer.addTrack(encoder.outputFormat)
                        muxer.start()
                        muxerStarted = true
                    }
                } else if (outIndex >= 0) {
                    val encodedData = encoder.getOutputBuffer(outIndex)
                    if (encodedData != null && bufferInfo.size > 0 && muxerStarted) {
                        encodedData.position(bufferInfo.offset)
                        encodedData.limit(bufferInfo.offset + bufferInfo.size)
                        muxer.writeSampleData(trackIndex, encodedData, bufferInfo)
                    }
                    encoder.releaseOutputBuffer(outIndex, false)
                    if ((bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                        break
                    }
                }
            }
        }

        for ((sIdx, shot) in shots.withIndex()) {
            val bg = rawBitmaps[sIdx]
            val pct = 62 + ((sIdx + 1) * 32 / totalShots)
            onProgress(
                pct,
                "阶段 4/4：正在压制第 ${shot.id}/$totalShots 镜 (${shot.motion_name})",
                "⚡ 正在合成镜头 #0${shot.id}：底层 2.5D 运镜 + 顶层静止防变形字幕..."
            )
            for (f in 0 until framesPerShot) {
                val t = f.toFloat() / framesPerShot.toFloat()
                frameCanvas.drawColor(Color.BLACK)

                // 底层：仅对背景图执行 2.5D 电影运镜 (推镜 / 拉镜 / 横移 / 震动)
                matrix.reset()
                when {
                    shot.motion.contains("OUT") -> {
                        val scale = 1.22f - 0.20f * t
                        val dx = -(width * (scale - 1f)) * 0.5f
                        val dy = -(height * (scale - 1f)) * 0.5f
                        matrix.postScale(scale, scale)
                        matrix.postTranslate(dx, dy)
                    }
                    shot.motion.contains("PAN") -> {
                        val scale = 1.16f
                        val maxShift = width * (scale - 1f)
                        val dx = -maxShift * (1f - t)
                        val dy = -(height * (scale - 1f)) * 0.5f
                        matrix.postScale(scale, scale)
                        matrix.postTranslate(dx, dy)
                    }
                    shot.motion.contains("SHAKE") -> {
                        val scale = 1.08f
                        val dx = -(width * (scale - 1f)) * 0.5f + (sin(f * 1.7) * 12.0).toFloat()
                        val dy = -(height * (scale - 1f)) * 0.5f + (cos(f * 2.1) * 12.0).toFloat()
                        matrix.postScale(scale, scale)
                        matrix.postTranslate(dx, dy)
                    }
                    else -> {
                        // ZOOM_IN
                        val scale = 1.0f + 0.22f * t
                        val dx = -(width * (scale - 1f)) * 0.5f
                        val dy = -(height * (scale - 1f)) * 0.5f
                        matrix.postScale(scale, scale)
                        matrix.postTranslate(dx, dy)
                    }
                }
                frameCanvas.drawBitmap(bg, matrix, paint)

                // 顶层：叠加静止不动的防变形字幕与说话人角标
                drawStationarySubtitleOverlay(frameCanvas, width, height, shot)

                frameBitmap.getPixels(argbPixels, 0, width, 0, 0, width, height)
                encodeYUV420SP(yuvBytes, argbPixels, width, height)

                val inIndex = encoder.dequeueInputBuffer(10_000)
                if (inIndex >= 0) {
                    val inBuf: ByteBuffer? = encoder.getInputBuffer(inIndex)
                    inBuf?.clear()
                    inBuf?.put(yuvBytes)
                    val ptsUsec = frameIndex * 1_000_000L / fps
                    val isLast = (sIdx == shots.lastIndex && f == framesPerShot - 1)
                    val flags = if (isLast) MediaCodec.BUFFER_FLAG_END_OF_STREAM else 0
                    encoder.queueInputBuffer(inIndex, 0, yuvBytes.size, ptsUsec, flags)
                    frameIndex++
                }
                drainEncoder(false)
            }
        }

        drainEncoder(true)
        try {
            encoder.stop()
            encoder.release()
        } catch (_: Exception) {
        }
        try {
            if (muxerStarted) muxer.stop()
            muxer.release()
        } catch (_: Exception) {
        }

        onProgress(100, "✅ 《${project.title}》全片渲染完成！", "🏆 成片已生成：${outMp4.absolutePath}")
        return@withContext outMp4.absolutePath
    }

    private fun encodeYUV420SP(yuv420sp: ByteArray, argb: IntArray, width: Int, height: Int) {
        val frameSize = width * height
        var yIndex = 0
        var uvIndex = frameSize
        var index = 0
        for (j in 0 until height) {
            for (i in 0 until width) {
                val c = argb[index]
                val r = (c shr 16) and 0xff
                val g = (c shr 8) and 0xff
                val b = c and 0xff

                val y = ((66 * r + 129 * g + 25 * b + 128) shr 8) + 16
                val u = ((-38 * r - 74 * g + 112 * b + 128) shr 8) + 128
                val v = ((112 * r - 94 * g - 18 * b + 128) shr 8) + 128

                yuv420sp[yIndex++] = y.coerceIn(0, 255).toByte()
                if (j % 2 == 0 && i % 2 == 0 && uvIndex + 1 < yuv420sp.size) {
                    yuv420sp[uvIndex++] = u.coerceIn(0, 255).toByte()
                    yuv420sp[uvIndex++] = v.coerceIn(0, 255).toByte()
                }
                index++
            }
        }
    }

    fun exportLocalMp4ToMovies(context: Context, localPath: String, title: String): String? {
        return try {
            val src = File(localPath)
            if (!src.exists()) return null
            val moviesDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES)
            moviesDir.mkdirs()
            val target = File(moviesDir, "${title}_曾练AI短剧_${System.currentTimeMillis() % 10000}.mp4")
            src.copyTo(target, overwrite = true)
            target.absolutePath
        } catch (_: Exception) {
            null
        }
    }
}
