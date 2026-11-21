"""Empirical Adversarial Verification and Stress Test Suite for Milestone 4 (Android & Web Adaptation - R4).

Written by teamwork_challenger (challenger_m4_2) to empirically stress-test:
1. Canonical archetypes endpoint schema and sorting
2. Archetypes apply input validation, injection resistance, and repeated application idempotency
3. Turnaround generation fallbacks, 16:9 PIL image dimension validation, and path traversal resistance
4. Turnaround GET edge cases (existing, empty, non-existent)
5. Web index.html HTML tag balance, Vue binding contracts, and safe null guards
6. Project story breakdown consistency fields propagation
"""
from pathlib import Path
import re
import urllib.parse
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image

from omnidrama.web.app import app, CharacterModel, ApplyArchetypeRequest, TurnaroundGenerateRequest
from omnidrama.config.archetypes import BUILTIN_ARCHETYPES, get_archetype


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def preserve_current_project():
    """Ensure current_project.json is preserved and restored after tests to prevent state leakage."""
    project_path = Path(__file__).resolve().parent.parent / "output" / "current_project.json"
    backup = None
    if project_path.exists():
        backup = project_path.read_text(encoding="utf-8")
    yield
    if backup is not None:
        project_path.write_text(backup, encoding="utf-8")


# =========================================================================
# 1. Canonical Archetypes Verification
# =========================================================================

def test_canonical_archetypes_endpoint_schema_and_order(client):
    """Verify /api/archetypes returns 4 canonical archetypes strictly ordered and fully specified."""
    res = client.get("/api/archetypes")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 4

    expected_codes = ["04", "05", "06", "08"]
    expected_ids = [
        "04_modern_female_urban",
        "05_modern_male_boss",
        "06_ancient_male_noble",
        "08_antagonist_female_greentea"
    ]

    actual_codes = [arch["code"] for arch in data]
    actual_ids = [arch["id"] for arch in data]

    assert actual_codes == expected_codes
    assert actual_ids == expected_ids

    required_fields = [
        "id", "code", "name", "genre_category", "gender", "role_type",
        "summary", "description", "voice_name", "voice_display",
        "visual_anchor", "visual_tags", "turnaround_prompt",
        "consistency_card", "generation_params"
    ]

    for arch in data:
        for field in required_fields:
            assert field in arch, f"Field '{field}' missing in archetype {arch.get('id')}"
            assert arch[field] is not None, f"Field '{field}' is None in archetype {arch.get('id')}"

        card = arch["consistency_card"]
        assert isinstance(card, dict)
        for lock in ["facial_lock", "hair_lock", "costume_lock", "exclusive_negative_prompt"]:
            assert lock in card
            assert isinstance(card[lock], str)
            assert len(card[lock].strip()) > 0, f"Lock '{lock}' is empty in archetype {arch['id']}"


# =========================================================================
# 2. Adversarial Input Stress for /api/archetypes/apply
# =========================================================================

@pytest.mark.parametrize("invalid_id", [
    "invalid_archetype_xyz",
    "00_unknown",
    "99_non_existent",
    "../../etc/passwd",
    "<script>alert(1)</script>",
    "04; DROP TABLE characters;",
    " ",
    "None",
    "04_modern_female_urban_extra_tail"
])
def test_apply_archetype_invalid_id_returns_404(client, invalid_id):
    """Verify applying an invalid or malicious archetype ID cleanly returns 404 without crashing."""
    payload = {
        "character_name": "测试角色_安全边界",
        "archetype_id": invalid_id
    }
    res = client.post("/api/archetypes/apply", json=payload)
    assert res.status_code == 404
    assert "未找到人设母版" in res.json()["detail"]


def test_apply_archetype_missing_payload_returns_422(client):
    """Verify schema validation returns 422 for missing required fields."""
    res1 = client.post("/api/archetypes/apply", json={})
    assert res1.status_code == 422

    res2 = client.post("/api/archetypes/apply", json={"character_name": "仅有名字"})
    assert res2.status_code == 422

    res3 = client.post("/api/archetypes/apply", json={"archetype_id": "04_modern_female_urban"})
    assert res3.status_code == 422


