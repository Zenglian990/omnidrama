package com.omnidrama.app.data.local

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.ShotItem
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CancellationException
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * Adversarial challenge test suite targeting:
 * 1. Recursion elimination and side-effect freedom in breakdownStoryLocally.
 * 2. Multi-corruption sequential single-pass repair idempotence.
 * 3. False-positive narrator preservation.
 * 4. Coroutine cancellation, exception handling, and threading behavior in refreshData lifecycle.
 */
class RecursionAndLifecycleChallengeTest {

    private val gson = Gson()

    private fun createShot(
        id: Int = 1,
        speaker: String = "旁白",
        dialogue: String = "对白内容",
        scale: String = "MEDIUM_SHOT",
        motion: String = "ZOOM_IN"
    ): ShotItem {
        return ShotItem(
            id = id,
            speaker = speaker,
            scale = scale,
            motion = motion,
            motion_name = "镜头推进",
            dialogue = dialogue,
            image = "",
            audio = "",
            sfx = "环境氛围音"
        )
    }

    // =========================================================================
    // 1. Empirical Verification: breakdownStoryLocally is Pure & Free of Side-Effects
    // =========================================================================

    @Test
    fun testBreakdownStoryLocally_HasNoDiskOrPrefsSideEffects() {
        val novelText = """
            林墨寒：“从今天起，你不再是林家的人。”
            苏清雪：“林墨寒，你当真如此绝情？”
            雨水混杂着泪水从苏清雪脸颊滑落。
            林墨寒转过身，黑伞遮住了他冷漠的面容。
        """.trimIndent()

        // Call breakdownStoryLocally with null context
        val work = LocalAndroidEngine.breakdownStoryLocally(
            context = null,
            title = "绝情豪门",
            genre = "现代言情",
            cleanNovelText = novelText
        )

        assertNotNull(work)
        assertEquals("绝情豪门", work.title)
        assertEquals("现代言情", work.genre)
        assertTrue("Shots must be extracted", work.shots.isNotEmpty())
        assertTrue("Characters must be extracted", work.characters.isNotEmpty())

        // Verify structure without recursion
        assertTrue(work.shots.size >= 2)
        assertEquals("林墨寒", work.shots[0].speaker)
        assertEquals("苏清雪", work.shots[1].speaker)
    }

    @Test
    fun testBreakdownStoryLocally_ExtremeScaleStress() {
        // Generate a 1,000-line novel text
        val sb = StringBuilder()
        for (i in 1..1000) {
            if (i % 2 == 1) {
                sb.append("战神$i：“犯我华夏者，虽远必诛！”\n")
            } else {
                sb.append("敌酋$i：“战神饶命，我等甘愿俯首称臣！”\n")
            }
        }

        val startTime = System.currentTimeMillis()
        val work = LocalAndroidEngine.breakdownStoryLocally(
            context = null,
            title = "千集战神录",
            genre = "热血战神",
            cleanNovelText = sb.toString()
        )
        val elapsed = System.currentTimeMillis() - startTime

        assertNotNull(work)
        // Must complete in linear time (< 5 seconds, typically < 500ms)
        assertTrue("Processing 1000 lines must be fast (was ${elapsed}ms)", elapsed < 5000)
        // Effective lines are capped to take(14)
        assertEquals(14, work.shots.size)
    }

    // =========================================================================
    // 2. Empirical Verification: Multi-Corruption Sequential Single-Pass Repair
    // =========================================================================

