from __future__ import annotations

import json
from pathlib import Path

from ocrskill.cli import main
from ocrskill.layer3_format import DocumentStore
from ocrskill.layer4_agentio import build_agent


def test_extract_and_open(sample_png: Path, store_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OCR_BACKEND", "mock")
    agent = build_agent(store=DocumentStore(store_path / "documents.sqlite"))
    env = agent.extract([str(sample_png)], mode="markdown", page_size_tokens=0)
    assert env.ok, env.error
    docs = env.data["documents"]
    assert len(docs) == 1
    # Ingest rewrites the page to work_dir/page-0001.png, so mock uses its
    # default template (expected.md siblings only apply when calling the engine
    # on the original fixture path directly).
    assert "Mock OCR" in docs[0]["markdown"]
    assert "UNTRUSTED-OCR-CONTENT" in docs[0]["content"]
    handle = docs[0]["handle"]

    opened = agent.open(handle, page=1, page_size_tokens=0)
    assert opened.ok
    assert opened.data["handle"] == handle


def test_cli_extract_json(sample_png: Path, store_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OCR_BACKEND", "mock")
    monkeypatch.setenv("OCR_CACHE_DIR", str(store_path))
    code = main(["extract", str(sample_png), "--json", "--backend", "mock"])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["data"]["documents"][0]["source_kind"] == "image"


def test_cli_extract_pdf(sample_pdf: Path, store_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OCR_BACKEND", "mock")
    monkeypatch.setenv("OCR_CACHE_DIR", str(store_path))
    code = main(
        [
            "extract",
            str(sample_pdf),
            "--json",
            "--backend",
            "mock",
            "--page-size-tokens",
            "0",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["data"]["documents"][0]["source_kind"] == "pdf"


def test_cli_doctor(monkeypatch, capsys) -> None:
    monkeypatch.setenv("OCR_BACKEND", "mock")
    code = main(["doctor", "--quick", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert "checks" in payload["data"]


def test_cli_missing_file(store_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OCR_BACKEND", "mock")
    monkeypatch.setenv("OCR_CACHE_DIR", str(store_path))
    code = main(
        [
            "extract",
            "/tmp/definitely-missing-ocr-skill-xyz.png",
            "--json",
            "--backend",
            "mock",
        ]
    )
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "not_found"
