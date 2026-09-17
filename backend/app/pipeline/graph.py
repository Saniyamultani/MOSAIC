"""LangGraph orchestration.

Two state machines:

  ingestion_graph   parse → extract → ⏸ human confirm → resolve → write → index
  monitor_graph     relate → retrieve → skeptic → relevance → alert

Conditional edges are where the Skeptic and Relevance agents earn their keep:
a refuted match or a sub-threshold score exits the graph without ever producing
a notification, and the reason is recorded in the run trace either way.
"""
from __future__ import annotations

import base64
import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from ..agents.alert import AlertAgent
from ..agents.base import Trace
from ..agents.entity import EntityAgent
from ..agents.ingestion import IngestionAgent
from ..agents.rag import RagAgent
from ..agents.relationship import RelationshipAgent
from ..agents.relevance import RelevanceAgent
from ..agents.skeptic import SkepticAgent
from ..models import AgentRun, ExternalItem, Source, utcnow
from .state import IngestionState, MonitorState

log = logging.getLogger("mosaic.pipeline")

# Shared across requests so an ingestion paused in one HTTP call can be resumed
# by the confirm call that follows.
INGESTION_CHECKPOINTER = MemorySaver()


# ---------------------------------------------------------------------------
# Ingestion graph
# ---------------------------------------------------------------------------
def build_ingestion_graph(db: Session, trace: Trace):
    ingestion = IngestionAgent(db, trace)
    entity_agent = EntityAgent(db, trace)

    def capture(state: IngestionState) -> dict:
        payload = state["payload"]
        kind_hint = payload.get("kind_hint")
        if state["input_type"] == "file":
            doc = ingestion.ingest_file(
                state["user_id"],
                payload["filename"],
                base64.b64decode(payload["content_b64"]),
                payload.get("mime_type"),
                kind_hint,
            )
        elif state["input_type"] == "url":
            doc = ingestion.ingest_url(state["user_id"], payload["url"], kind_hint)
        else:
            doc = ingestion.ingest_text(
                state["user_id"], payload["text"], kind_hint, payload.get("title")
            )
        db.commit()
        return {"document_id": doc.id, "extraction": doc.extraction, "steps": trace.as_list()}

    def commit(state: IngestionState) -> dict:
        from ..models import Document

        doc = db.get(Document, state["document_id"])
        result = entity_agent.apply_document(doc, state.get("overrides") or {})
        doc.status = "confirmed"
        doc.confirmed_at = utcnow()
        db.commit()
        return {
            "result": {
                "document_id": doc.id,
                "entities": [
                    {"id": e.id, "name": e.name, "type": e.type} for e in result["entities"]
                ],
                "created": result["created"],
                "merged": result["merged"],
                "edges": result["edges"],
            },
            "steps": trace.as_list(),
        }

    builder = StateGraph(IngestionState)
    builder.add_node("capture", capture)
    builder.add_node("commit", commit)
    builder.set_entry_point("capture")
    builder.add_edge("capture", "commit")
    builder.add_edge("commit", END)
    # The pause before `commit` is the user's single ✓ Confirm.
    return builder.compile(checkpointer=INGESTION_CHECKPOINTER, interrupt_before=["commit"])


