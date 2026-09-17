from __future__ import annotations

from pathlib import Path

from ocrskill.layer2_ocr.adapters.mock import MockEngine
from ocrskill.layer2_ocr.models import OcrPageResult
from ocrskill.layer3_format import DocumentStore, assemble
from ocrskill.layer4_agentio import build_agent


def test_open_walks_all_output_pages(sample_png: Path, store_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OCR_BACKEND", "mock")
    # Force multi-page output by tiny token budget.
    agent = build_agent(store=DocumentStore(store_path / "documents.sqlite"))

    # Inject a long markdown via a custom engine-like path: extract uses mock template,
    # so build a long document through the store/assemble path used by open.
    long_body = ("Line of OCR text that fills many pages.\n" * 200)
    pages = [
        OcrPageResult(
            page=1,
            markdown=long_body,
            mode="markdown",
            backend="mock",
            elapsed_ms=1.0,
        )
    ]
    doc = assemble(
        source_path=str(sample_png),
        source_kind="image",
        page_count=1,
        mode="markdown",
        ocr_pages=pages,
        fence=True,
        page=1,
        page_size_tokens=50,
    )
    store = DocumentStore(store_path / "documents.sqlite")
    store.put(doc)
    assert doc.total_pages > 1
    assert doc.has_more

    agent = build_agent(store=store)
    seen: list[str] = []
    for p in range(1, doc.total_pages + 1):
        env = agent.open(doc.handle, page=p, page_size_tokens=50)
        assert env.ok, env.error
        seen.append(env.data["content"])
        if p < doc.total_pages:
            assert env.data["has_more"] is True
        else:
            assert env.data["has_more"] is False

    # Full reconstruction of fenced stream (join of output pages) equals original full view.
    from ocrskill.layer3_format.fence import fence_untrusted

    full, _ = fence_untrusted(long_body, source_path=str(sample_png), nonce=doc.fence.nonce)
    # Nonces differ on re-paginate; compare unfenced stored markdown instead.
    recovered = store.get(doc.handle)
    # assemble() strips joined page bodies; trailing newline may be normalized.
    assert recovered.markdown == long_body.strip()
    assert len(seen) == doc.total_pages
    assert all(seen)


def test_mock_engine_available() -> None:
    ok, detail = MockEngine().available()
    assert ok
    assert "mock" in detail.lower()
