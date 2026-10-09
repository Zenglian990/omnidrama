package com.omnidrama.app.data.model

data class ProjectData(
    val title: String = "至尊龙王归位",
    val genre: String = "都市战神爽文",
    val video_url: String = "",
    val live_actor_video: String = "",
    val srt_url: String = "",
    val duration: Double = 61.61,
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
    val sfx: String
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
    val os: String = "Windows",
    val ffmpeg: Boolean = true,
    val jianying_installed: Boolean = false,
    val jianying_draft_path: String = ""
)

data class ProviderItem(
    val name: String,
    val role: String,
    val env_key: String,
    val configured: Boolean,
    val tier: String
)

data class VoiceItem(
    val name: String,
    val code: String,
    val tag: String,
    val gender: String
)
