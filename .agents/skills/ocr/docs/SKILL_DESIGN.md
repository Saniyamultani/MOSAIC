# Skill design notes (ocr-skill)

Why the agent-facing skill is shaped this way. Verified against Agent Skills practice as of mid-2026.

## Progressive disclosure (three levels)

From the [Agent Skills open standard](https://agentskills.io/specification) and Anthropic's engineering notes:

| Level | What | When loaded | Budget |
|---|---|---|---|
| 1 Metadata | YAML `name` + `description` | Every session, all skills | ~100 tokens each; `description` max **1024 chars** |
| 2 Instructions | Full `SKILL.md` body (canonical: `skills/ocr/SKILL.md`) | Only when the skill activates | Prefer **under ~5000 tokens / 500 lines** |
| 3 Resources | `references/*` beside that SKILL.md | Only when SKILL.md points the agent there | Unbounded |

Implications for this repo:

1. **`description` is the load-bearing discovery surface.** It must state *what* the skill does, *when* to use it, and trigger keywords. Agents match user turns against it before reading the body.
2. **Standing rules and decision procedure live in the body**, not the description.
3. **Env tables, model prompt tables, and edge cases** go in `references/` so casual extract runs do not pay for them.

## What the description must do

- Name the capability: local image/PDF → Markdown via CLI
- Trigger on real user language: PDF, scan, screenshot, receipt, invoice, table, OCR, "read this image"
- Prefer this skill over guessing text from a thumbnail or vision-chat paraphrases when exact text matters
- Stay under 1024 characters (spec hard limit)

## What the body must do

Modeled on research-skill / websearch-skill patterns that work in production agents:

1. **Standing rules first** (security, no guessing text, path resolution) so they are hard to skip
2. **When / When NOT** with disambiguation (PDF text extraction vs DOCX; vision describe vs OCR)
3. **Mode selection tree** (`markdown` vs `free` vs `figure` vs `ocr`) mapped to DeepSeek-OCR-2 prompts
4. **Context discipline**: extract → answer from fenced data → page with `open` only if needed
5. **Failure procedure**: read `error.code` / `error.hint`, run `doctor`, do not retry blindly
6. **Anti-patterns**: listing the skill without running it; dumping full JSON into chat; using mock in production answers

## Isolation vs skill packaging

- Runtime isolation stays in contract layers (`contracts/`, `src/ocrskill/layer*`).
- The skill package is only procedure for agents: `SKILL.md` + optional `references/`.
- Install surfaces (root, `skills/ocr/`, Claude/Codex plugins) are identical copies; edit
  `skills/ocr/` then run `scripts/sync-skill-copies.py`.
- No MCP: every harness shells out to the same `ocr` / `ocr-skill` entrypoint (stdio).

## Model prompts (engine, not skill)

DeepSeek-OCR-2 official prompt family (HF card / paper usage notes):

| Mode | Prompt string sent to the model |
|---|---|
| `markdown` | `<image>\n<|grounding|>Convert the document to markdown. ` |
| `ocr` | `<image>\n<|grounding|>OCR this image. ` |
| `free` | `<image>\nFree OCR. ` |
| `figure` | `<image>\nParse the figure. ` |

The skill tells the *agent* which mode to pick. Layer 2 maps mode → prompt. Do not invent free-form model prompts in the skill body; change adapters + contracts together if new modes are added.
