"""Agent 2 -- Entity resolution + Life Graph writes.

Decides whether "Samsung S26", "Galaxy S26" and "SM-S26XYZ" are the same thing
before anything is written, so the graph stays one node per real-world object.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import textutils as T
from ..graphstore.factory import get_graph_store
from ..ingest.structuring import build_graph_payload
from ..models import Document, Entity
from ..rag.store import PRIVATE, get_vector_store
from .base import Agent, Trace

MERGE_THRESHOLD = 0.55


class EntityAgent(Agent):
    name = "Entity Agent"

    def __init__(self, db: Session, trace: Trace | None = None) -> None:
        super().__init__(trace)
        self.db = db
        self.graph = get_graph_store(db)
        self.vectors = get_vector_store(db)

    # --- resolution ---------------------------------------------------------
    def resolve(self, user_id: str, type: str, name: str, attributes: dict) -> Entity | None:
        """Find an existing node this candidate refers to, or None."""
        candidates = [e for e in self.graph.entities(user_id, [type])]
        if not candidates:
            return None
        code = (attributes.get("model_code") or "").upper()
        for entity in candidates:
            existing_code = str((entity.attributes or {}).get("model_code") or "").upper()
            if code and existing_code and code == existing_code:
                self.log("resolve", f"'{name}' matched '{entity.name}' on model code {code}")
                return entity

        best, best_score = None, 0.0
        for entity in candidates:
            score = max(
                [T.token_overlap(name, entity.name)]
                + [T.token_overlap(name, alias) for alias in (entity.aliases or [])]
            )
            if score > best_score:
                best, best_score = entity, score
        if best is not None and best_score >= MERGE_THRESHOLD:
            self.log(
                "resolve",
                f"'{name}' resolved to existing node '{best.name}' "
                f"(name overlap {best_score:.2f})",
            )
            return best
        return None

    # --- graph writes -------------------------------------------------------
    def apply_document(self, document: Document, overrides: dict | None = None) -> dict:
        extraction = dict(document.extraction or {})
        fields = {**(extraction.get("fields") or {}), **(overrides or {})}
        fields = {k: v for k, v in fields.items() if v not in (None, "", [])}
        extraction["fields"] = fields
        document.extraction = extraction

        kind = extraction.get("kind", document.kind)
        node_specs, edge_specs = build_graph_payload(kind, fields)
        self.log(
            "plan",
            f"Planned {len(node_specs)} nodes and {len(edge_specs)} relationships from a {kind}",
            {"nodes": [n["name"] for n in node_specs], "edges": [e["type"] for e in edge_specs]},
        )

        name_to_entity: dict[str, Entity] = {}
        created, merged = 0, 0
        for spec in node_specs:
            existing = self.resolve(document.user_id, spec["type"], spec["name"], spec["attributes"])
            if existing is not None:
                entity = self.graph.upsert_node(
                    document.user_id,
                    existing.type,
                    existing.name,
                    attributes=spec["attributes"],
                    aliases=[spec["name"]],
                    document_id=document.id,
                )
                merged += 1
            else:
                entity = self.graph.upsert_node(
                    document.user_id,
                    spec["type"],
                    spec["name"],
                    attributes=spec["attributes"],
                    aliases=[spec["name"]],
                    document_id=document.id,
                )
                created += 1
            name_to_entity[spec["name"]] = entity

        edges = 0
        for spec in edge_specs:
            src = name_to_entity.get(spec["source"])
            dst = name_to_entity.get(spec["target"])
            if src and dst:
                if self.graph.upsert_edge(
                    document.user_id, src.id, dst.id, spec["type"], spec.get("attributes")
                ):
                    edges += 1

        self.log(
            "write",
            f"Life Graph updated: {created} new nodes, {merged} merged into existing nodes, "
            f"{edges} relationships",
        )

        self._index(document, name_to_entity)
        return {
            "entities": list(name_to_entity.values()),
            "created": created,
            "merged": merged,
            "edges": edges,
        }

    # --- private RAG --------------------------------------------------------
    def _index(self, document: Document, entities: dict[str, Entity]) -> None:
        fields = (document.extraction or {}).get("fields", {})
        summary = (document.extraction or {}).get("summary", "")
        doc_text = "\n".join(
            [
                f"{document.kind}: {summary}",
                *[f"{k}: {v}" for k, v in fields.items()],
                document.raw_text[:4000],
            ]
        )
        self.vectors.upsert(
            PRIVATE,
            ref_type="document",
            ref_id=document.id,
            text=doc_text,
            user_id=document.user_id,
            meta={
                "title": summary or document.title,
                "kind": document.kind,
                "document_id": document.id,
                "created_at": document.created_at.isoformat() if document.created_at else None,
            },
        )
        for entity in entities.values():
            attrs = entity.attributes or {}
            text = f"{entity.type}: {entity.name}\n" + "\n".join(
                f"{k}: {v}" for k, v in attrs.items()
            )
            self.vectors.upsert(
                PRIVATE,
                ref_type="entity",
                ref_id=entity.id,
                text=text,
                user_id=entity.user_id,
                meta={"title": entity.name, "entity_type": entity.type, "entity_id": entity.id},
            )
        self.log("index", f"Indexed the document and {len(entities)} entities into the private RAG")
