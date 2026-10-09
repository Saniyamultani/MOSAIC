"""Use-case layer sitting between the API and the agents."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import hashlib
import hmac
import secrets

from .agents.alert import AlertAgent
from .agents.base import Trace
from .agents.research import ResearchAgent
from .config import settings
from .graphstore.factory import get_graph_store
from .models import AgentRun, Alert, Document, Entity, ExternalItem, User, UserSession, utcnow
from .pipeline.graph import build_ingestion_graph, run_monitor_cycle

log = logging.getLogger("mosaic.services")


# --- users & authentication --------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${pw_hash}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or "$" not in hashed_password:
        return False
    try:
        salt, expected_hash = hashed_password.split("$", 1)
        pw_hash = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return hmac.compare_digest(pw_hash, expected_hash)
    except Exception:
        return False


def create_user_session(db: Session, user_id: str) -> str:
    token = secrets.token_hex(32)
    session = UserSession(token=token, user_id=user_id)
    db.add(session)
    db.commit()
    return token


def get_user_by_session_token(db: Session, token: str) -> User | None:
    if not token:
        return None
    session = db.get(UserSession, token)
    if session:
        return session.user
    return None


def delete_user_session(db: Session, token: str) -> bool:
    if not token:
        return False
    session = db.get(UserSession, token)
    if session:
        db.delete(session)
        db.commit()
        return True
    return False


def get_or_create_demo_user(db: Session) -> User:
    user = db.execute(
        select(User).where(User.email == settings.demo_user_email)
    ).scalar_one_or_none()
    if user is None:
        user = User(email=settings.demo_user_email, name=settings.demo_user_name)
        db.add(user)
        db.flush()
    elif user.name != settings.demo_user_name:
        # Keep the seeded single-user demo in sync when its configured name changes.
        user.name = settings.demo_user_name
    return user


# --- ingestion --------------------------------------------------------------
def start_ingestion(
    db: Session, user_id: str, input_type: str, payload: dict
) -> tuple[Document, list[dict], str]:
    """Runs the ingestion graph up to the human-confirm pause."""
    trace = Trace()
    graph = build_ingestion_graph(db, trace)
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.invoke(
        {"user_id": user_id, "input_type": input_type, "payload": payload, "steps": []},
        config=config,
    )
    document = db.get(Document, state["document_id"])
    return document, trace.as_list(), thread_id


def confirm_ingestion(
    db: Session, thread_id: str, document_id: str, overrides: dict | None = None
) -> dict:
    """Resumes the paused ingestion graph -- the ✓ Confirm step."""
    trace = Trace()
    graph = build_ingestion_graph(db, trace)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = graph.invoke(
            {"overrides": overrides or {}} if overrides else None, config=config
        )
        result = state.get("result")
    except Exception as exc:  # noqa: BLE001
        log.warning("resume failed (%s); committing directly", exc)
        result = None

    if not result:
        # Fallback path: the checkpoint is gone (process restarted). Do the same
        # work without the graph so a confirm never dead-ends.
        from .agents.entity import EntityAgent

        document = db.get(Document, document_id)
        applied = EntityAgent(db, trace).apply_document(document, overrides or {})
        document.status = "confirmed"
        document.confirmed_at = utcnow()
        db.flush()
        result = {
            "document_id": document.id,
            "entities": [
                {"id": e.id, "name": e.name, "type": e.type} for e in applied["entities"]
            ],
            "created": applied["created"],
            "merged": applied["merged"],
            "edges": applied["edges"],
        }

    document = db.get(Document, result["document_id"])
    run = AgentRun(
        user_id=document.user_id,
        run_type="ingestion",
        document_id=document.id,
        outcome="confirmed",
        steps=trace.as_list(),
        finished_at=utcnow(),
    )
    db.add(run)

    connections = detect_connections(db, document)
    db.commit()
    return {**result, "trace": trace.as_list(), "connections": connections}


def detect_connections(db: Session, document: Document) -> list[dict]:
    """🔵 New-connection tier: this document tied together things that were
    previously unrelated in the user's graph."""
    graph = get_graph_store(db)
    alerts = AlertAgent(db)
    found: list[dict] = []
    entities = [
        e
        for e in graph.entities(document.user_id)
        if e.document_id == document.id and e.type in ("product", "subscription", "bill")
    ]
    for entity in entities:
        for hop in graph.neighbors(entity.id, depth=2):
            other = hop["entity"]
            if other.document_id and other.document_id != document.id and hop["hops"] == 2:
                reason = (
                    f"Your {entity.name} and {other.name} are connected through "
                    f"{hop['relationship'].replace('_', ' ').lower()} — MOSAIC linked them "
                    "across two separate documents you uploaded."
                )
                alert = alerts.connection_alert(document.user_id, entity, other, reason)
                found.append({"alert_id": alert.id, "entity": entity.name, "related": other.name})
                break
    return found


