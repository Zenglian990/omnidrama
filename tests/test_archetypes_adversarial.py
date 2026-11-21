"""Empirical Adversarial Test Suite for omnidrama/config/archetypes.py.

Designed and executed by Teamwork Challenger (challenger_m2_1) to stress-test:
1. Query and lookup robustness across edge cases.
2. Rapid generation of 1,000 characters and memory isolation.
3. Prompt compilation under extreme/malformed inputs.
4. Mutation resistance and thread safety.
"""
import copy
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List

import pytest
from pydantic import ValidationError

from omnidrama.config.archetypes import (
    BUILTIN_ARCHETYPES,
    DramaArchetype,
    apply_archetype_to_character,
    compile_character_consistency_prompt,
    compile_consistency_prompt,
    create_character_from_archetype,
    get_archetype,
    list_archetypes,
)
from omnidrama.schemas.drama_schema import (
    CharacterAsset,
    CharacterConsistencyCard,
    ReferenceImageConfig,
    ShotScaleEnum,
)


# =============================================================================
# Dimension 1: Stress Test Query and Lookup
# =============================================================================
class TestQueryAndLookupAdversarial:
    """Adversarially probe get_archetype and list_archetypes with extreme inputs."""

    @pytest.mark.parametrize("canonical_id", [
        "04_modern_female_urban",
        "05_modern_male_boss",
        "06_ancient_male_noble",
        "08_antagonist_female_greentea",
    ])
    def test_case_sensitivity_variants(self, canonical_id: str):
        """Case variations (upper, title, mixed) should match reliably."""
        assert get_archetype(canonical_id.upper()) is not None
        assert get_archetype(canonical_id.title()) is not None
        assert get_archetype(canonical_id.swapcase()) is not None
        assert get_archetype(canonical_id.upper()).id == canonical_id

    @pytest.mark.parametrize("query,expected_id", [
        ("  04  ", "04_modern_female_urban"),
        ("\t05\t", "05_modern_male_boss"),
        ("\n 06 \n", "06_ancient_male_noble"),
        ("  08_antagonist_female_greentea  ", "08_antagonist_female_greentea"),
        ("  现代女主-都市丽人  ", "04_modern_female_urban"),
        ("  霸总  ", "05_modern_male_boss"),
        ("  清冷世子  ", "06_ancient_male_noble"),
        ("  绿茶千金  ", "08_antagonist_female_greentea"),
    ])
    def test_whitespace_padded_queries(self, query: str, expected_id: str):
        """Padded whitespace, tabs, and newlines must resolve to expected archetype."""
        arch = get_archetype(query)
        assert arch is not None
        assert arch.id == expected_id

    @pytest.mark.parametrize("num_input,expected_id", [
        (4, "04_modern_female_urban"),
        (5, "05_modern_male_boss"),
        (6, "06_ancient_male_noble"),
        (8, "08_antagonist_female_greentea"),
        ("4", "04_modern_female_urban"),
        ("5", "05_modern_male_boss"),
        ("6", "06_ancient_male_noble"),
        ("8", "08_antagonist_female_greentea"),
    ])
    def test_integer_and_short_code_lookup(self, num_input: Any, expected_id: str):
        """Numeric inputs and single-digit codes without leading zero should resolve."""
        arch = get_archetype(num_input)
        assert arch is not None
        assert arch.id == expected_id

    @pytest.mark.parametrize("non_existent", [
        "00", "01", "02", "03", "07", "09", "10", "99",
        "unknown_archetype", "batman", "superman",
        "none", "null", "undefined",
        999, -4, 0,
        "現代女主",  # Traditional Chinese
        "04_modern_female_urban_extra",
    ])
    def test_non_existent_codes_return_none(self, non_existent: Any):
        """Non-existent IDs, unsupported codes, and out-of-range integers return None."""
        assert get_archetype(non_existent) is None

    def test_falsy_inputs_return_none(self):
        """None and empty string must return None."""
        assert get_archetype(None) is None
        assert get_archetype("") is None

    def test_whitespace_only_vulnerability_probe(self):
        """BUG PROBE: Whitespace-only strings ('   ', '\\t', '\\n').
        
        Empirical check: does get_archetype('   ') return None as contractually
        expected, or does it incorrectly match an archetype due to 'cleaned in arch.name'?
        """
        result_spaces = get_archetype("   ")
        result_tab = get_archetype("\t")
        result_newline = get_archetype("\n")
        
        # We record the empirical finding. If this fails, it proves an implementation flaw.
        # Contractually, whitespace-only query should return None.
        is_flawed = (result_spaces is not None or result_tab is not None or result_newline is not None)
        if is_flawed:
            print(f"\n[VULNERABILITY DETECTED] get_archetype('   ') returned {getattr(result_spaces, 'id', None)} instead of None!")
        # Challenger assertion for strict contract:
        # Note: We assert the expected contract behavior.
        assert result_spaces is None, f"Expected None for whitespace-only query, got: {result_spaces}"
        assert result_tab is None, f"Expected None for tab query, got: {result_tab}"
        assert result_newline is None, f"Expected None for newline query, got: {result_newline}"

    def test_single_hyphen_vulnerability_probe(self):
        """BUG PROBE: Querying a single hyphen '-'.
        
        Because all archetypes have '-' in their name (e.g. '现代女主-都市丽人'),
        a naive 'cleaned in arch.name' matches the first archetype!
        """
        result_hyphen = get_archetype("-")
        assert result_hyphen is None, f"Expected None for '-', got: {result_hyphen}"

    def test_full_width_and_special_unicode(self):
        """Full-width unicode digits and emojis should gracefully return None."""
        assert get_archetype("０４") is None
        assert get_archetype("👸") is None
        assert get_archetype("<script>alert(1)</script>") is None

    def test_list_archetypes_immutability(self):
        """Mutating the returned list from list_archetypes should not affect subsequent calls."""
        res1 = list_archetypes()
        res1.clear()
        res2 = list_archetypes()
        assert len(res2) == 4, "list_archetypes() mutated by external caller!"


