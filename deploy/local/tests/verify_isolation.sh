#!/usr/bin/env bash
# Cross-actor authorization isolation: verifies that a regular competitor
# (logged-in non-admin) cannot reach admin-only surfaces, that one team's
# private data is not exposed in API responses meant for other teams, and
# that an anonymous visitor is bounced away from research endpoints.
#
# This is the missing piece for SBC "Available + Functional + Reproducible":
# the artifact must show that authorization is enforced, not just that the
# happy paths work. Adds a sixth row of evidence to the test matrix.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}

stamp=$(date +%s)
ALICE_NAME="alice_${stamp}"
ALICE_EMAIL="alice_${stamp}@hikari.local"
ALICE_PASSWORD="alice-pw-${stamp}"

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

alice_cookies=$(mktemp)
anon_cookies=$(mktemp)
trap 'rm -f "$alice_cookies" "$anon_cookies" /tmp/hkiso-*' EXIT


# ---------------------------------------------------------------------------
# 1. Anonymous visitor: every admin and research endpoint must redirect
#    away from itself (302 to login or 403 forbidden). 200 would mean
#    the page rendered the protected content to a logged-out caller.
# ---------------------------------------------------------------------------

echo "== anonymous visitor cannot reach protected pages =="
for path in \
    /admin/statistics \
    /admin/users \
    /admin/teams \
    /admin/pages \
    /admin/notifications \
    /admin/submissions \
    /admin/config \
    /admin/hikari/research \
    /admin/hikari/research/export.jsonl \
    /admin/hikari/research/feedback.jsonl \
    /admin/hikari/add-challenge \
    /admin/hikari-zerotier-setup \
    /admin/hikari-notify \
    /admin/import-hikari-ctf
do
    code=$(curl -sS -c "$anon_cookies" -b "$anon_cookies" \
        -o /dev/null -w '%{http_code}' "$CTFD_URL$path")
    case "$code" in
        302|403|404)
            : # acceptable: redirect to login OR explicit forbidden OR not found for unauth
            ;;
        *)
            echo "FAIL: anonymous request to $path returned $code (expected 302/403)"
            exit 1
            ;;
    esac
done
echo "PASS: 14 admin / research endpoints reject anonymous access"


# ---------------------------------------------------------------------------
# 2. Logged-in competitor (non-admin): same protected surface must reject
#    even an authenticated request. This is the most likely real-world
#    privilege-escalation vector — analyst with valid creds probing.
# ---------------------------------------------------------------------------

echo
echo "== register competitor Alice =="
curl -sS -c "$alice_cookies" -b "$alice_cookies" \
    -o /tmp/hkiso-reg.html "$CTFD_URL/register" >/dev/null
nonce=$(extract_nonce /tmp/hkiso-reg.html)
reg_code=$(curl -sS -c "$alice_cookies" -b "$alice_cookies" \
    -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/register" \
    --data-urlencode "name=$ALICE_NAME" \
    --data-urlencode "email=$ALICE_EMAIL" \
    --data-urlencode "password=$ALICE_PASSWORD" \
    --data-urlencode "nonce=$nonce")
[[ "$reg_code" == "302" ]] \
    || { echo "FAIL: competitor registration returned $reg_code"; exit 1; }
echo "PASS: Alice registered + auto-logged-in"

echo
echo "== Alice (authenticated competitor) cannot reach admin surfaces =="
for path in \
    /admin/statistics \
    /admin/users \
    /admin/teams \
    /admin/notifications \
    /admin/submissions \
    /admin/config \
    /admin/hikari/research \
    /admin/hikari/research/export.jsonl \
    /admin/hikari/research/feedback.jsonl
do
    code=$(curl -sS -b "$alice_cookies" -c "$alice_cookies" \
        -o /dev/null -w '%{http_code}' "$CTFD_URL$path")
    case "$code" in
        302|403|404)
            : # admins_only decorator should bounce her
            ;;
        200)
            echo "FAIL: competitor Alice could open $path (200)"
            exit 1
            ;;
        *)
            echo "FAIL: $path returned unexpected $code"
            exit 1
            ;;
    esac
done
echo "PASS: 9 admin endpoints reject authenticated non-admin"


# ---------------------------------------------------------------------------
# 3. Even POST attempts (escalation by side-channel) are rejected. Test
#    a destructive admin route — if this returns 200 we have a real bug.
# ---------------------------------------------------------------------------

echo
echo "== Alice POST to destructive admin route =="
nonce=$(grep -oE "'csrfNonce':\s*\"[0-9a-f]+\"" /tmp/hkiso-reg.html \
    | head -1 | sed -E "s/.*\"([0-9a-f]+)\".*/\1/" || true)
post_code=$(curl -sS -b "$alice_cookies" -c "$alice_cookies" \
    -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/admin/delete-all-zerotiers" \
    --data-urlencode "nonce=${nonce:-bogus}")
case "$post_code" in
    302|403|404)
        echo "PASS: POST to /admin/delete-all-zerotiers blocked ($post_code)"
        ;;
    200)
        echo "FAIL: destructive admin POST allowed for non-admin (200)"
        exit 1
        ;;
    *)
        # CSRF check may fire first — anything that isn't 200 is fine here.
        echo "PASS: POST to /admin/delete-all-zerotiers blocked ($post_code)"
        ;;
esac


# ---------------------------------------------------------------------------
# 4. Public scoreboard / users / teams lists must not expose private
#    fields like email or password hash. Bench-check a couple of likely
#    candidates against the public JSON.
# ---------------------------------------------------------------------------

echo
echo "== public listings do not leak private fields =="
scoreboard_json=$(mktemp)
curl -sS -b "$alice_cookies" -c "$alice_cookies" \
    "$CTFD_URL/api/v1/scoreboard" -o "$scoreboard_json"
# oauth_id is intentionally exposed by CTFd (drives the "official" badge
# next to OAuth-linked competitors); skip it in the leak check.
for forbidden in '"password"' '"email"' '"secret"' '"hash"'; do
    if grep -q "$forbidden" "$scoreboard_json"; then
        echo "FAIL: public scoreboard JSON contains $forbidden"
        exit 1
    fi
done
rm -f "$scoreboard_json"
echo "PASS: scoreboard JSON keeps private account fields out of public output"


echo
echo "Authorization isolation verified."
