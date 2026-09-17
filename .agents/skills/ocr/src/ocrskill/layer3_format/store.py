"""Persist full OCR documents so `ocr open` works across processes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .. import config, errors
from ..envelope import OcrSkillError
from .models import FormatDocument


class DocumentStore:
    def __init__(self, path: Path | None = None):
        self.path = path or config.store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    handle TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def put(self, doc: FormatDocument) -> None:
        payload = doc.model_dump(mode="json")
        # Store full markdown as canonical; content/page fields are re-derived on open.
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents(handle, payload, updated_at)
                VALUES (?, ?, strftime('%s','now'))
                ON CONFLICT(handle) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (doc.handle, json.dumps(payload, ensure_ascii=False)),
            )

    def get(self, handle: str) -> FormatDocument:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM documents WHERE handle = ?",
                (handle,),
            ).fetchone()
        if row is None:
            raise OcrSkillError(
                errors.NOT_OPENED,
                f"unknown handle: {handle}",
                hint="Run `ocr extract <path>` first, then `ocr open <handle> --page N`.",
            )
        data = json.loads(row["payload"])
        return FormatDocument.model_validate(data)
