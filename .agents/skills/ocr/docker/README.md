# OCR inference on Vulkan (llama.cpp)

Runs **DeepSeek-OCR-2 GGUF** in the same Docker pattern as
[llama-vulkan-strix](https://github.com/hec-ovi/llama-vulkan-strix):

- Image: `ghcr.io/ggml-org/llama.cpp:server-vulkan` (pull only, no build)
- Device: `/dev/dri` + render/video GIDs
- Memory: `GGML_VK_PREFER_HOST_MEMORY=1` (GTT on Strix Halo)
- Multimodal: `--model` + `--mmproj`

The skill stays on the host (or any client) and talks HTTP:

```bash
export OCR_BACKEND=llamacpp
export OCR_LLAMA_URL=http://127.0.0.1:8090
export OCR_LLAMA_MODEL=ocr
ocr extract ./scan.png --json
```

## Download weights

About 3.6 GB (Q8_0 + mmproj):

```bash
mkdir -p ~/models/gguf/DeepSeek-OCR-2
uvx --from 'huggingface_hub[cli]' hf download sabafallah/DeepSeek-OCR-2-GGUF \
  deepseek-ocr-2-q8_0.gguf \
  mmproj-deepseek-ocr-2-q8_0.gguf \
  --local-dir ~/models/gguf/DeepSeek-OCR-2
```

Official **DeepSeek-OCR (v1)** GGUF (ggml-org) also works if you point `OCR_MODEL` /
`OCR_MMPROJ` at it. OCR-2 is the default.

## Bring up

```bash
cp docker/.env.example docker/.env
# edit MODELS_DIR / RENDER_GID / VIDEO_GID if needed

docker compose -f docker/docker-compose.yml --env-file docker/.env up -d
docker compose -f docker/docker-compose.yml --env-file docker/.env logs -f ocr-llm
curl -fsS http://127.0.0.1:8090/health
```

Stop: `docker compose -f docker/docker-compose.yml --env-file docker/.env down`

Do not run this on the same port as the main llm stack (default here is **8090**).

## Why not torch/transformers in Docker?

On this box the proven path for local VLMs is **llama.cpp + Vulkan + GTT**, already
debugged in llama-vulkan-strix. DeepSeek-OCR-2 has GGUF + mmproj for that path, and
llama-server exposes OpenAI `/v1/chat/completions` with image_url content. That is the
isolated, real stack this skill targets.
