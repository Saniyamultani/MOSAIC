from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..services import get_or_create_demo_user, get_user_by_session_token


def extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    session_header = request.headers.get("X-Session-Token") or request.headers.get("X-User-Token")
    if session_header:
        return session_header.strip()
    return None


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authenticated user resolution.

    Resolves user from Bearer/Session token or X-User-Id header.
    Falls back to demo user if no auth token or header is present.
    """
    token = extract_token(request)
    if token:
        user = get_user_by_session_token(db, token)
        if user:
            return user
        raise HTTPException(status_code=401, detail="Invalid or expired session token")

    user_id_header = request.headers.get("X-User-Id")
    if user_id_header:
        user = db.get(User, user_id_header.strip())
        if user:
            return user
        raise HTTPException(status_code=404, detail="User not found")

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
