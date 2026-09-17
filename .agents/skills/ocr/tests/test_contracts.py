from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("jsonschema")
from jsonschema import Draft202012Validator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"


def _load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def test_envelope_schema_validates_ok() -> None:
    schema = _load("envelope.schema.json")
    Draft202012Validator.check_schema(schema)
    instance = {
        "contract_version": "1.0.0",
        "ok": True,
        "data": {"hello": 1},
        "error": None,
        "meta": {"layer": "agentio", "backend": "mock", "elapsed_ms": 1.2},
    }
    Draft202012Validator(schema).validate(instance)


def test_ingest_schema_validates() -> None:
    schema = _load("ingest.schema.json")
    Draft202012Validator.check_schema(schema)
    instance = {
        "source_path": "/tmp/a.png",
        "source_kind": "image",
        "page_count": 1,
        "work_dir": "/tmp/work",
        "pages": [
            {
                "page": 1,
                "path": "/tmp/work/page.png",
                "media_type": "image/png",
                "width": 10,
                "height": 10,
                "byte_size": 100,
                "checksum": "abc",
            }
        ],
    }
    Draft202012Validator(schema).validate(instance)


def test_ocr_and_format_schemas() -> None:
    for name in ("ocr.schema.json", "format.schema.json", "doctor.schema.json", "init.schema.json"):
        schema = _load(name)
        Draft202012Validator.check_schema(schema)


def test_live_extract_matches_format_fields(sample_png, store_path, monkeypatch) -> None:
    monkeypatch.setenv("OCR_BACKEND", "mock")
    monkeypatch.setenv("OCR_CACHE_DIR", str(store_path))
    from ocrskill.layer3_format import DocumentStore
    from ocrskill.layer4_agentio import build_agent

    env = build_agent(store=DocumentStore(store_path / "documents.sqlite")).extract(
        [str(sample_png)], page_size_tokens=0
    )
    assert env.ok
    doc = env.data["documents"][0]
    schema = _load("format.schema.json")
    Draft202012Validator(schema).validate(doc)
