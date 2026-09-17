"""Agent 1 -- Ingestion.

Parses PDFs, images, emails, calendar files, URLs and free text into a document
row plus a structured extraction awaiting the user's single ✓ Confirm.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..ingest import parsers
from ..llm.factory import get_llm
from ..models import Document
from .base import Agent, Trace


class IngestionAgent(Agent):
    name = "Ingestion Agent"

    def __init__(self, db: Session, trace: Trace | None = None) -> None:
        super().__init__(trace)
        self.db = db
        self.llm = get_llm()

    def ingest_text(
        self, user_id: str, text: str, kind_hint: str | None = None, title: str | None = None
    ) -> Document:
        self.log("parse", f"Read {len(text)} characters of text input")
        return self._create(user_id, text, kind_hint, title=title)

    def ingest_file(
        self,
        user_id: str,
        filename: str,
        data: bytes,
        mime_type: str | None = None,
        kind_hint: str | None = None,
    ) -> Document:
        text = parsers.parse_upload(filename, data, mime_type)
        self.log("parse", f"Parsed {filename} ({len(data)} bytes) into {len(text)} characters")
        return self._create(
            user_id, text, kind_hint, filename=filename, mime_type=mime_type, title=filename, raw_data=data
        )

    def ingest_url(self, user_id: str, url: str, kind_hint: str | None = None) -> Document:
        title, text = parsers.fetch_url(url)
        self.log("parse", f"Fetched {url}")
        return self._create(user_id, text, kind_hint, source_url=url, title=title)

    def _create(
        self,
        user_id: str,
        text: str,
        kind_hint: str | None,
        filename: str | None = None,
        mime_type: str | None = None,
        source_url: str | None = None,
        title: str | None = None,
        raw_data: bytes | None = None,
    ) -> Document:
        is_image = (mime_type and mime_type.startswith("image/")) or (
            filename and filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"))
        )
        image_bytes = raw_data if is_image else None
        extraction = self.llm.extract_document(
            text, kind_hint, image_bytes=image_bytes, mime_type=mime_type or "image/png"
        )
        self.log(
            "extract",
            f"Extracted {len(extraction.get('fields', {}))} fields as a {extraction.get('kind')} "
            f"using the {extraction.get('extractor')} extractor",
            extraction.get("fields"),
        )
        doc = Document(
            user_id=user_id,
            kind=extraction.get("kind", "note"),
            title=(extraction.get("summary") or title or "Untitled")[:300],
            filename=filename,
            mime_type=mime_type,
            source_url=source_url,
            raw_text=text[:60000],
            extraction=extraction,
            status="pending_confirmation",
        )
        self.db.add(doc)
        self.db.flush()
        return doc
