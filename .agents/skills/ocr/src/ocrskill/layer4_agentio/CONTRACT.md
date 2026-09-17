# Layer 4: Agent I/O

## Purpose

Single facade the CLI calls for `extract`, `open`, `init`, and `doctor`. Returns Envelopes only; never raises past the facade boundary.

## Inputs

- `extract`: one or more local paths, mode, fence, page size. Paths must be readable files.
- `open`: handle from a prior extract, page number.
- Schemas: `contracts/agent-io.schema.json`, `contracts/init.schema.json`, `contracts/doctor.schema.json`.

## Outputs

- Envelope with `data.documents[]` (extract) or one format document (open).
- Human default is rendered from the same data; `--json` prints the Envelope.

## Errors

All Layer 1-3 codes plus `internal_error`. Mapped into Envelope.error.

## Dependencies

- Layer 1 ingest, Layer 2 OCR, Layer 3 format contracts.

## Invariants

- No MCP server. Stdio CLI only.
- Full OCR text is stored; pagination never drops content.

## How to modify safely

Add agent commands here and in `cli.py` + `skills/ocr/SKILL.md` together. Do not reimplement fence/OCR logic.
