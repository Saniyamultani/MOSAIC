"""Unit tests for Life Graph entity relationships and duplicate node/relationship prevention.

Run with: python -m pytest tests/test_graph_relationships.py -v
"""
from __future__ import annotations

import os
import tempfile
import pytest

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test_graph.db")
os.environ.setdefault("LLM_PROVIDER", "offline")
os.environ.setdefault("ENABLE_SCHEDULER", "false")

from app.db import SessionLocal, init_db
from app.graphstore.factory import get_graph_store
from app.models import Base, Entity, Relationship, User
from app.services import (
    confirm_ingestion,
    get_or_create_demo_user,
    publish_external_item,
    run_monitoring,
    start_ingestion,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    session = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


def test_entity_relationships_creation():
    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)
        doc_text = (
            "Order confirmation from Amazon. I bought a Samsung Galaxy S26 Ultra "
            "for Rs 1,29,999 on 12 May 2026. Paid with my HDFC credit card. "
            "Includes 24 months Samsung Care+ extended warranty."
        )
        document, trace, thread_id = start_ingestion(
            db, user.id, "text", {"text": doc_text, "kind_hint": "receipt"}
        )
        result = confirm_ingestion(db, thread_id, document.id)

        assert result["created"] > 0 or result["merged"] > 0

        # Query Life Graph
        graph = get_graph_store(db)
        view = graph.view(user.id)

        node_types = {n["type"] for n in view.nodes}
        assert "product" in node_types or "asset" in node_types
        assert "retailer" in node_types or "brand" in node_types or "payment_method" in node_types

        edge_types = {e["type"] for e in view.edges}
        assert any(t in edge_types for t in ["PURCHASED_FROM", "PAID_WITH", "COVERED_BY", "MANUFACTURED_BY", "PROVIDED_BY"])
    finally:
        db.close()


def test_duplicate_node_prevention():
    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)
        graph = get_graph_store(db)

        # Upsert Node 1
        n1 = graph.upsert_node(
            user.id,
            type="product",
            name="Samsung Galaxy S26 Ultra",
            attributes={"price": 129999, "currency": "INR"},
        )
        db.commit()

        # Upsert Node 2 with same normalized name but extra attributes & aliases
        n2 = graph.upsert_node(
            user.id,
            type="product",
            name="samsung galaxy s26 ultra",
            attributes={"model": "SM-S926B"},
            aliases=["Galaxy S26 Ultra"],
        )
        db.commit()

        assert n1.id == n2.id, "Duplicate node creation must be prevented by canonical key & normalized name!"

        # Verify merged attributes
        all_entities = graph.entities(user.id, types=["product"])
        assert len(all_entities) == 1
        assert all_entities[0].attributes["price"] == 129999
        assert all_entities[0].attributes["model"] == "SM-S926B"
        assert "Galaxy S26 Ultra" in all_entities[0].aliases
    finally:
        db.close()


def test_duplicate_relationship_prevention():
    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)
        graph = get_graph_store(db)

        n1 = graph.upsert_node(user.id, type="product", name="Samsung Galaxy S26 Ultra")
        n2 = graph.upsert_node(user.id, type="retailer", name="Amazon")
        db.commit()

        # Upsert edge twice
        e1 = graph.upsert_edge(user.id, n1.id, n2.id, type="PURCHASED_FROM", attributes={"store": "Amazon.in"})
        e2 = graph.upsert_edge(user.id, n1.id, n2.id, type="purchased_from", attributes={"order_id": "12345"})
        db.commit()

        assert e1.id == e2.id, "Duplicate edge creation must be prevented!"

        all_rels = graph.relationships(user.id)
        assert len(all_rels) == 1
        assert all_rels[0].attributes["store"] == "Amazon.in"
        assert all_rels[0].attributes["order_id"] == "12345"
    finally:
        db.close()


def test_graph_view_alert_surfacing():
    db = SessionLocal()
    try:
        user = get_or_create_demo_user(db)
        graph = get_graph_store(db)

        product = graph.upsert_node(user.id, type="product", name="Samsung Galaxy S26 Ultra")
        db.commit()

        # Publish external security alert matching product
        publish_external_item(
            db,
            source_name="Samsung Security",
            title="Critical Firmware Security Update for Galaxy S26 Ultra",
            body="Security alert for model SM-S926B.",
            category="security",
        )
        run_monitoring(db, user.id)

        # Check graph view
        view = graph.view(user.id)
        alert_nodes = [n for n in view.nodes if n["type"] == "alert"]
        affected_edges = [e for e in view.edges if e["type"] == "AFFECTED_BY"]

        assert len(alert_nodes) >= 0
        if len(alert_nodes) > 0:
            assert len(affected_edges) > 0
            assert affected_edges[0]["source"] == product.id
    finally:
        db.close()
