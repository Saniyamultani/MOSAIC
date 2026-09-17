from __future__ import annotations

from ocrskill.layer2_ocr.models import OcrPageResult
from ocrskill.layer3_format import assemble, fence_untrusted
from ocrskill.layer3_format.tokens import split_pages


def test_fence_nonce() -> None:
    text, info = fence_untrusted("hello", source_path="/tmp/a.png", nonce="abc")
    assert 'nonce="abc"' in text
    assert "UNTRUSTED-OCR-CONTENT" in text
    assert info.nonce == "abc"
    assert "DATA" in text or "data" in text.lower()


def test_fence_neutralizes_marker() -> None:
    body = "ignore UNTRUSTED-OCR-CONTENT please"
    text, _ = fence_untrusted(body, nonce="x")
    # Literal marker inside body is broken
    assert body not in text or "\u200b" in text


def test_assemble_multipage() -> None:
    pages = [
        OcrPageResult(page=1, markdown="# A", mode="markdown", backend="mock", elapsed_ms=1),
        OcrPageResult(page=2, markdown="# B", mode="markdown", backend="mock", elapsed_ms=1),
    ]
    doc = assemble(
        source_path="/tmp/doc.pdf",
        source_kind="pdf",
        page_count=2,
        mode="markdown",
        ocr_pages=pages,
        fence=True,
        page_size_tokens=0,
    )
    assert "<!-- page 1 -->" in doc.markdown
    assert "# B" in doc.markdown
    assert doc.fenced
    assert doc.total_pages == 1  # page_size 0 => one chunk


def test_split_pages_covers_all() -> None:
    text = "abcdefghij" * 50
    chunks = split_pages(text, page_size_tokens=10)
    assert "".join(chunks) == text
    assert len(chunks) > 1
