# Layer 1: Ingest

## Purpose

Turn a local image or PDF path into ordered page media references (PNG files + checksums). No OCR.

## Inputs

- `source_path` (string path): must exist and be a file. Schema: see `contracts/ingest.schema.json` for the output shape; input is a filesystem path string.
- Preconditions: readable file; extension or content is image (`png`, `jpg`, `jpeg`, `webp`, `gif`, `bmp`, `tif`, `tiff`) or PDF.

## Outputs

- Ingest result object per `contracts/ingest.schema.json`: `source_path`, `source_kind`, `page_count`, `work_dir`, `pages[]` with `page`, `path`, `media_type`, `width`, `height`, `byte_size`, `checksum`.
- Postconditions: every `pages[].path` exists on disk as PNG; `page` is 1-based and contiguous; PDF page order is preserved.

## Errors

- `not_found`: path missing
- `unsupported_media`: not an image or PDF
- `ingest_failed`: rasterization or decode failed
- `invalid_input`: empty path or not a file

## Dependencies

None (other contracts).

## Invariants

- Never runs the OCR model.
- Binary crosses only as path + mediaType + checksum (reference), not bare bytes in the envelope.
- Callers may delete `work_dir` after OCR finishes.

## How to modify safely

Change only this folder + `contracts/ingest.schema.json`. Keep page refs stable; bump contract MINOR for additive fields only.