def test_apply_archetype_repeated_in_place_updates_no_duplicates(client):
    """Verify switching archetypes multiple times updates the character in place without duplicating."""
    char_name = "多重套用测试角色"

    # Step 1: Apply 04
    r1 = client.post("/api/archetypes/apply", json={"character_name": char_name, "archetype_id": "04_modern_female_urban"})
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["character"]["archetype"] == "04_modern_female_urban"

    # Step 2: Apply 05
    r2 = client.post("/api/archetypes/apply", json={"character_name": char_name, "archetype_id": "05_modern_male_boss"})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["character"]["archetype"] == "05_modern_male_boss"

    # Step 3: Apply 06
    r3 = client.post("/api/archetypes/apply", json={"character_name": char_name, "archetype_id": "06_ancient_male_noble"})
    assert r3.status_code == 200
    data3 = r3.json()
    assert data3["character"]["archetype"] == "06_ancient_male_noble"

    # Step 4: Apply 08
    r4 = client.post("/api/archetypes/apply", json={"character_name": char_name, "archetype_id": "08_antagonist_female_greentea"})
    assert r4.status_code == 200
    data4 = r4.json()
    assert data4["character"]["archetype"] == "08_antagonist_female_greentea"

    # Verify no duplicates in project characters
    chars = [c for c in data4["characters"] if c["name"] == char_name]
    assert len(chars) == 1
    assert chars[0]["archetype"] == "08_antagonist_female_greentea"
    assert "heart-shaped" in chars[0]["consistency_card"]["facial_lock"]


