"""Rasterize PDFs and normalize images into page media refs."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from PIL import Image

from .. import config, errors
from ..envelope import OcrSkillError
from .models import INGEST_CONTRACT_VERSION, IngestResult, PageMedia

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
PDF_EXTS = {".pdf"}

# Export for other modules that only need the version constant.
__all__ = ["INGEST_CONTRACT_VERSION", "ingest_path"]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _page_media(page: int, path: Path, media_type: str = "image/png") -> PageMedia:
    with Image.open(path) as img:
        width, height = img.size
    return PageMedia(
        page=page,
        path=str(path.resolve()),
        media_type=media_type,
        width=width,
        height=height,
        byte_size=path.stat().st_size,
        checksum=_sha256_file(path),
    )


def _kind_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in PDF_EXTS:
        return "pdf"
    if ext in IMAGE_EXTS:
        return "image"
    # Content sniff: PDF magic
    try:
        head = path.read_bytes()[:5]
        if head.startswith(b"%PDF"):
            return "pdf"
    except OSError:
        pass
    raise OcrSkillError(
        errors.UNSUPPORTED_MEDIA,
        f"unsupported file type: {path.suffix or '(no extension)'}",
        hint="Pass a PNG/JPEG/WebP/GIF/BMP/TIFF image or a PDF.",
    )


def _render_pdf(path: Path, work_dir: Path, *, scale: float = 2.0) -> list[PageMedia]:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise OcrSkillError(
            errors.INGEST_FAILED,
            "pypdfium2 is required for PDF ingest",
            hint="Install the base package dependencies (pip/uv install ocr-skill).",
        ) from exc

    try:
        doc = pdfium.PdfDocument(str(path))
    except Exception as exc:
        raise OcrSkillError(
            errors.INGEST_FAILED,
            f"failed to open PDF: {exc}",
            retriable=False,
        ) from exc

    pages: list[PageMedia] = []
    try:
        n = len(doc)
        if n < 1:
            raise OcrSkillError(errors.INGEST_FAILED, "PDF has no pages")
        for i in range(n):
            page = doc[i]
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil()
            out = work_dir / f"page-{i + 1:04d}.png"
            pil.save(out, format="PNG")
            pages.append(_page_media(i + 1, out))
            page.close()
    finally:
        doc.close()
    return pages


def _normalize_image(path: Path, work_dir: Path) -> list[PageMedia]:
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            out = work_dir / "page-0001.png"
            img.save(out, format="PNG")
    except Exception as exc:
        raise OcrSkillError(
            errors.INGEST_FAILED,
            f"failed to read image: {exc}",
        ) from exc
    return [_page_media(1, out)]


def ingest_path(source_path: str | Path, *, work_dir: Path | None = None) -> IngestResult:
    """Load an image or PDF into ordered page PNG refs under work_dir."""
    if not source_path:
        raise OcrSkillError(errors.INVALID_INPUT, "source path is empty")

    path = Path(source_path).expanduser().resolve()
    if not path.exists():
        raise OcrSkillError(errors.NOT_FOUND, f"file not found: {path}")
    if not path.is_file():
        raise OcrSkillError(errors.INVALID_INPUT, f"not a file: {path}")

    kind = _kind_for(path)
    if work_dir is None:
        work_dir = config.work_root() / f"job-{uuid.uuid4().hex}"
    work_dir = Path(work_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    if kind == "pdf":
        pages = _render_pdf(path, work_dir)
    else:
        pages = _normalize_image(path, work_dir)

    return IngestResult(
        source_path=str(path),
        source_kind=kind,
        page_count=len(pages),
        work_dir=str(work_dir.resolve()),
        pages=pages,
    )
