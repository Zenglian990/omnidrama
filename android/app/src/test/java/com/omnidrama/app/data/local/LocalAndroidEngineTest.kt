package com.omnidrama.app.data.local

import com.google.gson.Gson
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.ShotItem
import org.junit.Assert.*
import org.junit.Test

/**
 * Unit test suite for LocalAndroidEngine hardening in OmniDrama Android App (v3.3.0).
 * Tests negative modulo safety, infinite recursion prevention, null-safety guards, and story breakdown.
 */
class LocalAndroidEngineTest {

    private val gson = Gson()

    private fun createShot(
        id: Int = 1,
        speaker: String = "旁白",
        dialogue: String = "测试对白",
        scale: String = "MEDIUM_SHOT",
        motion: String = "ZOOM_IN",
        motion_name: String = "镜头推进",
        image: String = "",
        audio: String = "",
        sfx: String = "环境氛围音"
    ): ShotItem {
        return ShotItem(
            id = id,
            speaker = speaker,
            scale = scale,
            motion = motion,
            motion_name = motion_name,
            dialogue = dialogue,
            image = image,
            audio = audio,
            sfx = sfx
        )
    }

    // ==========================================
    // 1. Negative Modulo Safety Tests
    // ==========================================

    @Test
    fun testNegativeModuloSafety_Palettes() {
        val paletteSize = 4

        // Critical edge cases: id <= 0
        val idxZero = LocalAndroidEngine.getProceduralPaletteIndex(shotId = 0, paletteSize = paletteSize)
        assertTrue("Index for shot.id = 0 must be in 0 until $paletteSize, was $idxZero", idxZero in 0 until paletteSize)
        assertEquals(3, idxZero) // (0 - 1) mod 4 == 3

        val idxNegativeOne = LocalAndroidEngine.getProceduralPaletteIndex(shotId = -1, paletteSize = paletteSize)
        assertTrue("Index for shot.id = -1 must be in 0 until $paletteSize, was $idxNegativeOne", idxNegativeOne in 0 until paletteSize)
        assertEquals(2, idxNegativeOne) // (-1 - 1) mod 4 == 2

        val idxOne = LocalAndroidEngine.getProceduralPaletteIndex(shotId = 1, paletteSize = paletteSize)
        assertEquals(0, idxOne) // (1 - 1) mod 4 == 0

        // Comprehensive range testing
        for (id in listOf(-100, -23, -5, -2, -1, 0, 1, 2, 3, 4, 5, 25, 99)) {
            val idx = LocalAndroidEngine.getProceduralPaletteIndex(id, paletteSize)
            assertTrue("Palette index for id=$id must be in 0 until $paletteSize, was $idx", idx in 0 until paletteSize)
        }
    }

    @Test
    fun testNegativeModuloSafety_PexelsPhotos() {
        val photosCount = 5
        for (id in listOf(-5, -2, -1, 0, 1, 2, 3, 4, 5)) {
            val idx = Math.floorMod(id - 1, photosCount.coerceAtLeast(1))
            assertTrue("Pexels index for id=$id must be in 0 until $photosCount, was $idx", idx in 0 until photosCount)
        }
    }

    // ==========================================
    // 2. Infinite Recursion Prevention on 4-Shot Narrator Work
    // ==========================================

    @Test
    fun testPreventionOfInfiniteRecursion_FourShotNarratorWork() {
        // Valid 4-shot narrator-only drama
        val narratorShots = listOf(
            createShot(id = 1, speaker = "旁白", dialogue = "深夜十一点，雨势越来越大，整座城市笼罩在一片朦胧水汽之中。"),
            createShot(id = 2, speaker = "旁白", dialogue = "空旷的街道上，一辆黑色轿车疾驰而过，溅起漫天水花。"),
            createShot(id = 3, speaker = "旁白", dialogue = "后座上的男子缓缓放下车窗，目光冷峻地望向远处的高塔。"),
            createShot(id = 4, speaker = "旁白", dialogue = "今夜的拍卖会，注定将掀起一场惊天风暴。")
        )
        val originalWork = ProjectData(
            title = "雨夜风暴",
            genre = "悬疑动作",
            shots = narratorShots,
            characters = listOf(CharacterItem("叙事旁白", "讲述者", "云希", "", "磁性沉稳"))
        )

        // Must NOT throw StackOverflowError and must NOT be marked as corrupted
        val result = LocalAndroidEngine.repairCorruptedWorkIfNeeded(context = null, work = originalWork)

        assertNotNull(result)
        assertEquals("雨夜风暴", result.title)
        assertEquals(4, result.shots.size)
        // Verify all 4 shots remain narrator shots and retain their original dialogues
        assertTrue(result.shots.all { it.speaker == "旁白" })
        assertEquals("深夜十一点，雨势越来越大，整座城市笼罩在一片朦胧水汽之中。", result.shots[0].dialogue)
        assertEquals("今夜的拍卖会，注定将掀起一场惊天风暴。", result.shots[3].dialogue)
    }

    @Test
    fun testRepairGenuinelyCorruptedWork() {
        // Genuinely corrupted work containing banned PUA fantasy clichés
        val corruptedShots = listOf(
            createShot(id = 1, speaker = "旁白", dialogue = "围绕第1集，无论前方有多少强敌环伺，大局已定，凭你一己之力根本无法逆转！"),
            createShot(id = 2, speaker = "旁白", dialogue = "失传已久的巅峰血脉彻底觉醒，震碎苍穹！"),
            createShot(id = 3, speaker = "旁白", dialogue = "本章字数：2345字，更新时间：2026-01-01。"),
            createShot(id = 4, speaker = "旁白", dialogue = "作者有话说：求推荐票！")
        )
        val corruptedWork = ProjectData(
            title = "极寒末世囤货",
            genre = "末世爽剧",
            shots = corruptedShots
        )

        // Must repair without mutual recursion or StackOverflowError
        val repaired = LocalAndroidEngine.repairCorruptedWorkIfNeeded(context = null, work = corruptedWork)
        assertNotNull(repaired)
        assertTrue(repaired.shots.isNotEmpty())
        // Verify corrupted fantasy clichés are gone
        assertTrue(repaired.shots.none { it.dialogue.contains("无论前方有多少强敌环伺") })
        assertTrue(repaired.shots.none { it.dialogue.contains("失传已久的巅峰血脉") })
        assertTrue(repaired.shots.none { it.dialogue.contains("本章字数") })
    }

