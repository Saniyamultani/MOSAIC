from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..services import get_or_create_demo_user


def current_user(db: Session = Depends(get_db)) -> User:
    """Single-user demo auth.

    Real auth would swap in here (JWT/session -> User); everything downstream
    already scopes by user_id.
    """
    user = get_or_create_demo_user(db)
    db.commit()
    return user


def serialize_document(doc) -> dict:
    return {
        "id": doc.id,
        "kind": doc.kind,
        "title": doc.title,
        "status": doc.status,
        "filename": doc.filename,
        "source_url": doc.source_url,
        "extraction": doc.extraction or {},
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def serialize_alert(alert, entity=None, item=None) -> dict:
    return {
        "id": alert.id,
        "severity": alert.severity,
        "headline": alert.headline,
        "explanation": alert.explanation,
        "confidence": alert.confidence,
        "status": alert.status,
        "suggested_action": alert.suggested_action,
        "why_it_matters": alert.why_it_matters or [],
        "reasoning_chain": alert.reasoning_chain or [],
        "evidence": alert.evidence or [],
        "entity": {"id": entity.id, "name": entity.name, "type": entity.type} if entity else None,
        "external_item": (
            {"id": item.id, "title": item.title, "url": item.url, "category": item.category}
            if item
            else None
        ),
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }
