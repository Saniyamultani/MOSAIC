"""Unit tests for OCR and Firecrawl skill integrations."""

from unittest.mock import MagicMock, patch

from app.agents.research import ResearchAgent
from app.db import SessionLocal, init_db
from app.ingest.parsers import fetch_url, parse_image, parse_pdf
from app.models import Source


def setup_module():
    init_db()


def test_parse_image_fallback():
    # Test that parse_image doesn't crash when OCR CLI is absent
    fake_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    res = parse_image(fake_image_bytes)
    assert isinstance(res, str)


def test_parse_pdf_fallback():
    fake_pdf_bytes = b"%PDF-1.4 header"
    res = parse_pdf(fake_pdf_bytes)
    assert isinstance(res, str)


def test_ocr_cli_mock():
    fake_bytes = b"fake image content"
    mock_json = (
        '{"ok": true, "data": {"documents": [{"content": "# OCR Extract Text\\nInvoice #12345"}]}}'
    )
    with patch("app.ingest.parsers._find_ocr_cli", return_value="/usr/local/bin/ocr"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_json)
            extracted = parse_image(fake_bytes)
            assert "Invoice #12345" in extracted


def test_fetch_url_firecrawl_mock():
    target_url = "https://example.com/receipt-policy"
    mock_markdown = "# Receipt Policy\nAll receipts are backed by a 1-year warranty."

    with patch("app.ingest.parsers.settings.enable_network_research", True):
        with patch("app.ingest.parsers.fetch_url_firecrawl", return_value=("Receipt Policy", mock_markdown)):
            title, text = fetch_url(target_url)
            assert title == "Receipt Policy"
            assert "1-year warranty" in text


def test_research_agent_firecrawl():
    db = SessionLocal()
    try:
        source = Source(name="Firecrawl Tech News", kind="firecrawl", url="https://tech.example.com", category="external_update")
        db.add(source)
        db.commit()

        agent = ResearchAgent(db)
        with patch.object(agent, "_poll_firecrawl", return_value=[]) as mock_poll:
            agent.poll()
            assert mock_poll.called
    finally:
        db.close()
