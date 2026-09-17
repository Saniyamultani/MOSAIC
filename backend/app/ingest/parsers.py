"""Get plain text out of whatever the user handed us.

Every heavy dependency is optional and imported lazily, so a fresh clone runs
without PyMuPDF or Tesseract installed -- those paths just report what's missing.
"""
from __future__ import annotations

import io
import logging
import re

from pathlib import Path

import httpx

from ..config import BASE_DIR, settings

log = logging.getLogger("mosaic.ingest")

TEXT_MIMES = ("text/", "application/json", "application/xml")
TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.DOTALL | re.IGNORECASE)
WS_RE = re.compile(r"[ \t\r\f\v]+")


def strip_html(html: str) -> str:
    text = TAG_RE.sub(" ", html)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&")
        .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"')
    )
    lines = [WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _find_ocr_cli() -> str | None:
    """Find installed ocr skill binary/script or system command."""
    import sys
    workspace_root = Path(BASE_DIR).parent
    candidates = [
        workspace_root / ".agents" / "skills" / "ocr" / "bin" / "ocr.exe",
        workspace_root / ".agents" / "skills" / "ocr" / "dist" / "ocr.exe",
        workspace_root / ".agents" / "skills" / "ocr" / "bin" / "ocr",
        workspace_root / ".agents" / "skills" / "ocr" / "dist" / "ocr",
        workspace_root / ".agents" / "skills" / "ocr" / "ocr",
    ]
    for cand in candidates:
        if cand.exists():
            if sys.platform == "win32":
                if cand.suffix == ".exe" or os.access(cand, os.X_OK):
                    return str(cand)
            elif os.access(cand, os.X_OK):
                return str(cand)

    return shutil.which("ocr") or shutil.which("ocr-skill")


def run_ocr_cli(data: bytes, filename_hint: str = "document.png") -> str | None:
    import json
    import os
    import subprocess
    import tempfile

    cli = _find_ocr_cli()
    if not cli:
        return None
    suffix = Path(filename_hint).suffix or ".png"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        res = subprocess.run(
            [cli, "extract", tmp_path, "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if res.returncode == 0 and res.stdout:
            payload = json.loads(res.stdout)
            docs = payload.get("data", {}).get("documents", [])
            extracted = []
            for doc in docs:
                content = doc.get("content") or doc.get("markdown")
                if content:
                    extracted.append(content)
            if extracted:
                return "\n\n".join(extracted).strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("OCR CLI execution failed: %s", exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return None


def parse_pdf(data: bytes) -> str:
    # 1. Try OCR Skill CLI if enabled/available
    ocr_res = run_ocr_cli(data, "document.pdf")
    if ocr_res:
        return ocr_res

    # 2. PyMuPDF fallback
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "[PDF received, but PyMuPDF is not installed. `pip install pymupdf` to read PDFs.]"
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc).strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("PDF parse failed: %s", exc)
        return f"[PDF received, but failed to parse: {exc}]"


def parse_image_easyocr(data: bytes) -> str | None:
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        results = reader.readtext(data)
        lines = [res[1] for res in results if res and len(res) > 1 and res[1].strip()]
        if lines:
            return "\n".join(lines).strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("EasyOCR execution failed: %s", exc)
    return None


def parse_image(data: bytes) -> str:
    """OCR. Tries EasyOCR first, then OCR Skill CLI, then PyTesseract."""
    # 1. Try EasyOCR (Python-native)
    eocr_res = parse_image_easyocr(data)
    if eocr_res:
        return eocr_res

    # 2. Try OCR Skill CLI
    ocr_res = run_ocr_cli(data, "image.png")
    if ocr_res:
        return ocr_res

    # 3. Try PyTesseract
    try:
        import pytesseract
        from PIL import Image

        if shutil.which("tesseract") is None:
            common_tess_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
            ]
            for p in common_tess_paths:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

        img = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img).strip()
        if text:
            return text
    except Exception as exc:  # noqa: BLE001
        log.warning("PyTesseract OCR failed: %s", exc)

    return "[Image document uploaded. OCR extraction ready.]"


def parse_upload(filename: str, data: bytes, mime_type: str | None = None) -> str:
    name = (filename or "").lower()
    mime = (mime_type or "").lower()
    if name.endswith(".pdf") or mime == "application/pdf":
        return parse_pdf(data)
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")) or mime.startswith("image/"):
        return parse_image(data)
    if name.endswith((".html", ".htm")) or mime == "text/html":
        return strip_html(data.decode("utf-8", errors="replace"))
    if name.endswith((".eml", ".msg")):
        return parse_email(data)
    if name.endswith((".ics",)):
        return parse_ics(data)
    if mime.startswith(TEXT_MIMES) or name.endswith((".txt", ".md", ".csv", ".json")):
        return data.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def parse_email(data: bytes) -> str:
    from email import policy
    from email.parser import BytesParser

    msg = BytesParser(policy=policy.default).parsebytes(data)
    parts = [f"Subject: {msg.get('subject', '')}", f"From: {msg.get('from', '')}",
             f"Date: {msg.get('date', '')}"]
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is not None:
        content = body.get_content()
        parts.append(strip_html(content) if body.get_content_type() == "text/html" else content)
    return "\n".join(parts).strip()


def parse_ics(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    keep = ("SUMMARY:", "DTSTART", "DTEND", "DESCRIPTION:", "LOCATION:")
    lines = [ln.strip() for ln in text.splitlines() if ln.startswith(keep)]
    return "\n".join(lines)


import os
import shutil


def fetch_url_firecrawl(url: str) -> tuple[str, str] | None:
    """Scrape webpage via Firecrawl API or CLI if available."""
    api_key = settings.firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
    if api_key:
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    json={"url": url, "formats": ["markdown"]},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    payload = resp.json().get("data", {})
                    meta = payload.get("metadata", {})
                    title = meta.get("title") or url
                    markdown = payload.get("markdown") or ""
                    if markdown:
                        return title, markdown
        except Exception as exc:  # noqa: BLE001
            log.warning("Firecrawl API fetch failed for %s: %s", url, exc)

    firecrawl_bin = shutil.which("firecrawl")
    if firecrawl_bin:
        import subprocess
        try:
            res = subprocess.run(
                [firecrawl_bin, "scrape", url],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0 and res.stdout.strip():
                content = res.stdout.strip()
                first_line = content.splitlines()[0] if content else ""
                title = first_line.lstrip("# ").strip() if first_line.startswith("#") else url
                return title, content
        except Exception as exc:  # noqa: BLE001
            log.warning("Firecrawl CLI fetch failed for %s: %s", url, exc)

    return None


def fetch_url(url: str) -> tuple[str, str]:
    """Returns (title, text). Used for 'paste a product/policy URL'."""
    if not settings.enable_network_research:
        return url, (
            f"[URL saved: {url}. Network fetching is disabled -- "
            "set ENABLE_NETWORK_RESEARCH=true to let MOSAIC read the page.]"
        )

    # 1. Try Firecrawl scraper first
    fc_res = fetch_url_firecrawl(url)
    if fc_res:
        return fc_res

    # 2. Default HTTP fetcher fallback
    headers = {"User-Agent": settings.research_user_agent}
    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    title = strip_html(match.group(1)).strip() if match else url
    return title, strip_html(html)[:20000]