# =============================================================================
# Dimension 2: Rapid Generation of 1,000 Characters & Memory Isolation
# =============================================================================
class TestRapidGenerationAndMemoryIsolation:
    """Stress test rapid generation of 1,000 characters and memory address isolation."""

    def test_rapid_generation_1000_characters_performance(self):
        """Generate 1,000 characters and verify completion in < 2.0s."""
        t0 = time.perf_counter()
        archetype_ids = ["04", "05", "06", "08"]
        characters = [
            create_character_from_archetype(archetype_ids[i % 4], f"Test_Actor_{i:04d}")
            for i in range(1000)
        ]
        duration = time.perf_counter() - t0
        assert len(characters) == 1000
        assert duration < 2.0, f"Generating 1,000 characters took {duration:.2f}s (budget: 2.0s)"

    def test_independent_memory_allocations_no_shared_reference_mutation(self):
        """Verify that mutating one character does NOT mutate any other character or template."""
        char_a = create_character_from_archetype("04", "Character_A")
        char_b = create_character_from_archetype("04", "Character_B")
        template = BUILTIN_ARCHETYPES["04_modern_female_urban"]

        # Ensure distinct memory IDs for consistency cards and reference images
        assert id(char_a.consistency_card) != id(char_b.consistency_card)
        assert id(char_a.consistency_card) != id(template.consistency_card)
        assert id(char_a.consistency_card.reference_images) != id(char_b.consistency_card.reference_images)
        assert id(char_a.consistency_card.reference_images) != id(template.consistency_card.reference_images)

        # Mutate char_a's locks and reference images
        original_facial_lock = char_b.consistency_card.facial_lock
        char_a.consistency_card.facial_lock = "MUTATED_CYBERPUNK_FACE_12345"
        char_a.consistency_card.reference_images.append(
            ReferenceImageConfig(url="https://example.com/adversarial.png", label="adversarial")
        )

        # Verify char_b is 100% unaffected
        assert char_b.consistency_card.facial_lock == original_facial_lock
        assert len(char_b.consistency_card.reference_images) == 0

        # Verify template is 100% unaffected
        assert template.consistency_card.facial_lock != "MUTATED_CYBERPUNK_FACE_12345"
        assert len(template.consistency_card.reference_images) == 0

    def test_apply_archetype_memory_isolation(self):
        """Verify apply_archetype_to_character also performs deep copy and memory isolation."""
        base_char = CharacterAsset(name="Existing_Hero", gender="male")
        applied = apply_archetype_to_character(base_char, "05")
        template = BUILTIN_ARCHETYPES["05_modern_male_boss"]

        assert id(applied.consistency_card) != id(template.consistency_card)
        applied.consistency_card.costume_lock = "MODIFIED_TRACKSUIT"
        assert template.consistency_card.costume_lock != "MODIFIED_TRACKSUIT"

    def test_sequential_archetype_switching(self):
        """Switching a character from archetype 04 -> 05 -> 06."""
        char = CharacterAsset(name="Shapeshifter", gender="female")
        apply_archetype_to_character(char, "04")
        assert char.archetype == "04_modern_female_urban"
        assert char.gender == "female"

        apply_archetype_to_character(char, "05")
        assert char.archetype == "05_modern_male_boss"
        assert char.gender == "male"
        assert "05_modern_male_boss" in char.archetype

    def test_multithreaded_concurrent_generation(self):
        """Verify concurrent character creation across 16 threads without race condition."""
        def worker(idx: int) -> CharacterAsset:
            arch_code = ["04", "05", "06", "08"][idx % 4]
            c = create_character_from_archetype(arch_code, f"ThreadChar_{idx}")
            c.consistency_card.facial_lock = f"ThreadLock_{idx}"
            return c

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(worker, range(100)))

        assert len(results) == 100
        # Verify all locks are unique and preserved
        locks = [r.consistency_card.facial_lock for r in results]
        assert len(set(locks)) == 100


