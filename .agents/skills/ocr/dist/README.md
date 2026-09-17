# Bundled CLI

`ocr` is a self-contained Linux x86_64 **musl** binary (PyInstaller onefile), built for the noob-cli Alpine runtime. Same idea as blockchain-skill shipping `dist/agent-wallet.mjs`: agents run the pack launcher with **no pip/uv/Python install**.

```bash
./ocr extract /path/to/file.pdf --json
# or via skill root:
./ocr extract ...
bin/ocr extract ...
```

Rebuild:

```bash
./scripts/build-bundle.sh   # needs Docker
```

Host glibc machines cannot exec this ELF; use `uv sync` + `.venv` for local dev, or run the binary inside `noob:local` / Alpine.
