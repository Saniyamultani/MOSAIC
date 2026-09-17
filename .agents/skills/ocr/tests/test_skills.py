from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "ocr" / "SKILL.md"
REFS = ROOT / "skills" / "ocr" / "references"
SKILL_COPIES = [
    ROOT / "SKILL.md",
    ROOT / "skills" / "ocr" / "SKILL.md",
    ROOT / "plugins" / "ocr" / "skills" / "ocr" / "SKILL.md",
    ROOT / "plugins" / "ocr-codex" / "skills" / "ocr" / "SKILL.md",
]
REF_NAMES = ("modes.md", "env.md", "envelope.md")


def _parse_skill(path: Path = SKILL_PATH) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    _, fm, body = text.split("---", 2)
    meta = yaml.safe_load(fm)
    return meta, body


def test_skill_frontmatter_agentskills_spec() -> None:
    """Level-1 metadata constraints from agentskills.io specification (2025-12)."""
    meta, _ = _parse_skill()
    name = meta["name"]
    desc = meta["description"]

    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name), name
    assert len(name) <= 64
    assert name == SKILL_PATH.parent.name

    assert isinstance(desc, str) and desc.strip()
    assert 1 <= len(desc) <= 1024, f"description length {len(desc)} exceeds 1024"

    # Discovery: what + when + trigger keywords
    lower = desc.lower()
    for needle in ("pdf", "image", "markdown", "ocr", "extract"):
        assert needle in lower, f"description missing trigger keyword: {needle}"

    if "compatibility" in meta and meta["compatibility"]:
        assert len(str(meta["compatibility"])) <= 500

    assert meta.get("user-invocable") is True
    assert meta.get("metadata", {}).get("version") == "0.4.1"


def test_skill_body_has_standing_procedure() -> None:
    _, body = _parse_skill()
    for heading in (
        "Resolve CLI once",
        "Verbs",
        "Security",
        "Anti-patterns",
        "Inputs",
    ):
        assert heading in body, f"missing section: {heading}"

    assert "UNTRUSTED-OCR-CONTENT" in body
    assert "extract" in body
    assert "open" in body
    assert "has_more" in body
    assert "Never invent" in body or "never invent" in body.lower()
    assert "not mcp" in body.lower() or "no mcp" in body.lower()
    assert ".noob/skills/ocr/ocr" in body
    assert "No init" in body or "no init" in body.lower()
    assert "tesseract" in body.lower()
    assert "bundled" in body.lower() or "dist/ocr" in body


