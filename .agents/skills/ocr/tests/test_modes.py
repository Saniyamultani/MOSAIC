from __future__ import annotations

from pathlib import Path

from ocrskill.layer2_ocr.adapters.mock import MockEngine
from ocrskill.layer2_ocr.modes import DEEPSEEK_PROMPTS, MODES
from ocrskill.layer3_format import DocumentStore
from ocrskill.layer4_agentio import build_agent


def test_modes_lockstep_with_schema() -> None:
    import json
    from pathlib import Path as P

    schema = json.loads(
        (P(__file__).resolve().parents[1] / "contracts" / "ocr.schema.json").read_text()
    )
    enum = schema["properties"]["mode"]["enum"]
    assert set(enum) == set(MODES)


def test_mock_all_modes(sample_png: Path) -> None:
    sample_png.with_suffix(".expected.md").unlink(missing_ok=True)
    eng = MockEngine()
    for mode in MODES:
        out = eng.extract_page(str(sample_png), page=1, mode=mode)
        assert out.mode == mode
        assert out.markdown


def test_extract_rejects_bad_mode(sample_png: Path, store_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OCR_BACKEND", "mock")
    agent = build_agent(store=DocumentStore(store_path / "documents.sqlite"))
    env = agent.extract([str(sample_png)], mode="not-a-mode")
    assert not env.ok
    assert env.error is not None
    assert env.error.code == "invalid_input"


def test_deepseek_prompt_strings_stable() -> None:
    # Pin strings so a casual edit does not silently change production OCR quality.
    assert DEEPSEEK_PROMPTS["markdown"].startswith("<image>\n<|grounding|>")
    assert DEEPSEEK_PROMPTS["markdown"].endswith("markdown. ")
    assert DEEPSEEK_PROMPTS["free"] == "<image>\nFree OCR. "
    assert DEEPSEEK_PROMPTS["figure"] == "<image>\nParse the figure. "
    assert DEEPSEEK_PROMPTS["ocr"] == "<image>\n<|grounding|>OCR this image. "
