package com.omnidrama.app

import com.google.gson.Gson
import com.omnidrama.app.data.local.LocalAndroidEngine
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ConsistencyCardItem
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.PropItem
import org.junit.Assert.*
import org.junit.Test

/**
 * Adversarial Stress Test Suite for Milestone 4 (Android Consistency & Archetypes R4).
 * Stress tests Gson deserialization edge cases, archetype lookup variants, prompt compilation fallbacks,
 * and null-safety boundaries.
 */
class AdversarialConsistencyM4Test {

    private val gson = Gson()

    // ==========================================
    // 1. Gson Deserialization Stress Tests
    // ==========================================

    @Test
    fun testGson_MissingAllNewConsistencyFields_PreservesSafeDefaults() {
        val legacyJson = """
            {
                "name": "旧项目主角",
                "role": "男二号",
                "voice": "云扬 (热血青年男主)",
                "avatar": "https://example.com/avatar.png",
                "traits": "热血少年",
                "visual_anchor": "高马尾黑袍"
            }
        """.trimIndent()

        val item = gson.fromJson(legacyJson, CharacterItem::class.java)
        assertEquals("旧项目主角", item.name)
        assertEquals("男二号", item.role)
        assertEquals("", item.archetype)
        assertEquals("", item.turnaround_prompt)
        assertEquals("", item.turnaround_image)

        // Safe card must not be null
        val safeCard = item.safe_consistency_card
        assertNotNull(safeCard)
        assertEquals("", safeCard.facial_lock)
        assertEquals("", safeCard.hair_lock)
        assertEquals("", safeCard.costume_lock)
        assertEquals("", safeCard.exclusive_negative_prompt)
        assertTrue(safeCard.reference_images.isEmpty())
    }

    @Test
    fun testGson_ExplicitNullConsistencyCard_SafeAccessorNeverThrows() {
        val nullCardJson = """
            {
                "name": "空卡主角",
                "role": "主角",
                "consistency_card": null
            }
        """.trimIndent()

        val item = gson.fromJson(nullCardJson, CharacterItem::class.java)
        assertEquals("空卡主角", item.name)
        assertNull(item.consistency_card)

        // safe_consistency_card accessor must never return null
        val safeCard = item.safe_consistency_card
        assertNotNull(safeCard)
        assertEquals("", safeCard.facial_lock)

        // LocalAndroidEngine must safely accept this item without NPE
        val prompt = LocalAndroidEngine.buildCharacterTurnaroundPrompt(item)
        assertTrue(prompt.contains("空卡主角"))
        assertTrue(prompt.contains("Three full-body standing views"))

        val (pos, neg) = LocalAndroidEngine.compileCharacterConsistencyPrompt(item)
        assertTrue(pos.contains("空卡主角"))
        assertTrue(neg.contains("cartoon, anime"))
    }

    @Test
    fun testGson_UnknownAndMalformedFields_DeserializesCleanly() {
        val strangeJson = """
            {
                "name": "异构字段角色",
                "unknown_extra_field_1": "random_payload",
                "unknown_nested_object": { "key": 999 },
                "archetype": "05_modern_male_boss",
                "turnaround_prompt": "custom turnaround prompt",
                "consistency_card": {
                    "facial_lock": "angular jaw",
                    "unexpected_card_field": true
                }
            }
        """.trimIndent()

        val item = gson.fromJson(strangeJson, CharacterItem::class.java)
        assertEquals("异构字段角色", item.name)
        assertEquals("05_modern_male_boss", item.archetype)
        assertEquals("custom turnaround prompt", item.turnaround_prompt)
        assertEquals("angular jaw", item.safe_consistency_card.facial_lock)
    }

    @Test
    fun testGson_ProjectData_PropsNullAndEmptyResilience() {
        // Case 1: missing props field in ProjectData
        val missingPropsJson = """
            {
                "title": "无道具老剧",
                "genre": "都市"
            }
        """.trimIndent()

        val p1 = gson.fromJson(missingPropsJson, ProjectData::class.java)
        assertEquals("无道具老剧", p1.title)
        assertNotNull(p1.props)
        assertTrue(p1.props.isEmpty())

        // Case 2: round trip with full PropItem
        val prop = PropItem(
            name = "玄阴剑",
            category = "上古神兵",
            description = "千年玄冰铸造",
            visual_tags = "玄冰微光, 剑身雕纹",
            feature_lock = "冰晶半透明剑柄",
            turnaround_prompt = "Prop turnaround sheet of icy sword",
            negative_prompt = "plastic toy, blunt edge",
            reference_images = listOf("ref1.png")
        )
        val p2 = ProjectData(title = "仙侠剧", props = listOf(prop))
        val json2 = gson.toJson(p2)
        val restored2 = gson.fromJson(json2, ProjectData::class.java)
        assertEquals(1, restored2.props.size)
        assertEquals("玄阴剑", restored2.props[0].name)
        assertEquals("冰晶半透明剑柄", restored2.props[0].feature_lock)
    }

