"""Central configuration.

MOSAIC is designed to run with ZERO infrastructure by default (SQLite + a local
embedder + an in-process graph store) so the project can be cloned and run in two
commands.  Every heavier component from the spec -- PostgreSQL, Neo4j, Qdrant,
Gemini -- is opt-in via environment variables and swaps in behind the same
interface.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "MOSAIC"
    environment: str = "development"

    # --- Relational store ---------------------------------------------------
    # sqlite by default; set DATABASE_URL=postgresql+psycopg://... for Postgres.
    database_url: str = f"sqlite:///{DATA_DIR / 'mosaic.db'}"

    # --- LLM ----------------------------------------------------------------
    # auto  -> gemini when GOOGLE_API_KEY is present, otherwise the offline
    #          rule-based provider (so the demo always runs).
    llm_provider: str = "auto"          # auto | gemini | offline
    google_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    llm_timeout_seconds: float = 45.0

    # --- Vector store / embeddings -----------------------------------------
    vector_backend: str = "sqlite"      # sqlite | qdrant
    qdrant_url: str = "http://localhost:6333"
    embedding_backend: str = "local"    # local (hashing, no download) | sentence-transformers
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # --- Graph store --------------------------------------------------------
    graph_backend: str = "sql"          # sql | neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "mosaic-dev"

    # --- Research / external sources ---------------------------------------
    enable_network_research: bool = True   # RSS/HTTP polling; enabled for Assistant research
    newsapi_key: str = ""
    tavily_api_key: str = ""
    firecrawl_api_key: str = ""
    ocr_engine: str = "auto"               # auto | ocr_cli | pytesseract
    research_user_agent: str = "MOSAIC/0.1 (personal intelligence demo)"

    # --- Monitoring ---------------------------------------------------------
    enable_scheduler: bool = True
    monitor_interval_minutes: int = 30
    alert_confidence_floor: float = 0.55

    # --- API ----------------------------------------------------------------
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    demo_user_email: str = "demo@mosaic.local"
    demo_user_name: str = "Saniya"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_llm_provider(self) -> str:
        if self.llm_provider == "auto":
            return "gemini" if self.google_api_key else "offline"
        return self.llm_provider


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Convenience for scripts run before FastAPI boots.
os.environ.setdefault("MOSAIC_DATA_DIR", str(DATA_DIR))
