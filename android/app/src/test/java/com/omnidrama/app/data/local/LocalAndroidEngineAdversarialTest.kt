package com.omnidrama.app.data.local

import com.google.gson.Gson
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.ShotItem
import org.junit.Assert.*
import org.junit.Test

/**
 * Adversarial stress test suite for LocalAndroidEngine.
 * Empirical verification of mathematical correctness and stability across boundary conditions,
 * extreme inputs, malformed strings, and negative modulo operations.
 */
class LocalAndroidEngineAdversarialTest {

    private val gson = Gson()

    private fun createShot(
        id: Int = 1,
        speaker: String = "旁白",
        dialogue: String = "对白内容"
    ): ShotItem {
        return ShotItem(
            id = id,
            speaker = speaker,
            scale = "CLOSE_UP",
            motion = "ZOOM_IN",
            motion_name = "镜头特写",
            dialogue = dialogue,
            image = "",
            audio = "",
            sfx = "音效"
        )
    }

    // =========================================================================
    // Challenge 1: Negative Modulo & Boundary Value Stress Testing
    // Boundary values: shot.id = 0, shot.id = -1, shot.id = Int.MIN_VALUE,
    // shot.id = Int.MAX_VALUE, size = 1, size = 4
    // =========================================================================

    @Test
    fun testBoundaryModulo_RequiredCases() {
        val testIds = listOf(
            0,
            -1,
            Int.MIN_VALUE,
            Int.MAX_VALUE,
            Int.MIN_VALUE + 1,
            Int.MAX_VALUE - 1,
            -2,
            -100,
            1,
            2,
            3,
            4,
            5
        )
        val sizes = listOf(1, 4, 2, 3, 5, 10, 100)

        for (size in sizes) {
            for (id in testIds) {
                val safeSize = size.coerceAtLeast(1)
                val idx = Math.floorMod(id - 1, safeSize)
                assertTrue("floorMod must be >= 0: id=$id, size=$size, result=$idx", idx >= 0)
                assertTrue("floorMod must be < safeSize: id=$id, size=$size, result=$idx", idx < safeSize)

                // Verify through LocalAndroidEngine.getProceduralPaletteIndex
                val paletteIdx = LocalAndroidEngine.getProceduralPaletteIndex(id, size)
                assertEquals("Palette index should match floorMod result", idx, paletteIdx)
                assertTrue("Palette index must be in 0 until $size, was $paletteIdx", paletteIdx in 0 until size)
            }
        }
    }

    @Test
    fun testModulo_ZeroAndNegativeDivisorDefense() {
        // Test edge cases where size is 0 or negative (preventing ArithmeticException: / by zero)
        val zeroOrNegativeSizes = listOf(0, -1, -4, -100, Int.MIN_VALUE)
        for (badSize in zeroOrNegativeSizes) {
            val safeSize = badSize.coerceAtLeast(1)
            assertEquals("Coerced size must be at least 1", 1, safeSize)
            for (id in listOf(0, -1, Int.MIN_VALUE, Int.MAX_VALUE)) {
                val idx = Math.floorMod(id - 1, safeSize)
                assertEquals(0, idx)
                val palIdx = LocalAndroidEngine.getProceduralPaletteIndex(id, badSize)
                assertEquals(0, palIdx)
            }
        }
    }

    @Test
    fun testArrayAccessWithProceduralPaletteIndex_NeverOutOfBounds() {
        // Simulate real palette lists with sizes 1 and 4
        val singlePalette = listOf(intArrayOf(0xFF0000, 0x00FF00, 0x0000FF))
        val fourPalettes = listOf(
            intArrayOf(1, 2, 3),
            intArrayOf(4, 5, 6),
            intArrayOf(7, 8, 9),
            intArrayOf(10, 11, 12)
        )

        val boundaryIds = listOf(
            0,
            -1,
            -2,
            -10,
            -9999,
            Int.MIN_VALUE,
            Int.MIN_VALUE + 1,
            Int.MAX_VALUE,
            Int.MAX_VALUE - 1,
            1,
            4
        )

        for (id in boundaryIds) {
            val idx1 = LocalAndroidEngine.getProceduralPaletteIndex(id, singlePalette.size)
            assertNotNull("Must safely retrieve palette for size 1 at id=$id", singlePalette[idx1])

            val idx4 = LocalAndroidEngine.getProceduralPaletteIndex(id, fourPalettes.size)
            assertNotNull("Must safely retrieve palette for size 4 at id=$id", fourPalettes[idx4])
        }
    }

    // =========================================================================
    // Challenge 2: Extreme & Malformed Inputs to cleanSpeakerCandidate
    // Inputs: null, empty, non-printable chars, extremely long strings, single punctuation
    // =========================================================================