    // ==========================================
    // 2. Archetype Preset Lookup Stress Tests
    // ==========================================

    @Test
    fun testArchetypeLookup_ValidIds_AllFourPreserved() {
        val validIds = listOf(
            "04_modern_female_urban",
            "05_modern_male_boss",
            "06_ancient_male_noble",
            "08_antagonist_female_greentea"
        )
        for (id in validIds) {
            val preset = LocalAndroidEngine.getArchetypePreset(id)
            assertNotNull("Preset for id $id must exist", preset)
            assertEquals(id, preset!!.id)
        }
    }

    @Test
    fun testArchetypeLookup_CaseInsensitiveVariants() {
        // Uppercase
        val p04Upper = LocalAndroidEngine.getArchetypePreset("04_MODERN_FEMALE_URBAN")
        assertNotNull(p04Upper)
        assertEquals("04_modern_female_urban", p04Upper!!.id)

        val p05Upper = LocalAndroidEngine.getArchetypePreset("05_MODERN_MALE_BOSS")
        assertNotNull(p05Upper)
        assertEquals("05_modern_male_boss", p05Upper!!.id)

        val p06Upper = LocalAndroidEngine.getArchetypePreset("06_ANCIENT_MALE_NOBLE")
        assertNotNull(p06Upper)
        assertEquals("06_ancient_male_noble", p06Upper!!.id)

        val p08Upper = LocalAndroidEngine.getArchetypePreset("08_ANTAGONIST_FEMALE_GREENTEA")
        assertNotNull(p08Upper)
        assertEquals("08_antagonist_female_greentea", p08Upper!!.id)

        // Mixed case
        val p04Mixed = LocalAndroidEngine.getArchetypePreset("04_Modern_Female_Urban")
        assertNotNull(p04Mixed)
        assertEquals("04_modern_female_urban", p04Mixed!!.id)
    }

    @Test
    fun testArchetypeLookup_NumericCodes_WithAndWithoutLeadingZero() {
        // With leading zero ("04", "05", "06", "08")
        assertEquals("04_modern_female_urban", LocalAndroidEngine.getArchetypePreset("04")?.id)
        assertEquals("05_modern_male_boss", LocalAndroidEngine.getArchetypePreset("05")?.id)
        assertEquals("06_ancient_male_noble", LocalAndroidEngine.getArchetypePreset("06")?.id)
        assertEquals("08_antagonist_female_greentea", LocalAndroidEngine.getArchetypePreset("08")?.id)

        // Without leading zero ("4", "5", "6", "8")
        assertEquals("04_modern_female_urban", LocalAndroidEngine.getArchetypePreset("4")?.id)
        assertEquals("05_modern_male_boss", LocalAndroidEngine.getArchetypePreset("5")?.id)
        assertEquals("06_ancient_male_noble", LocalAndroidEngine.getArchetypePreset("6")?.id)
        assertEquals("08_antagonist_female_greentea", LocalAndroidEngine.getArchetypePreset("8")?.id)
    }

    @Test
    fun testArchetypeLookup_WhitespacePaddedInputs() {
        assertEquals("04_modern_female_urban", LocalAndroidEngine.getArchetypePreset("  04  ")?.id)
        assertEquals("05_modern_male_boss", LocalAndroidEngine.getArchetypePreset("\t05_modern_male_boss\n")?.id)
        assertEquals("06_ancient_male_noble", LocalAndroidEngine.getArchetypePreset(" 6 ")?.id)
        assertEquals("08_antagonist_female_greentea", LocalAndroidEngine.getArchetypePreset("   08   ")?.id)
    }

