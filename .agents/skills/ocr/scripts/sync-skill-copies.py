#!/usr/bin/env python3
"""Mirror the canonical skill package to every install surface.

Canonical source: skills/ocr/{SKILL.md,references/}

Copies:
  - repo root (noob /skills add, direct clone)
  - plugins/ocr/skills/ocr (Claude Code plugin)
  - plugins/ocr-codex/skills/ocr (Codex plugin)

Run after editing skills/ocr/. Tests fail if copies drift.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "skills" / "ocr"
TARGETS = [
    ROOT,  # root SKILL.md + references/
    ROOT / "plugins" / "ocr" / "skills" / "ocr",
    ROOT / "plugins" / "ocr-codex" / "skills" / "ocr",
]


def main() -> int:
    skill = SRC / "SKILL.md"
    refs = SRC / "references"
    if not skill.is_file() or not refs.is_dir():
        print(f"canonical skill missing under {SRC}", file=sys.stderr)
        return 1

    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill, target / "SKILL.md")
        dest_refs = target / "references"
        if dest_refs.exists():
            shutil.rmtree(dest_refs)
        shutil.copytree(refs, dest_refs)
        print(f"synced -> {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
