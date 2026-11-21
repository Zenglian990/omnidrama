"""Unit tests for Web Monitor & API Layer Archetypes and Turnaround Integration (Milestone 4 - R4)."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from omnidrama.web.app import app, CharacterModel, ApplyArchetypeRequest, TurnaroundGenerateRequest
from omnidrama.config.archetypes import BUILTIN_ARCHETYPES, list_archetypes, get_archetype


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



def test_character_model_backward_compatibility():
    """Verify legacy CharacterModel instances without new fields validate seamlessly."""
    char = CharacterModel(
        name="林清雪",
        role="核心主角",
        voice="云希 (磁性沉稳霸道)",
        avatar="",
        traits="职场丽人"
    )
    assert char.name == "林清雪"
    assert char.role == "核心主角"
    assert char.archetype == ""
    assert char.turnaround_prompt == ""
    assert char.turnaround_image == ""
    assert char.consistency_card is None

    char_dict = char.model_dump() if hasattr(char, "model_dump") else char.dict()
    assert "archetype" in char_dict
    assert "consistency_card" in char_dict


def test_character_model_with_consistency_card():
    """Verify CharacterModel stores and serializes consistency card and turnaround prompt."""
    card = {
        "facial_lock": "delicate Asian oval face",
        "hair_lock": "clavicle-grazing wavy lob",
        "costume_lock": "tailored oatmeal-white blazer",
        "exclusive_negative_prompt": "childish round face",
        "reference_images": []
    }
    char = CharacterModel(
        name="林清雪",
        role="女主角",
        voice="晓晓 (知性独立女声)",
        avatar="/output/turnarounds/turnaround_linqingxue.jpg",
        traits="26岁职场精英独立女性",
        archetype="04_modern_female_urban",
        turnaround_prompt="Character model turnaround sheet of modern urban chic female",
        turnaround_image="/output/turnarounds/turnaround_linqingxue.jpg",
        consistency_card=card
    )
    assert char.archetype == "04_modern_female_urban"
    assert char.consistency_card["facial_lock"] == "delicate Asian oval face"
    assert char.turnaround_image == "/output/turnarounds/turnaround_linqingxue.jpg"


def test_get_archetypes_endpoint(client):
    """Verify GET /api/archetypes returns all 4 canonical archetypes with complete schema."""
    response = client.get("/api/archetypes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 4

    codes = [arch["code"] for arch in data]
    assert "04" in codes
    assert "05" in codes
    assert "06" in codes
    assert "08" in codes

    ids = [arch["id"] for arch in data]
    assert "04_modern_female_urban" in ids
    assert "05_modern_male_boss" in ids
    assert "06_ancient_male_noble" in ids
    assert "08_antagonist_female_greentea" in ids

    for arch in data:
        assert "name" in arch and len(arch["name"]) > 0
        assert "summary" in arch and len(arch["summary"]) > 0
        assert "turnaround_prompt" in arch and len(arch["turnaround_prompt"]) > 0
        assert "consistency_card" in arch and isinstance(arch["consistency_card"], dict)
        card = arch["consistency_card"]
        assert "facial_lock" in card
        assert "hair_lock" in card
        assert "costume_lock" in card
        assert "exclusive_negative_prompt" in card


def test_apply_archetype_endpoint_new_character(client):
    """Verify POST /api/archetypes/apply can instantiate and persist a new character from archetype."""
    payload = {
        "character_name": "测试新女主_苏清音",
        "archetype_id": "04_modern_female_urban",
        "custom_role": "第一女主角"
    }
    response = client.post("/api/archetypes/apply", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    char = res_data["character"]
    assert char["name"] == "测试新女主_苏清音"
    assert char["role"] == "第一女主角"
    assert char["archetype"] == "04_modern_female_urban"
    assert "delicate Asian oval face" in char["consistency_card"]["facial_lock"]
    assert "oatmeal-white" in char["consistency_card"]["costume_lock"]
    assert "Character model turnaround sheet" in char["turnaround_prompt"]


def test_apply_archetype_endpoint_existing_character(client):
    """Verify POST /api/archetypes/apply updates an existing character in the project."""
    # 1. Add base character
    base_char = {
        "name": "测试霸总_傅沉渊",
        "role": "主要人物",
        "voice": "云希 (磁性沉稳霸道)",
        "avatar": "",
        "traits": "冷酷总裁"
    }
    r1 = client.post("/api/characters", json=base_char)
    assert r1.status_code == 200

    # 2. Apply archetype 05_modern_male_boss
    payload = {
        "character_name": "测试霸总_傅沉渊",
        "archetype_id": "05_modern_male_boss"
    }
    response = client.post("/api/archetypes/apply", json=payload)
    assert response.status_code == 200
    data = response.json()
    char = data["character"]
    assert char["name"] == "测试霸总_傅沉渊"
    assert char["archetype"] == "05_modern_male_boss"
    assert "sculpted masculine Chinese jawline" in char["consistency_card"]["facial_lock"]
    assert "three-piece" in char["consistency_card"]["costume_lock"]


def test_apply_archetype_not_found(client):
    """Verify POST /api/archetypes/apply returns 404 for non-existent archetype."""
    payload = {
        "character_name": "未知角色",
        "archetype_id": "non_existent_archetype_999"
    }
    response = client.post("/api/archetypes/apply", json=payload)
    assert response.status_code == 404
    assert "未找到人设母版" in response.json()["detail"]


def test_character_turnaround_generation_and_fetch(client):
    """Verify POST /api/characters/{name}/turnaround triggers generation and GET fetches metadata."""
    name = "测试三视图_沈清秋"
    gen_resp = client.post(f"/api/characters/{name}/turnaround", json={"prompt": "", "regenerate": True})
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["status"] == "success"
    assert "turnaround_image" in gen_data
    assert gen_data["turnaround_image"].endswith(".jpg")
    assert "turnaround_prompt" in gen_data
    assert len(gen_data["turnaround_prompt"]) > 20

    # Query turnaround
    get_resp = client.get(f"/api/characters/{name}/turnaround")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["status"] == "success"
    assert get_data["name"] == name
    assert get_data["turnaround_image"] == gen_data["turnaround_image"]
    assert get_data["turnaround_prompt"] == gen_data["turnaround_prompt"]


def test_get_character_turnaround_not_found(client):
    """Verify GET /api/characters/{name}/turnaround returns 404 when character does not exist."""
    response = client.get("/api/characters/绝对不存在的角色_99999/turnaround")
    assert response.status_code == 404


def test_get_project_by_id_endpoint(client):
    """Verify GET /api/projects/{project_id} returns project state data."""
    response = client.get("/api/projects/default_work")
    assert response.status_code == 200
    data = response.json()
    assert "characters" in data
    assert "shots" in data


def test_character_crud_preserves_consistency_card(client):
    """Verify POST /api/characters and PUT /api/characters/{name} correctly preserve consistency fields."""
    char_payload = {
        "name": "测试CRUD角色_白月光",
        "role": "女配角",
        "voice": "晓涵 (温柔清纯甜美)",
        "avatar": "/output/turnarounds/turnaround_baiyueguang.jpg",
        "traits": "心形脸，自然卧蚕",
        "archetype": "08_antagonist_female_greentea",
        "turnaround_prompt": "Turnaround prompt test",
        "turnaround_image": "/output/turnarounds/turnaround_baiyueguang.jpg",
        "consistency_card": {
            "facial_lock": "heart-shaped Asian face",
            "hair_lock": "half-up mermaid waves",
            "costume_lock": "French tweed cropped jacket",
            "exclusive_negative_prompt": "overt villain smirk",
            "reference_images": []
        }
    }

    # Create
    create_resp = client.post("/api/characters", json=char_payload)
    assert create_resp.status_code == 200
    chars = create_resp.json()["characters"]
    target = next((c for c in chars if c["name"] == "测试CRUD角色_白月光"), None)
    assert target is not None
    assert target["archetype"] == "08_antagonist_female_greentea"
    assert target["consistency_card"]["facial_lock"] == "heart-shaped Asian face"

    # Update
    char_payload["role"] = "反派女二"
    update_resp = client.put("/api/characters/测试CRUD角色_白月光", json=char_payload)
    assert update_resp.status_code == 200
    updated_chars = update_resp.json()["characters"]
    updated_target = next((c for c in updated_chars if c["name"] == "测试CRUD角色_白月光"), None)
    assert updated_target is not None
    assert updated_target["role"] == "反派女二"
    assert updated_target["consistency_card"]["costume_lock"] == "French tweed cropped jacket"
