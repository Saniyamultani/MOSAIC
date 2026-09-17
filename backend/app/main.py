from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import assistant, documents, graph, profile, radar
from .config import settings
from .db import init_db, session_scope
from .scheduler import start_scheduler, stop_scheduler
from .services import get_or_create_demo_user

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
)
log = logging.getLogger("mosaic")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with session_scope() as db:
        get_or_create_demo_user(db)
        from .agents.research import ResearchAgent

        ResearchAgent(db).ensure_sources()
    log.info("MOSAIC ready — LLM=%s, graph=%s, vectors=%s",
             settings.resolved_llm_provider, settings.graph_backend, settings.vector_backend)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="MOSAIC",
    description=(
        "A proactive personal intelligence system: builds a Life Graph of what you own "
        "and owe, watches approved external sources, and alerts you only when the two "
        "worlds actually collide."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(graph.router)
app.include_router(radar.router)
app.include_router(assistant.router)
app.include_router(profile.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "llm_provider": settings.resolved_llm_provider,
        "graph_backend": settings.graph_backend,
        "vector_backend": settings.vector_backend,
        "embedding_backend": settings.embedding_backend,
        "network_research": settings.enable_network_research,
        "scheduler": settings.enable_scheduler,
    }
