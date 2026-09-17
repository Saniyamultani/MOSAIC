from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from ocrskill.envelope import OcrSkillError
from ocrskill.layer2_ocr.adapters.llamacpp import LlamaCppEngine, _text_prompt


def test_text_prompt_strips_image_token() -> None:
    assert not _text_prompt("markdown").startswith("<image>")
    assert "markdown" in _text_prompt("markdown").lower()


def test_llamacpp_extract_parses_response(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    Image.new("RGB", (32, 16), color=(255, 255, 255)).save(img)

    payload = {
        "choices": [{"message": {"content": "# Hello\n\nFrom llama."}}],
    }
    raw = json.dumps(payload).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = raw
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    eng = LlamaCppEngine(base_url="http://127.0.0.1:8090", model="ocr", timeout_s=5)
    with patch("ocrskill.layer2_ocr.adapters.llamacpp.urlopen", return_value=mock_resp):
        out = eng.extract_page(str(img), page=1, mode="markdown")
    assert out.backend == "llamacpp"
    assert "Hello" in out.markdown
    assert out.mode == "markdown"


def test_llamacpp_unavailable_health() -> None:
    eng = LlamaCppEngine(base_url="http://127.0.0.1:1", model="ocr", timeout_s=0.5)
    ok, detail = eng.available()
    assert ok is False
    assert "not reachable" in detail.lower() or "failed" in detail.lower()


def test_llamacpp_missing_file(tmp_path: Path) -> None:
    eng = LlamaCppEngine(base_url="http://127.0.0.1:8090")
    with pytest.raises(OcrSkillError) as ei:
        eng.extract_page(str(tmp_path / "nope.png"))
    assert ei.value.code == "not_found"


def test_request_embeds_base64_image(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    Image.new("RGB", (8, 8), color=(0, 0, 0)).save(img)
    blob = img.read_bytes()

    captured: dict = {}

    class _Resp:
        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": "ok"}}]}
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _Resp()

    eng = LlamaCppEngine(base_url="http://example.test:8090", model="ocr")
    with patch("ocrskill.layer2_ocr.adapters.llamacpp.urlopen", side_effect=fake_urlopen):
        eng.extract_page(str(img), mode="free")

    assert captured["url"].endswith("/v1/chat/completions")
    content = captured["body"]["messages"][0]["content"]
    image_part = next(c for c in content if c.get("type") == "image_url")
    url = image_part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == blob