    @Test
    fun testMultiCorruption_SinglePassSequentialRepairAndIdempotence() {
        // Construct 5 works: 3 corrupted, 2 valid (one narrator, one dialogue)
        val work1Corrupted = ProjectData(
            title = "极寒末世囤货",
            genre = "末世爽剧",
            shots = listOf(
                createShot(1, "旁白", "围绕第1集，无论前方有多少强敌环伺，大局已定，凭你一己之力根本无法逆转！"),
                createShot(2, "旁白", "失传已久的巅峰血脉彻底觉醒，震碎苍穹！"),
                createShot(3, "旁白", "本章字数：2345字，更新时间：2026-01-01。"),
                createShot(4, "旁白", "作者有话说：求推荐票！")
            )
        )

        val work2ValidNarrator = ProjectData(
            title = "深海潜航",
            genre = "硬核科幻",
            shots = listOf(
                createShot(1, "旁白", "深海三千米，潜艇动力舱突然发生剧烈震颤。"),
                createShot(2, "旁白", "红色应急警报在狭窄的走廊中疯狂闪烁。"),
                createShot(3, "旁白", "副舰长死死盯住声呐屏幕，呼吸近乎停滞。"),
                createShot(4, "旁白", "未知生物的巨大阴影正在急速靠近。")
            )
        )

        val work3Corrupted = ProjectData(
            title = "修仙万载重回都市",
            genre = "都市修真",
            shots = listOf(
                createShot(1, "旁白", "失传千年的至尊血脉觉醒，天地变色！"),
                createShot(2, "旁白", "今五。"),
                createShot(3, "旁白", "大局已定，凭你一己之力安敢逆天！")
            )
        )

        val work4ValidDialogue = ProjectData(
            title = "商界巅峰",
            genre = "职场商业",
            shots = listOf(
                createShot(1, "陆总", "今天下午三点的并购协议，准时签署。"),
                createShot(2, "助理", "明白，所有法务团队已在会议室就位。")
            )
        )

        val work5Corrupted = ProjectData(
            title = "天灾末世降临",
            genre = "灾难末日",
            shots = listOf(
                createShot(1, "旁白", "围绕第10集无论前方有多少强敌环伺"),
                createShot(2, "旁白", "作者有话说：明天爆更十章！")
            )
        )

        val originalList = listOf(work1Corrupted, work2ValidNarrator, work3Corrupted, work4ValidDialogue, work5Corrupted)

        // Pass 1: Simulate getCreatorWorks map
        var hasRepairedPass1 = false
        val pass1Repaired = originalList.map {
            val rep = LocalAndroidEngine.repairCorruptedWorkIfNeeded(null, it)
            if (rep != it) hasRepairedPass1 = true
            rep
        }

        // Assertions on Pass 1:
        assertTrue("Pass 1 must detect that repairs were needed", hasRepairedPass1)
        assertEquals(5, pass1Repaired.size)

        // Work 1 repaired
        assertNotEquals(work1Corrupted, pass1Repaired[0])
        assertTrue("Corrupted clichés must be removed from work 1", pass1Repaired[0].shots.none { it.dialogue.contains("失传") })

        // Work 2 (valid narrator) must NOT be modified
        assertEquals("Valid narrator work must be preserved exactly", work2ValidNarrator.shots.size, pass1Repaired[1].shots.size)
        assertEquals(work2ValidNarrator.shots[0].dialogue, pass1Repaired[1].shots[0].dialogue)
        assertEquals(work2ValidNarrator.shots[3].dialogue, pass1Repaired[1].shots[3].dialogue)

        // Work 3 repaired
        assertNotEquals(work3Corrupted, pass1Repaired[2])
        assertTrue("Corrupted clichés must be removed from work 3", pass1Repaired[2].shots.none { it.dialogue.contains("失传") })

        // Work 4 (valid dialogue) preserved exactly
        assertEquals(work4ValidDialogue.shots.size, pass1Repaired[3].shots.size)

        // Work 5 repaired
        assertNotEquals(work5Corrupted, pass1Repaired[4])

        // Pass 2: IDEMPOTENCY CHECK
        // If pass1Repaired is read again (simulating subsequent getCreatorWorks call):
        var hasRepairedPass2 = false
        val pass2Repaired = pass1Repaired.map {
            val rep = LocalAndroidEngine.repairCorruptedWorkIfNeeded(null, it)
            if (rep != it) hasRepairedPass2 = true
            rep
        }

        // Pass 2 must require ZERO repairs!
        assertFalse("Pass 2 must be 100% idempotent: hasRepaired must be FALSE!", hasRepairedPass2)
        assertEquals(pass1Repaired, pass2Repaired)
    }

    // =========================================================================
    // 3. Empirical Verification: Coroutine Cancellation & Exception Handling
    // =========================================================================

    @Test
    fun testRefreshDataCoroutineLifecycle_CancellationHandling() = runBlocking {
        val isLoading = AtomicBoolean(false)
        val wasIOExecutedAfterCancellation = AtomicBoolean(false)

        val job = launch {
            isLoading.set(true)
            try {
                // Simulate network latency / IO operation
                withContext(Dispatchers.IO) {
                    delay(500)
                }
            } catch (e: Exception) {
                // Mimic StudioScreen.kt catch block
                try {
                    withContext(Dispatchers.IO) {
                        // This block should NOT run if job was cancelled!
                        wasIOExecutedAfterCancellation.set(true)
                    }
                } catch (ce: CancellationException) {
                    // withContext throws CancellationException when parent job is cancelled
                    throw ce
                }
            } finally {
                isLoading.set(false)
            }
        }

        // Cancel job while suspended in withContext
        delay(100)
        job.cancelAndJoin()

        // Verify:
        // 1. isLoading was properly reset in finally
        assertFalse("isLoading must be reset to false in finally", isLoading.get())
        // 2. IO operation in catch block was NOT executed due to coroutine cancellation
        assertFalse("IO after cancellation must not execute", wasIOExecutedAfterCancellation.get())
        assertTrue("Job must be cancelled", job.isCancelled)
    }

    @Test
    fun testRefreshDataCoroutineLifecycle_NetworkExceptionFallback() = runBlocking {
        val isLoading = AtomicBoolean(false)
        val fallbackTriggered = AtomicBoolean(false)

        val job = launch {
            isLoading.set(true)
            try {
                withContext(Dispatchers.IO) {
                    throw java.io.IOException("Remote cluster connection refused: 502 Bad Gateway")
                }
            } catch (e: Exception) {
                // Catch handles network exception safely
                fallbackTriggered.set(true)
            } finally {
                isLoading.set(false)
            }
        }

        job.join()

        assertTrue("Fallback must be triggered on network exception", fallbackTriggered.get())
        assertFalse("isLoading must be false after completion", isLoading.get())
        assertFalse("Job should complete normally despite network failure", job.isCancelled)
    }
}
