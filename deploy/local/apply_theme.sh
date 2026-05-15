#!/usr/bin/env bash
# Sets the CTFd theme_header config to inject the Hikari design tokens into
# every theme page. Idempotent: if the desired value is already set, the
# script just confirms and exits 0.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari-admin-pw}

THEME_HEADER='<link rel="stylesheet" href="/plugins/hikari_plugin/assets/theme.css?cache=20260514c">'

cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar"' EXIT

page=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" "$CTFD_URL/login"
nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' "$page" \
  | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
rm -f "$page"

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "admin login returned $code"; exit 1; }

page=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" -L "$CTFD_URL/admin"
csrf=$(grep -oE "'csrfNonce':[[:space:]]*\"[^\"]+\"" "$page" \
  | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
rm -f "$page"
[[ -n "$csrf" ]] || { echo "could not extract CSRF nonce"; exit 1; }

current=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  "$CTFD_URL/api/v1/configs/theme_header" \
  | jq -r '.data.value // ""')

if [[ "$current" == "$THEME_HEADER" ]]; then
  echo "theme_header already set; no change"
  exit 0
fi

if [[ -z "$current" ]]; then
  response=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
    -H "Content-Type: application/json" \
    -H "Csrf-Token: $csrf" \
    -X POST "$CTFD_URL/api/v1/configs" \
    -d "{\"key\":\"theme_header\",\"value\":$(jq -Rn --arg v "$THEME_HEADER" '$v')}")
else
  response=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
    -H "Content-Type: application/json" \
    -H "Csrf-Token: $csrf" \
    -X PATCH "$CTFD_URL/api/v1/configs/theme_header" \
    -d "{\"value\":$(jq -Rn --arg v "$THEME_HEADER" '$v')}")
fi

success=$(echo "$response" | jq -r '.success')
[[ "$success" == "true" ]] \
  || { echo "FAIL: config update response: $response"; exit 1; }

echo "theme_header applied: $THEME_HEADER"
