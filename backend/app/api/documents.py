from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Document, User
from ..schemas import ConfirmRequest, TextIngestRequest, UrlIngestRequest
from ..services import confirm_ingestion, start_ingestion
from .deps import current_user, serialize_document

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _ingest_response(document, trace, thread_id) -> dict:
    return {
        "document": serialize_document(document),
        "thread_id": thread_id,
        "trace": trace,
        "awaiting_confirmation": document.status == "pending_confirmation",
    }


@router.post("/text")
def ingest_text(
    body: TextIngestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    document, trace, thread_id = start_ingestion(
        db, user.id, "text",
        {"text": body.text, "kind_hint": body.kind_hint, "title": body.title},
    )
    return _ingest_response(document, trace, thread_id)


@router.post("/upload")
async def ingest_file(
    file: UploadFile = File(...),
    kind_hint: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    document, trace, thread_id = start_ingestion(
        db, user.id, "file",
        {
            "filename": file.filename,
            "content_b64": base64.b64encode(data).decode("ascii"),
            "mime_type": file.content_type,
            "kind_hint": kind_hint,
        },
    )
    return _ingest_response(document, trace, thread_id)


@router.post("/url")
def ingest_url(
    body: UrlIngestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    document, trace, thread_id = start_ingestion(
        db, user.id, "url", {"url": body.url, "kind_hint": body.kind_hint}
    )
    return _ingest_response(document, trace, thread_id)


@router.post("/{document_id}/confirm")
def confirm(
    document_id: str,
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="document not found")
    if document.status == "confirmed":
        return {"document_id": document.id, "already_confirmed": True}
    result = confirm_ingestion(db, body.thread_id or "", document_id, body.overrides)
    return result


@router.delete("/{document_id}")
def reject(document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="document not found")
    document.status = "rejected"
    db.commit()
    return {"document_id": document.id, "status": document.status}


@router.get("")
def list_documents(db: Session = Depends(get_db), user: User = Depends(current_user)):
    docs = list(
        db.execute(
            select(Document)
            .where(Document.user_id == user.id)
            .order_by(Document.created_at.desc())
        ).scalars()
    )
    return {"documents": [serialize_document(d) for d in docs]}
