"""Tests for the 3-Account Google Colab Free T4 (48GB VRAM) Cluster Provider & Mobile API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from providers.colab_cluster_provider import ColabClusterManager
from web.app import app


def test_colab_cluster_nodes_and_routing():
    mgr = ColabClusterManager.get_instance()
    assert "node_1_llm" in mgr.nodes
    assert "node_2_image" in mgr.nodes
    assert "node_3_audio" in mgr.nodes

    # Security hardening [OD-02]: personal Gmail addresses are never hardcoded or exposed in public dicts
    for nid in ("node_1_llm", "node_2_image", "node_3_audio"):
        assert mgr.nodes[nid].email == ""
        assert "email" not in mgr.nodes[nid].to_public_dict()
        mgr.nodes[nid].scopes = ["https://www.googleapis.com/auth/colaboratory"]
        mgr.nodes[nid].refresh_token = f"1//test_refresh_token_{nid}"
        mgr.nodes[nid].status = "STANDBY_T4_READY"

    assert mgr.nodes["node_1_llm"].has_colab_scope is True
    assert mgr.nodes["node_2_image"].has_colab_scope is True
    assert mgr.nodes["node_3_audio"].has_colab_scope is True

    # Smart routing: each task maps to its dedicated T4 node
    llm_node = mgr.select_node_for_task("llm")
    img_node = mgr.select_node_for_task("image")
    aud_node = mgr.select_node_for_task("audio")
    assert llm_node is not None and llm_node.node_id == "node_1_llm"
    assert img_node is not None and img_node.node_id == "node_2_image"
    assert aud_node is not None and aud_node.node_id == "node_3_audio"


def test_generate_oauth_urls_for_node2_and_node3(monkeypatch):
    monkeypatch.setenv("COLAB_CLI_CLIENT_ID", "test-colab-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("COLAB_CLI_CLIENT_SECRET", "test-colab-client-secret")
    mgr = ColabClusterManager.get_instance()
    oauth2 = mgr.generate_mobile_oauth_url("node_2_image")
    oauth3 = mgr.generate_mobile_oauth_url("node_3_audio")

    assert oauth2["node_id"] == "node_2_image"
    assert "email" not in oauth2
    assert "colaboratory" in oauth2["auth_url"]
    assert "code_challenge_method=S256" in oauth2["auth_url"]

    assert oauth3["node_id"] == "node_3_audio"
    assert "email" not in oauth3
    assert "colaboratory" in oauth3["auth_url"]
    assert oauth2["state"] != oauth3["state"]


def test_fastapi_colab_and_sota_endpoints(monkeypatch):
    monkeypatch.setenv("COLAB_CLI_CLIENT_ID", "test-colab-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("COLAB_CLI_CLIENT_SECRET", "test-colab-client-secret")
    client = TestClient(app)

    res_sota = client.get("/api/sota/status")
    assert res_sota.status_code == 200
    data_sota = res_sota.json()
    assert "colab_cluster" in data_sota["providers"]
    assert "colab_cluster" in data_sota
    assert data_sota["colab_cluster"]["total_vram_gb"] == 48

    res_oauth = client.get("/api/colab/oauth-url?node_id=node_2_image")
    assert res_oauth.status_code == 200
    assert "auth_url" in res_oauth.json()