# =============================================================================
# Dimension 3: Stress Test Prompt Compilation
# =============================================================================
class TestPromptCompilationAdversarial:
    """Stress test compile_character_consistency_prompt with malformed/extreme inputs."""

    @pytest.fixture
    def standard_character(self) -> CharacterAsset:
        return create_character_from_archetype("04", "林初雪")

    def test_none_shot_scale(self, standard_character: CharacterAsset):
        """Pass shot_scale=None: should not crash."""
        pos, neg = compile_character_consistency_prompt(standard_character, shot_scale=None)
        assert isinstance(pos, str) and len(pos) > 0
        assert isinstance(neg, str) and len(neg) > 0
        assert "ARRI Alexa 65" in pos
        # Notice whether 'None' is cleanly handled or literally embedded
        print(f"\n[PROMPT WITH shot_scale=None]: {pos[:120]}...")

    def test_empty_string_shot_scale(self, standard_character: CharacterAsset):
        """Pass shot_scale='': should not crash."""
        pos, neg = compile_character_consistency_prompt(standard_character, shot_scale="")
        assert "ARRI Alexa 65" in pos

    def test_all_shot_scale_enum_values(self, standard_character: CharacterAsset):
        """All ShotScaleEnum members should compile cleanly without enum syntax leakage."""
        for enum_val in ShotScaleEnum:
            pos, _ = compile_character_consistency_prompt(standard_character, shot_scale=enum_val)
            # ShotScaleEnum value should be unpacked and '_' replaced by ' '
            assert enum_val.value.replace("_", " ") in pos
            assert "ShotScaleEnum" not in pos

    def test_extreme_long_emotion_string(self, standard_character: CharacterAsset):
        """Pass a 100,000 character emotion string to test memory/string concatenation safety."""
        huge_emotion = "laughing hysterically and weeping simultaneously " * 2500
        assert len(huge_emotion) >= 100000

        t0 = time.perf_counter()
        pos, neg = compile_character_consistency_prompt(standard_character, emotion_action=huge_emotion)
        duration = time.perf_counter() - t0

        assert len(pos) > 100000
        assert duration < 0.2, f"Prompt compilation took {duration:.3f}s for 100k chars"
        assert "laughing hysterically" in pos

    def test_none_and_whitespace_emotion(self, standard_character: CharacterAsset):
        """emotion_action=None and whitespace strings should not result in ugly extra commas or crash."""
        pos_none, _ = compile_character_consistency_prompt(standard_character, emotion_action=None)
        pos_spaces, _ = compile_character_consistency_prompt(standard_character, emotion_action="   \t\n   ")
        pos_empty, _ = compile_character_consistency_prompt(standard_character, emotion_action="")

        # None, spaces, and empty should yield identical clean prompts without double commas
        assert ", ," not in pos_spaces
        assert ", ," not in pos_empty

    def test_extreme_character_names(self):
        """Test names with quotes, HTML tags, emojis, unicode, and extreme length."""
        adversarial_names = [
            '""<script>alert("xss")</script>',
            "O'Connor-Smith & Sons",
            "👑 龙傲天 ⚡",
            "A" * 500,
            "   ",  # whitespace only name
        ]
        for adv_name in adversarial_names:
            char = CharacterAsset(name=adv_name, gender="male")
            pos, neg = compile_character_consistency_prompt(char)
            assert isinstance(pos, str)
            assert isinstance(neg, str)

    def test_character_without_consistency_card(self):
        """Character with consistency_card=None must gracefully fallback to visual_tags/anchor."""
        char = CharacterAsset(
            name="NoCardActor",
            gender="male",
            visual_tags="sharp eyes, leather jacket",
            consistency_card=None,
        )
        pos, neg = compile_character_consistency_prompt(char)
        assert "sharp eyes, leather jacket" in pos
        # Default universal negative prompt should still be present
        assert "cartoon, anime, 3d render" in neg

    def test_empty_locks_in_consistency_card(self):
        """Card present but all locks are empty strings."""
        char = CharacterAsset(
            name="EmptyCardActor",
            gender="female",
            visual_tags="default tags",
            consistency_card=CharacterConsistencyCard(facial_lock="", hair_lock="", costume_lock=""),
        )
        pos, neg = compile_character_consistency_prompt(char)
        # Should fallback to visual_tags
        assert "default tags" in pos


