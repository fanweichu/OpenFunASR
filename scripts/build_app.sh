#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-local}"
if [[ "$MODE" != "local" && "$MODE" != "full" ]]; then
  echo "Expected local or full build mode." >&2; exit 64
fi
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This build pipeline supports Apple Silicon macOS only." >&2; exit 1
fi
PYTHON="${OPENFUNASR_PYTHON:-$ROOT/.venv/bin/python}"
IDENTITY="${OPENFUNASR_SIGN_IDENTITY:-OpenFunASR Local Signing}"
ASSETS="$ROOT/runtime-assets"
SPEECH_RUNTIME="${OPENFUNASR_SPEECH_RUNTIME:-$(brew --prefix whisper-cpp)/libexec}"
DIST="$ROOT/dist-$MODE"
WORK="$ROOT/build-$MODE"
APP="$DIST/OpenFunASR.app"
for name in funasr-encoder-f16.gguf qwen3-0.6b-q5km.gguf fsmn-vad.gguf ggml-silero-v6.2.0.bin; do
  [[ -f "$ASSETS/models/$name" ]] || { echo "Missing $name; run ./setup.sh first." >&2; exit 1; }
done
[[ -x "$ASSETS/bin/llama-funasr-cli" && -x "$SPEECH_RUNTIME/bin/whisper-vad-speech-segments" ]] || {
  echo "Missing runtime executables; run ./setup.sh first." >&2; exit 1;
}
if [[ "$IDENTITY" == "-" ]]; then
  [[ "${OPENFUNASR_ALLOW_ADHOC:-0}" == "1" ]] || { echo "Ad-hoc development signing requires OPENFUNASR_ALLOW_ADHOC=1." >&2; exit 1; }
else
  security find-identity -v -p codesigning | grep -F "\"$IDENTITY\"" >/dev/null || {
    echo "Stable signing identity not found. Read docs/AI_INSTALL.md." >&2; exit 1;
  }
fi
rm -rf "$DIST" "$WORK"
export PYINSTALLER_CONFIG_DIR="$WORK/pyinstaller-config"
"$PYTHON" -m PyInstaller --noconfirm --windowed --name OpenFunASR \
  --distpath "$DIST" --workpath "$WORK" --specpath "$WORK" \
  --osx-bundle-identifier local.openfunasr.app "$ROOT/openfunasr_app.py"
if [[ "$MODE" == "full" ]]; then
  RUNTIME="$APP/Contents/Resources"
else
  RUNTIME="$DIST/runtime"
fi
mkdir -p "$RUNTIME/bin" "$RUNTIME/lib" "$RUNTIME/models"
cp "$SPEECH_RUNTIME/bin/whisper-vad-speech-segments" "$RUNTIME/bin/speech-vad"
cp "$ASSETS/bin/llama-funasr-cli" "$RUNTIME/bin/llama-funasr-cli"
cp -a "$SPEECH_RUNTIME/lib/"*.dylib "$RUNTIME/lib/"
cp "$ASSETS/models/"* "$RUNTIME/models/"
chmod +x "$RUNTIME/bin/"*
if ! otool -l "$RUNTIME/bin/speech-vad" | grep -q '@executable_path/../lib'; then
  install_name_tool -add_rpath '@executable_path/../lib' "$RUNTIME/bin/speech-vad"
fi
# Editing an executable invalidates its previous signature; re-sign runtime code.
find "$RUNTIME/lib" -type f -name '*.dylib' -exec codesign --force --sign "$IDENTITY" {} \;
codesign --force --sign "$IDENTITY" "$RUNTIME/bin/speech-vad"
codesign --force --sign "$IDENTITY" "$RUNTIME/bin/llama-funasr-cli"
"$PYTHON" - "$ROOT/Info.plist" "$APP/Contents/Info.plist" <<'PY'
import plistlib
import sys
from pathlib import Path
template = plistlib.loads(Path(sys.argv[1]).read_bytes())
path = Path(sys.argv[2])
generated = plistlib.loads(path.read_bytes())
# Retain PyInstaller's actual executable and metadata needed by the bootloader.
template.pop("CFBundleExecutable", None)
generated.update(template)
path.write_bytes(plistlib.dumps(generated))
PY
"$ROOT/sign_openfunasr_bundle.sh" "$APP" "$IDENTITY"
echo "$APP"
echo "$RUNTIME"
