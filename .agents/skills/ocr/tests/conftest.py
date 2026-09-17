from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

# Force mock backend for the whole suite unless a test opts into deepseek.
os.environ.setdefault("OCR_BACKEND", "mock")


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_png(tmp_path: Path) -> Path:
    path = tmp_path / "sample.png"
    Image.new("RGB", (120, 40), color=(255, 255, 255)).save(path)
    expected = path.with_suffix(".expected.md")
    expected.write_text("# Fixture\n\nHello OCR.\n", encoding="utf-8")
    return path


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """Minimal one-page PDF via pypdfium2-compatible writer (raw PDF bytes)."""
    # Tiny valid PDF with one blank page.
    pdf = b"""%PDF-1.1
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>endobj
4 0 obj<< /Length 0 >>stream
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer<< /Size 5 /Root 1 0 R >>
startxref
291
%%EOF
"""
    path = tmp_path / "sample.pdf"
    path.write_bytes(pdf)
    return path


@pytest.fixture()
def store_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "cache"
    monkeypatch.setenv("OCR_CACHE_DIR", str(cache))
    return cache
