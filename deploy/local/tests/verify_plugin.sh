#!/usr/bin/env bash
# Logs in as admin and verifies the Hikari plugin pieces:
#  1. /admin/hikari renders (200) -> blueprint is wired
#  2. /api/v1/challenges/types contains 'hikari' -> challenge type is registered
# Exits non-zero on the first failure.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}

cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar"' EXIT

login_page=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$login_page" "$CTFD_URL/login"
nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' "$login_page" \
  | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
rm -f "$login_page"
[[ -n "$nonce" ]] || { echo "no nonce on /login"; exit 1; }

status=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$status" == "302" ]] || { echo "login returned $status (expected 302)"; exit 1; }
echo "PASS: admin login succeeded"

admin_check=$(curl -sSL -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' "$CTFD_URL/admin")
[[ "$admin_check" == "200" ]] || { echo "/admin returned $admin_check after redirects"; exit 1; }
echo "PASS: /admin redirected to admin home (200 after follow)"

hikari_status=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /tmp/ctfd-admin-hikari.html -w '%{http_code}' "$CTFD_URL/admin/hikari")
if [[ "$hikari_status" != "200" ]]; then
  echo "FAIL: /admin/hikari returned $hikari_status"
  head -40 /tmp/ctfd-admin-hikari.html
  exit 1
fi
echo "PASS: /admin/hikari rendered (200)"

types=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  "$CTFD_URL/api/v1/challenges/types" \
  | jq -r '.data | keys[]?' 2>/dev/null | sort | tr '\n' ' ')
if [[ -z "$types" ]]; then
  echo "FAIL: could not list challenge types"; exit 1
fi
echo "challenge types available: $types"
echo "$types" | grep -qw "hikari" \
  || { echo "FAIL: 'hikari' challenge type not registered"; exit 1; }
echo "PASS: 'hikari' challenge type is registered"

echo
echo "All plugin verification checks passed."
