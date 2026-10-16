#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
INSTALL=0
CREATE_IDENTITY=0
for arg in "$@"; do
  case "$arg" in
    --install) INSTALL=1 ;;
    --create-signing-identity) CREATE_IDENTITY=1 ;;
    --help|-h)
      echo "Usage: ./setup.sh [--install] [--create-signing-identity]"
      echo "Default: prepare dependencies and models only."
      echo "--install builds and installs a stably signed macOS app."
      echo "--create-signing-identity explicitly permits a new local Keychain signing identity."
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 64 ;;
  esac
done
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "The automated desktop installer supports Apple Silicon macOS only." >&2
  exit 1
fi
if [[ "$CREATE_IDENTITY" == "1" && "$INSTALL" != "1" ]]; then
  echo "--create-signing-identity requires --install." >&2
  exit 64
fi
if ! command -v brew >/dev/null; then
  echo "Install Homebrew from https://brew.sh first, then rerun this command." >&2
  exit 1
fi
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Run xcode-select --install, finish the Apple installer, then rerun setup." >&2
  exit 1
fi
PYTHON="${OPENFUNASR_PYTHON:-python3}"
if ! "$PYTHON" -c 'import sys; assert (3, 10) <= sys.version_info[:2] < (3, 13)' >/dev/null 2>&1; then
  if [[ -n "${OPENFUNASR_PYTHON:-}" ]]; then
    echo "OPENFUNASR_PYTHON must point to Python 3.10–3.12." >&2
    exit 1
  fi
  brew list --versions python@3.12 >/dev/null 2>&1 || brew install python@3.12
  PYTHON="$(brew --prefix python@3.12)/bin/python3.12"
fi
brew list --versions whisper-cpp >/dev/null 2>&1 || brew install whisper-cpp
brew list --versions openssl@3 >/dev/null 2>&1 || brew install openssl@3
"$PYTHON" -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" "$ROOT/scripts/fetch_runtime.py"
export OPENFUNASR_PYTHON="$ROOT/.venv/bin/python"
export OPENFUNASR_OPENSSL="$(brew --prefix openssl@3)/bin/openssl"
export PATH="$ROOT/.venv/bin:$PATH"
export OPENFUNASR_CONFIG_DIR="$ROOT/.cache/test-config"
"$OPENFUNASR_PYTHON" "$ROOT/test_openfunasr.py"
unset OPENFUNASR_CONFIG_DIR
if [[ "$INSTALL" != "1" ]]; then
  echo "Prepared dependencies and models. Read docs/AI_INSTALL.md to build or install."
  exit 0
fi
if [[ "$CREATE_IDENTITY" == "1" ]]; then
  OPENFUNASR_CREATE_SIGNING_IDENTITY=1 "$ROOT/create_local_signing_identity.sh"
fi
"$ROOT/install_openfunasr.sh"
