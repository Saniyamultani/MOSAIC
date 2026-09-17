"""Tools for MOSAIC Assistant: Life Graph, Private RAG, Web Search, Purchases/Expenses, Warranties, Alerts, Upcoming Items, and Current DateTime."""
from __future__ import annotations

import html
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..agents.skeptic import SkepticAgent
from ..config import settings
from ..graphstore.factory import get_graph_store
from ..models import Alert, Document, Entity, ExternalItem, Relationship
from ..rag.store import get_vector_store

# India Standard Time: UTC+5:30
_IST = timezone(timedelta(hours=5, minutes=30))


def get_current_datetime() -> Dict[str, str]:
    """Return the current date, time, timezone, day, and ISO timestamp in Asia/Kolkata (IST)."""
    now = datetime.now(_IST)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "time_full": now.strftime("%H:%M:%S"),
        "timezone": "Asia/Kolkata (IST, UTC+5:30)",
        "day": now.strftime("%A"),
        "month": now.strftime("%B"),
        "year": str(now.year),
        "iso": now.isoformat(),
        "human": now.strftime("%A, %d %B %Y at %I:%M %p IST"),
    }


def search_life_graph(db: Session, user_id: str, query: str) -> List[Dict[str, Any]]:
    """Search user's Life Graph entities and relationships."""
    graph = get_graph_store(db)
    terms = [w for w in re.findall(r"[a-zA-Z0-9]+", query) if len(w) >= 3]
    entities = graph.search_entities(user_id, terms)
    if not entities:
        entities = graph.entities(user_id)

    results: List[Dict[str, Any]] = []
    for entity in entities[:10]:
        neighbors = graph.neighbors(entity.id, depth=1)
        connected_names = [n["entity"].name for n in neighbors if hasattr(n["entity"], "name")]
        results.append({
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "attributes": entity.attributes or {},
            "aliases": entity.aliases or [],
            "connections": connected_names,
        })
    return results


def lookup_entity(db: Session, user_id: str, identifier: str) -> Optional[Dict[str, Any]]:
    """Find a specific entity by ID or name within user's Life Graph."""
    graph = get_graph_store(db)
    # Check by ID first
    entity = graph.get_entity(identifier)
    if entity and entity.user_id != user_id:
        return None

    if not entity:
        # Search by exact or partial name
        stmt = select(Entity).where(Entity.user_id == user_id)
        all_entities = list(db.execute(stmt).scalars())
        for e in all_entities:
            if identifier.lower() in e.name.lower() or any(identifier.lower() in a.lower() for a in (e.aliases or [])):
                entity = e
                break

    if not entity:
        return None

    neighbors = graph.neighbors(entity.id, depth=1)
    connected = [
        {
            "id": n["entity"].id,
            "name": n["entity"].name,
            "type": n["entity"].type,
            "relationship": n["relationship"],
        }
        for n in neighbors if hasattr(n["entity"], "name")
    ]

    return {
        "id": entity.id,
        "name": entity.name,
        "type": entity.type,
        "attributes": entity.attributes or {},
        "aliases": entity.aliases or [],
        "document_id": entity.document_id,
        "connections": connected,
    }


def search_private_documents(db: Session, user_id: str, query: str) -> List[Dict[str, Any]]:
    """Search private documents and text extractions belonging to user."""
    vector_store = get_vector_store(db)
    raw_hits = vector_store.search(collection="private", query=query, k=5, user_id=user_id)

    hits: List[Dict[str, Any]] = []
    for hit in raw_hits:
        hits.append({
            "title": hit.meta.get("title", "Document"),
            "snippet": hit.text,
            "score": hit.score,
            "doc_id": hit.ref_id,
            "is_private": True,
        })

    # Direct DB document keyword search fallback
    raw_terms = [w for w in re.findall(r"[a-zA-Z0-9]+", query) if len(w) >= 3]
    terms = set(raw_terms)
    if "buy" in terms or "bought" in terms or "when" in terms:
        terms.update({"bought", "buy", "purchase", "purchased", "receipt", "invoice"})
    if "invoice" in terms or "receipt" in terms:
        terms.update({"invoice", "receipt", "paid"})

    if terms:
        clauses = [Document.raw_text.ilike(f"%{t}%") for t in terms]
        clauses += [Document.title.ilike(f"%{t}%") for t in terms]
        docs = list(
            db.execute(
                select(Document).where(Document.user_id == user_id, or_(*clauses))
            ).scalars()
        )
        for doc in docs:
            if not any(h["doc_id"] == doc.id for h in hits):
                hits.append({
                    "title": doc.title or "Uploaded document",
                    "snippet": (doc.raw_text or "")[:400],
                    "score": 0.8,
                    "doc_id": doc.id,
                    "is_private": True,
                })

    return hits[:5]