def test_apply_archetype_with_special_characters_in_name(client):
    """Verify applying archetype to character with Unicode emojis, punctuation, and spaces."""
    special_name = "✨剑圣·独孤求败 (S-Rank)✨"
    res = client.post("/api/archetypes/apply", json={
        "character_name": special_name,
        "archetype_id": "06_ancient_male_noble",
        "custom_role": "天下第一剑客"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["character"]["name"] == special_name
    assert data["character"]["role"] == "天下第一剑客"
    assert data["character"]["archetype"] == "06_ancient_male_noble"


# =========================================================================
# 3. Turnaround Sheet Generation, Dimensions, and Fallback
# =========================================================================

def test_turnaround_generation_offline_fallback_pil_16_9(client):
    """Force offline fallback and verify PIL generates an exact 16:9 image (1280x720)."""
    char_name = "测试纯白底16比9三视图"

    # Ensure no SiliconFlow key and mock requests to fail
    with patch.dict("os.environ", {"SILICONFLOW_API_KEY": ""}):
        with patch("requests.get", side_effect=Exception("Simulated Network Offline")):
            res = client.post(f"/api/characters/{char_name}/turnaround", json={"prompt": "", "regenerate": True})
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert "turnaround_image" in data

            # Verify image file on disk
            img_rel_path = data["turnaround_image"].lstrip("/")
            project_root = Path(__file__).resolve().parent.parent
            img_abs_path = project_root / img_rel_path

            assert img_abs_path.exists(), f"Generated image not found at {img_abs_path}"
            assert img_abs_path.stat().st_size > 500

            # Open image with PIL and empirically verify aspect ratio
            with Image.open(img_abs_path) as img:
                width, height = img.size
                assert width == 1280
                assert height == 720
                aspect_ratio = width / height
                assert pytest.approx(aspect_ratio, rel=1e-3) == 16.0 / 9.0


def test_turnaround_path_traversal_and_illegal_chars_sanitization(client):
    """Verify malicious character names with directory traversal and illegal characters are properly sanitized."""
    # 1. Unencoded raw path traversal attempt gets blocked by routing
    raw_res = client.post("/api/characters/../../etc/passwd/turnaround", json={"prompt": "safe turnaround"})
    assert raw_res.status_code == 404

    # 2. URL-encoded or dot-dot style names with illegal filesystem characters
    malicious_name = "test..traversal:with*bad?chars<and>pipes|"
    encoded_name = urllib.parse.quote(malicious_name, safe="")
    res = client.post(f"/api/characters/{encoded_name}/turnaround", json={"prompt": "safe turnaround", "regenerate": True})
    assert res.status_code == 200
    data = res.json()

    img_url = data["turnaround_image"]
    assert ".." not in img_url, "Path traversal characters leaked into turnaround URL"
    assert ":" not in img_url and "*" not in img_url and "?" not in img_url

    project_root = Path(__file__).resolve().parent.parent
    turnarounds_dir = project_root / "output" / "turnarounds"

    # Verify the generated file is contained strictly inside output/turnarounds/
    created_files = list(turnarounds_dir.glob("*test__traversal_with_bad_chars_and_pipes_*.jpg"))
    assert len(created_files) > 0
    for f in created_files:
        assert turnarounds_dir.resolve() in f.resolve().parents


def test_turnaround_get_matrix_endpoints(client):
    """Verify GET /api/characters/{name}/turnaround across all matrix states."""
    # State A: non-existent character -> 404
    r_not_found = client.get("/api/characters/绝对不存在的角色_99999/turnaround")
    assert r_not_found.status_code == 404

    # State B: existing character without turnaround generated -> 200 with empty turnaround_image
    client.post("/api/characters", json={
        "name": "空三视图角色",
        "role": "配角",
        "voice": "云希 (磁性沉稳霸道)",
        "avatar": "",
        "traits": "路人"
    })
    r_empty = client.get("/api/characters/空三视图角色/turnaround")
    assert r_empty.status_code == 200
    data_empty = r_empty.json()
    assert data_empty["status"] == "success"
    assert data_empty["name"] == "空三视图角色"
    assert data_empty["turnaround_image"] == ""

    # State C: character with generated turnaround -> 200 with non-empty URL
    client.post("/api/characters/空三视图角色/turnaround", json={"prompt": "sample prompt"})
    r_filled = client.get("/api/characters/空三视图角色/turnaround")
    assert r_filled.status_code == 200
    data_filled = r_filled.json()
    assert data_filled["turnaround_image"].endswith(".jpg")
    assert len(data_filled["turnaround_prompt"]) > 0


# =========================================================================
# 4. Web Monitor index.html Static Syntax & Vue Binding Checks
# =========================================================================

def test_web_index_html_syntax_and_vue_contracts():
    """Empirically inspect index.html for tag balance and Vue setup binding contracts."""
    index_path = Path(__file__).resolve().parent.parent / "web" / "index.html"
    assert index_path.exists(), "web/index.html not found"
    html_content = index_path.read_text(encoding="utf-8")

    # 1. Check tag closures for key blocks
    for tag in ["html", "head", "body", "script", "style"]:
        open_count = len(re.findall(rf"<{tag}[\s>]", html_content, re.IGNORECASE))
        close_count = len(re.findall(rf"</{tag}>", html_content, re.IGNORECASE))
        assert open_count == close_count, f"Unmatched <{tag}> tags: {open_count} open vs {close_count} close"

    # 2. Check Vue setup() return bindings for Milestone 4 features
    required_vue_exports = [
        "availableArchetypes",
        "isGeneratingTurnaround",
        "fetchArchetypes",
        "applyArchetype",
        "generateTurnaround",
        "openCharacterEdit",
        "saveCharacterEdit"
    ]

    for export_name in required_vue_exports:
        assert export_name in html_content, f"Vue binding '{export_name}' missing from index.html"

    # 3. Check for presence of canonical archetype labels in template
    assert "都市丽人" in html_content
    assert "霸总男主" in html_content
    assert "清冷世子" in html_content
    assert "绿茶千金" in html_content
    assert "三视图" in html_content
    assert "Consistency Card" in html_content or "一致性控制卡" in html_content


# =========================================================================
# 5. Project Generation / Script Breakdown Integration
# =========================================================================

def test_project_generation_preserves_consistency_schema(client):
    """Verify POST /api/project/generate populates all characters with consistency schema fields."""
    payload = {
        "title": "测试全流程短剧",
        "genre": "都市爽文",
        "novel_text": "第一章：战神归来。萧天站在江城机场，冷冷地看着曾经欺辱他的人。苏清雪快步上前迎接。"
    }
    res = client.post("/api/project/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "characters" in data
    assert len(data["characters"]) >= 1

    for char in data["characters"]:
        assert "archetype" in char
        assert "turnaround_prompt" in char
        assert "turnaround_image" in char
        assert "consistency_card" in char

