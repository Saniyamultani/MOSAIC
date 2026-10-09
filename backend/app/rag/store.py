"""Two knowledge stores, one interface.

PRIVATE  -> the user's own world (receipts, warranties, bills, subscriptions...)
EXTERNAL -> the outside world (manufacturer notices, recalls, regulator updates)

Backend defaults to the relational DB (works on SQLite and Postgres alike);
set VECTOR_BACKEND=qdrant to use Qdrant instead.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Embedding
from .embeddings import get_embedder

log = logging.getLogger("mosaic.rag.store")

PRIVATE = "private"
EXTERNAL = "external"
MIN_SIMILARITY_SCORE = 0.06


@dataclass
class RetrievedChunk:
    ref_type: str
    ref_id: str
    text: str
    score: float
    collection: str
    meta: dict = field(default_factory=dict)

    def as_evidence(self) -> dict:
        text_snip = self.text[:400].strip()
        if text_snip.startswith("{") and "}" in text_snip:
            try:
                import json
                data = json.loads(self.text)
                if isinstance(data, dict):
                    summary = data.get("summary") or data.get("kind")
                    fields = data.get("fields") or {}
                    field_str = ", ".join(f"{k}: {v}" for k, v in fields.items() if v is not None and v != "")
                    text_snip = f"{summary}: {field_str}" if summary else field_str
            except Exception:
                pass
        return {
            "kind": self.collection,
            "ref_type": self.ref_type,
            "ref_id": self.ref_id,
            "score": round(self.score, 3),
            "title": self.meta.get("title") or self.text[:80],
            "snippet": text_snip,
            "url": self.meta.get("url"),
            "source": self.meta.get("source_name"),
        }


class VectorStore:
    """SQL-backed cosine store. Small corpora, zero infrastructure."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedder = get_embedder()

    def upsert(
        self,
        collection: str,
        ref_type: str,
        ref_id: str,
        text: str,
        meta: dict | None = None,
        user_id: str | None = None,
    ) -> None:
        if not (text or "").strip():
            return
        self.db.execute(
            delete(Embedding).where(
                Embedding.collection == collection,
                Embedding.ref_type == ref_type,
                Embedding.ref_id == ref_id,
            )
        )
        vector = self.embedder.embed(text)
        self.db.add(
            Embedding(
                collection=collection,
                user_id=user_id,
                ref_type=ref_type,
                ref_id=ref_id,
                text=text[:20000],
                meta=meta or {},
                vector=vector.astype(np.float32).tobytes(),
            )
        )
        self.db.flush()

    def search(
        self,
        collection: str,
        query: str,
        k: int = 5,
        user_id: str | None = None,
        ref_types: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        stmt = select(Embedding).where(Embedding.collection == collection)
        if user_id:
            stmt = stmt.where(Embedding.user_id == user_id)
        if ref_types:
            stmt = stmt.where(Embedding.ref_type.in_(ref_types))
        rows = list(self.db.execute(stmt).scalars())
        if not rows:
            return []
        qvec = self.embedder.embed(query)
        if not np.any(qvec):
            return []
        matrix = np.vstack([np.frombuffer(r.vector, dtype=np.float32) for r in rows])
        if matrix.shape[1] != qvec.shape[0]:
            log.warning("embedding dimension changed; rebuild the index")
            return []
        scores = matrix @ qvec
        order = np.argsort(-scores)[:k]
        return [
            RetrievedChunk(
                ref_type=rows[i].ref_type,
                ref_id=rows[i].ref_id,
                text=rows[i].text,
                score=float(scores[i]),
                collection=collection,
                meta=rows[i].meta or {},
            )
            for i in order
            if float(scores[i]) >= MIN_SIMILARITY_SCORE
        ]

    def count(self, collection: str, user_id: str | None = None) -> int:
        stmt = select(Embedding).where(Embedding.collection == collection)
        if user_id:
            stmt = stmt.where(Embedding.user_id == user_id)
        return len(list(self.db.execute(stmt).scalars()))


class QdrantVectorStore(VectorStore):  # pragma: no cover - optional path
    """Opt-in Qdrant backend; same interface, remote index."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self.client = QdrantClient(url=settings.qdrant_url)
        self._VectorParams = VectorParams
        self._Distance = Distance
        for collection in (PRIVATE, EXTERNAL):
            if not self.client.collection_exists(collection):
                self.client.create_collection(
                    collection,
                    vectors_config=VectorParams(
                        size=self.embedder.dim, distance=Distance.COSINE
                    ),
                )

    def upsert(self, collection, ref_type, ref_id, text, meta=None, user_id=None) -> None:
        import uuid

        from qdrant_client.models import PointStruct

        if not (text or "").strip():
            return
        payload = {
            "ref_type": ref_type, "ref_id": ref_id, "user_id": user_id,
            "text": text[:20000], **(meta or {}),
        }
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{collection}/{ref_type}/{ref_id}"))
        self.client.upsert(
            collection,
            [PointStruct(id=point_id, vector=self.embedder.embed(text).tolist(), payload=payload)],
        )

    def search(self, collection, query, k=5, user_id=None, ref_types=None):
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        must = []
        if user_id:
            must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        if ref_types:
            must.append(FieldCondition(key="ref_type", match=MatchAny(any=ref_types)))
        hits = self.client.search(
            collection,
            query_vector=self.embedder.embed(query).tolist(),
            limit=k,
            query_filter=Filter(must=must) if must else None,
        )
        return [
            RetrievedChunk(
                ref_type=h.payload.get("ref_type", ""),
                ref_id=h.payload.get("ref_id", ""),
                text=h.payload.get("text", ""),
                score=float(h.score),
                collection=collection,
                meta=h.payload,
            )
            for h in hits
            if float(h.score) >= MIN_SIMILARITY_SCORE
        ]


def get_vector_store(db: Session) -> VectorStore:
    if settings.vector_backend == "qdrant":
        try:
            return QdrantVectorStore(db)
        except Exception as exc:  # noqa: BLE001
            log.warning("Qdrant unavailable (%s); using the SQL vector store", exc)
    return VectorStore(db)
