# Contracts

Every inter-layer message and CLI `--json` output is a JSON Schema 2020-12 document.
A layer is swappable as long as it keeps the same contract.

| File | Layer | Version |
|---|---|---|
| `envelope.schema.json` | Cross-cutting wrapper | 1.0.0 |
| `ingest.schema.json` | Layer 1: image/PDF → page media | 1.0.0 |
| `ocr.schema.json` | Layer 2: per-page OCR engine result | 1.0.0 |
| `format.schema.json` | Layer 3: assembled Markdown, fence, pagination | 1.0.0 |
| `agent-io.schema.json` | Layer 4: agent extract/open surface | 1.0.0 |
| `doctor.schema.json` | Installation self-test | 1.0.0 |
| `init.schema.json` | Session bring-up | 1.0.0 |

## Rules

- Outsiders only read this folder and each layer's `CONTRACT.md`. They never import another layer's `src` internals across boundaries except through the declared facade.
- Every payload is a schema-validated JSON envelope. Binary images cross by reference (path + mediaType + checksum), never as bare bytes between layers.
- No output-length cap on OCR text. Pagination is progressive disclosure of the full body; `has_more` means more pages exist.
- OCR text is untrusted and fenced on the agent face (document content can carry prompt injection).

## Versioning

Each file has `x-contract-version`. MINOR is additive optional fields. MAJOR is remove/rename/type/meaning change.
