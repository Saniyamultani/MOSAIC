"""End-to-end tests for the agent pipeline.

Run with:  pytest -q   (from the backend/ directory)

These use a throwaway SQLite file so they never touch the demo database.
"""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("LLM_PROVIDER", "offline")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from app.db import SessionLocal, init_db  # noqa: E402
from app.graphstore.factory import get_graph_store  # noqa: E402
from app.models import Alert, Base  # noqa: E402
from app.llm.offline import OfflineProvider  # noqa: E402
from app.services import (  # noqa: E402
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


def add(db, user, text, kind):
    document, _trace, thread = start_ingestion(
        db, user.id, "text", {"text": text, "kind_hint": kind}
    )
    return confirm_ingestion(db, thread, document.id)


def test_extraction_pulls_the_fields_that_matter(db, user):
    document, trace, _thread = start_ingestion(
        db,
        user.id,
        "text",
        {
            "text": "I bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for "
                    "Rs 79,999 on 12 May 2026, paid with HDFC card.",
            "kind_hint": "receipt",
        },
    )
    fields = document.extraction["fields"]
    assert document.extraction["kind"] == "receipt"
    assert fields["brand"] == "Samsung"
    assert fields["seller"] == "Amazon"
    assert fields["model_code"] == "SM-S926B"
    assert fields["price"] == 79999.0
    assert fields["purchase_date"] == "2026-05-12"
    assert document.status == "pending_confirmation", "must wait for the user's ✓ Confirm"
    assert any(step["agent"] == "Ingestion Agent" for step in trace)


def test_confirmation_builds_the_life_graph(db, user):
    result = add(
        db, user,
        "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 79,999 "
        "on 12 May 2026 with my HDFC card.",
        "receipt",
    )
    assert result["created"] >= 4  # product, brand, retailer, payment method
    graph = get_graph_store(db)
    names = {e.name for e in graph.entities(user.id)}
    assert any("Galaxy S26" in n for n in names)
    assert "Samsung" in names and "Amazon" in names


def test_entity_resolution_merges_aliases(db, user):
    add(db, user,
        "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 79,999 on 12 May 2026.",
        "receipt")
    before = len(get_graph_store(db).entities(user.id, ["product"]))
    add(db, user,
        "Samsung Care+ warranty for Galaxy S26 Ultra, model SM-S926B, 24 months from 12 May 2026.",
        "warranty")
    after = len(get_graph_store(db).entities(user.id, ["product"]))
    assert after == before, "the warranty must attach to the existing phone, not create a second one"


def test_matching_announcement_raises_an_alert(db, user):
    add(db, user,
        "Bought a Samsung Galaxy S26 Ultra (SM-S926B) from Amazon for Rs 79,999 on 12 May 2026.",
        "receipt")
    publish_external_item(
        db,
        source_name="Samsung Newsroom (official)",
        title="Samsung announces a display service programme for the Galaxy S26 Ultra",
        body="Units with model code SM-S926B are eligible for a free panel replacement.",
        category="service_program",
        metadata={"affected_models": ["SM-S926B"], "region": "India", "deadline": "2026-12-31"},
    )
    summary = run_monitoring(db, user.id)
    assert summary["alerts"] >= 1
    alert = db.query(Alert).filter(Alert.user_id == user.id, Alert.severity == "critical").first()
    assert alert is not None
    assert alert.reasoning_chain, "every alert carries its reasoning chain"
    assert alert.evidence, "every alert carries evidence"


def test_skeptic_suppresses_a_model_mismatch(db, user):
    """The whole point of the Skeptic Agent: recall for Model A, user owns Model B."""
    add(db, user,
        "Croma invoice: Sony BRAVIA XR-65A80K OLED TV for Rs 1,89,990 on 20 May 2026.",
        "receipt")
    publish_external_item(
        db,
        source_name="Consumer Product Safety Notices",
        title="Recall: Sony BRAVIA XR-55A80K power boards may overheat",
        body="Only units with model code XR-55A80K are affected.",
        category="recall",
        metadata={"affected_models": ["XR-55A80K"], "region": "India"},
        trust_tier=1,
    )
    before = db.query(Alert).filter(Alert.user_id == user.id).count()
    summary = run_monitoring(db, user.id)
    after = db.query(Alert).filter(Alert.user_id == user.id).count()
    assert summary["suppressed"] >= 1
    assert after == before, "a mismatched recall must never reach the user"


def test_irrelevant_news_produces_nothing(db, user):
    add(db, user, "Netflix Premium plan Rs 649 per month, renews 18 September 2026.",
        "subscription")
    publish_external_item(
        db,
        source_name="Technology press wire",
        title="Foldable shipments grew 14% last quarter",
        body="Analysts attribute growth to lower entry prices.",
        category="external_update",
        trust_tier=5,
    )
    summary = run_monitoring(db, user.id)
    assert summary["no_match"] >= 1


def test_offline_assistant_formats_relevant_updates_as_numbered_points():
    context = (
        "CONFIRMED DOCUMENTS:\n"
        "- Old receipt: bought a phone\n"
        "NEW ALERTS:\n"
        "- Airtel bill due on 2026-09-15: amount due Rs 799\n"
        "- Netflix renews on 2026-09-18: Rs 649 per month\n"
    )
    answer = OfflineProvider().answer_question("What updates do I have on my bills?", context)
    assert answer.startswith("Here's what I found:")
    assert "1. Airtel bill due" in answer
    assert "2. Netflix renews" in answer
    assert "Old receipt" not in answer