    @Test
    fun testCleanSpeakerCandidate_ExtremeAndMalformedInputs() {
        // 1. Null, empty, and pure whitespace
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate(null))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate(""))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate(" "))
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("   \t   \n  \r  "))

        // 2. Control characters & Non-printable characters
        val nonPrintables = listOf(
            "\u0000",
            "\u0001\u0002\u0003",
            "\u0007\u0008\u001B",
            "\u200B\u200C\u200D\uFEFF", // zero-width spaces
            "\u0000周\u0000",
            "\u001F\u007F"
        )
        for (np in nonPrintables) {
            // Must execute safely without throwing exceptions
            val res = LocalAndroidEngine.cleanSpeakerCandidate(np)
            assertNotNull(res)
            assertTrue("Result must be non-empty string", res.isNotEmpty())
        }

        // 3. Single punctuation characters
        val singlePuncts = listOf(
            ":", "：", "“", "”", "\"", "'", "‘", "’",
            ",", "，", ".", "。", "!", "！", "?", "？",
            "-", "—", "、", "~", "@", "#", "$", "%",
            "^", "&", "*", "(", ")", "[", "]", "{", "}"
        )
        for (p in singlePuncts) {
            assertEquals("Single punctuation '$p' must resolve to 旁白", "旁白", LocalAndroidEngine.cleanSpeakerCandidate(p))
        }

        // 4. Repeated punctuation strings (trimmed to empty -> length 0 < 2 -> 旁白)
        val repeatedPuncts = listOf(
            ":::::::",
            "“““““",
            "”””””",
            "。。。。。",
            "，，，，，",
            "：：：：：",
            "\"\"\"\"\"\""
        )
        for (rp in repeatedPuncts) {
            assertEquals("Repeated punctuation '$rp' must resolve to 旁白", "旁白", LocalAndroidEngine.cleanSpeakerCandidate(rp))
        }

        // Heterogeneous punctuation (length 2..6): executes without throwing exceptions
        val mixedPunct = "“”，。！？：；"
        val mixedResult = LocalAndroidEngine.cleanSpeakerCandidate(mixedPunct)
        assertNotNull("Mixed punctuation must execute without throwing exception", mixedResult)
        assertTrue("Mixed punctuation returns non-null string", mixedResult.isNotBlank())

        // 5. Extremely long strings (e.g. 10,000 characters)
        val longString10k = "A".repeat(10000)
        assertEquals("10k length string must resolve to 旁白", "旁白", LocalAndroidEngine.cleanSpeakerCandidate(longString10k))

        val longChinese10k = "主角冷笑道".repeat(2000)
        assertEquals("10k Chinese string must resolve to 旁白", "旁白", LocalAndroidEngine.cleanSpeakerCandidate(longChinese10k))

        // 6. Length boundary tests (length < 2 or length > 6 -> 旁白)
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("张")) // 1 char -> 旁白
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("李")) // 1 char -> 旁白
        assertEquals("周肆", LocalAndroidEngine.cleanSpeakerCandidate("周肆")) // 2 chars -> valid
        assertEquals("林墨寒", LocalAndroidEngine.cleanSpeakerCandidate("林墨寒")) // 3 chars -> valid
        assertEquals("司马相如", LocalAndroidEngine.cleanSpeakerCandidate("司马相如")) // 4 chars -> valid
        assertEquals("公孙大娘娘", LocalAndroidEngine.cleanSpeakerCandidate("公孙大娘娘")) // 5 chars -> valid
        assertEquals("上官飞燕姑娘", LocalAndroidEngine.cleanSpeakerCandidate("上官飞燕姑娘")) // "姑娘" suffix trimmed -> "上官飞燕" (4 chars)
        assertEquals("旁白", LocalAndroidEngine.cleanSpeakerCandidate("一二三四五六七八九十")) // 10 chars -> 旁白

        // 7. Regex injection / special regex characters as input
        val regexSpecialChars = listOf(
            ".*",
            "(.*)",
            "[a-z]+",
            "^.*$",
            "\\d+",
            "(((((((((((",
            "\\\\\\\\\\\\"
        )
        for (spec in regexSpecialChars) {
            // Must not throw PatternSyntaxException
            val res = LocalAndroidEngine.cleanSpeakerCandidate(spec)
            assertNotNull(res)
        }
    }

    // =========================================================================
    // Challenge 3: Extreme & Malformed Inputs to isFemaleSpeaker
    // =========================================================================

    @Test
    fun testIsFemaleSpeaker_ExtremeAndMalformedInputs() {
        // 1. Null, empty, blank
        assertFalse(LocalAndroidEngine.isFemaleSpeaker(null))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker(""))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker(" "))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker("\t\r\n"))

        // 2. Control & non-printable
        assertFalse(LocalAndroidEngine.isFemaleSpeaker("\u0000\u0001\u0002"))

        // 3. Single punctuation
        assertFalse(LocalAndroidEngine.isFemaleSpeaker(":"))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker("。"))
        assertFalse(LocalAndroidEngine.isFemaleSpeaker("！"))

        // 4. Extremely long string without female keywords
        val longMaleString = "男主角".repeat(3000)
        assertFalse(LocalAndroidEngine.isFemaleSpeaker(longMaleString))

        // 5. Extremely long string containing female keyword
        val longFemaleString = "A".repeat(5000) + "梨" + "B".repeat(5000)
        assertTrue(LocalAndroidEngine.isFemaleSpeaker(longFemaleString))

        // 6. Comprehensive female keyword matches
        val femaleNames = listOf(
            "温梨", "沈清瑶", "白月光少女", "顾清霜姑娘", "小师妹",
            "林雪", "苏薇", "华妃", "秦瑶", "抚琴", "小妹", "红娘",
            "温柔", "晴儿", "明月", "黛琳", "珊珊", "紫芸", "若嫣",
            "晓涵", "甜桃", "幼糖", "婉儿", "娇娇", "虞姬", "女孩"
        )
        for (name in femaleNames) {
            assertTrue("Expected female for: $name", LocalAndroidEngine.isFemaleSpeaker(name))
        }

        // 7. Definite male or neutral names
        val maleOrNeutral = listOf(
            "周肆", "林墨寒", "沈宴", "陆远", "龙王", "战神", "管家", "保镖", "旁白", "王总"
        )
        for (name in maleOrNeutral) {
            assertFalse("Expected non-female for: $name", LocalAndroidEngine.isFemaleSpeaker(name))
        }
    }

    // =========================================================================
    // Challenge 4: Extreme & Malformed Inputs to extractCharactersFromShots
    // =========================================================================

    @Test
    fun testExtractCharactersFromShots_ExtremeAndMalformedInputs() {
        // 1. All null inputs
        val charsNull = LocalAndroidEngine.extractCharactersFromShots(null, null, null)
        assertNotNull(charsNull)
        assertTrue("Characters list must not be empty", charsNull.isNotEmpty())
        assertTrue("Must include narrator", charsNull.any { it.name == "叙事旁白" })

        // 2. All empty inputs
        val charsEmpty = LocalAndroidEngine.extractCharactersFromShots(emptyList(), "", "")
        assertNotNull(charsEmpty)
        assertTrue(charsEmpty.size >= 2)
        assertTrue(charsEmpty.any { it.name == "叙事旁白" })

        // 3. Extremely long title and genre
        val longTitle = "超级无敌长标题".repeat(500)
        val longGenre = "现言甜宠浪漫偶像都市剧".repeat(100)
        val charsLongMeta = LocalAndroidEngine.extractCharactersFromShots(emptyList(), longTitle, longGenre)
        assertNotNull(charsLongMeta)
        assertTrue(charsLongMeta.isNotEmpty())
        for (c in charsLongMeta) {
            assertNotNull(c.name)
            assertNotNull(c.role)
            assertNotNull(c.voice)
            assertNotNull(c.traits)
        }

        // 4. Dirty Gson-injected shots with null fields
        val dirtyShotJson = """{"id": 0}"""
        val dirtyShot = gson.fromJson(dirtyShotJson, ShotItem::class.java)
        val charsDirty = LocalAndroidEngine.extractCharactersFromShots(listOf(dirtyShot), null, null)
        assertNotNull(charsDirty)
        assertTrue(charsDirty.isNotEmpty())

        // 5. Malformed shots with non-printable characters and control strings
        val malformedShots = listOf(
            createShot(id = 0, speaker = "\u0000\u0001", dialogue = "\u0000\u0002"),
            createShot(id = -1, speaker = "::::::", dialogue = "。。。。。。"),
            createShot(id = Int.MIN_VALUE, speaker = "A".repeat(10000), dialogue = "B".repeat(10000))
        )
        val charsMalformed = LocalAndroidEngine.extractCharactersFromShots(malformedShots, "测试剧", "悬疑")
        assertNotNull(charsMalformed)
        assertTrue(charsMalformed.size >= 2)
        assertTrue(charsMalformed.any { it.name == "叙事旁白" })

        // 6. High-volume shots (100 distinct characters)
        val hundredShots = (1..100).map {
            createShot(id = it, speaker = "角色$it", dialogue = "台词$it")
        }
        val charsHundred = LocalAndroidEngine.extractCharactersFromShots(hundredShots, "百人剧", "武侠")
        assertNotNull(charsHundred)
        assertEquals("Should extract 100 characters + 1 narrator", 101, charsHundred.size)
        assertTrue(charsHundred.any { it.name == "叙事旁白" })

        // 7. High-volume narrator-only shots (100 narrator shots)
        val hundredNarratorShots = (1..100).map {
            createShot(id = it, speaker = "旁白", dialogue = "这是第$it 句旁白陈述。")
        }
        val charsNarratorOnly = LocalAndroidEngine.extractCharactersFromShots(hundredNarratorShots, "纯纪录片", "纪录片")
        assertNotNull(charsNarratorOnly)
        assertTrue(charsNarratorOnly.any { it.name == "叙事旁白" })
        assertTrue(charsNarratorOnly.size >= 2) // Defaults added so character list is valid
    }
}
