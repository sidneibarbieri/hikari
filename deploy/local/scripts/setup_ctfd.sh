#!/usr/bin/env bash
# Drives the CTFd setup wizard end-to-end via HTTP. Idempotent: if setup has
# already been completed, the GET to /setup returns 302 and the script exits 0.
# Reads admin credentials from environment with sane defaults for local use.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
CTF_NAME=${CTF_NAME:-Hikari}
CTF_DESCRIPTION=${CTF_DESCRIPTION:-Hikari local development instance}
USER_MODE=${USER_MODE:-teams}
ADMIN_NAME=${ADMIN_NAME:-admin}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}

cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar"' EXIT

echo "Checking $CTFD_URL/setup ..."
status=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /tmp/ctfd-setup-page.html \
  -w '%{http_code}' "$CTFD_URL/setup")

if [[ "$status" == "302" ]]; then
  echo "setup already complete (GET /setup -> 302)"
  exit 0
fi
[[ "$status" == "200" ]] || { echo "unexpected setup status $status"; exit 1; }

nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' /tmp/ctfd-setup-page.html \
  | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')

[[ -n "$nonce" ]] || { echo "could not extract nonce from /setup page"; exit 1; }
echo "nonce captured (${#nonce} bytes)"

echo "Submitting setup form ..."
status=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /tmp/ctfd-setup-resp.html \
  -w '%{http_code}' \
  -X POST "$CTFD_URL/setup" \
  --data-urlencode "nonce=$nonce" \
  --data-urlencode "ctf_name=$CTF_NAME" \
  --data-urlencode "ctf_description=$CTF_DESCRIPTION" \
  --data-urlencode "user_mode=$USER_MODE" \
  --data-urlencode "name=$ADMIN_NAME" \
  --data-urlencode "email=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "challenge_visibility=private" \
  --data-urlencode "account_visibility=public" \
  --data-urlencode "score_visibility=public" \
  --data-urlencode "registration_visibility=public" \
  --data-urlencode "verify_emails=" \
  --data-urlencode "team_size=" \
  --data-urlencode "ctf_theme=core-beta" \
  --data-urlencode "theme_color=" \
  --data-urlencode "start=" \
  --data-urlencode "end=" \
  --data-urlencode "_submit=Finish")

if [[ "$status" != "302" ]]; then
  echo "setup POST returned $status (expected 302)"
  echo "----- response head -----"
  head -50 /tmp/ctfd-setup-resp.html
  exit 1
fi

echo "setup complete; admin = $ADMIN_EMAIL"
