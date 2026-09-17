"""Optional Neo4j mirror of the Life Graph.

Enable with GRAPH_BACKEND=neo4j (plus a running Neo4j and `pip install neo4j`).
Relational rows stay the system of record; Neo4j gets every node and edge and
serves multi-hop traversal in Cypher, which is what the spec's
`(User)-[:OWNS]->(Phone)-[:COVERED_BY]->(Warranty)` query shape wants.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Entity, Relationship
from .base import GraphStore

log = logging.getLogger("mosaic.graph.neo4j")


class Neo4jGraphStore(GraphStore):  # pragma: no cover - optional path
    def __init__(self, db: Session) -> None:
        super().__init__(db)
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        self.driver.verify_connectivity()
        with self.driver.session() as s:
            s.run(
                "CREATE CONSTRAINT mosaic_entity_id IF NOT EXISTS "
                "FOR (n:Entity) REQUIRE n.id IS UNIQUE"
            )

    def upsert_node(self, user_id, type, name, attributes=None, aliases=None, document_id=None):
        entity = super().upsert_node(user_id, type, name, attributes, aliases, document_id)
        self._mirror_node(entity)
        return entity

    def upsert_edge(self, user_id, source_id, target_id, type, attributes=None):
        edge = super().upsert_edge(user_id, source_id, target_id, type, attributes)
        if edge is not None:
            self._mirror_edge(edge)
        return edge

    def _mirror_node(self, entity: Entity) -> None:
        with self.driver.session() as s:
            s.run(
                """
                MERGE (u:User {id: $user_id})
                MERGE (n:Entity {id: $id})
                SET n.name = $name, n.type = $type, n.user_id = $user_id
                MERGE (u)-[:OWNS]->(n)
                """,
                id=entity.id, name=entity.name, type=entity.type, user_id=entity.user_id,
            )

    def _mirror_edge(self, edge: Relationship) -> None:
        rel = "".join(ch if ch.isalnum() else "_" for ch in edge.type.upper())
        with self.driver.session() as s:
            s.run(
                f"""
                MATCH (a:Entity {{id: $src}}), (b:Entity {{id: $dst}})
                MERGE (a)-[r:{rel}]->(b)
                SET r.id = $id
                """,
                src=edge.source_id, dst=edge.target_id, id=edge.id,
            )

    def neighbors(self, entity_id: str, depth: int = 1) -> list[dict]:
        with self.driver.session() as s:
            records = s.run(
                """
                MATCH path = (n:Entity {id: $id})-[*1..%d]-(m:Entity)
                RETURN DISTINCT m.id AS id, length(path) AS hops,
                       type(relationships(path)[0]) AS rel
                ORDER BY hops
                """ % max(1, min(depth, 5)),
                id=entity_id,
            )
            rows = [dict(r) for r in records]
        out = []
        for row in rows:
            entity = self.db.get(Entity, row["id"])
            if entity is not None:
                out.append(
                    {
                        "entity": entity,
                        "relationship": row.get("rel") or "RELATED_TO",
                        "direction": "outgoing",
                        "hops": row["hops"],
                    }
                )
        return out

    def rebuild(self, user_id: str) -> None:
        for entity in self.entities(user_id):
            self._mirror_node(entity)
        for edge in self.relationships(user_id):
            self._mirror_edge(edge)
