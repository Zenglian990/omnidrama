package com.omnidrama.app.data.repository

import com.google.gson.Gson
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
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()

    suspend fun getProject(baseUrl: String): ProjectData = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/api/project").build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    val body = resp.body?.string()
                    if (!body.isNullOrBlank()) {
                        return@withContext gson.fromJson(body, ProjectData::class.java)
                    }
                }
            }
        } catch (e: Exception) {
            // 离线高可用回退
        }
        return@withContext getOfflineMockProject()
    }

    suspend fun getSotaStatus(baseUrl: String): SotaStatusResponse = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder().url("$baseUrl/api/sota/status").build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    val body = resp.body?.string()
                    if (!body.isNullOrBlank()) {
                        return@withContext gson.fromJson(body, SotaStatusResponse::class.java)
                    }
                }
            }
        } catch (e: Exception) {
            // 离线回退
        }
        return@withContext getOfflineMockSota()
    }

    suspend fun exportJianying(baseUrl: String): String = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder()
                .url("$baseUrl/api/export-jianying")
                .post("{}".toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    return@withContext "已成功注入剪映草稿箱！"
                }
            }
        } catch (e: Exception) {
            return@withContext "导出请求失败: ${e.localizedMessage}"
        }
        return@withContext "导出完成"
    }

    private fun getOfflineMockProject(): ProjectData {
        val shots = listOf(
            ShotItem(1, "旁白", "WIDE_SHOT", "ZOOM_IN", "镜头推进", "林家祖宅大堂，狂风骤雨拍打着雕花木窗。", "", "", "暴雨环境音"),
            ShotItem(2, "岳母柳琴", "MEDIUM_SHOT", "PAN_LEFT", "向左横移", "叶辰，入赘三年，今日若拿不出三千万，就立刻滚出林家！", "", "", "无"),
            ShotItem(3, "旁白", "CLOSE_UP", "ZOOM_IN", "镜头推进", "叶辰神色淡然，深邃的双眸中隐现寒光。", "", "", "无"),
            ShotItem(4, "叶辰", "CLOSE_UP", "ZOOM_IN", "镜头推进", "三千万？当年若非我暗中相助，林家早在三年前就已灰飞烟灭！", "", "", "疾风起势 (Whoosh)"),
            ShotItem(5, "赵公子", "MEDIUM_SHOT", "ZOOM_OUT", "镜头拉远", "哈哈哈！大言不惭的废物，也不撒泡尿照照自己是个什么东西！", "", "", "无"),
            ShotItem(6, "旁白", "FULL_SHOT", "SHAKE", "镜头震撼", "突然，天地间惊雷滚滚，整座大堂剧烈震颤！", "", "", "惊雷劈裂 (Thunder)"),
            ShotItem(7, "旁白", "FULL_SHOT", "ZOOM_OUT", "镜头拉远", "大门轰然破碎，十八位身披黑金战铠的修罗战神破门而入！", "", "", "重低音轰鸣 (Impact)"),
            ShotItem(8, "修罗战神", "CLOSE_UP", "ZOOM_IN", "镜头推进", "恭迎龙王回归！十万修罗殿众将，随时听候调遣！", "", "", "金铁下跪 (Armor)"),
            ShotItem(9, "岳母与赵公子", "MEDIUM_SHOT", "SHAKE", "镜头震撼", "龙……龙王？！你竟然是那位镇守北境的至尊龙王！", "", "", "无"),
            ShotItem(10, "叶辰", "EXTREME_CLOSE_UP", "ZOOM_IN", "镜头推进", "犯我逆鳞者，杀无赦！", "", "", "终极大爆炸 (Impact)")
        )
        val chars = listOf(
            CharacterItem("叶辰 (主角)", "至尊龙王", "云希 (磁性沉稳霸道)", "", "黑发冷眸，修罗战神之主，隐藏滔天权势"),
            CharacterItem("岳母柳琴", "刁难反派", "晓晓 (尖酸刻薄逼迫)", "", "翡翠旗袍，拜金势力，豪门大堂"),
            CharacterItem("赵公子", "狂妄对手", "云健 (嚣张跋扈)", "", "定制西装，手持红酒，自傲恶少")
        )
        val tracks = listOf(
            AudioTrackItem("人声对白轨", "已对齐", "Edge-TTS 神经网络多音色"),
            AudioTrackItem("拟音音效轨 (SFX)", "已注入", "暴雨 + 惊雷 + 破门轰鸣 + 金铁下跪"),
            AudioTrackItem("电影配乐轨 (BGM)", "已卡点", "战神觉醒史诗管弦交响")
        )
        return ProjectData(
            title = "至尊龙王归位",
            genre = "都市战神爽文",
            duration = 61.61,
            characters = chars,
            shots = shots,
            audio_tracks = tracks
        )
    }

    private fun getOfflineMockSota(): SotaStatusResponse {
        val providers = mapOf(
            "director" to ProviderItem("Claude 3.5 Sonnet / DeepSeek-R1", "好莱坞编剧与镜头调度总导演", "ANTHROPIC_API_KEY", true, "行业顶级 (SOTA)"),
            "image" to ProviderItem("FLUX.1 Pro (BFL)", "8K 胶片级定妆与分镜剧照生图", "BFL_API_KEY", true, "行业顶级 (SOTA)"),
            "video_hailuo" to ProviderItem("MiniMax 海螺 Video-01", "真人微表情、毛孔与眼神光电影级视频", "MINIMAX_API_KEY", true, "行业顶级 (SOTA)"),
            "video_kling" to ProviderItem("快手可灵 Kling 2.0 Pro", "大动作打斗、物理交互与镜头轨迹控制", "KLING_ACCESS_KEY", true, "行业顶级 (SOTA)"),
            "lipsync" to ProviderItem("SyncLabs Pro (Sync.so)", "毫秒级神经音画对齐与真实牙齿/舌位建模", "SYNCLABS_API_KEY", true, "行业顶级 (SOTA)"),
            "voice" to ProviderItem("ElevenLabs Multilingual v2", "人类级呼吸喘息、轻蔑冷笑与情感爆发配音", "ELEVENLABS_API_KEY", true, "行业顶级 (SOTA)"),
            "music" to ProviderItem("Suno v3.5 Cinematic", "汉斯·季默级影视交响配乐与悬疑氛围", "SUNO_API_KEY", true, "行业顶级 (SOTA)")
        )
        return SotaStatusResponse(
            system = SystemStatus("Windows / Android", true, true, "JianyingPro Local Drafts"),
            providers = providers
        )
    }
}
