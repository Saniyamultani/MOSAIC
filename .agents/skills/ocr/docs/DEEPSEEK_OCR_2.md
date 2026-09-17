# DeepSeek-OCR 2

Notes for this project. Verified against the paper, HF model card, and GitHub (2026-07-26).

## What it is

DeepSeek-OCR 2 (also DeepSeek-OCR-2) is a ~3B-parameter open vision-language model from DeepSeek AI, aimed at document OCR and layout-aware text extraction, not general vision chat.

- Released / open-sourced around **2026-01-27**
- Builds on DeepSeek-OCR (2025-10)
- Paper: [arXiv:2601.20552](https://arxiv.org/abs/2601.20552) (*DeepSeek-OCR 2: Visual Causal Flow*)
- Weights: [deepseek-ai/DeepSeek-OCR-2](https://huggingface.co/deepseek-ai/DeepSeek-OCR-2)
- Code: [github.com/deepseek-ai/DeepSeek-OCR-2](https://github.com/deepseek-ai/DeepSeek-OCR-2)
- License: Apache 2.0 (per HF/GitHub packaging)

## Core idea: Visual Causal Flow (DeepEncoder V2)

Most VLMs feed image patches in fixed raster order (left-to-right, top-to-bottom). That breaks multi-column pages, tables, and non-linear layouts.

DeepEncoder V2:

- Uses an **LLM-style encoder** (Qwen2-0.5B class) instead of a plain CLIP vision tower
- **Reorders visual tokens** by semantic / reading structure before the decoder runs
- Uses learnable causal-flow queries and a special attention mask so the encoder can do causal-style reasoning over tokens
- Keeps **high compression**: typically on the order of **256-1,120 visual tokens per page** (budget-dependent)

Goal: reading order closer to a human (columns, tables, formulas) at a small token budget.

## Benchmarks (OmniDocBench v1.5)

From the paper / tables cited with the release:

| Metric | DeepSeek-OCR 2 | Notes |
|--------|----------------|--------|
| Overall | **91.09%** | **+3.73** vs prior DeepSeek-OCR under similar train data |
| R-order edit distance | **0.057** (was 0.085) | Reading-order improvement |
| Document parsing ED (~1120 v-tokens) | **0.100** | Vs Gemini-3 Pro **0.115** at similar token budget |

Also reports better edit distances on text / table / formula categories in most slices, and lower repetition in production-style output. Multilingual docs; prompts include free OCR and structured markdown-style extraction.

Numbers can shift with harness details. OmniDocBench is mainly EN/ZH and uses edit distance; some competing OCR teams argue that limits fairness for other languages/layouts.

## Runtime surface

Common stacks:

- Hugging Face Transformers (`trust_remote_code=True` in official samples)
- vLLM (recipes list dense ~3B, 8k ctx class)
- Unsloth (run + fine-tune guides)
- Official repo scripts for image/PDF and batch OmniDocBench eval

Not currently present under `/home/hec/models` (checked 2026-07-26). Prefer that tree if/when weights are downloaded; do not re-download duplicates.

## Why it matters for this repo

Target engine for an agent OCR skill: strong open model for real documents (columns, tables, formulas) without burning thousands of visual tokens per page. Next design steps should pin deploy path (Transformers vs vLLM), hardware fit, and contract I/O around image/PDF in → structured text/markdown out.
