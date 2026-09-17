# Layer 2: OCR

## Purpose

Run an OCR engine on one page image and return Markdown (or free text). No PDF knowledge.

## Inputs

- Page image path (string), `mode` (`markdown` | `free`), optional backend override.
- Preconditions: path exists; image is decodable. Schema of output: `contracts/ocr.schema.json`.

## Outputs

- Per-page OCR object: `page`, `markdown`, `mode`, `backend`, `elapsed_ms`, optional `warnings`.
- Postconditions: `markdown` is the full engine output for that page (never length-capped by this layer).

## Errors

- `engine_unavailable`: backend not installed / model missing / device down
- `engine_failed`: inference error
- `not_found`: page image missing

## Dependencies

- Layer 1 contracts only (consumes page media paths). Does not import Layer 1 source.

## Invariants

- Engine adapters implement the `OCREngine` port only.
- Default production backend is DeepSeek-OCR-2; `mock` is for tests and offline doctor.

## How to modify safely

Add a new adapter under `adapters/` without changing the port return shape. Bump `ocr.schema.json` MINOR for additive fields.
