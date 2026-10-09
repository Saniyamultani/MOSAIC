from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import assistant, auth, documents, graph, profile, radar
from .config import settings
from .db import init_db, session_scope
from .scheduler import start_scheduler, stop_scheduler
from .services import get_or_create_demo_user

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
)
log = logging.getLogger("mosaic")


import os
from sqlalchemy import select
from .models import Document

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        with session_scope() as db:
            user = get_or_create_demo_user(db)
            has_docs = db.execute(select(Document).where(Document.user_id == user.id)).first()
            if not has_docs:
                try:
                    from .seed import seed
                    seed(reset=False, monitor=True)
                except Exception as seed_exc:
                    log.warning("Auto-seed notice during startup: %s", seed_exc)
            else:
                try:
                    from .agents.research import ResearchAgent
                    ResearchAgent(db).ensure_sources()
                except Exception as res_exc:
                    log.warning("ensure_sources notice during startup: %s", res_exc)
    except Exception as exc:
        log.warning("Lifespan database startup notice: %s", exc)

    log.info("MOSAIC ready — LLM=%s, graph=%s, vectors=%s",
             settings.resolved_llm_provider, settings.graph_backend, settings.vector_backend)
    is_vercel = bool(os.environ.get("VERCEL"))
    if settings.enable_scheduler and not is_vercel:
        start_scheduler()
    yield
    if settings.enable_scheduler and not is_vercel:
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

app.include_router(auth.router)
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
