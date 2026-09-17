from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..graphstore.factory import get_graph_store
from ..models import Alert, Document, User
from .deps import current_user, serialize_alert, serialize_document

router = APIRouter(prefix="/api/graph", tags=["life-graph"])


@router.get("")
def life_graph(db: Session = Depends(get_db), user: User = Depends(current_user)):
    view = get_graph_store(db).view(user.id)
    return {"nodes": view.nodes, "edges": view.edges}


@router.get("/entities/{entity_id}")
def entity_detail(
    entity_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    graph = get_graph_store(db)
    entity = graph.get_entity(entity_id)
    if entity is None or entity.user_id != user.id:
        raise HTTPException(status_code=404, detail="entity not found")

    neighbors = graph.neighbors(entity.id, depth=2)
    document = db.get(Document, entity.document_id) if entity.document_id else None
    linked_docs = [document] if document else []
    for hop in neighbors:
        if hop["entity"].document_id:
            doc = db.get(Document, hop["entity"].document_id)
            if doc and doc.id not in {d.id for d in linked_docs}:
                linked_docs.append(doc)

    alerts = list(
        db.execute(
            select(Alert)
            .where(Alert.user_id == user.id, Alert.entity_id == entity.id)
            .order_by(Alert.created_at.desc())
        ).scalars()
    )
    return {
        "entity": {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "attributes": entity.attributes or {},
            "aliases": entity.aliases or [],
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
        },
        "connections": [
            {
                "id": hop["entity"].id,
                "name": hop["entity"].name,
                "type": hop["entity"].type,
                "relationship": hop["relationship"],
                "direction": hop["direction"],
                "hops": hop["hops"],
            }
            for hop in neighbors
        ],
        "documents": [serialize_document(d) for d in linked_docs],
        "alerts": [serialize_alert(a, entity) for a in alerts],
        "counts": {
            "connections": len(neighbors),
            "documents": len(linked_docs),
            "alerts": len(alerts),
        },
    }
