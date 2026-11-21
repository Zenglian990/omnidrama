package com.omnidrama.app

import com.google.gson.Gson
import com.omnidrama.app.data.local.LocalAndroidEngine
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ConsistencyCardItem
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.PropItem
import org.junit.Assert.*
import org.junit.Test

class LocalAndroidConsistencyTest {

    private val gson = Gson()

    @Test
    fun testLegacyCharacterItemDeserialization_DefaultsPreserved() {
        val legacyJson = """
            {
                "name": "林清雪",
                "role": "女主角",
                "voice": "晓涵 (温柔清纯甜美)",
                "avatar": "",
                "traits": "职场丽人",
                "visual_anchor": "燕麦白双排扣西装"
            }
        """.trimIndent()

        val char = gson.fromJson(legacyJson, CharacterItem::class.java)
        assertEquals("林清雪", char.name)
        assertEquals("女主角", char.role)
        assertEquals("", char.archetype)
        assertEquals("", char.turnaround_prompt)
        assertEquals("", char.turnaround_image)
        assertNotNull(char.consistency_card)
        assertEquals("", char.consistency_card.facial_lock)
        assertEquals("", char.safe_consistency_card.facial_lock)
    }

    @Test
    fun testExplicitNullConsistencyCard_SafeAccessorHandlesNull() {
        val jsonWithNullCard = """
            {
                "name": "萧天",
                "role": "男主角",
                "voice": "云希 (磁性霸总男声)",
                "avatar": "",
                "traits": "顶级财阀",
                "archetype": "05_modern_male_boss",
                "turnaround_prompt": "turnaround prompt",
                "turnaround_image": "/path/img.jpg",
                "consistency_card": null
            }
        """.trimIndent()

        val char = gson.fromJson(jsonWithNullCard, CharacterItem::class.java)
        assertEquals("萧天", char.name)
        assertEquals("05_modern_male_boss", char.archetype)
        // safe_consistency_card must never return null
        val safeCard = char.safe_consistency_card
        assertNotNull(safeCard)
        assertEquals("", safeCard.facial_lock)
        assertEquals("", safeCard.hair_lock)
    }

    @Test
    fun testFullCharacterItemSerializationRoundTrip() {
        val original = CharacterItem(
            name = "林清雪",
            role = "核心女主",
            voice = "晓晓 (知性独立女声)",
            avatar = "https://example.com/avatar.jpg",
            traits = "26岁职场精英独立女性",
            visual_anchor = "鹅蛋骨相脸，燕麦白双排扣西装",
            archetype = "04_modern_female_urban",
            turnaround_prompt = "Character model turnaround sheet of modern urban chic female",
            turnaround_image = "/data/local/turnaround_linqingxue.jpg",
            consistency_card = ConsistencyCardItem(
                facial_lock = "delicate Asian oval face",
                hair_lock = "clavicle-grazing wavy lob",
                costume_lock = "tailored oatmeal-white blazer",
                exclusive_negative_prompt = "childish round face, chubby cheeks",
                reference_images = listOf("ref1.png", "ref2.png")
            )
        )

        val json = gson.toJson(original)
        val deserialized = gson.fromJson(json, CharacterItem::class.java)

        assertEquals(original.name, deserialized.name)
        assertEquals(original.role, deserialized.role)
        assertEquals(original.voice, deserialized.voice)
        assertEquals(original.avatar, deserialized.avatar)
        assertEquals(original.traits, deserialized.traits)
        assertEquals(original.visual_anchor, deserialized.visual_anchor)
        assertEquals(original.archetype, deserialized.archetype)
        assertEquals(original.turnaround_prompt, deserialized.turnaround_prompt)
        assertEquals(original.turnaround_image, deserialized.turnaround_image)
        assertEquals(original.consistency_card.facial_lock, deserialized.consistency_card.facial_lock)
        assertEquals(original.consistency_card.hair_lock, deserialized.consistency_card.hair_lock)
        assertEquals(original.consistency_card.costume_lock, deserialized.consistency_card.costume_lock)
        assertEquals(original.consistency_card.exclusive_negative_prompt, deserialized.consistency_card.exclusive_negative_prompt)
        assertEquals(2, deserialized.consistency_card.reference_images.size)
    }

    @Test
    fun testProjectDataWithPropsSerialization() {
        val prop = PropItem(
            name = "龙王令",
            category = "信物",
            description = "号令十万修罗的玄铁令牌",
            visual_tags = "黑曜玄铁, 盘龙纹路, 幽蓝微光",
            feature_lock = "九爪金龙浮雕, 磨砂黑曜石质感",
            turnaround_prompt = "Prop model turnaround sheet of ancient dragon token on white background",
            negative_prompt = "plastic, cheap toy",
            reference_images = listOf("prop_ref.jpg")
        )

        val project = ProjectData(
            title = "修罗殿归位",
            genre = "战神归来",
            characters = listOf(CharacterItem(name = "萧天", role = "男主角")),
            props = listOf(prop)
        )

        val json = gson.toJson(project)
        val deserialized = gson.fromJson(json, ProjectData::class.java)

        assertEquals("修罗殿归位", deserialized.title)
        assertEquals(1, deserialized.characters.size)
        assertEquals(1, deserialized.props.size)
        val p = deserialized.props[0]
        assertEquals("龙王令", p.name)
        assertEquals("信物", p.category)
        assertEquals("九爪金龙浮雕, 磨砂黑曜石质感", p.feature_lock)
        assertEquals("Prop model turnaround sheet of ancient dragon token on white background", p.turnaround_prompt)
    }

