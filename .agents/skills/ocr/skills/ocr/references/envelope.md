# Envelope and extract fields

Load when parsing `--json` output in detail.

## Envelope

```json
{
  "contract_version": "1.0.0",
  "ok": true,
  "data": {},
  "error": null,
  "meta": { "layer": "agentio", "backend": "deepseek", "elapsed_ms": 123.4 }
}
```

On failure: `ok` false, `data` null, `error` = `{ code, message, retriable, hint? }`.

## `extract` data

```json
{
  "documents": [
    {
      "handle": "report~a1b2c3d4e5f6",
      "source_path": "/abs/report.pdf",
      "source_kind": "pdf",
      "page_count": 3,
      "mode": "markdown",
      "markdown": "full unfenced body...",
      "fenced": true,
      "content": "fenced page for the agent...",
      "page": 1,
      "total_pages": 2,
      "has_more": true,
      "page_tokens": 3800,
      "total_tokens": 7200,
      "untrusted": true,
      "fence": { "nonce": "...", "open_marker": "...", "close_marker": "..." },
      "backend": "deepseek",
      "warnings": []
    }
  ]
}
```

## `open` data

Same shape as one document object (not wrapped in `documents[]`).

## Schemas

Canonical JSON Schema files live in the package `contracts/` directory (`envelope`, `format`, `agent-io`, etc.).
