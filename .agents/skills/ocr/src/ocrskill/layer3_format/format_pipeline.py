"""Assemble multi-page OCR into fenced, paginated Markdown."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import DEFAULT_PAGE_SIZE_TOKENS
from ..layer2_ocr.models import OcrPageResult
from .fence import fence_untrusted
from .models import FORMAT_CONTRACT_VERSION, FormatDocument
from .tokens import estimate_tokens, split_pages

__all__ = ["FORMAT_CONTRACT_VERSION", "assemble", "paginate", "make_handle"]


def make_handle(source_path: str) -> str:
    path = Path(source_path)
    digest = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]
    safe = path.stem.replace(" ", "_")[:40] or "doc"
    return f"{safe}~{digest}"


def _join_pages(pages: list[OcrPageResult]) -> str:
    if len(pages) == 1:
        return pages[0].markdown.strip()
    parts: list[str] = []
    for p in pages:
        parts.append(f"<!-- page {p.page} -->\n{p.markdown.strip()}")
    return "\n\n".join(parts).strip() + "\n"


def assemble(
    *,
    source_path: str,
    source_kind: str,
    page_count: int,
    mode: str,
    ocr_pages: list[OcrPageResult],
    fence: bool = True,
    page: int = 1,
    page_size_tokens: int = DEFAULT_PAGE_SIZE_TOKENS,
    handle: str | None = None,
) -> FormatDocument:
    markdown = _join_pages(ocr_pages)
    backend = ocr_pages[0].backend if ocr_pages else None
    warnings: list[str] = []
    for p in ocr_pages:
        warnings.extend(p.warnings)

    handle = handle or make_handle(source_path)
    return paginate(
        handle=handle,
        source_path=source_path,
        source_kind=source_kind,
        page_count=page_count,
        mode=mode,
        markdown=markdown,
        fence=fence,
        page=page,
        page_size_tokens=page_size_tokens,
        backend=backend,
        warnings=warnings,
    )


def paginate(
    *,
    handle: str,
    source_path: str,
    source_kind: str,
    page_count: int,
    mode: str,
    markdown: str,
    fence: bool = True,
    page: int = 1,
    page_size_tokens: int = DEFAULT_PAGE_SIZE_TOKENS,
    backend: str | None = None,
    warnings: list[str] | None = None,
) -> FormatDocument:
    if fence:
        full_view, fence_info = fence_untrusted(markdown, source_path=source_path)
        fenced = True
        untrusted = True
    else:
        full_view = markdown
        fence_info = None
        fenced = False
        untrusted = False

    chunks = split_pages(full_view, page_size_tokens)
    total_pages = len(chunks)
    if page < 1 or page > total_pages:
        # Clamp is wrong for agents; raise via caller. Here pick safe slice.
        page = max(1, min(page, total_pages))
    content = chunks[page - 1]
    return FormatDocument(
        handle=handle,
        source_path=source_path,
        source_kind=source_kind,
        page_count=page_count,
        mode=mode,
        markdown=markdown,
        fenced=fenced,
        content=content,
        page=page,
        total_pages=total_pages,
        has_more=page < total_pages,
        page_tokens=estimate_tokens(content),
        total_tokens=estimate_tokens(full_view),
        untrusted=untrusted,
        fence=fence_info,
        backend=backend,
        warnings=list(warnings or []),
    )
