#!/usr/bin/env bash
# Exercises US-15 (Enviar notificações — admin) end-to-end.
#
# Closes the previously-manual gap in the user-story traceability matrix:
# - Login as admin
# - POST a notification through CTFd's REST API
# - Verify the notification persists by GET-ing it back
# - Confirm it's exposed to authenticated users (they're meant to see
#   notifications the admin broadcasts)
#
# Schema for the POST body matches CTFd 3.7 (toast / alert / background +
# optional sound). The competitor-side fetch uses the same /api/v1
# endpoint authenticated competitors hit when their notification badge
# polls.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}

stamp=$(date +%s)
TITLE="HKQA-$stamp"
CONTENT="Verificação automatizada US-15 ($stamp)."

admin_cookies=$(mktemp)
trap 'rm -f "$admin_cookies" /tmp/hkqa-notif-*' EXIT

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

# ---------------------------------------------------------------------------
# Admin login
# ---------------------------------------------------------------------------

curl -sS -c "$admin_cookies" -b "$admin_cookies" \
  -o /tmp/hkqa-notif-login.html \
  "$CTFD_URL/login" >/dev/null
nonce=$(extract_nonce /tmp/hkqa-notif-login.html)
[[ -n "$nonce" ]] || { echo "FAIL: could not extract login nonce"; exit 1; }

login_code=$(curl -sS -c "$admin_cookies" -b "$admin_cookies" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$login_code" == "302" ]] \
  || { echo "FAIL: admin login returned $login_code"; exit 1; }
echo "PASS: admin authenticated"

# CTFd regenerates the session on successful login, which invalidates the
# pre-login nonce. Refetch any authenticated page to pick up the fresh
# CSRF nonce — the value is exposed as `init.csrfNonce` in the page
# bootstrap script.
curl -sS -b "$admin_cookies" -c "$admin_cookies" \
  -o /tmp/hkqa-notif-admin.html \
  "$CTFD_URL/admin/notifications" >/dev/null
nonce=$(grep -oE "'csrfNonce':\s*\"[0-9a-f]+\"" /tmp/hkqa-notif-admin.html \
  | head -1 | sed -E "s/.*\"([0-9a-f]+)\".*/\1/")
[[ -n "$nonce" ]] \
  || { echo "FAIL: could not extract post-login csrf nonce"; exit 1; }

# ---------------------------------------------------------------------------
# Post a notification via REST API. CSRF nonce travels in a header
# (CTFd convention) rather than the body for JSON requests.
# ---------------------------------------------------------------------------

post_body=$(printf '{"title":"%s","content":"%s","type":"toast","sound":true}' \
  "$TITLE" "$CONTENT")

post_response=$(curl -sS -b "$admin_cookies" -c "$admin_cookies" \
  -H "Content-Type: application/json" \
  -H "CSRF-Token: $nonce" \
  -X POST "$CTFD_URL/api/v1/notifications" \
  --data "$post_body")

success=$(printf '%s' "$post_response" | python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print("true" if d.get("success") else "false")
except Exception:
    print("false")')
[[ "$success" == "true" ]] \
  || { echo "FAIL: POST /api/v1/notifications did not return success — $post_response"; exit 1; }
echo "PASS: notification posted via REST API"

# ---------------------------------------------------------------------------
# Verify the notification round-trips. GET the listing and look for our
# stamp-tagged title. Spool to temp file (avoid SIGPIPE under pipefail).
# ---------------------------------------------------------------------------

list_tmp=$(mktemp)
curl -sS -b "$admin_cookies" -c "$admin_cookies" \
  "$CTFD_URL/api/v1/notifications" > "$list_tmp"

# CTFd JSON-serializes with a space after the colon ("title": "..."), and
# accented chars in CONTENT come back as \uXXXX escapes — match TITLE alone
# (it's ASCII + stamp, unambiguous) using a regex that tolerates whitespace.
grep -qE "\"title\"\s*:\s*\"$TITLE\"" "$list_tmp" \
  || { echo "FAIL: notification $TITLE not found in listing"; cat "$list_tmp"; exit 1; }
rm -f "$list_tmp"
echo "PASS: notification visible via GET /api/v1/notifications"

# ---------------------------------------------------------------------------
# Competitor-side visibility. Register a fresh user, log in, and confirm
# the same notification is reachable on the public-facing endpoint —
# that's what the competitor's bell-icon poller hits.
# ---------------------------------------------------------------------------

competitor_cookies=$(mktemp)
trap 'rm -f "$admin_cookies" "$competitor_cookies" /tmp/hkqa-notif-*' EXIT

curl -sS -c "$competitor_cookies" -b "$competitor_cookies" \
  -o /tmp/hkqa-notif-reg.html \
  "$CTFD_URL/register" >/dev/null
reg_nonce=$(extract_nonce /tmp/hkqa-notif-reg.html)

competitor_name="notif_$stamp"
competitor_email="$competitor_name@hikari.local"
competitor_password="notif-pw-$stamp"

reg_code=$(curl -sS -c "$competitor_cookies" -b "$competitor_cookies" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/register" \
  --data-urlencode "name=$competitor_name" \
  --data-urlencode "email=$competitor_email" \
  --data-urlencode "password=$competitor_password" \
  --data-urlencode "nonce=$reg_nonce")
[[ "$reg_code" == "302" ]] \
  || { echo "FAIL: competitor registration returned $reg_code"; exit 1; }

competitor_list=$(curl -sS -b "$competitor_cookies" -c "$competitor_cookies" \
  "$CTFD_URL/api/v1/notifications")
printf '%s' "$competitor_list" | grep -qF "$TITLE" \
  || { echo "FAIL: competitor cannot see admin notification"; exit 1; }
echo "PASS: competitor sees admin notification ($TITLE)"

echo
echo "US-15 notifications flow verified."
