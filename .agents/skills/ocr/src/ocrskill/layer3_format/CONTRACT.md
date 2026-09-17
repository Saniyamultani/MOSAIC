# Layer 3: Format

## Purpose

Assemble multi-page OCR Markdown, fence it as untrusted, paginate for agent context, and store the full document for `open`.

## Inputs

- Source metadata + list of per-page OCR results (from Layer 2 shapes).
- Pagination: `page`, `page_size_tokens`. Schema: `contracts/format.schema.json`.

## Outputs

- Format document: full `markdown`, one-page `content` (fenced), `handle`, pagination fields, fence metadata.
- Postconditions: full body stored under handle; `has_more` means more pages are reachable via open; nothing is truncated away.

## Errors

- `not_opened`: handle unknown when paging
- `invalid_input`: bad page number

## Dependencies

- Layer 2 OCR result shape only (JSON-level).

## Invariants

- Never cap OCR output length. Pagination is progressive disclosure only.
- Agent-facing `content` is fenced unless `--no-fence` was requested.

## How to modify safely

Fence format changes need SKILL.md updates. Additive format fields: MINOR bump only.
