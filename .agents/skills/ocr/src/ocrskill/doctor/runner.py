"""Installation self-test."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .. import config
from ..layer2_ocr import build_engine
from ..layer2_ocr.adapters.mock import MockEngine

DOCTOR_CONTRACT_VERSION = "1.0.0"
INIT_CONTRACT_VERSION = "1.0.0"


def _check(id_: str, status: str, detail: str) -> dict[str, str]:
    return {"id": id_, "status": status, "detail": detail}


def run_doctor(*, quick: bool = False) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    # Core deps
    for mod, id_ in (("PIL", "pillow"), ("pypdfium2", "pypdfium2"), ("pydantic", "pydantic")):
        if importlib.util.find_spec(mod if mod != "PIL" else "PIL") is not None:
            checks.append(_check(id_, "ok", f"{mod} importable"))
        else:
            checks.append(_check(id_, "fail", f"{mod} missing"))

    cache = config.cache_dir()
    if cache.is_dir() and os_writable(cache):
        checks.append(_check("cache_dir", "ok", str(cache)))
    else:
        checks.append(_check("cache_dir", "fail", f"not writable: {cache}"))

    # Backend
    backend = config.backend_name()
    checks.append(_check("backend_config", "ok", f"OCR_BACKEND={backend}"))

    mock = MockEngine()
    ok, detail = mock.available()
    checks.append(_check("engine_mock", "ok" if ok else "fail", detail))

    try:
        from ..layer2_ocr.adapters.deepseek import DeepSeekEngine

        deep = DeepSeekEngine()
        ok, detail = deep.available()
        checks.append(_check("engine_deepseek", "ok" if ok else "warn", detail))
    except Exception as exc:
        checks.append(_check("engine_deepseek", "warn", str(exc)))

    try:
        from ..layer2_ocr.adapters.llamacpp import LlamaCppEngine

        llama = LlamaCppEngine()
        ok, detail = llama.available()
        checks.append(_check("engine_llamacpp", "ok" if ok else "warn", detail))
    except Exception as exc:
        checks.append(_check("engine_llamacpp", "warn", str(exc)))

    if not quick:
        # Smoke: mock extract on a tiny generated image if possible.
        try:
            from PIL import Image

            work = config.work_root() / "doctor-smoke"
            work.mkdir(parents=True, exist_ok=True)
            img_path = work / "smoke.png"
            Image.new("RGB", (64, 32), color=(255, 255, 255)).save(img_path)
            result = mock.extract_page(str(img_path), page=1, mode="markdown")
            if result.markdown:
                checks.append(_check("mock_infer", "ok", f"{len(result.markdown)} chars"))
            else:
                checks.append(_check("mock_infer", "fail", "empty markdown"))
        except Exception as exc:
            checks.append(_check("mock_infer", "fail", str(exc)))

    mock_ok = any(c["id"] == "engine_mock" and c["status"] == "ok" for c in checks)
    deep_ok = any(c["id"] == "engine_deepseek" and c["status"] == "ok" for c in checks)
    llama_ok = any(c["id"] == "engine_llamacpp" and c["status"] == "ok" for c in checks)
    core_fail_ids = ("pillow", "pypdfium2", "pydantic", "cache_dir")
    core_ok = not any(c["status"] == "fail" and c["id"] in core_fail_ids for c in checks)

    if not core_ok:
        status, ready = "broken", False
    elif backend == "mock":
        status, ready = ("ready", True) if mock_ok else ("broken", False)
    elif backend == "deepseek":
        status, ready = ("ready", True) if deep_ok else ("broken", False)
    elif backend == "llamacpp":
        status, ready = ("ready", True) if llama_ok else ("broken", False)
    else:  # auto
        if llama_ok or deep_ok:
            status, ready = "ready", True
        elif mock_ok:
            # Deps for mock work, but production engine is missing.
            status, ready = "degraded", False
        else:
            status, ready = "broken", False

    next_actions: list[str] = []
    # Only suggest fixes for the active backend (or for auto when no engine works).
    if backend == "llamacpp" and not llama_ok:
        next_actions.append(
            "Start Vulkan OCR server: "
            "docker compose -f docker/docker-compose.yml --env-file docker/.env up -d"
        )
        next_actions.append("Set OCR_BACKEND=llamacpp and OCR_LLAMA_URL=http://127.0.0.1:8090")
    elif backend == "deepseek" and not deep_ok:
        next_actions.append("Install deepseek extra: uv sync --extra deepseek")
        next_actions.append(
            "Set OCR_MODEL_PATH to a local checkpoint under ~/models if already downloaded"
        )
    elif backend == "auto" and not llama_ok and not deep_ok:
        next_actions.append(
            "Start Vulkan OCR server: "
            "docker compose -f docker/docker-compose.yml --env-file docker/.env up -d"
        )
        next_actions.append("Or: uv sync --extra deepseek and OCR_BACKEND=deepseek")
        next_actions.append("Or set OCR_BACKEND=mock for offline/tests")
    # When auto and at least one production engine is up: no next_actions noise.

    return {
        "status": status,
        "ready": ready,
        "checks": checks,
        "next_actions": next_actions,
    }


def run_init(*, quick: bool = False) -> dict[str, Any]:
    doctor = run_doctor(quick=quick)
    backend = config.backend_name()
    model = config.model_id()
    device = config.device()
    def _cap(cid: str) -> str:
        return (
            "ok"
            if any(c["id"] == cid and c["status"] == "ok" for c in doctor["checks"])
            else "down"
        )

    caps = {
        "ingest_image": "ok",
        "ingest_pdf": "ok",
        "engine_mock": _cap("engine_mock"),
        "engine_deepseek": _cap("engine_deepseek"),
        "engine_llamacpp": _cap("engine_llamacpp"),
    }
    try:
        eng = build_engine(backend if backend != "auto" else None)
        resolved = eng.name
    except Exception:
        resolved = backend

    state = doctor["status"]
    return {
        "state": state,
        "ready": doctor["ready"],
        "backend": resolved,
        "model": model,
        "device": device,
        "capabilities": caps,
        "next_actions": doctor["next_actions"],
        "doctor": doctor,
    }


def os_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False
