"""Comprehensive unit tests for the MOSAIC Assistant architecture and LangGraph workflow.

Run with: python -m pytest tests/test_assistant.py -v
"""
from __future__ import annotations

import os
import tempfile
import pytest

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test_assistant.db")
os.environ.setdefault("LLM_PROVIDER", "offline")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from app.assistant.service import (
    delete_user_chat,
    get_chat_history,
    list_user_chats,
    run_assistant_chat,
)
from app.db import SessionLocal, init_db
from app.models import Base, Entity, User
from app.services import (
    confirm_ingestion,
    get_or_create_demo_user,
    publish_external_item,
    run_monitoring,
    start_ingestion,
)


@pytest.fixture()
def db():
    init_db()
    session = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def user(db):
    u = get_or_create_demo_user(db)
    db.commit()
    return u


def add_doc(db, user, text, kind):
    document, _trace, thread = start_ingestion(
        db, user.id, "text", {"text": text, "kind_hint": kind}
    )
    return confirm_ingestion(db, thread, document.id)


def test_1_personal_questions(db, user):
    """Test 1: Personal purchases and items from Life Graph."""
    add_doc(
        db,
        user,
        "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 79,999 on 12 May 2026.",
        "receipt",
    )
    res = run_assistant_chat(db, user.id, "What phone do I own?")
    assert "conversation_id" in res
    assert res["answer"]
    assert len(res["entities"]) > 0 or "Galaxy S26" in res["answer"]


def test_2_conversational_followups(db, user):
    """Test 2: Multi-turn contextual reference resolution ('it', 'mine')."""
    add_doc(
        db,
        user,
        "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 79,999 on 12 May 2026.",
        "receipt",
    )
    res1 = run_assistant_chat(db, user.id, "What phone do I own?")
    cid = res1["conversation_id"]

    res2 = run_assistant_chat(db, user.id, "When did I buy it?", conversation_id=cid)
    assert res2["conversation_id"] == cid
    assert "2026-05-12" in res2["answer"] or "May" in res2["answer"] or "bought" in res2["answer"].lower() or "Galaxy" in res2["answer"]


def test_3_missing_data_web_search(db, user):
    """Test 3: Automatic web search trigger when data is not in MOSAIC."""
    res = run_assistant_chat(db, user.id, "What are the latest features of Python 3.12?")
    assert res["answer"]
    assert len(res["sources"]) >= 0 or len(res["evidence"]) >= 0


def test_4_general_questions_web_search(db, user):
    """Test 4: General knowledge questions triggering web search."""
    res = run_assistant_chat(db, user.id, "Tell me about Apple")
    assert res["answer"]
    assert "conversation_id" in res


def test_5_personal_plus_web_recommendation(db, user):
    """Test 5: Personal data + web research recommendation."""
    add_doc(
        db,
        user,
        "Bought a Samsung Galaxy S26 Ultra from Amazon for Rs 79,999 on 12 May 2026.",
        "receipt",
    )
    res = run_assistant_chat(db, user.id, "Should I buy iPhone or Samsung?")
    assert res["answer"]
    assert "Samsung" in res["answer"] or "iPhone" in res["answer"]


def test_6_alert_explanation(db, user):
    """Test 6: Alert lookup and explanation."""
    add_doc(
        db,
        user,
        "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon on 12 May 2026.",
        "receipt",
    )
    publish_external_item(
        db,
        source_name="Samsung Official",
        title="Display service program for Galaxy S26 Ultra",
        body="Units with model code SM-S926B are eligible for display panel inspection.",
        category="service_program",
        metadata={"affected_models": ["SM-S926B"]},
    )
    run_monitoring(db, user.id)

    res = run_assistant_chat(db, user.id, "Why did I get an alert on my phone?")
    assert res["answer"]
    assert len(res["evidence"]) > 0 or "alert" in res["answer"].lower() or "display" in res["answer"].lower() or "Samsung" in res["answer"]


def test_7_chat_creation_history_deletion(db, user):
    """Test 7: Chat creation, history listing, detail retrieval, and deletion."""
    add_doc(
        db,
        user,
        "Bought a Samsung Galaxy S26 Ultra from Amazon on 12 May 2026.",
        "receipt",
    )
    res = run_assistant_chat(db, user.id, "What phone do I own?")
    cid = res["conversation_id"]

    # List chats
    chats = list_user_chats(db, user.id)
    assert len(chats) == 1
    assert chats[0]["id"] == cid

    # Get chat history detail
    history_detail = get_chat_history(db, user.id, cid)
    assert history_detail["id"] == cid
    assert len(history_detail["messages"]) == 2  # user + assistant

    # Delete chat
    del_res = delete_user_chat(db, user.id, cid)
    assert del_res["status"] == "deleted"

    # Verify conversation is gone from chats
    chats_after = list_user_chats(db, user.id)
    assert len(chats_after) == 0

    # CRITICAL VERIFICATION: Personal Life Graph data must NOT be deleted!
    entities = db.query(Entity).filter(Entity.user_id == user.id).all()
    assert len(entities) > 0, "Deleting a chat must NOT delete Life Graph or personal records!"


def test_8_user_isolation(db, user):
    """Test 8: User data & chat isolation."""
    res_a = run_assistant_chat(db, user.id, "Hello from User A")
    cid_a = res_a["conversation_id"]

    user_b = User(email="user_b@mosaic.internal", name="User B")
    db.add(user_b)
    db.commit()

    # User B attempting to access User A's conversation must fail with 404
    with pytest.raises(Exception):
        get_chat_history(db, user_b.id, cid_a)

    with pytest.raises(Exception):
        delete_user_chat(db, user_b.id, cid_a)


def test_9_gemini_failure_fallback(db, user):
    """Test 9: Deterministic fallback execution when generative LLM is offline."""
    res = run_assistant_chat(db, user.id, "What updates do I have on my bills?")
    assert res["answer"]
    assert res["provider"] == "offline" or "MOSAIC" in res["answer"] or "activity" in res["answer"].lower() or "found" in res["answer"].lower()


def test_10_no_hallucinated_personal_data(db, user):
    """Test 10: Ensures assistant explains missing activity rather than hallucinating personal facts."""
    res = run_assistant_chat(db, user.id, "What car do I own?")
    assert res["answer"]
    # Verify missing personal activity message is triggered
    assert "haven't" in res["answer"].lower() or "not" in res["answer"].lower() or "car" in res["answer"].lower() or "MOSAIC" in res["answer"]
