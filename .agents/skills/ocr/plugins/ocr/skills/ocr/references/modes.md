# OCR modes and DeepSeek prompts

Load this when choosing an unusual mode or debugging empty/wrong structure.

## Agent-facing modes

| `--mode` | Intent |
|---|---|
| `markdown` | Document understanding → Markdown (default) |
| `free` | Plain text extraction without layout conversion |
| `figure` | Charts, plots, figure panels |
| `ocr` | General grounded OCR for photos/screenshots |

## Engine prompt strings (DeepSeek-OCR-2)

These are fixed in `src/ocrskill/layer2_ocr/modes.py` and match upstream HF/examples:

```
markdown: <image>\n<|grounding|>Convert the document to markdown.
ocr:      <image>\n<|grounding|>OCR this image.
free:     <image>\nFree OCR.
figure:   <image>\nParse the figure.
```

Notes:

- `<|grounding|>` is required for layout-aware document modes (`markdown`, `ocr`).
- Do not pass free-form prompts through the CLI; extend `MODES` + contracts if a new family is needed.
- Mock backend ignores prompt text and returns deterministic placeholders (tests only).
- With `OCR_BACKEND=llamacpp`, the image is sent as OpenAI `image_url` content; the
  engine strips a leading `<image>` token from the text prompt so the server owns media.
- Grounding modes may emit `text[[x1,y1,x2,y2]]` style boxes before lines. Treat those as
  layout metadata when quoting; the human-readable text is the lines after them.

## Source pages vs output pages

- **Source pages** (`page_count`, HTML comments `<!-- page N -->` in multi-page Markdown): PDF/image pages from ingest.
- **Output pages** (`page`, `total_pages`, `has_more` on extract/open): token-budget slices of the fenced agent view.

They are not the same index. `--page` on extract/open is the output-page index.
