from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    from . import models  # noqa: F401  (registers metadata)

    models.Base.metadata.create_all(bind=engine)

    # SQLite lightweight schema migration for new columns on existing DB files
    if engine.name == "sqlite":
        with engine.connect() as conn:
            from sqlalchemy import inspect, text
            inspector = inspect(engine)

            if "users" in inspector.get_table_names():
                user_cols = {c["name"] for c in inspector.get_columns("users")}
                if "hashed_password" not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255) DEFAULT ''"))
                if "profile_json" not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN profile_json JSON DEFAULT '{}'"))
            conn.commit()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """For background jobs and scripts."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