def search_web(query: str) -> List[Dict[str, Any]]:
    """Perform live web search via Tavily API or DuckDuckGo research fallback.

    Every result is stamped with ``retrieved_at`` (current IST datetime ISO string)
    so the freshness router and answer node can emit "as of" dates.
    """
    retrieved_at = datetime.now(_IST).isoformat()
    results: List[Dict[str, Any]] = []

    # 1. Try Tavily API search if key is set
    tavily_key = settings.tavily_api_key or os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_key,
                    "query": query,
                    "max_results": 6,
                    "include_answer": True,
                    "search_depth": "advanced",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for res in data.get("results", []):
                    results.append({
                        "source": res.get("title") or "Tavily Search",
                        "title": res.get("title", "Web Result"),
                        "snippet": res.get("content", ""),
                        "url": res.get("url"),
                        "published_at": res.get("published_date"),  # Tavily may include this
                        "retrieved_at": retrieved_at,
                        "search_provider": "tavily",
                        "is_web": True,
                    })
                if results:
                    return results
        except Exception:
            pass

    # 2. DuckDuckGo HTML search fallback
    try:
        resp = httpx.get(
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
            headers={"User-Agent": settings.research_user_agent},
            timeout=8,
        )
        if resp.status_code == 200:
            snippets = re.findall(
                r'class="result__snippet"[^>]*>(.*?)</a?>',
                resp.text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            titles = re.findall(
                r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                resp.text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            for index, (raw_url, title) in enumerate(titles[:5]):
                clean_title = re.sub(r"<[^>]+>", "", html.unescape(title)).strip()
                clean_snippet = (
                    re.sub(r"<[^>]+>", "", html.unescape(snippets[index])).strip()
                    if index < len(snippets)
                    else ""
                )
                clean_url = html.unescape(raw_url)
                if "uddg=" in clean_url:
                    parsed = urlparse(clean_url)
                    qs = parse_qs(parsed.query)
                    if "uddg" in qs:
                        clean_url = qs["uddg"][0]
                elif clean_url.startswith("//"):
                    clean_url = "https:" + clean_url

                results.append({
                    "source": "Web Search",
                    "title": clean_title,
                    "snippet": clean_snippet,
                    "url": clean_url,
                    "published_at": None,
                    "retrieved_at": retrieved_at,
                    "search_provider": "duckduckgo",
                    "is_web": True,
                })
    except Exception:
        pass
    return results


def search_external_information(
    db: Session, user_id: str, query: str, device_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Perform external research and run Skeptic check against user's specific device model."""
    results: List[Dict[str, Any]] = []

    # Extract search terms to filter database items
    terms = [w for w in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(w) >= 3]

    # 1. Search database external items matching relevant query terms or device context
    matched_items: List[ExternalItem] = []
    if terms:
        clauses = [ExternalItem.title.ilike(f"%{t}%") for t in terms]
        clauses += [ExternalItem.body.ilike(f"%{t}%") for t in terms]
        matched_items = list(
            db.execute(
                select(ExternalItem).where(or_(*clauses)).order_by(ExternalItem.ingested_at.desc()).limit(5)
            ).scalars()
        )

    # 2. Live web search
    web_results = search_web(query)
    results.extend(web_results)

    # 3. Skeptic check on matching external database items
    skeptic = SkepticAgent(db)
    for item in matched_items:
        if device_context and device_context.get("id"):
            entity = db.get(Entity, device_context["id"])
            if entity:
                candidate = {"entity": entity, "match_strength": 0.8, "reasons": ["matching name"]}
                review = skeptic.review(item, candidate)
                results.append({
                    "source": item.external_id,
                    "title": item.title,
                    "snippet": item.body[:400],
                    "url": item.url,
                    "affected_models": (item.metadata_json or {}).get("affected_models", []),
                    "refuted": review["refuted"],
                    "objections": review["objections"],
                    "checks": review["checks"],
                    "is_web": False,
                })
                continue

        results.append({
            "source": item.external_id,
            "title": item.title,
            "snippet": item.body[:400],
            "url": item.url,
            "refuted": False,
            "is_web": False,
        })

    return results[:6]


def lookup_purchases_and_expenses(db: Session, user_id: str, query: str) -> List[Dict[str, Any]]:
    """Find purchase receipts, prices, payment methods, and expense records for user."""
    stmt = select(Entity).where(Entity.user_id == user_id)
    entities = list(db.execute(stmt).scalars())

    purchases: List[Dict[str, Any]] = []
    for e in entities:
        attrs = e.attributes or {}
        if "price" in attrs or "amount" in attrs or "purchase_date" in attrs or e.type in ("product", "bill", "subscription"):
            purchases.append({
                "id": e.id,
                "name": e.name,
                "type": e.type,
                "price": attrs.get("price") or attrs.get("amount"),
                "currency": attrs.get("currency", "INR"),
                "purchase_date": attrs.get("purchase_date") or attrs.get("due_date"),
                "seller": attrs.get("seller") or attrs.get("provider") or attrs.get("biller"),
                "payment_method": attrs.get("payment_method"),
            })
    return purchases


def lookup_warranties(db: Session, user_id: str, identifier: Optional[str] = None) -> List[Dict[str, Any]]:
    """Look up warranty information for user's owned items."""
    stmt = select(Entity).where(Entity.user_id == user_id)
    all_entities = list(db.execute(stmt).scalars())

    warranties: List[Dict[str, Any]] = []
    for e in all_entities:
        attrs = e.attributes or {}
        if e.type == "warranty" or "expiry_date" in attrs or "duration_months" in attrs or "start_date" in attrs:
            if identifier and identifier.lower() not in e.name.lower() and not any(identifier.lower() in a.lower() for a in (e.aliases or [])):
                continue
            warranties.append({
                "id": e.id,
                "name": e.name,
                "type": e.type,
                "provider": attrs.get("provider") or attrs.get("brand"),
                "start_date": attrs.get("start_date") or attrs.get("purchase_date"),
                "expiry_date": attrs.get("expiry_date"),
                "duration_months": attrs.get("duration_months"),
                "attributes": attrs,
            })
    return warranties


def lookup_alerts(db: Session, user_id: str, alert_id_or_status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Look up active or historical alerts for user."""
    stmt = select(Alert).where(Alert.user_id == user_id)
    if alert_id_or_status and alert_id_or_status in {"new", "dismissed", "acted"}:
        stmt = stmt.where(Alert.status == alert_id_or_status)
    alerts = list(db.execute(stmt.order_by(Alert.created_at.desc())).scalars())

    out: List[Dict[str, Any]] = []
    for a in alerts[:8]:
        out.append({
            "id": a.id,
            "headline": a.headline,
            "explanation": a.explanation,
            "severity": a.severity,
            "confidence": a.confidence,
            "status": a.status,
            "why_it_matters": a.why_it_matters or [],
            "reasoning_chain": a.reasoning_chain or [],
            "evidence": a.evidence or [],
            "suggested_action": a.suggested_action,
        })
    return out


def lookup_upcoming(db: Session, user_id: str) -> List[Dict[str, Any]]:
    """Find upcoming renewals, bill due dates, and warranty expiries."""
    stmt = select(Entity).where(Entity.user_id == user_id)
    entities = list(db.execute(stmt).scalars())

    upcoming: List[Dict[str, Any]] = []
    for e in entities:
        attrs = e.attributes or {}
        date_str = attrs.get("due_date") or attrs.get("renewal_date") or attrs.get("expiry_date") or attrs.get("event_date")
        if date_str:
            label = "due" if "due_date" in attrs else ("renews" if "renewal_date" in attrs else "expires")
            upcoming.append({
                "entity_id": e.id,
                "name": e.name,
                "label": label,
                "date": str(date_str),
                "attributes": attrs,
            })
    return upcoming
