from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ocrskill.envelope import OcrSkillError
from ocrskill.layer1_ingest import ingest_path


def test_ingest_image(tmp_path: Path) -> None:
    img = tmp_path / "a.png"
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(img)
    result = ingest_path(img, work_dir=tmp_path / "work")
    assert result.source_kind == "image"
    assert result.page_count == 1
    assert Path(result.pages[0].path).is_file()
    assert result.pages[0].checksum


def test_ingest_pdf(sample_pdf: Path, tmp_path: Path) -> None:
    result = ingest_path(sample_pdf, work_dir=tmp_path / "work")
    assert result.source_kind == "pdf"
    assert result.page_count >= 1
    assert all(Path(p.path).is_file() for p in result.pages)


def test_ingest_missing() -> None:
    with pytest.raises(OcrSkillError) as ei:
        ingest_path("/no/such/file.png")
    assert ei.value.code == "not_found"


def test_ingest_unsupported(tmp_path: Path) -> None:
    bad = tmp_path / "x.txt"
    bad.write_text("hi", encoding="utf-8")
    with pytest.raises(OcrSkillError) as ei:
        ingest_path(bad)
    assert ei.value.code == "unsupported_media"
