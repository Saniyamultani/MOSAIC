# Layer index

Map "what to change" to the one folder to open. Outsiders read contracts only.

| Want | Open |
|---|---|
| Image/PDF → page images | `src/ocrskill/layer1_ingest/` + `contracts/ingest.schema.json` |
| OCR engine / adapters | `src/ocrskill/layer2_ocr/` + `contracts/ocr.schema.json` |
| Fence, pagination, store | `src/ocrskill/layer3_format/` + `contracts/format.schema.json` |
| Agent extract/open face | `src/ocrskill/layer4_agentio/` + `contracts/agent-io.schema.json` |
| CLI flags / human output | `src/ocrskill/cli.py` |
| Doctor / init | `src/ocrskill/doctor/` |
| Agent launcher (bootstrap .venv) | `ocr`, `ocr-skill`, `bin/ocr` |
| Portable skill instructions (canonical) | `skills/ocr/SKILL.md` |
| Skill level-3 references | `skills/ocr/references/` |
| Root skill copy (noob install) | `SKILL.md` + `references/` (synced) |
| Claude plugin | `plugins/ocr/` |
| Codex plugin | `plugins/ocr-codex/` |
| Sync skill copies after edit | `scripts/sync-skill-copies.py` |
| Skill design / progressive disclosure | `docs/SKILL_DESIGN.md` |
| System architecture | `docs/ARCHITECTURE.md` |
| Install across CLIs | `docs/INSTALL.md` |
| Vulkan / llama.cpp Docker | `docker/` |
| Claude marketplace manifest | `.claude-plugin/marketplace.json` |
| Codex marketplace manifest | `.agents/plugins/marketplace.json` |
| Model research notes | `docs/DEEPSEEK_OCR_2.md` |
| Engine mode ↔ prompt map | `src/ocrskill/layer2_ocr/modes.py` |
| Envelope wrapper | `contracts/envelope.schema.json` + `src/ocrskill/envelope.py` |
