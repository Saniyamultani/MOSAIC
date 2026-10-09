"""Tests for authenticated post-upload retrieval evaluation."""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{tempfile.mkdtemp()}/test_document_evaluation.db",
)
os.environ.setdefault("LLM_PROVIDER", "offline")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Base

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    session = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


def create_user(email: str) -> dict:
    response = client.post(
        "/api/auth/signup",
        json={"name": "Eval User", "email": email, "password": "test-password"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_confirmed_upload_shows_source_attributed_retrieval_evaluation():
    account = create_user("eval-owner@example.com")
    headers = {"Authorization": f"Bearer {account['token']}"}
    upload = client.post(
        "/api/documents/text",
        headers=headers,
        json={
            "text": (
                "Bought a Samsung Galaxy S26 Ultra from Amazon for Rs 129999 "
                "on 12 May 2026, paid with HDFC card."
            ),
            "kind_hint": "receipt",
        },
    )
    assert upload.status_code == 200, upload.text
    document_id = upload.json()["document"]["id"]

    pending = client.get(
        f"/api/documents/{document_id}/evaluation",
        headers=headers,
    )
    assert pending.status_code == 409

    confirmation = client.post(
        f"/api/documents/{document_id}/confirm",
        headers=headers,
        json={"thread_id": upload.json()["thread_id"]},
    )
    assert confirmation.status_code == 200, confirmation.text

    evaluation = client.get(
        f"/api/documents/{document_id}/evaluation",
        headers=headers,
    )
    assert evaluation.status_code == 200, evaluation.text
    result = evaluation.json()
    assert result["method"] == "deterministic_source_attribution"
    assert result["metrics"]["context_recall"] == 1.0
    assert any(check["passed"] for check in result["checks"])
    assert any(
        hit["document_id"] == document_id and hit["matches_uploaded_document"]
        for hit in result["retrieved_documents"]
    )
    assert "No RAGAS package" in result["note"]


def test_document_evaluation_is_scoped_to_authenticated_owner():
    owner = create_user("eval-owner-2@example.com")
    other_user = create_user("eval-other@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    other_headers = {"Authorization": f"Bearer {other_user['token']}"}
    upload = client.post(
        "/api/documents/text",
        headers=owner_headers,
        json={"text": "Netflix Premium subscription is Rs 649 monthly.", "kind_hint": "subscription"},
    )
    document_id = upload.json()["document"]["id"]
    response = client.get(
        f"/api/documents/{document_id}/evaluation",
        headers=other_headers,
    )
    assert response.status_code == 404
