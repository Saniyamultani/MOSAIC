from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..graphstore.factory import get_graph_store
from ..models import Document, User
from ..rag.store import PRIVATE, get_vector_store
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


@router.get("/{document_id}/evaluation")
def evaluate_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Measure whether an uploaded document is retrievable from this user's private index."""
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="document not found")
    if document.status != "confirmed":
        raise HTTPException(status_code=409, detail="confirm the document before evaluating retrieval")

    extraction = document.extraction or {}
    fields = extraction.get("fields") or {}
    query_parts = [
        str(fields.get(key) or "").strip()
        for key in ("product", "brand", "seller", "biller", "subscription_name")
    ]
    query_parts = [part for part in query_parts if part]
    query = " ".join(query_parts) or extraction.get("summary") or document.title or document.kind

    hits = get_vector_store(db).search(
        collection=PRIVATE,
        query=str(query),
        k=5,
        user_id=user.id,
        ref_types=["document"],
    )
    matched_hits = [hit for hit in hits if hit.ref_id == document.id]
    retrieved_count = len(hits)
    matched_count = len(matched_hits)
    context_precision = matched_count / retrieved_count if retrieved_count else 0.0
    context_recall = 1.0 if matched_hits else 0.0

    graph = get_graph_store(db)
    linked_entities = [
        entity
        for entity in graph.entities(user.id)
        if entity.document_id == document.id
    ]

    return {
        "document_id": document.id,
        "method": "deterministic_source_attribution",
        "query": str(query),
        "note": (
            "RAGAS-style retrieval checks use exact document IDs as relevance labels. "
            "No RAGAS package, LLM judge, semantic faithfulness score, or answer quality "
            "score was run."
        ),
        "metrics": {
            "context_precision": context_precision,
            "context_precision_definition": (
                "Retrieved document hits matching this upload divided by all retrieved document hits."
            ),
            "context_recall": context_recall,
            "context_recall_definition": (
                "1 when this upload appears in the top five document hits; otherwise 0."
            ),
        },
        "checks": [
            {
                "name": "Uploaded document is retrievable",
                "passed": bool(matched_hits),
                "actual": (
                    f"Found at rank {hits.index(matched_hits[0]) + 1} with similarity "
                    f"{matched_hits[0].score:.3f}."
                    if matched_hits
                    else "The uploaded document did not appear in the top five document hits."
                ),
            },
            {
                "name": "Life Graph provenance",
                "passed": bool(linked_entities),
                "actual": (
                    f"{len(linked_entities)} graph entities are linked to this document."
                    if linked_entities
                    else "No graph entities are linked to this document."
                ),
            },
        ],
        "retrieved_documents": [
            {
                "document_id": hit.ref_id,
                "title": hit.meta.get("title") or hit.ref_id,
                "score": round(hit.score, 4),
                "matches_uploaded_document": hit.ref_id == document.id,
            }
            for hit in hits
        ],
        "extracted_fields": {
            key: fields.get(key)
            for key in (
                "product",
                "price",
                "purchase_date",
                "seller",
                "payment_method",
                "warranty_months",
                "duration_months",
            )
            if fields.get(key) not in (None, "", [])
        },
    }


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
