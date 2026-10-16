#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 APP_PATH [SIGNING_IDENTITY]" >&2
  exit 64
fi

APP="$1"
IDENTITY="${2:-${OPENFUNASR_SIGN_IDENTITY:-OpenFunASR Local Signing}}"
BUNDLE_ID="local.openfunasr.app"
ALLOW_ADHOC="${OPENFUNASR_ALLOW_ADHOC:-0}"

if [[ ! -d "$APP" ]]; then
  echo "App bundle not found: $APP" >&2
  exit 1
fi

ACTUAL_BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")"
if [[ "$ACTUAL_BUNDLE_ID" != "$BUNDLE_ID" ]]; then
  echo "Refusing to sign unexpected Bundle ID: $ACTUAL_BUNDLE_ID" >&2
  echo "Expected: $BUNDLE_ID" >&2
  exit 1
fi

if [[ "$IDENTITY" == "-" ]]; then
  if [[ "$ALLOW_ADHOC" != "1" ]]; then
    echo "Refusing ad-hoc signing for OpenFunASR." >&2
    echo "For a disposable development build only, set OPENFUNASR_ALLOW_ADHOC=1 explicitly." >&2
    exit 1
  fi
  codesign --force --deep --sign - "$APP"
else
  IDENTITY_LINE="$(security find-identity -v -p codesigning | grep -F "\"$IDENTITY\"" | head -n 1 || true)"
  if [[ -z "$IDENTITY_LINE" ]]; then
    echo "Missing stable signing identity: $IDENTITY" >&2
    echo "Run ./create_local_signing_identity.sh once, with explicit approval." >&2
    exit 1
  fi

  IDENTITY_HASH="$(printf '%s\n' "$IDENTITY_LINE" | awk '{print $2}')"
  REQUIREMENTS_FILE="$(mktemp /tmp/openfunasr-requirements.XXXXXX)"
  trap 'rm -f "$REQUIREMENTS_FILE"' EXIT

  printf 'designated => identifier "%s" and certificate leaf = H"%s"\n' \
    "$BUNDLE_ID" "$IDENTITY_HASH" > "$REQUIREMENTS_FILE"

  # Sign nested code first, then seal the top-level bundle with one explicit,
  # certificate-pinned designated requirement.  TCC stores this requirement;
  # keeping it byte-for-byte stable is what preserves Accessibility permission.
  codesign --force --deep --sign "$IDENTITY_HASH" "$APP"
  codesign --force --sign "$IDENTITY_HASH" --requirements "$REQUIREMENTS_FILE" "$APP"
fi

codesign --verify --deep --strict --verbose=2 "$APP"

SIGNED_BUNDLE_ID="$(codesign -dvv "$APP" 2>&1 | sed -n 's/^Identifier=//p')"
if [[ "$SIGNED_BUNDLE_ID" != "$BUNDLE_ID" ]]; then
  echo "Signed Bundle ID mismatch: $SIGNED_BUNDLE_ID" >&2
  exit 1
fi

codesign -dvv --requirements - "$APP" 2>&1