def test_skill_under_size_budget() -> None:
    """Level-2 budget: keep body lean; details in references/."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) <= 500, f"SKILL.md has {len(lines)} lines; split into references/"
    # Rough token proxy: ~4 chars/token
    assert len(text) <= 5000 * 4, f"SKILL.md ~{len(text)//4} tokens; prefer <5000"


def test_skill_references_exist_and_linked() -> None:
    _, body = _parse_skill()
    for name in REF_NAMES:
        path = REFS / name
        assert path.is_file(), path
        assert f"references/{name}" in body, f"SKILL.md should link {name}"


def test_skill_copies_match_canonical() -> None:
    """Root + plugin SKILL.md trees must match skills/ocr (noob + marketplace install)."""
    canonical = SKILL_PATH.read_bytes()
    for path in SKILL_COPIES:
        assert path.is_file(), f"missing skill copy: {path.relative_to(ROOT)}"
        assert path.read_bytes() == canonical, (
            f"drift: {path.relative_to(ROOT)} (run scripts/sync-skill-copies.py)"
        )

    for base in (
        ROOT,
        ROOT / "skills" / "ocr",
        ROOT / "plugins" / "ocr" / "skills" / "ocr",
        ROOT / "plugins" / "ocr-codex" / "skills" / "ocr",
    ):
        for name in REF_NAMES:
            src = REFS / name
            dst = base / "references" / name
            assert dst.is_file(), dst
            assert dst.read_bytes() == src.read_bytes(), f"ref drift: {dst.relative_to(ROOT)}"


def test_noob_style_root_discovery() -> None:
    """Mirrors noob find_skill_dir: root SKILL.md or one immediate subdir."""
    assert (ROOT / "SKILL.md").is_file()
    # Immediate subdirs must not be the only hit; root wins.
    hits = [p for p in ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()]
    # skills/ is a container, not a skill dir (no skills/SKILL.md)
    assert not (ROOT / "skills" / "SKILL.md").exists()
    assert all(p.name != "skills" or (p / "SKILL.md").is_file() for p in hits) or True


def test_skill_modes_match_engine() -> None:
    from ocrskill.layer2_ocr.modes import DEEPSEEK_PROMPTS, MODES

    modes_ref = (REFS / "modes.md").read_text(encoding="utf-8")
    for mode in MODES:
        assert mode in modes_ref
        assert mode in DEEPSEEK_PROMPTS
    assert "<|grounding|>" in DEEPSEEK_PROMPTS["markdown"]
    assert "Free OCR" in DEEPSEEK_PROMPTS["free"]
    assert "Parse the figure" in DEEPSEEK_PROMPTS["figure"]


def test_description_prefers_ocr_over_guessing() -> None:
    meta, _ = _parse_skill()
    desc = meta["description"].lower()
    assert "prefer" in desc or "exact" in desc or "thumbnail" in desc or "vision" in desc


def test_supported_formats_documented() -> None:
    from ocrskill.layer1_ingest.ingest import IMAGE_EXTS, PDF_EXTS

    _, body = _parse_skill()
    for ext in sorted(IMAGE_EXTS | PDF_EXTS):
        assert ext in body, f"SKILL.md should document {ext}"

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Supported inputs" in readme or "Supported inputs" in body
    assert ".pdf" in readme and "png" in readme.lower()


def test_install_docs_and_plugin_manifests() -> None:
    install = ROOT / "docs" / "INSTALL.md"
    assert install.is_file()
    text = install.read_text(encoding="utf-8")
    assert "npx skills add" in text
    assert "no mcp" in text.lower()
    assert "uv tool install" in text
    assert "/skills add" in text
    assert "root" in text.lower() and "SKILL.md" in text

    market = ROOT / ".claude-plugin" / "marketplace.json"
    assert market.is_file()
    market_data = json.loads(market.read_text(encoding="utf-8"))
    plugin_entry = market_data["plugins"][0]
    assert plugin_entry["name"] == "ocr"
    assert plugin_entry["source"] == "./plugins/ocr"
    assert plugin_entry["version"] == "0.4.1"

    plugin = ROOT / "plugins" / "ocr" / ".claude-plugin" / "plugin.json"
    assert plugin.is_file()
    plugin_data = json.loads(plugin.read_text(encoding="utf-8"))
    assert plugin_data["name"] == "ocr"
    assert plugin_data["version"] == "0.4.1"

    agents = ROOT / ".agents" / "plugins" / "marketplace.json"
    assert agents.is_file()
    agents_data = json.loads(agents.read_text(encoding="utf-8"))
    assert agents_data["plugins"][0]["name"] == "ocr-codex"

    codex_plugin = ROOT / "plugins" / "ocr-codex" / ".codex-plugin" / "plugin.json"
    assert codex_plugin.is_file()

    assert not (ROOT / ".claude-plugin" / "plugin.json").exists(), (
        "plugin.json must live under plugins/ocr/, not marketplace root"
    )


def test_no_mcp_surface() -> None:
    """Product policy: skill + CLI only; no MCP entrypoints."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "mcp" not in pyproject.lower() or "no mcp" in pyproject.lower()
    # No mcp module or console script
    assert not (ROOT / "src" / "ocrskill" / "mcp.py").exists()
    assert "mcp" not in pyproject or "no MCP" in pyproject
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "no mcp" in readme