# --- monitoring -------------------------------------------------------------
def run_monitoring(db: Session, user_id: str | None = None, only_unprocessed: bool = True) -> dict:
    """Poll approved sources, then run the verification pipeline for each user."""
    trace = Trace()
    research = ResearchAgent(db, trace)
    research.poll()
    db.commit()

    users = (
        [db.get(User, user_id)] if user_id else list(db.execute(select(User)).scalars())
    )
    users = [u for u in users if u is not None]

    stmt = select(ExternalItem)
    if only_unprocessed:
        stmt = stmt.where(ExternalItem.processed.is_(False))
    items = list(db.execute(stmt.order_by(ExternalItem.ingested_at)).scalars())

    summary = {
        "polled_items": len(items),
        "alerts": 0,
        "suppressed": 0,
        "no_match": 0,
        "runs": [],
    }
    for item in items:
        for user in users:
            run = run_monitor_cycle(db, user.id, item)
            summary["runs"].append(
                {"run_id": run.id, "item": item.title, "outcome": run.outcome}
            )
            if run.outcome == "alerted":
                summary["alerts"] += 1
            elif run.outcome in ("refuted", "below_threshold"):
                summary["suppressed"] += 1
            else:
                summary["no_match"] += 1
    db.commit()
    return summary


def publish_external_item(
    db: Session,
    source_name: str,
    title: str,
    body: str,
    category: str = "external_update",
    url: str | None = None,
    metadata: dict | None = None,
    trust_tier: int = 2,
) -> ExternalItem:
    """Inject an outside-world event (used by the demo's 'Day 7')."""
    from .models import Source

    source = db.execute(
        select(Source).where(Source.name == source_name)
    ).scalar_one_or_none()
    if source is None:
        source = Source(name=source_name, kind="fixture", trust_tier=trust_tier, category=category)
        db.add(source)
        db.flush()
    research = ResearchAgent(db)
    item = research.record_item(
        source,
        external_id=f"manual-{uuid.uuid4().hex[:8]}",
        title=title,
        body=body,
        url=url,
        category=category,
        published_at=None,
        metadata=metadata or {},
    )
    db.commit()
    return item


# --- dashboard --------------------------------------------------------------
def dashboard_summary(db: Session, user_id: str) -> dict:
    graph = get_graph_store(db)
    view = graph.view(user_id)
    alerts = list(
        db.execute(
            select(Alert).where(Alert.user_id == user_id, Alert.status == "new")
        ).scalars()
    )
    upcoming = []
    for node in view.nodes:
        attrs = node["attributes"]
        for key, label in (
            ("expiry_date", "Warranty expires"),
            ("renewal_date", "Renews"),
            ("due_date", "Bill due"),
            ("event_date", "Event"),
        ):
            if attrs.get(key):
                upcoming.append(
                    {"entity_id": node["id"], "name": node["name"], "label": label,
                     "date": attrs[key]}
                )
    upcoming.sort(key=lambda u: u["date"])
    documents = db.execute(
        select(Document).where(Document.user_id == user_id)
    ).scalars()
    return {
        "important": len([a for a in alerts if a.severity == "critical"]),
        "connections": len(view.edges),
        "upcoming": len(upcoming),
        "upcoming_items": upcoming[:6],
        "nodes": len(view.nodes),
        "edges": len(view.edges),
        "documents": len(list(documents)),
        "unread_alerts": len(alerts),
        "llm_provider": settings.resolved_llm_provider,
    }
