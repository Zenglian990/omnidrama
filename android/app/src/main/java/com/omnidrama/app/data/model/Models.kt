package com.omnidrama.app.data.model

data class ProjectData(
    val title: String = "",
    val genre: String = "",
    val video_url: String = "",
    val live_actor_video: String = "",
    val srt_url: String = "",
    val duration: Double = 0.0,
    val characters: List<CharacterItem> = emptyList(),
    val shots: List<ShotItem> = emptyList(),
    val audio_tracks: List<AudioTrackItem> = emptyList()
)

data class ShotItem(
    val id: Int,
    val speaker: String,
    val scale: String,
    val motion: String,
    val motion_name: String,
    val dialogue: String,
    val image: String,
    val audio: String,
    val sfx: String,
    val visual_prompt: String = ""
)

data class CharacterItem(
    val name: String,
    val role: String,
    val voice: String,
    val avatar: String,
    val traits: String
)

data class AudioTrackItem(
    val track: String,
    val status: String,
    val source: String
)

data class SotaStatusResponse(
    val system: SystemStatus = SystemStatus(),
    val providers: Map<String, ProviderItem> = emptyMap()
)

data class SystemStatus(
    val os: String = "未连接远程机房",
    val ffmpeg: Boolean = false,
    val jianying_installed: Boolean = false,
    val jianying_draft_path: String = ""
)

data class ProviderItem(
    val name: String,
    val role: String,
    val env_key: String,
    val configured: Boolean = false,
    val masked_key: String = "",
    val tier: String = ""
)

data class VoiceItem(
    val name: String,
    val code: String,
    val tag: String,
    val gender: String
)

data class RenderStatusResponse(
    val is_rendering: Boolean = false,
    val progress: Int = 0,
    val step_index: Int = 0,
    val total_steps: Int = 5,
    val current_step: String = "就绪",
    val logs: List<String> = emptyList(),
    val video_url: String = "",
    val error: String? = null
)

data class FanqieChapterItem(
    val chapter_id: String = "",
    val title: String = "",
    val order: Int = 1
)

data class FanqieBookItem(
    val book_id: String = "",
    val title: String = "",
    val author: String = "",
    val genre: String = "",
    val abstract: String = "",
    val first_chapter_title: String = "",
    val story_text: String = "",
    val url: String = "",
    val chapters: List<FanqieChapterItem> = emptyList()
)

