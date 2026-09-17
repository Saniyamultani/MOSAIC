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
from ..models import Entity, Relationship, utcnow

log = logging.getLogger("mosaic.graph")

# Node types used across the app (kept small on purpose).
NODE_TYPES = (
    "product", "brand", "retailer", "warranty", "subscription",
    "payment_method", "service", "bill", "event", "policy", "category",
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
        key = f"{type}:{T.normalize_key(name)}"
        entity = self.db.execute(
            select(Entity).where(Entity.user_id == user_id, Entity.canonical_key == key)
        ).scalar_one_or_none()
        if entity is None:
            entity = Entity(
                user_id=user_id,
                type=type,
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
        edge = self.db.execute(
            select(Relationship).where(
                Relationship.source_id == source_id,
                Relationship.target_id == target_id,
                Relationship.type == type,
            )
        ).scalar_one_or_none()
        if edge is None:
            edge = Relationship(
                user_id=user_id,
                source_id=source_id,
                target_id=target_id,
                type=type,
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
        degree: dict[str, int] = {}
        for e in edges:
            degree[e.source_id] = degree.get(e.source_id, 0) + 1
            degree[e.target_id] = degree.get(e.target_id, 0) + 1
        return GraphView(
            nodes=[
                {
                    "id": e.id,
                    "type": e.type,
                    "name": e.name,
                    "attributes": e.attributes or {},
                    "aliases": e.aliases or [],
                    "document_id": e.document_id,
                    "degree": degree.get(e.id, 0),
                }
                for e in entities
            ],
            edges=[
                {
                    "id": e.id,
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.type,
                    "attributes": e.attributes or {},
                }
                for e in edges
            ],
        )
