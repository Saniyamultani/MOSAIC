from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..config import settings
from .base import GraphStore

log = logging.getLogger("mosaic.graph")


def get_graph_store(db: Session) -> GraphStore:
    if settings.graph_backend == "neo4j":
        try:
            from .neo4j_store import Neo4jGraphStore

            return Neo4jGraphStore(db)
        except Exception as exc:  # noqa: BLE001
            log.warning("Neo4j unavailable (%s); using the relational graph store", exc)
    return GraphStore(db)
