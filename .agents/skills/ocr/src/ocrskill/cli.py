"""The `ocr` CLI: extract images/PDFs to Markdown for agents.

Default output is a compact human view. ``--json`` emits the Envelope.
Exit 0 on success, 1 on an error Envelope.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import __version__, config
from .doctor.runner import INIT_CONTRACT_VERSION, run_doctor, run_init
from .envelope import ENVELOPE_CONTRACT_VERSION, Envelope, error_envelope
from .layer2_ocr.modes import MODES
from .layer4_agentio import AGENTIO_CONTRACT_VERSION, build_agent


def _emit(envelope: Envelope, *, as_json: bool, render: Any = None) -> int:
    if as_json:
        print(json.dumps(envelope.model_dump(mode="json"), indent=2, ensure_ascii=False))
    elif not envelope.ok and envelope.error:
        print(f"error [{envelope.error.code}]: {envelope.error.message}", file=sys.stderr)
        if envelope.error.hint:
            print(f"hint: {envelope.error.hint}", file=sys.stderr)
    elif render is not None:
        render(envelope.data)
    else:
        print(json.dumps(envelope.data, indent=2, ensure_ascii=False))
    return 0 if envelope.ok else 1


def _render_extract(data: dict[str, Any]) -> None:
    docs = data.get("documents") or []
    for i, doc in enumerate(docs):
        if i:
            print("\n" + "=" * 60 + "\n")
        print(doc.get("content", ""))
        if doc.get("has_more"):
            print(
                f"\n[page {doc['page']} of {doc['total_pages']}; "
                f"handle={doc['handle']}; "
                f"re-run: ocr open {doc['handle']} --page {doc['page'] + 1}]"
            )


def _render_open(data: dict[str, Any]) -> None:
    print(data.get("content", ""))
    if data.get("has_more"):
        print(
            f"\n[page {data['page']} of {data['total_pages']}; "
            f"ocr open {data['handle']} --page {data['page'] + 1}]"
        )


def _render_doctor(data: dict[str, Any]) -> None:
    print(f"status: {data.get('status')}  ready={data.get('ready')}")
    for c in data.get("checks") or []:
        print(f"  [{c['status']:<7}] {c['id']}: {c['detail']}")
    for a in data.get("next_actions") or []:
        print(f"next: {a}")


def _render_init(data: dict[str, Any]) -> None:
    print(f"state: {data.get('state')}  ready={data.get('ready')}")
    print(
        f"backend: {data.get('backend')}  "
        f"model: {data.get('model')}  device: {data.get('device')}"
    )
    caps = data.get("capabilities") or {}
    for k, v in caps.items():
        print(f"  {k}: {v}")
    for a in data.get("next_actions") or []:
        print(f"next: {a}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ocr",
        description="Extract text from images and PDFs as Markdown (agent skill CLI).",
    )
    p.add_argument("--version", action="version", version=f"ocr-skill {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_json(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--json", action="store_true", help="Emit structured Envelope on stdout")

    # extract
    pe = sub.add_parser("extract", help="OCR an image or PDF to Markdown")
    pe.add_argument("paths", nargs="+", help="Image or PDF path(s)")
    pe.add_argument(
        "--mode",
        choices=MODES,
        default="markdown",
        help=(
            "Engine prompt: markdown (default, document to MD), free (plain text), "
            "figure (charts/plots), ocr (general grounded OCR)"
        ),
    )
    pe.add_argument("--page", type=int, default=1, help="Output page (token-budget pagination)")
    pe.add_argument(
        "--page-size-tokens",
        type=int,
        default=config.DEFAULT_PAGE_SIZE_TOKENS,
        help="Tokens per output page; 0 = entire document as one page",
    )
    pe.add_argument("--no-fence", action="store_true", help="Do not wrap content as untrusted")
    pe.add_argument("--quiet", action="store_true", help="Print only the fenced content")
    pe.add_argument(
        "--backend",
        choices=("auto", "mock", "deepseek", "llamacpp"),
        default=None,
        help="Override OCR_BACKEND for this run (llamacpp = Vulkan GGUF server)",
    )
    pe.add_argument("--keep-work", action="store_true", help="Keep rasterized page images")
    add_json(pe)

    # open
    po = sub.add_parser("open", help="Page through a previously extracted document")
    po.add_argument("handle", help="Handle from extract (e.g. invoice~a1b2c3d4e5f6)")
    po.add_argument("--page", type=int, default=1)
    po.add_argument("--page-size-tokens", type=int, default=config.DEFAULT_PAGE_SIZE_TOKENS)
    po.add_argument("--no-fence", action="store_true")
    po.add_argument("--quiet", action="store_true")
    add_json(po)

    # doctor
    pd = sub.add_parser("doctor", help="Self-test installation and backends")
    pd.add_argument("--quick", action="store_true")
    add_json(pd)

    # init
    pi = sub.add_parser("init", help="Report capability state for this session")
    pi.add_argument("--quick", action="store_true")
    add_json(pi)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        data = run_doctor(quick=args.quick)
        from .doctor.runner import DOCTOR_CONTRACT_VERSION
        from .envelope import ok_envelope

        env = ok_envelope(
            DOCTOR_CONTRACT_VERSION, data, layer="doctor", backend=config.backend_name()
        )
        return _emit(env, as_json=args.json, render=_render_doctor)

    if args.command == "init":
        data = run_init(quick=args.quick)
        from .envelope import ok_envelope

        env = ok_envelope(INIT_CONTRACT_VERSION, data, layer="init", backend=data.get("backend"))
        _emit(env, as_json=args.json, render=_render_init)
        # exit 1 only when broken
        return 1 if data.get("state") == "broken" else 0

    if args.command == "extract":
        if args.backend:
            os.environ["OCR_BACKEND"] = args.backend
        agent = build_agent()
        env = agent.extract(
            list(args.paths),
            mode=args.mode,
            fence=not args.no_fence,
            page=args.page,
            page_size_tokens=args.page_size_tokens,
            keep_work=args.keep_work,
        )
        if args.quiet and env.ok and env.data:
            for doc in env.data.get("documents") or []:
                print(doc.get("content", ""))
            return 0
        return _emit(env, as_json=args.json, render=_render_extract)

    if args.command == "open":
        agent = build_agent()
        env = agent.open(
            args.handle,
            page=args.page,
            page_size_tokens=args.page_size_tokens,
            fence=not args.no_fence,
        )
        if args.quiet and env.ok and env.data:
            print(env.data.get("content", ""))
            return 0
        return _emit(env, as_json=args.json, render=_render_open)

    # unreachable
    env = error_envelope(
        ENVELOPE_CONTRACT_VERSION,
        code="invalid_input",
        message=f"unknown command: {args.command}",
        retriable=False,
        layer="cli",
    )
    return _emit(env, as_json=True)


# Silence unused import warnings for contract version re-exports used by tests.
_ = AGENTIO_CONTRACT_VERSION
