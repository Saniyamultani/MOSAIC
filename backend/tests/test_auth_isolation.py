"""Unit tests for authentication (signup, login, logout, me) and strict multi-user data isolation.

Run with: python -m pytest tests/test_auth_isolation.py -v
"""
from __future__ import annotations

import os
import tempfile
import pytest

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test_auth.db")
os.environ.setdefault("LLM_PROVIDER", "offline")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal, init_db
from app.models import Base, Document, Entity, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    session = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


def test_signup_login_logout_flow():
    # 1. Signup user
    signup_resp = client.post(
        "/api/auth/signup",
        json={"name": "Alice Developer", "email": "alice@example.com", "password": "SecretPassword123"},
    )
    assert signup_resp.status_code == 200, signup_resp.text
    signup_data = signup_resp.json()
    assert "token" in signup_data
    assert signup_data["user"]["name"] == "Alice Developer"
    assert signup_data["user"]["email"] == "alice@example.com"
    alice_token = signup_data["token"]

    # 2. Duplicate signup should fail
    dup_resp = client.post(
        "/api/auth/signup",
        json={"name": "Alice Impostor", "email": "alice@example.com", "password": "OtherPassword"},
    )
    assert dup_resp.status_code == 400
    assert "already registered" in dup_resp.json()["detail"].lower()

    # 3. Login with wrong password should fail
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401

    # 4. Login with correct password
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "SecretPassword123"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "token" in login_data
    assert login_data["user"]["name"] == "Alice Developer"

    # 5. Fetch /me with valid token
    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "alice@example.com"

    # 6. Logout
    logout_resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert logout_resp.status_code == 200

    # 7. Accessing /me with invalidated token should fail
    me_invalid = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert me_invalid.status_code == 401


def test_multi_user_data_isolation():
    # Register User 1 (Alice)
    r1 = client.post(
        "/api/auth/signup",
        json={"name": "Alice", "email": "alice@isolation.com", "password": "pass123"},
    )
    alice_token = r1.json()["token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    # Register User 2 (Bob)
    r2 = client.post(
        "/api/auth/signup",
        json={"name": "Bob", "email": "bob@isolation.com", "password": "pass123"},
    )
    bob_token = r2.json()["token"]
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    # Alice ingests a document
    doc_alice_resp = client.post(
        "/api/documents/text",
        headers=alice_headers,
        json={"text": "Alice bought a MacBook Pro 16 inch for Rs 240000 on 10 June 2026.", "kind_hint": "receipt"},
    )
    assert doc_alice_resp.status_code == 200
    doc_alice_id = doc_alice_resp.json()["document"]["id"]
    client.post(
        f"/api/documents/{doc_alice_id}/confirm",
        headers=alice_headers,
        json={"thread_id": doc_alice_resp.json()["thread_id"]},
    )

    # Bob ingests a document
    doc_bob_resp = client.post(
        "/api/documents/text",
        headers=bob_headers,
        json={"text": "Bob bought a Sony OLED TV for Rs 180000 on 15 June 2026.", "kind_hint": "receipt"},
    )
    assert doc_bob_resp.status_code == 200
    doc_bob_id = doc_bob_resp.json()["document"]["id"]
    client.post(
        f"/api/documents/{doc_bob_id}/confirm",
        headers=bob_headers,
        json={"thread_id": doc_bob_resp.json()["thread_id"]},
    )

    # --- ISOLATION CHECK 1: Documents ---
    alice_docs = client.get("/api/documents", headers=alice_headers).json()["documents"]
    bob_docs = client.get("/api/documents", headers=bob_headers).json()["documents"]

    alice_doc_ids = {d["id"] for d in alice_docs}
    bob_doc_ids = {d["id"] for d in bob_docs}

    assert doc_alice_id in alice_doc_ids
    assert doc_alice_id not in bob_doc_ids, "Bob must NOT see Alice's documents!"

    assert doc_bob_id in bob_doc_ids
    assert doc_bob_id not in alice_doc_ids, "Alice must NOT see Bob's documents!"

    # --- ISOLATION CHECK 2: Life Graph ---
    alice_graph = client.get("/api/graph", headers=alice_headers).json()
    bob_graph = client.get("/api/graph", headers=bob_headers).json()

    alice_node_names = [n["name"] for n in alice_graph["nodes"]]
    bob_node_names = [n["name"] for n in bob_graph["nodes"]]

    assert any("MacBook" in name for name in alice_node_names) or len(alice_node_names) > 0
    assert not any("Sony OLED" in name for name in alice_node_names), "Alice graph must not contain Bob's entities!"

    assert any("Sony OLED" in name for name in bob_node_names) or len(bob_node_names) > 0
    assert not any("MacBook" in name for name in bob_node_names), "Bob graph must not contain Alice's entities!"

    # --- ISOLATION CHECK 3: Assistant Conversations ---
    chat_alice = client.post(
        "/api/assistant/chat",
        headers=alice_headers,
        json={"message": "What laptop do I own?"},
    ).json()
    cid_alice = chat_alice["conversation_id"]

    # Bob trying to view Alice's conversation history must fail with 404
    bob_access = client.get(f"/api/assistant/chats/{cid_alice}", headers=bob_headers)
    assert bob_access.status_code == 404, "Bob must NOT be able to view Alice's chat conversation!"

    # --- ISOLATION CHECK 4: Profile Updates ---
    client.put(
        "/api/profile",
        headers=alice_headers,
        json={"display_name": {"value": "Alice Cooper", "shared": True}, "city": {"value": "Bengaluru", "shared": True}},
    )

    alice_profile = client.get("/api/profile", headers=alice_headers).json()
    bob_profile = client.get("/api/profile", headers=bob_headers).json()

    assert alice_profile["name"] == "Alice Cooper"
    assert alice_profile["profile"]["city"]["value"] == "Bengaluru"

    assert bob_profile["name"] == "Bob"
    assert bob_profile["profile"]["city"]["value"] is None
