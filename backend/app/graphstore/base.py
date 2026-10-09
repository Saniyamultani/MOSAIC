"""The Life Graph.

Default store keeps nodes/edges in the relational DB, so the whole project runs
without Neo4j.  Set GRAPH_BACKEND=neo4j to additionally mirror the graph into
Neo4j and run multi-hop traversal in Cypher -- the interface is unchanged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import textutils as T
from ..models import Alert, Document, Entity, Relationship, utcnow

log = logging.getLogger("mosaic.graph")

# Node types used across the app ecosystem.
NODE_TYPES = (
    "product", "asset", "purchase", "warranty", "subscription",
    "document", "expense", "bill", "alert", "service", "retailer",
    "brand", "payment_method", "event", "policy", "category",
)


@dataclass
class GraphView:
    nodes: list[dict]
    edges: list[dict]


class GraphStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- writes -------------------------------------------------------------
    def upsert_node(
        self,
        user_id: str,
        type: str,
        name: str,
        attributes: dict | None = None,
        aliases: list[str] | None = None,
        document_id: str | None = None,
    ) -> Entity:
        type_norm = type.strip().lower()
        key = f"{type_norm}:{T.normalize_key(name)}"
        entity = self.db.execute(
            select(Entity).where(Entity.user_id == user_id, Entity.canonical_key == key)
        ).scalar_one_or_none()

        if entity is None:
            entity = Entity(
                user_id=user_id,
                type=type_norm,
                name=name.strip(),
                canonical_key=key,
                aliases=sorted({a for a in (aliases or []) if a}),
                attributes=attributes or {},
                document_id=document_id,
            )
            self.db.add(entity)
            self.db.flush()
            return entity

        merged = dict(entity.attributes or {})
        for k, v in (attributes or {}).items():
            if v not in (None, "", []):
                merged[k] = v
        entity.attributes = merged
        entity.aliases = sorted(set(entity.aliases or []) | {a for a in (aliases or []) if a})
        entity.document_id = entity.document_id or document_id
        entity.updated_at = utcnow()
        self.db.flush()
        return entity

    def upsert_edge(
        self,
        user_id: str,
        source_id: str,
        target_id: str,
        type: str,
        attributes: dict | None = None,
    ) -> Relationship | None:
        if source_id == target_id:
            return None
        norm_type = type.strip().upper().replace(" ", "_")
        edge = self.db.execute(
            select(Relationship).where(
                Relationship.user_id == user_id,
                or_(
                    (Relationship.source_id == source_id) & (Relationship.target_id == target_id) & (Relationship.type == norm_type),
                    (Relationship.source_id == target_id) & (Relationship.target_id == source_id) & (Relationship.type == norm_type),
                ),
            )
        ).scalars().first()
        if edge is None:
            edge = Relationship(
                user_id=user_id,
                source_id=source_id,
                target_id=target_id,
                type=norm_type,
                attributes=attributes or {},
            )
            self.db.add(edge)
            self.db.flush()
        elif attributes:
            edge.attributes = {**(edge.attributes or {}), **attributes}
            self.db.flush()
        return edge

    # --- reads --------------------------------------------------------------
    def get_entity(self, entity_id: str) -> Entity | None:
        return self.db.get(Entity, entity_id)

    def entities(self, user_id: str, types: list[str] | None = None) -> list[Entity]:
        stmt = select(Entity).where(Entity.user_id == user_id)
        if types:
            stmt = stmt.where(Entity.type.in_(types))
        return list(self.db.execute(stmt.order_by(Entity.created_at)).scalars())

    def relationships(self, user_id: str) -> list[Relationship]:
        return list(
            self.db.execute(
                select(Relationship).where(Relationship.user_id == user_id)
            ).scalars()
        )

    def search_entities(self, user_id: str, terms: list[str]) -> list[Entity]:
        """Cheap lexical prefilter before the Entity Agent scores candidates."""
        terms = [t for t in {t.strip() for t in terms} if len(t) >= 3]
        if not terms:
            return []
        clauses = [Entity.canonical_key.contains(T.normalize_key(t)) for t in terms]
        clauses += [Entity.name.ilike(f"%{t}%") for t in terms]
        return list(
            self.db.execute(
                select(Entity).where(Entity.user_id == user_id, or_(*clauses))
            ).scalars()
        )

    def neighbors(self, entity_id: str, depth: int = 1) -> list[dict]:
        """Breadth-first traversal returning {entity, type, direction, hops}."""
        seen = {entity_id}
        frontier = [entity_id]
        out: list[dict] = []
        for hop in range(1, depth + 1):
            if not frontier:
                break
            edges = list(
                self.db.execute(
                    select(Relationship).where(
                        or_(
                            Relationship.source_id.in_(frontier),
                            Relationship.target_id.in_(frontier),
                        )
                    )
                ).scalars()
            )
            next_frontier: list[str] = []
            for edge in edges:
                for other, direction in (
                    (edge.target_id, "outgoing"),
                    (edge.source_id, "incoming"),
                ):
                    if other in seen:
                        continue
                    entity = self.db.get(Entity, other)
                    if entity is None:
                        continue
                    seen.add(other)
                    next_frontier.append(other)
                    out.append(
                        {
                            "entity": entity,
                            "relationship": edge.type,
                            "direction": direction,
                            "hops": hop,
                        }
                    )
            frontier = next_frontier
        return out

    def view(self, user_id: str) -> GraphView:
        entities = self.entities(user_id)
        edges = self.relationships(user_id)

        node_map: dict[str, dict] = {}
        edge_map: dict[str, dict] = {}
        degree: dict[str, int] = {}

        for e in entities:
            node_map[e.id] = {
                "id": e.id,
                "type": e.type,
                "name": e.name,
                "attributes": e.attributes or {},
                "aliases": e.aliases or [],
                "document_id": e.document_id,
                "degree": 0,
            }

        for edge in edges:
            if edge.source_id in node_map and edge.target_id in node_map:
                edge_key = f"{edge.source_id}:{edge.target_id}:{edge.type}"
                if edge_key not in edge_map:
                    edge_map[edge_key] = {
                        "id": edge.id,
                        "source": edge.source_id,
                        "target": edge.target_id,
                        "type": edge.type,
                        "attributes": edge.attributes or {},
                    }
                    degree[edge.source_id] = degree.get(edge.source_id, 0) + 1
                    degree[edge.target_id] = degree.get(edge.target_id, 0) + 1

        # Surface active Alerts linked to user entities
        user_alerts = list(
            self.db.execute(
                select(Alert).where(Alert.user_id == user_id, Alert.entity_id.isnot(None))
            ).scalars()
        )
        for alert in user_alerts:
            if alert.entity_id and alert.entity_id in node_map:
                alert_node_id = f"alert_{alert.id}"
                if alert_node_id not in node_map:
                    node_map[alert_node_id] = {
                        "id": alert_node_id,
                        "type": "alert",
                        "name": alert.headline,
                        "attributes": {
                            "severity": alert.severity,
                            "explanation": alert.explanation,
                            "confidence": alert.confidence,
                        },
                        "aliases": [],
                        "document_id": None,
                        "degree": 1,
                    }
                edge_key = f"{alert.entity_id}:{alert_node_id}:AFFECTED_BY"
                if edge_key not in edge_map:
                    edge_map[edge_key] = {
                        "id": f"rel_{alert.id}",
                        "source": alert.entity_id,
                        "target": alert_node_id,
                        "type": "AFFECTED_BY",
                        "attributes": {"severity": alert.severity},
                    }
                    degree[alert.entity_id] = degree.get(alert.entity_id, 0) + 1
                    degree[alert_node_id] = 1

        # Surface confirmed Documents linked to user entities
        user_docs = list(
            self.db.execute(
                select(Document).where(Document.user_id == user_id, Document.status == "confirmed")
            ).scalars()
        )
        for doc in user_docs:
            linked_entities = [e for e in entities if e.document_id == doc.id]
            if linked_entities:
                doc_node_id = f"doc_{doc.id}"
                if doc_node_id not in node_map:
                    node_map[doc_node_id] = {
                        "id": doc_node_id,
                        "type": "document",
                        "name": doc.title or doc.filename or "Document",
                        "attributes": {
                            "kind": doc.kind,
                            "filename": doc.filename,
                            "source_url": doc.source_url,
                        },
                        "aliases": [],
                        "document_id": doc.id,
                        "degree": len(linked_entities),
                    }
                for entity in linked_entities:
                    edge_key = f"{entity.id}:{doc_node_id}:DOCUMENTED_BY"
                    if edge_key not in edge_map:
                        edge_map[edge_key] = {
                            "id": f"rel_doc_{doc.id}_{entity.id}",
                            "source": entity.id,
                            "target": doc_node_id,
                            "type": "DOCUMENTED_BY",
                            "attributes": {"kind": doc.kind},
                        }
                        degree[entity.id] = degree.get(entity.id, 0) + 1
                        degree[doc_node_id] = degree.get(doc_node_id, 0) + 1

        for nid, node in node_map.items():
            node["degree"] = degree.get(nid, 0)

        return GraphView(
            nodes=list(node_map.values()),
            edges=list(edge_map.values()),
        )
