"""Agent 4 -- RAG retrieval across both knowledge stores."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..rag.store import EXTERNAL, PRIVATE, RetrievedChunk, get_vector_store
from .base import Agent, Trace


class RagAgent(Agent):
    name = "RAG Agent"

    def __init__(self, db: Session, trace: Trace | None = None) -> None:
        super().__init__(trace)
        self.db = db
        self.vectors = get_vector_store(db)

    def retrieve_private(self, user_id: str, query: str, k: int = 5) -> list[RetrievedChunk]:
        chunks = self.vectors.search(PRIVATE, query, k=k, user_id=user_id)
        self.log(
            "retrieve_private",
            f"Retrieved {len(chunks)} pieces of your own evidence for: {query[:80]}",
            [c.meta.get("title") for c in chunks],
        )
        return chunks

    def retrieve_external(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        chunks = self.vectors.search(EXTERNAL, query, k=k)
        self.log(
            "retrieve_external",
            f"Retrieved {len(chunks)} outside-world documents for: {query[:80]}",
            [c.meta.get("title") for c in chunks],
        )
        return chunks

    def evidence_for(self, user_id: str, query: str, k: int = 4) -> list[dict]:
        private = self.retrieve_private(user_id, query, k)
        external = self.retrieve_external(query, k)
        return [c.as_evidence() for c in private + external]
