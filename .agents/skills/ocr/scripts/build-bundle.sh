#!/usr/bin/env bash
# Build a self-contained ocr CLI into dist/ocr (Linux x86_64 musl).
# Matches the noob-cli runtime (Alpine). Agents exec this binary with zero
# Python/uv install steps.
#
# Usage (from repo root):
#   ./scripts/build-bundle.sh
#
# Requires Docker. Output: dist/ocr (~25-30 MiB).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/dist"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/ocr-bundle.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

mkdir -p "$OUT" "$STAGE"

echo "building musl onefile bundle via Alpine + PyInstaller..."
docker run --rm \
  -v "$ROOT:/src:ro" \
  -v "$STAGE:/out" \
  alpine:3.22 \
  sh -c '
set -e
apk add --no-cache python3 py3-pip binutils >/dev/null
python3 -m venv /tmp/venv
/tmp/venv/bin/pip install -q --upgrade pip
/tmp/venv/bin/pip install -q "pyinstaller>=6" "pydantic>=2.7" "Pillow>=10" "pypdfium2>=4.30"
/tmp/venv/bin/pip install -q /src
cat > /tmp/ocr_entry.py << "EOF"
from ocrskill.cli import main
raise SystemExit(main())
EOF
/tmp/venv/bin/pyinstaller --noconfirm --onefile --name ocr \
  --distpath /out --workpath /tmp/build --specpath /tmp \
  --collect-all pypdfium2 --collect-binaries pypdfium2 \
  --collect-all PIL \
  /tmp/ocr_entry.py
chmod 755 /out/ocr
OCR_BACKEND=mock /out/ocr --version
'

# Stage may be root-owned; copy with install
install -m 0755 "$STAGE/ocr" "$OUT/ocr"
echo "wrote $OUT/ocr ($(du -h "$OUT/ocr" | awk '{print $1}'))"
file "$OUT/ocr"
OCR_BACKEND=mock "$OUT/ocr" doctor --quick 2>/dev/null | head -5 || true
echo "ok: ship dist/ocr with the skill pack (noob Alpine / musl)."
