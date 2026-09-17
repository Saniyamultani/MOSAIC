from __future__ import annotations

from pathlib import Path

from ocrskill.layer2_ocr.adapters.mock import MockEngine


def test_mock_uses_expected_md(sample_png: Path) -> None:
    eng = MockEngine()
    out = eng.extract_page(str(sample_png), page=1, mode="markdown")
    assert "Hello OCR" in out.markdown
    assert out.backend == "mock"


def test_mock_free_mode(sample_png: Path) -> None:
    eng = MockEngine()
    # Remove expected so free template applies
    sample_png.with_suffix(".expected.md").unlink()
    out = eng.extract_page(str(sample_png), page=1, mode="free")
    assert "Mock OCR page 1" in out.markdown