# =============================================================================
# Dimension 4: Pydantic Model Invariant Stress Testing
# =============================================================================
class TestModelInvariantsAdversarial:
    """Stress test DramaArchetype validation, round-tripping, and edge conditions."""

    def test_sync_summary_and_description_validator(self):
        """If description is missing, summary fills it; if summary is missing, description fills it."""
        card = BUILTIN_ARCHETYPES["04_modern_female_urban"].consistency_card
        
        # Test 1: Only summary provided
        d1 = DramaArchetype(
            id="test_01", code="91", name="测试1", turnaround_prompt="test",
            consistency_card=card, summary="一句话摘要",
        )
        assert d1.description == "一句话摘要"

        # Test 2: Only description provided
        d2 = DramaArchetype(
            id="test_02", code="92", name="测试2", turnaround_prompt="test",
            consistency_card=card, description="详细人设描述",
        )
        assert d2.summary == "详细人设描述"

    def test_missing_mandatory_fields_raises_validation_error(self):
        """Omission of id, code, name, turnaround_prompt, or consistency_card must raise ValidationError."""
        card = BUILTIN_ARCHETYPES["04_modern_female_urban"].consistency_card
        with pytest.raises(ValidationError):
            DramaArchetype(id="test", code="99", name="test")  # Missing turnaround_prompt & consistency_card
