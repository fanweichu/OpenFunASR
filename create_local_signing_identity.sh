#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Local code signing requires macOS." >&2
  exit 1
fi
IDENTITY="OpenFunASR Local Signing"
LOGIN_KEYCHAIN="$(security default-keychain -d user \
  | sed 's/^[[:space:]]*"//; s/"[[:space:]]*$//')"

EXISTING_IDENTITIES="$(security find-identity -v -p codesigning | grep -F "\"$IDENTITY\"" || true)"
EXISTING_COUNT="$(printf '%s\n' "$EXISTING_IDENTITIES" | sed '/^$/d' | wc -l | tr -d ' ')"

if [[ "$EXISTING_COUNT" -gt 1 ]]; then
  echo "Multiple signing identities have the same name; refusing an ambiguous setup:" >&2
  printf '%s\n' "$EXISTING_IDENTITIES" >&2
  exit 1
fi

if [[ "$EXISTING_COUNT" == "1" ]]; then
  echo "Signing identity already exists; it will not be regenerated:"
  printf '%s\n' "$EXISTING_IDENTITIES"
  exit 0
fi

if [[ "${OPENFUNASR_CREATE_SIGNING_IDENTITY:-0}" != "1" ]]; then
  echo "Creating an identity imports a private key and adds user-level code-signing trust." >&2
  echo "After the user approves, run ./setup.sh --install --create-signing-identity." >&2
  exit 1
fi
OPENSSL="${OPENFUNASR_OPENSSL:-$(brew --prefix openssl@3)/bin/openssl}"
TEMP_DIR="$(mktemp -d /tmp/openfunasr-signing.XXXXXX)"
trap 'rm -rf "$TEMP_DIR"' EXIT
umask 077
IMPORT_PASSWORD="$("$OPENSSL" rand -hex 24)"
export OPENFUNASR_IMPORT_PASSWORD="$IMPORT_PASSWORD"

"$OPENSSL" req \
  -x509 \
  -newkey rsa:2048 \
  -nodes \
  -days 3650 \
  -config "$ROOT/local_signing_openssl.cnf" \
  -keyout "$TEMP_DIR/openfunasr-signing.key" \
  -out "$TEMP_DIR/openfunasr-signing.crt"

"$OPENSSL" pkcs12 \
  -export \
  -legacy \
  -passout env:OPENFUNASR_IMPORT_PASSWORD \
  -inkey "$TEMP_DIR/openfunasr-signing.key" \
  -in "$TEMP_DIR/openfunasr-signing.crt" \
  -name "$IDENTITY" \
  -out "$TEMP_DIR/openfunasr-signing.p12"

security import "$TEMP_DIR/openfunasr-signing.p12" \
  -k "$LOGIN_KEYCHAIN" \
  -f pkcs12 \
  -P "$IMPORT_PASSWORD" \
  -T /usr/bin/codesign

security add-trusted-cert \
  -r trustRoot \
  -p codeSign \
  -k "$LOGIN_KEYCHAIN" \
  "$TEMP_DIR/openfunasr-signing.crt"

CREATED_IDENTITIES="$(security find-identity -v -p codesigning | grep -F "\"$IDENTITY\"" || true)"
CREATED_COUNT="$(printf '%s\n' "$CREATED_IDENTITIES" | sed '/^$/d' | wc -l | tr -d ' ')"
if [[ "$CREATED_COUNT" != "1" ]]; then
  echo "Expected exactly one usable signing identity after import." >&2
  printf '%s\n' "$CREATED_IDENTITIES" >&2
  exit 1
fi

printf '%s\n' "$CREATED_IDENTITIES"
echo "Created stable local signing identity: $IDENTITY"
echo "Do not delete or regenerate this certificate; TCC continuity depends on its fingerprint."
