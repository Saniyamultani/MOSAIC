# Architecture

ocr-skill is a **stdio CLI + portable skill**. Agents never import Python internals; they run `ocr` and parse Envelopes. Layers are blackboxes: change one folder by reading only its `CONTRACT.md` and `schema/` (here under `contracts/`).

## Face

```
agent  --shell-->  ocr CLI  -->  Layer 4 Agent I/O  -->  Layers 1-3
                     |                |
                  human text      Envelope JSON (--json)
```

There is no MCP server, no long-lived daemon in the skill itself. The optional Docker stack under `docker/` is only the **inference server** (llama.cpp Vulkan); the CLI is a short-lived client process.

## Layers

| # | Folder | Purpose | Schema |
|---|---|---|---|
| 1 | `src/ocrskill/layer1_ingest/` | Path → ordered page PNG refs + checksums | `contracts/ingest.schema.json` |
| 2 | `src/ocrskill/layer2_ocr/` | Page image → text/Markdown (engine port) | `contracts/ocr.schema.json` |
| 3 | `src/ocrskill/layer3_format/` | Join, fence, paginate, store | `contracts/format.schema.json` |
| 4 | `src/ocrskill/layer4_agentio/` | `extract` / `open` / `init` / `doctor` facade | `contracts/agent-io.schema.json` (+ init, doctor) |

Envelope wrapper: `contracts/envelope.schema.json` + `src/ocrskill/envelope.py`.

### Cross-layer rules

1. **Outsiders read contracts only.** No importing another layer's private modules across the boundary for new features; compose through the facade and schemas.
2. **Binary as reference, not bare bytes.** Page media crosses as path + `mediaType` + `checksum` (+ size). No shared memory buffers between layers.
3. **Fail closed.** Invalid inputs become Envelope errors with a closed `error.code` set; the CLI exits 1.
4. **No output-length caps on model text.** Layer 2 returns full engine output. Pagination in Layer 3 is progressive disclosure for the agent context budget, not truncation of stored OCR.
5. **Additive schema changes** bump a minor `contract_version`. Breaking shapes land as new contracts, migrate callers, then remove.

## Engine port (Layer 2)

```
OCREngine
  ├── llamacpp   OCR_BACKEND=llamacpp  → OpenAI-compatible llama-server (Vulkan GGUF)
  ├── deepseek   OCR_BACKEND=deepseek  → torch + transformers weights
  └── mock       OCR_BACKEND=mock      → deterministic placeholders (tests)
```

Modes (`markdown`, `free`, `figure`, `ocr`) map to fixed DeepSeek-OCR-2 prompts in `modes.py`. Agents choose a mode; they do not pass free-form model prompts.

## Media path (Layer 1)

| Input | Behavior |
|---|---|
| Image extensions | Decode with Pillow; single page ref |
| `.pdf` | Rasterize each page with pypdfium2 → PNG at scale 2.0 |
| Other | `unsupported_media` |

Supported extensions: `.png` `.jpg` `.jpeg` `.webp` `.gif` `.bmp` `.tif` `.tiff` `.pdf`.

## Agent view (Layers 3-4)

1. Full Markdown is stored under the cache dir (SQLite handle).
2. Agent-facing `content` is one token-budget **page**, wrapped in `UNTRUSTED-OCR-CONTENT` with a random nonce.
3. `has_more` + `ocr open` continue without re-running OCR.
4. Source PDF page count (`page_count`) is not the same index as output pagination (`page` / `total_pages`).

## Skill package vs runtime

| Concern | Location |
|---|---|
| Agent procedure | `skills/ocr/SKILL.md` (+ `references/`) |
| Runtime implementation | `src/ocrskill/` |
| Install surfaces | root `SKILL.md`, `plugins/ocr`, `plugins/ocr-codex` (synced from `skills/ocr/`) |

Progressive disclosure: YAML description always loaded; body on activate; references only when linked. Design notes: [`SKILL_DESIGN.md`](SKILL_DESIGN.md).

## Resolver

See [`INDEX.md`](INDEX.md) for "what to change → which folder".

## Definition of done (layer change)

1. That layer's `CONTRACT.md` still matches behavior.
2. Linked schemas under `contracts/` match inputs/outputs.
3. Layer-relevant tests pass with `OCR_BACKEND=mock uv run pytest`.
4. No unrelated layer `src/` edited unless a contract boundary requires it.