    @Test
    fun testArchetypeLookup_ChineseNameAndSubstrings() {
        // Full canonical names
        assertEquals("04_modern_female_urban", LocalAndroidEngine.getArchetypePreset("现代女主-都市丽人")?.id)
        assertEquals("05_modern_male_boss", LocalAndroidEngine.getArchetypePreset("现代男主-霸总")?.id)
        assertEquals("06_ancient_male_noble", LocalAndroidEngine.getArchetypePreset("古装男主-清冷世子")?.id)
        assertEquals("08_antagonist_female_greentea", LocalAndroidEngine.getArchetypePreset("反派女二-绿茶千金")?.id)

        // Substrings
        assertEquals("04_modern_female_urban", LocalAndroidEngine.getArchetypePreset("都市丽人")?.id)
        assertEquals("04_modern_female_urban", LocalAndroidEngine.getArchetypePreset("现代女主")?.id)
        assertEquals("05_modern_male_boss", LocalAndroidEngine.getArchetypePreset("霸总")?.id)
        assertEquals("06_ancient_male_noble", LocalAndroidEngine.getArchetypePreset("清冷世子")?.id)
        assertEquals("06_ancient_male_noble", LocalAndroidEngine.getArchetypePreset("世子")?.id)
        assertEquals("08_antagonist_female_greentea", LocalAndroidEngine.getArchetypePreset("绿茶千金")?.id)
        assertEquals("08_antagonist_female_greentea", LocalAndroidEngine.getArchetypePreset("绿茶")?.id)
    }

    @Test
    fun testArchetypeLookup_NonExistentAndEdgeInputs_ReturnNullSafely() {
        val nonExistentInputs = listOf(
            null,
            "",
            "   ",
            "\n\t",
            "0",
            "00",
            "01",
            "02",
            "03",
            "07",
            "09",
            "10",
            "99",
            "random_string_xyz",
            "non_existent_hero",
            "路人甲",
            "仙帝尊者",
            "深渊魔皇",
            "12345"
        )
        for (input in nonExistentInputs) {
            val result = LocalAndroidEngine.getArchetypePreset(input)
            assertNull("Expected null for invalid input: '$input'", result)
        }
    }

    // ==========================================
    // 3. Prompt Compilation Stress Tests
    // ==========================================

    @Test
    fun testTurnaroundPrompt_WithPreExistingPrompt_PreservedVerbatim() {
        val customPrompt = "EXACT CUSTOM PRE-EXISTING TURNAROUND PROMPT FOR HERO 123"
        val char = CharacterItem(
            name = "主角A",
            turnaround_prompt = customPrompt,
            consistency_card = ConsistencyCardItem(facial_lock = "ignored because prompt is set")
        )
        val compiled = LocalAndroidEngine.buildCharacterTurnaroundPrompt(char)
        assertEquals(customPrompt, compiled)
    }

    @Test
    fun testTurnaroundPrompt_WithFullConsistencyLocks_IncludesAllLocksAndSpecs() {
        val char = CharacterItem(
            name = "林婉儿",
            consistency_card = ConsistencyCardItem(
                facial_lock = "delicate porcelain skin, almond eyes",
                hair_lock = "long jet-black hair with silk ribbon",
                costume_lock = "embroidered sky-blue Hanfu robes",
                exclusive_negative_prompt = "modern clothes"
            )
        )
        val compiled = LocalAndroidEngine.buildCharacterTurnaroundPrompt(char)
        assertTrue(compiled.contains("Character model turnaround sheet of 林婉儿"))
        assertTrue(compiled.contains("pure plain white cyclorama studio background"))
        assertTrue(compiled.contains("delicate porcelain skin, almond eyes"))
        assertTrue(compiled.contains("long jet-black hair with silk ribbon"))
        assertTrue(compiled.contains("embroidered sky-blue Hanfu robes"))
        assertTrue(compiled.contains("85mm portrait prime lens"))
        assertTrue(compiled.contains("8k resolution"))
        assertTrue(compiled.contains("proportions strictly preserved"))
    }

    @Test
    fun testTurnaroundPrompt_WithoutLocks_FallsBackToTraitsAndAnchor() {
        val char = CharacterItem(
            name = "无锁主角",
            traits = "坚毅果敢特警队长",
            visual_anchor = "深黑色战术背心与作战军靴"
        )
        val compiled = LocalAndroidEngine.buildCharacterTurnaroundPrompt(char)
        assertTrue(compiled.contains("无锁主角"))
        assertTrue(compiled.contains("深黑色战术背心与作战军靴, 坚毅果敢特警队长"))
        assertTrue(compiled.contains("pure plain white cyclorama studio background"))
    }