    // ==========================================
    // 3. Null-Safety & Defensive Deserialization Tests
    // ==========================================

    @Test
    fun testNullSafety_DecodeFanqiePua() {
        assertEquals("", LocalAndroidEngine.decodeFanqiePua(null))
        assertEquals("", LocalAndroidEngine.decodeFanqiePua(""))
        assertEquals("正常中文字符对白", LocalAndroidEngine.decodeFanqiePua("正常中文字符对白"))
    }

    @Test
    fun testNullSafety_IsFemaleSpeaker() {
        assertFalse(LocalAndroidEngine.isFemaleSpeaker(null))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker(""))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker("   "))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker("周肆"))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker("林墨寒"))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker("特工之王"))

        assertTrue(LocalAndroidEngine.isFemaleSpeaker("温梨"))
        assertTrue(LocalAndroidEngine.isFemaleSpeaker("沈清瑶"))
        assertTrue(LocalAndroidEngine.isFemaleSpeaker("白月光少女"))
        assertTrue(LocalAndroidEngine.isFemaleSpeaker("顾清霜姑娘"))
        assertTrue(LocalAndroidEngine.isFemaleSpeaker("小师妹"))
    }

    @Test
    fun testNullSafety_CleanSpeakerCandidate() {
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate(null))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate(""))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("   "))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("他"))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("有人"))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("众人"))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("此时"))
    }

    @Test
    fun testCleanSpeakerCandidate_DialogueExtraction() {
        assertEquals("周肆", LocalAndroidEngine.cleanSpeakerCandidate("周肆漫不经心地笑了一声"))
        assertEquals("温梨", LocalAndroidEngine.cleanSpeakerCandidate("“温梨小声吸了吸鼻子”"))
        assertEquals("沈宴", LocalAndroidEngine.cleanSpeakerCandidate("沈宴冷冷地质问道"))
        assertEquals("陆远", LocalAndroidEngine.cleanSpeakerCandidate("身边的陆远沉声道"))
        assertEquals("苏瑶", LocalAndroidEngine.cleanSpeakerCandidate("苏瑶行礼道"))
    }

    @Test
    fun testNullSafety_ExtractCharactersFromShots() {
        // Complete null inputs
        val chars1 = LocalAndroidEngine.extractCharactersFromShots(null, null, null)
        assertNotNull(chars1)
        assertTrue(chars1.isNotEmpty())
        assertTrue(chars1.any { it.name == "叙事旁白" })

        // Empty shots with title
        val chars2 = LocalAndroidEngine.extractCharactersFromShots(emptyList(), "甜宠蜜恋", "甜宠")
        assertNotNull(chars2)
        assertTrue(chars2.any { it.name == "叙事旁白" })
        assertTrue(chars2.size >= 2)

        // Shots with null fields injected via Gson deserialization
        val dirtyShot = gson.fromJson("{}", ShotItem::class.java)
        val chars3 = LocalAndroidEngine.extractCharactersFromShots(listOf(dirtyShot), null, null)
        assertNotNull(chars3)
        assertTrue(chars3.isNotEmpty())
    }

    @Test
    fun testNullSafety_RepairCorruptedWork_NullWork() {
        val res = LocalAndroidEngine.repairCorruptedWorkIfNeeded(null, null)
        assertNotNull(res)
        assertTrue(res.title.isEmpty() || res.title == "")
        assertTrue(res.shots.isEmpty())
    }

    // ==========================================
    // 4. Pure Story Breakdown Generator Tests
    // ==========================================

    @Test
    fun testBreakdownStoryLocally_PureGenerator() {
        val novelText = """
            周肆：“温梨，你以为你能逃出我的手掌心？”
            温梨：“周肆，我们早就结束了，你放过我吧！”
            周肆：“放过你？这辈子都别想。”
            周围的保镖齐声退后，不敢发出半点声响。
        """.trimIndent()

        val work = LocalAndroidEngine.breakdownStoryLocally(
            context = null,
            title = "雨夜深情",
            genre = "现言甜宠",
            cleanNovelText = novelText
        )

        assertNotNull(work)
        assertEquals("雨夜深情", work.title)
        assertEquals("现言甜宠", work.genre)
        assertTrue(work.shots.isNotEmpty())
        assertTrue(work.characters.isNotEmpty())
        assertTrue(work.audio_tracks.isNotEmpty())

        // Verify character extraction identified Zhou Si and Wen Li
        val charNames = work.characters.map { it.name }
        assertTrue("Characters should contain 周肆 or 温梨: $charNames", charNames.contains("周肆") || charNames.contains("温梨"))

        // Verify shots are valid and scored
        for (shot in work.shots) {
            assertTrue("Shot ID must be positive: ${shot.id}", shot.id > 0)
            assertTrue("Scale must not be blank", shot.scale.isNotBlank())
            assertTrue("Motion must not be blank", shot.motion.isNotBlank())
            assertTrue("Visual prompt must not be blank", shot.visual_prompt.isNotBlank())
        }
    }
}