    @Test
    fun testCanonicalArchetypesCatalogIntegrity() {
        val presets = LocalAndroidEngine.ARCHETYPE_PRESETS
        assertEquals(4, presets.size)

        val ids = presets.map { it.id }.toSet()
        assertTrue(ids.contains("04_modern_female_urban"))
        assertTrue(ids.contains("05_modern_male_boss"))
        assertTrue(ids.contains("06_ancient_male_noble"))
        assertTrue(ids.contains("08_antagonist_female_greentea"))

        for (preset in presets) {
            assertTrue(preset.code.isNotBlank())
            assertTrue(preset.name.isNotBlank())
            assertTrue(preset.voiceName.isNotBlank())
            assertTrue(preset.turnaroundPrompt.isNotBlank())
            assertTrue(preset.consistencyCard.facial_lock.isNotBlank())
            assertTrue(preset.consistencyCard.hair_lock.isNotBlank())
            assertTrue(preset.consistencyCard.costume_lock.isNotBlank())
            assertTrue(preset.consistencyCard.exclusive_negative_prompt.isNotBlank())
        }
    }

    @Test
    fun testArchetypePresetLookup() {
        val p04ById = LocalAndroidEngine.getArchetypePreset("04_modern_female_urban")
        assertNotNull(p04ById)
        assertEquals("04", p04ById!!.code)

        val p04ByCode = LocalAndroidEngine.getArchetypePreset("04")
        assertNotNull(p04ByCode)
        assertEquals("04_modern_female_urban", p04ByCode!!.id)

        val p05BySingleDigit = LocalAndroidEngine.getArchetypePreset("5")
        assertNotNull(p05BySingleDigit)
        assertEquals("05_modern_male_boss", p05BySingleDigit!!.id)

        val p06ByName = LocalAndroidEngine.getArchetypePreset("清冷世子")
        assertNotNull(p06ByName)
        assertEquals("06_ancient_male_noble", p06ByName!!.id)

        val p08ByName = LocalAndroidEngine.getArchetypePreset("绿茶千金")
        assertNotNull(p08ByName)
        assertEquals("08_antagonist_female_greentea", p08ByName!!.id)

        assertNull(LocalAndroidEngine.getArchetypePreset("non_existent_archetype"))
    }

    @Test
    fun testApplyArchetypeToCharacter() {
        val baseChar = CharacterItem(name = "苏晓曼", role = "配角")
        val updated = LocalAndroidEngine.applyArchetypeToCharacter(baseChar, "04_modern_female_urban")

        assertEquals("苏晓曼", updated.name)
        assertEquals("女主角", updated.role)
        assertEquals("04_modern_female_urban", updated.archetype)
        assertEquals("晓晓 (知性独立女声)", updated.voice)
        assertTrue(updated.turnaround_prompt.contains("Character model turnaround sheet"))
        assertTrue(updated.consistency_card.facial_lock.contains("delicate Asian oval face"))
        assertTrue(updated.consistency_card.costume_lock.contains("oatmeal-white"))
    }

    @Test
    fun testCreateCharacterFromArchetype() {
        val char05 = LocalAndroidEngine.createCharacterFromArchetype("05_modern_male_boss", "傅沉渊")
        assertEquals("傅沉渊", char05.name)
        assertEquals("男主角", char05.role)
        assertEquals("05_modern_male_boss", char05.archetype)
        assertEquals("云希 (磁性霸总男声)", char05.voice)
        assertTrue(char05.consistency_card.facial_lock.contains("razor-sharp angular mandibles"))

        val char06 = LocalAndroidEngine.createCharacterFromArchetype("06_ancient_male_noble")
        assertEquals("清冷世子", char06.name)
        assertEquals("男主角", char06.role)
        assertEquals("云健 (清冷孤傲男声)", char06.voice)
        assertTrue(char06.consistency_card.costume_lock.contains("moonlight-white silk flowing Hanfu"))
    }

    @Test
    fun testBuildCharacterTurnaroundPrompt() {
        val charWithoutPrompt = CharacterItem(
            name = "沈清秋",
            traits = "青衫剑客，眉目如画",
            visual_anchor = "青衫玉佩",
            consistency_card = ConsistencyCardItem(
                facial_lock = "classical sword eyebrows",
                costume_lock = "bamboo green silk robe"
            )
        )
        val prompt = LocalAndroidEngine.buildCharacterTurnaroundPrompt(charWithoutPrompt)
        assertTrue(prompt.contains("沈清秋"))
        assertTrue(prompt.contains("pure plain white cyclorama studio background"))
        assertTrue(prompt.contains("classical sword eyebrows"))
        assertTrue(prompt.contains("bamboo green silk robe"))
        assertTrue(prompt.contains("Three full-body standing views"))
    }

    @Test
    fun testCompileCharacterConsistencyPrompt() {
        val char = CharacterItem(
            name = "陆沉",
            consistency_card = ConsistencyCardItem(
                facial_lock = "angular jawline, deep eyes",
                hair_lock = "short fade",
                costume_lock = "charcoal blazer",
                exclusive_negative_prompt = "chubby face, round cheeks"
            )
        )
        val (pos, neg) = LocalAndroidEngine.compileCharacterConsistencyPrompt(
            character = char,
            shotScale = "close up",
            emotionAction = "gazing cold into distance"
        )

        assertTrue(pos.contains("ARRI Alexa 65"))
        assertTrue(pos.contains("close up"))
        assertTrue(pos.contains("陆沉"))
        assertTrue(pos.contains("angular jawline, deep eyes"))
        assertTrue(pos.contains("gazing cold into distance"))
        assertTrue(neg.contains("cartoon, anime"))
        assertTrue(neg.contains("chubby face, round cheeks"))
    }
}