    @Test
    fun testTurnaroundPrompt_CompletelyEmptyCharacter_GracefulBaselineFallback() {
        val emptyChar = CharacterItem()
        val compiled = LocalAndroidEngine.buildCharacterTurnaroundPrompt(emptyChar)
        assertTrue(compiled.contains("Character model turnaround sheet of protagonist"))
        assertTrue(compiled.contains("authentic Asian actor, high-end editorial cosmetics"))
        assertTrue(compiled.contains("pure plain white cyclorama studio background"))
    }

    @Test
    fun testConsistencyPrompt_FullLocksAndExclusiveNegative() {
        val char = CharacterItem(
            name = "傅沉渊",
            consistency_card = ConsistencyCardItem(
                facial_lock = "sculpted jawline, piercing narrow eyes",
                hair_lock = "slicked back side-part",
                costume_lock = "midnight-navy three-piece suit",
                exclusive_negative_prompt = "boyish face, casual clothes"
            )
        )
        val (pos, neg) = LocalAndroidEngine.compileCharacterConsistencyPrompt(
            character = char,
            shotScale = "extreme_close_up",
            emotionAction = "clenching fists with cold fury"
        )

        // Positive check: scale underscore replaced, camera spec, actor name, locks, emotion
        assertTrue(pos.contains("ARRI Alexa 65"))
        assertTrue(pos.contains("35mm Panavision anamorphic lens"))
        assertTrue(pos.contains("extreme close up"))
        assertTrue(pos.contains("傅沉渊"))
        assertTrue(pos.contains("sculpted jawline, piercing narrow eyes"))
        assertTrue(pos.contains("slicked back side-part"))
        assertTrue(pos.contains("midnight-navy three-piece suit"))
        assertTrue(pos.contains("clenching fists with cold fury"))
        assertTrue(pos.contains("vertical 9:16"))

        // Negative check: universal base + exclusive negative
        assertTrue(neg.contains("cartoon, anime, 3d render"))
        assertTrue(neg.contains("boyish face, casual clothes"))
    }

    @Test
    fun testConsistencyPrompt_EmptyExclusiveNegative_UniversalNegativeClean() {
        val char = CharacterItem(
            name = "普通角色",
            consistency_card = ConsistencyCardItem(
                facial_lock = "simple facial lock",
                exclusive_negative_prompt = ""
            )
        )
        val (pos, neg) = LocalAndroidEngine.compileCharacterConsistencyPrompt(char)
        assertTrue(neg.startsWith("cartoon, anime"))
        assertFalse("Should not end with trailing comma or space", neg.endsWith(","))
    }

    // ==========================================
    // 4. Character Creation & Apply Stress Tests
    // ==========================================

    @Test
    fun testApplyArchetype_InvalidId_ReturnsOriginalUnmodified() {
        val original = CharacterItem(name = "原始人", role = "路人甲", voice = "原声")
        val result = LocalAndroidEngine.applyArchetypeToCharacter(original, "invalid_archetype_xyz")
        assertSame(original, result)
        assertEquals("原始人", result.name)
        assertEquals("路人甲", result.role)
    }

    @Test
    fun testCreateCharacter_InvalidId_ThrowsIllegalArgumentException() {
        try {
            LocalAndroidEngine.createCharacterFromArchetype("invalid_id_999")
            fail("Expected IllegalArgumentException for unknown archetype id")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message?.contains("未找到指定人设母版") == true)
        }
    }

    @Test
    fun testCreateCharacter_ValidIdWithCustomName() {
        val char = LocalAndroidEngine.createCharacterFromArchetype("08", "白楚楚")
        assertEquals("白楚楚", char.name)
        assertEquals("反派女二", char.role)
        assertEquals("08_antagonist_female_greentea", char.archetype)
        assertEquals("晓伊 (娇嗲千金女声)", char.voice)
        assertTrue(char.consistency_card.facial_lock.contains("heart-shaped Asian face"))
        assertTrue(char.turnaround_prompt.contains("23-year-old deceptively innocent Chinese wealthy heiress"))
    }

    @Test
    fun testCreateCharacter_ValidIdWithoutCustomName_UsesDefaultArchetypeName() {
        val char = LocalAndroidEngine.createCharacterFromArchetype("04_modern_female_urban")
        assertEquals("都市丽人", char.name)
        assertEquals("女主角", char.role)
        assertEquals("04_modern_female_urban", char.archetype)
    }
}
