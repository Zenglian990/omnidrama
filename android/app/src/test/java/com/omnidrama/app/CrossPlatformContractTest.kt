package com.omnidrama.app

import com.google.gson.Gson
import com.google.gson.JsonSyntaxException
import com.omnidrama.app.data.model.CharacterItem
import com.omnidrama.app.data.model.ConsistencyCardItem
import com.omnidrama.app.data.model.ProjectData
import com.omnidrama.app.data.model.PropItem
import org.junit.Assert.*
import org.junit.Test

class CrossPlatformContractTest {

    private val gson = Gson()

    @Test
    fun testPythonExportedJson_StringRefsPasses() {
        val jsonStringRefs = """
            {
              "title": "盛世宠妻",
              "genre": "都市职场",
              "synopsis": "顾氏集团继承人夺回家族遗产的复仇爽剧",
              "characters": [
                {
                  "name": "顾清雪",
                  "gender": "female",
                  "archetype": "04_modern_female_urban",
                  "turnaround_prompt": "Character turnaround sheet of 顾清雪...",
                  "turnaround_image": "https://example.com/turnaround_gu.png",
                  "consistency_card": {
                    "facial_lock": "delicate porcelain skin, almond eyes",
                    "hair_lock": "long wavy jet-black hair",
                    "costume_lock": "tailored oatmeal-white blazer",
                    "exclusive_negative_prompt": "chubby cheeks, cartoon",
                    "reference_images": [
                      "https://example.com/face.jpg",
                      "https://example.com/dress.jpg"
                    ]
                  }
                }
              ],
              "shots": [
                {
                  "id": 1,
                  "speaker": "顾清雪",
                  "scale": "close_up",
                  "motion": "zoom_in",
                  "motion_name": "镜头推进",
                  "dialogue": "这玉玺，是我顾家之物。",
                  "image": "",
                  "audio": "",
                  "sfx": "",
                  "visual_prompt": "ARRI Alexa 65, close up of 顾清雪 holding 传家玉玺",
                  "prop_refs": ["传家玉玺"]
                }
              ],
              "props": [
                {
                  "name": "传家玉玺",
                  "category": "imperial_seal",
                  "description": "千年温润和田玉",
                  "visual_tags": "warm white jade, dragon carving",
                  "feature_lock": "translucent jade luster with gold inlays",
                  "turnaround_prompt": "Prop turnaround sheet of 传家玉玺",
                  "negative_prompt": "plastic, modern metal",
                  "reference_images": [
                    "https://example.com/prop_ref.jpg"
                  ]
                }
              ]
            }
        """.trimIndent()

        val project = gson.fromJson(jsonStringRefs, ProjectData::class.java)
        assertNotNull(project)
        assertEquals("盛世宠妻", project.title)
        assertEquals(1, project.characters.size)
        assertEquals(1, project.props.size)
        assertEquals(1, project.shots.size)

        val c = project.characters[0]
        assertEquals("顾清雪", c.name)
        assertEquals("04_modern_female_urban", c.archetype)
        assertEquals("delicate porcelain skin, almond eyes", c.safe_consistency_card.facial_lock)
        assertEquals(2, c.safe_consistency_card.reference_images.size)

        val p = project.props[0]
        assertEquals("传家玉玺", p.name)
        assertEquals("translucent jade luster with gold inlays", p.feature_lock)
        assertEquals(1, p.reference_images.size)
    }

    @Test
    fun testPythonExportedJson_WithStructuredReferenceImageObjects() {
        val jsonWithObjectRefs = """
            {
              "title": "盛世宠妻",
              "characters": [
                {
                  "name": "顾清雪",
                  "consistency_card": {
                    "facial_lock": "delicate porcelain skin, almond eyes",
                    "reference_images": [
                      {
                        "url": "https://example.com/face.jpg",
                        "role": "face",
                        "weight": 1.0
                      }
                    ]
                  }
                }
              ]
            }
        """.trimIndent()

        try {
            val project = gson.fromJson(jsonWithObjectRefs, ProjectData::class.java)
            fail("Expected JsonSyntaxException when reference_images contains objects")
        } catch (e: JsonSyntaxException) {
            println("Verified: Gson throws JsonSyntaxException as expected: ${e.message}")
            assertTrue(e.message?.contains("Expected a string but was BEGIN_OBJECT") == true)
        }
    }

    @Test
    fun testPythonExportedJson_ShotFieldMismatchHandling() {
        // Python schema DramaProject exports shot_id, shot_scale, camera_motion, image_path, audio_path
        // Whereas Android ShotItem expects id, scale, motion, motion_name, image, audio
        val pythonShotJson = """
            {
              "title": "盛世宠妻",
              "shots": [
                {
                  "shot_id": 1,
                  "shot_scale": "close_up",
                  "camera_motion": "zoom_in",
                  "speaker": "顾清雪",
                  "dialogue": "台词",
                  "visual_prompt": "prompt",
                  "prop_refs": ["传家玉玺"]
                }
              ]
            }
        """.trimIndent()

        val project = gson.fromJson(pythonShotJson, ProjectData::class.java)
        assertNotNull(project)
        assertEquals(1, project.shots.size)
        val shot = project.shots[0]
        // Note: shot.id is 0 because JSON had shot_id instead of id
        assertEquals(0, shot.id)
        // Note: shot.scale and shot.motion are null because JSON had shot_scale and camera_motion
        assertNull(shot.scale)
        assertNull(shot.motion)
    }
}
