#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_ID="local.openfunasr.app"
IDENTITY="${OPENFUNASR_SIGN_IDENTITY:-OpenFunASR Local Signing}"
ALLOW_ADHOC="${OPENFUNASR_ALLOW_ADHOC:-0}"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "OpenFunASR desktop installation requires macOS." >&2
  exit 1
fi
ALLOW_MIGRATION="${OPENFUNASR_SIGNING_MIGRATION:-0}"
INSTALLED_APP="/Applications/OpenFunASR.app"
INSTALLED_SUPPORT="$HOME/Library/Application Support/OpenFunASR"
APP_LOG="$INSTALLED_SUPPORT/app.log"
NEW_APP="$ROOT/dist-local/OpenFunASR.app"
NEW_RUNTIME="$ROOT/dist-local/runtime"

bundle_id_of() {
  /usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$1/Contents/Info.plist"
}

designated_requirement_of() {
  codesign -d --requirements - "$1" 2>&1 \
    | sed -n 's/^.*designated => /designated => /p'
}

if [[ "$IDENTITY" == "-" ]]; then
  echo "Refusing ad-hoc signing for /Applications/OpenFunASR.app; use a stable identity." >&2
  exit 1
fi
if ! security find-identity -v -p codesigning | grep -F "\"$IDENTITY\"" >/dev/null; then
  echo "Missing stable signing identity: $IDENTITY" >&2
  echo "Read docs/AI_INSTALL.md before creating a signing identity." >&2
  exit 1
fi

OLD_EXISTS=0
OLD_REQUIREMENT=""
if [[ -d "$INSTALLED_APP" ]]; then
  OLD_EXISTS=1
  OLD_BUNDLE_ID="$(bundle_id_of "$INSTALLED_APP")"
  if [[ "$OLD_BUNDLE_ID" != "$BUNDLE_ID" ]]; then
    echo "Refusing to overwrite an app with unexpected Bundle ID: $OLD_BUNDLE_ID" >&2
    exit 1
  fi
  codesign --verify --deep --strict --verbose=2 "$INSTALLED_APP"
  OLD_REQUIREMENT="$(designated_requirement_of "$INSTALLED_APP")"
fi

OPENFUNASR_SIGN_IDENTITY="$IDENTITY" \
OPENFUNASR_ALLOW_ADHOC="$ALLOW_ADHOC" \
  "$ROOT/build_local_app.sh"

if [[ ! -d "$NEW_APP" || ! -d "$NEW_RUNTIME" ]]; then
  echo "Build output is incomplete." >&2
  exit 1
fi

NEW_BUNDLE_ID="$(bundle_id_of "$NEW_APP")"
if [[ "$NEW_BUNDLE_ID" != "$BUNDLE_ID" ]]; then
  echo "Refusing candidate with changed Bundle ID: $NEW_BUNDLE_ID" >&2
  exit 1
fi

codesign --verify --deep --strict --verbose=2 "$NEW_APP"
NEW_REQUIREMENT="$(designated_requirement_of "$NEW_APP")"

NEEDS_REAUTH=0
REAUTH_REASON=""

if [[ -z "$NEW_REQUIREMENT" || ( "$OLD_EXISTS" == "1" && -z "$OLD_REQUIREMENT" ) ]]; then
  echo "Missing designated requirement; refusing an unverifiable installation." >&2
  exit 1
fi
if [[ "$OLD_EXISTS" == "0" ]]; then
  NEEDS_REAUTH=1
  REAUTH_REASON="first stable installation"
elif [[ "$OLD_REQUIREMENT" != "$NEW_REQUIREMENT" ]]; then
  if [[ "$ALLOW_MIGRATION" != "1" ]]; then
    echo "STOP: signing identity continuity check failed; the installed app was not changed." >&2
    echo "Installed requirement: $OLD_REQUIREMENT" >&2
    echo "Candidate requirement: $NEW_REQUIREMENT" >&2
    echo "For an intentional one-time certificate migration only, set OPENFUNASR_SIGNING_MIGRATION=1." >&2
    exit 1
  fi
  NEEDS_REAUTH=1
  REAUTH_REASON="intentional one-time signing identity migration"
fi

STAGE_DIR="$(mktemp -d /Applications/.openfunasr-install.XXXXXX)"
STAGED_APP="$STAGE_DIR/OpenFunASR.app"
STAGED_RUNTIME="$STAGE_DIR/runtime"
BACKUP_APP="$STAGE_DIR/OpenFunASR.previous.app"
BACKUP_RUNTIME="$STAGE_DIR/runtime.previous"
INSTALL_COMMITTED=0
NEW_APP_INSTALLED=0
NEW_RUNTIME_INSTALLED=0

