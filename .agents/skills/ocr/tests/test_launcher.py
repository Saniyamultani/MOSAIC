"""Bundled ./ocr launcher (agent skill pack entrypoint). Binary only, no pip/uv."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_scripts_exist_and_executable() -> None:
    for rel in ("ocr", "ocr-skill", "bin/ocr"):
        path = ROOT / rel
        assert path.is_file(), rel
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{rel} must be executable"


def test_bundled_binary_shipped() -> None:
    bundle = ROOT / "dist" / "ocr"
    assert bundle.is_file(), "dist/ocr missing; run ./scripts/build-bundle.sh"
    assert bundle.stat().st_mode & stat.S_IXUSR
    assert bundle.stat().st_size > 1_000_000


def test_launcher_source_has_no_uv_or_pip() -> None:
    text = (ROOT / "bin" / "ocr").read_text(encoding="utf-8")
    lower = text.lower()
    assert "uv sync" not in lower
    assert "pip install" not in lower
    assert "venv" not in lower or "never" in lower
    assert "dist/ocr" in text


def _run_ocr(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run the skill launcher. Host may be glibc; binary is musl → use noob Alpine."""
    env = os.environ.copy()
    env["OCR_BACKEND"] = "mock"
    native = subprocess.run(
        [str(ROOT / "ocr"), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if native.returncode == 0:
        return native
    if not shutil.which("docker"):
        return native
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{ROOT}:/skill:ro",
            "-e",
            "HOME=/tmp/home",
            "-e",
            "OCR_BACKEND=mock",
            "--entrypoint",
            "/skill/ocr",
            "noob:local",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def test_launcher_runs_version() -> None:
    proc = _run_ocr(["--version"])
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "ocr-skill" in proc.stdout
    assert "0.4.1" in proc.stdout


def test_launcher_doctor_quick() -> None:
    proc = _run_ocr(["doctor", "--quick", "--json"])
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert '"ok": true' in proc.stdout or '"ok":true' in proc.stdout
    assert "pillow" in proc.stdout


def test_skill_md_forbids_hand_pip_and_uv() -> None:
    body = (ROOT / "skills" / "ocr" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "pip" in body
    assert "uv" in body  # ban mention
    assert "never" in body
    assert "extract" in body
    assert ".noob/skills/ocr/ocr" in body
    assert "tesseract" in body
    # ban list may name uv/pip; must not instruct the agent to install
    assert "uv sync --" not in body
    assert "pip install " not in body
    assert "hard ban" in body or "never run" in body
