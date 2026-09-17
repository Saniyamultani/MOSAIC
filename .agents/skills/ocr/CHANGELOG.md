# Changelog

## 0.4.1

- Launcher is binary-only: no uv/pip/venv fallback (agents must not install packages).
- SKILL.md hard-bans pip/uv/apt; allowed-tools no longer list uv/uvx.

## 0.4.0

- **Bundled CLI:** ship `dist/ocr` (PyInstaller onefile, Linux x86_64 musl) so agent
  skill packs run with zero Python/uv/pip install (blockchain-skill style).
- Launcher prefers `dist/ocr`; uv/venv is dev fallback only.
- Skill body: direct `extract` / `open`; no init step.

## 0.3.3

- Skill body simplified to direct verbs: `extract` / `open` (no mandatory init).
- Resolve CLI is three lines; doctor only after extract fails.

## 0.3.2

- Skill description forces load-first for image/PDF questions; bans tesseract/pip/apt OCR paths; list workspace if paths omitted.

## 0.3.1

- Resolve CLI snippet always exits 0 when a launcher is found (no false bash error on `command -v` miss).
- `init`/`doctor` `next_actions` only for the active broken backend; quiet when llamacpp is ready.

## 0.3.0

### Agent-friendly launcher (blockchain-skill pattern)

- Ship `./ocr`, `./ocr-skill`, and `bin/ocr`: self-bootstrapping entrypoints that
  create a skill-pack `.venv` via `uv sync --no-dev` on first run, then exec the CLI.
- Agents resolve `.noob/skills/ocr/ocr` (or PATH) and never hand-probe pip/PYTHONPATH.
- SKILL.md rewritten with resolve-CLI-first workflow; anti-patterns ban pip install.
- Cold pack bootstrap tested (~1s with cache); subsequent runs use pack-local `.venv`.

## 0.2.0

### Packaging (install fix)

- Root `SKILL.md` + `references/` so noob `/skills add hec-ovi/ocr-skill` and other
  root-discovery installers find the skill (they do not walk `skills/<name>/`).
- Claude plugin moved to `plugins/ocr/` with marketplace `source: "./plugins/ocr"`.
- Codex plugin + marketplace: `plugins/ocr-codex/`, `.agents/plugins/marketplace.json`.
- Identical skill copies kept in sync via `scripts/sync-skill-copies.py`.

### Product

- Explicit supported formats table (images + PDF) in skill body and README.
- Senior architecture and install docs (`docs/ARCHITECTURE.md`, expanded INSTALL).
- Version metadata 0.2.0; no MCP (stdio skill + CLI only, unchanged policy).

## 0.1.0

- Initial skill: `ocr extract` / `ocr open` / `ocr init` / `ocr doctor`
- Contract layers: ingest, OCR, format, agent I/O
- Backends: `llamacpp` (Vulkan GGUF via llama.cpp Docker, recommended), `deepseek` (torch), `mock`
- Docker stack mirroring llama-vulkan-strix (`docker/`, server-vulkan + mmproj)
- Modes: `markdown`, `free`, `figure`, `ocr` (official DeepSeek prompt family)
- Portable `skills/ocr/SKILL.md` with progressive disclosure (`references/`)
- Multi-CLI install docs and Claude plugin manifests (no MCP)
- Envelope JSON output, untrusted OCR fence, on-disk document store for pagination
- Skill-quality tests (Agent Skills frontmatter limits, standing rules, mode lockstep)
- llamacpp adapter unit tests; real smoke on DeepSeek-OCR-2 Q8 GGUF over Vulkan