cleanup_install() {
  install_status=$?
  set +e
  if [[ "$INSTALL_COMMITTED" != "1" ]]; then
    pkill -x OpenFunASR 2>/dev/null || true
    if [[ "$NEW_APP_INSTALLED" == "1" && -d "$INSTALLED_APP" ]]; then
      rm -rf "$INSTALLED_APP"
    fi
    if [[ -d "$BACKUP_APP" ]]; then
      mv "$BACKUP_APP" "$INSTALLED_APP"
    fi
    if [[ "$NEW_RUNTIME_INSTALLED" == "1" && -d "$INSTALLED_SUPPORT/runtime" ]]; then
      rm -rf "$INSTALLED_SUPPORT/runtime"
    fi
    if [[ -d "$BACKUP_RUNTIME" ]]; then
      mv "$BACKUP_RUNTIME" "$INSTALLED_SUPPORT/runtime"
    fi
    if [[ -d "$INSTALLED_APP" ]]; then
      open -a "$INSTALLED_APP"
    fi
  fi
  rm -rf "$STAGE_DIR"
  exit "$install_status"
}

trap cleanup_install EXIT

ditto "$NEW_APP" "$STAGED_APP"
ditto "$NEW_RUNTIME" "$STAGED_RUNTIME"
codesign --verify --deep --strict --verbose=2 "$STAGED_APP"

pkill -x OpenFunASR 2>/dev/null || true

if [[ -d "$INSTALLED_APP" ]]; then
  mv "$INSTALLED_APP" "$BACKUP_APP"
fi
if ! mv "$STAGED_APP" "$INSTALLED_APP"; then
  exit 1
fi
NEW_APP_INSTALLED=1

mkdir -p "$INSTALLED_SUPPORT"
if [[ -d "$INSTALLED_SUPPORT/runtime" ]]; then
  mv "$INSTALLED_SUPPORT/runtime" "$BACKUP_RUNTIME"
fi
if ! mv "$STAGED_RUNTIME" "$INSTALLED_SUPPORT/runtime"; then
  exit 1
fi
NEW_RUNTIME_INSTALLED=1

codesign --verify --deep --strict --verbose=2 "$INSTALLED_APP"
INSTALLED_REQUIREMENT="$(designated_requirement_of "$INSTALLED_APP")"
if [[ "$INSTALLED_REQUIREMENT" != "$NEW_REQUIREMENT" ]]; then
  echo "Installed designated requirement changed during copy." >&2
  exit 1
fi

if [[ "$NEEDS_REAUTH" == "1" ]]; then
  echo "One-time authorization is required: $REAUTH_REASON"
else
  echo "Signing continuity verified; existing TCC permissions must be preserved."
fi

LOG_LINES_BEFORE=0
if [[ -f "$APP_LOG" ]]; then
  LOG_LINES_BEFORE="$(wc -l < "$APP_LOG" | tr -d ' ')"
fi

open -a "$INSTALLED_APP"

STARTUP_LINE=""
for openfunasr_attempt in {1..20}; do
  sleep 0.5
  if [[ -f "$APP_LOG" ]]; then
    STARTUP_LINE="$(tail -n "+$((LOG_LINES_BEFORE + 1))" "$APP_LOG" \
      | grep 'startup permissions' \
      | tail -n 1 || true)"
  fi
  if [[ -n "$STARTUP_LINE" ]]; then
    break
  fi
done

if [[ "$NEEDS_REAUTH" == "1" && -z "$STARTUP_LINE" ]]; then
  echo "ERROR: the newly installed app did not write a startup permission record." >&2
  exit 1
elif [[ "$NEEDS_REAUTH" == "1" ]]; then
  INSTALL_COMMITTED=1
  open 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'
  echo "Grant Accessibility once, restart OpenFunASR, then run the resident paste smoke test."
elif [[ "$STARTUP_LINE" == *"accessibility=已授权"* && "$STARTUP_LINE" == *"microphone=已授权(3)"* ]]; then
  INSTALL_COMMITTED=1
  echo "Runtime verification passed: $STARTUP_LINE"
else
  echo "ERROR: stable signing matched, but the app process did not report both required authorizations." >&2
  echo "Observed startup line: ${STARTUP_LINE:-<missing>}" >&2
  echo "Do not reset TCC automatically; diagnose the installed signature and TCC entry first." >&2
  exit 1
fi

echo "Installed Bundle ID: $BUNDLE_ID"
echo "Installed requirement: $INSTALLED_REQUIREMENT"