# ---------------------------------------------------------------------------
# Monitoring graph
# ---------------------------------------------------------------------------
def build_monitor_graph(db: Session, trace: Trace):
    relationship = RelationshipAgent(db, trace)
    rag = RagAgent(db, trace)
    skeptic = SkepticAgent(db, trace)
    relevance = RelevanceAgent(trace)
    alert_agent = AlertAgent(db, trace)

    def _item(state: MonitorState) -> ExternalItem:
        item = db.get(ExternalItem, state["item_id"])
        if item is not None and not (item.metadata_json or {}).get("source_name"):
            source = db.get(Source, item.source_id)
            if source is not None:
                item.metadata_json = {
                    **(item.metadata_json or {}),
                    "source_name": source.name,
                    "trust_tier": source.trust_tier,
                }
        return item

    def relate(state: MonitorState) -> dict:
        item = _item(state)
        candidates = relationship.find_candidates(state["user_id"], item)
        return {
            "candidates": candidates,
            "candidate": candidates[0] if candidates else None,
            "steps": trace.as_list(),
        }

    def retrieve(state: MonitorState) -> dict:
        item = _item(state)
        candidate = state["candidate"]
        query = f"{candidate['entity'].name} {item.title}"
        evidence = rag.evidence_for(state["user_id"], query, k=3)
        return {"evidence": evidence, "steps": trace.as_list()}

    def challenge(state: MonitorState) -> dict:
        item = _item(state)
        return {"skeptic": skeptic.review(item, state["candidate"]), "steps": trace.as_list()}

    def score(state: MonitorState) -> dict:
        item = _item(state)
        return {
            "scores": relevance.score(item, state["candidate"], state["skeptic"]),
            "steps": trace.as_list(),
        }

    def notify(state: MonitorState) -> dict:
        item = _item(state)
        alert = alert_agent.compose(
            state["user_id"], item, state["candidate"], state["skeptic"], state["scores"]
        )
        return {"alert_id": alert.id, "outcome": "alerted", "steps": trace.as_list()}

    # --- routers ------------------------------------------------------------
    def after_relate(state: MonitorState) -> str:
        if not state.get("candidate"):
            trace.add(
                "Relationship Agent", "no_match",
                "Nothing in this user's Life Graph is touched by the announcement.",
            )
            return "stop"
        return "continue"

    def after_challenge(state: MonitorState) -> str:
        if state["skeptic"]["refuted"]:
            trace.add(
                "Skeptic Agent", "suppressed",
                "Alert suppressed: " + (state["skeptic"]["objections"] or ["match refuted"])[0],
            )
            return "stop"
        return "continue"

    def after_score(state: MonitorState) -> str:
        if state["scores"]["severity"] == "suppressed":
            trace.add(
                "Relevance Agent", "suppressed",
                f"Below the {int(state['scores']['confidence'] * 100)}% confidence floor — "
                "not worth interrupting you.",
            )
            return "stop"
        return "continue"

    def stop_no_match(state: MonitorState) -> dict:
        return {"outcome": "no_match", "reason": "no entity in the Life Graph matched",
                "steps": trace.as_list()}

    def stop_refuted(state: MonitorState) -> dict:
        objections = state.get("skeptic", {}).get("objections") or ["match refuted"]
        return {"outcome": "refuted", "reason": objections[0], "steps": trace.as_list()}

    def stop_low(state: MonitorState) -> dict:
        return {
            "outcome": "below_threshold",
            "reason": f"confidence {state['scores']['confidence']:.2f} below floor",
            "steps": trace.as_list(),
        }

    builder = StateGraph(MonitorState)
    builder.add_node("relate", relate)
    builder.add_node("retrieve", retrieve)
    builder.add_node("challenge", challenge)
    builder.add_node("score", score)
    builder.add_node("notify", notify)
    builder.add_node("stop_no_match", stop_no_match)
    builder.add_node("stop_refuted", stop_refuted)
    builder.add_node("stop_low", stop_low)

    builder.set_entry_point("relate")
    builder.add_conditional_edges(
        "relate", after_relate, {"continue": "retrieve", "stop": "stop_no_match"}
    )
    builder.add_edge("retrieve", "challenge")
    builder.add_conditional_edges(
        "challenge", after_challenge, {"continue": "score", "stop": "stop_refuted"}
    )
    builder.add_conditional_edges(
        "score", after_score, {"continue": "notify", "stop": "stop_low"}
    )
    for terminal in ("notify", "stop_no_match", "stop_refuted", "stop_low"):
        builder.add_edge(terminal, END)
    return builder.compile()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_monitor_cycle(db: Session, user_id: str, item: ExternalItem) -> AgentRun:
    """Run the full pipeline for one external item and persist the trace."""
    trace = Trace()
    run = AgentRun(user_id=user_id, run_type="monitor", external_item_id=item.id)
    db.add(run)
    db.flush()

    graph = build_monitor_graph(db, trace)
    try:
        final = graph.invoke({"user_id": user_id, "item_id": item.id, "steps": []})
        run.outcome = final.get("outcome", "alerted" if final.get("alert_id") else "no_match")
        run.alert_id = final.get("alert_id")
    except Exception as exc:  # noqa: BLE001
        log.exception("monitor cycle failed")
        trace.add("Pipeline", "error", str(exc))
        run.outcome = "error"
    run.steps = trace.as_list()
    run.finished_at = utcnow()
    item.processed = True
    db.flush()
    return run
