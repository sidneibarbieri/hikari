#!/usr/bin/env bash
# Verifies the Hikari Google OAuth invariants:
#   * with HIKARI_GOOGLE_CLIENT_ID unset, the button is NOT rendered on
#     /login or /register (clean slate for reviewers)
#   * the /auth/google/login route exists and refuses to start the flow
#     when no credentials are configured (flashes an error and bounces
#     back to /login instead of redirecting to accounts.google.com)
#
# This script does NOT test the live Google flow: that would require
# real credentials and an outbound network round-trip. It only validates
# that the artifact's default posture is correct.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}

login_page=$(mktemp)
register_page=$(mktemp)
oauth_response=$(mktemp)
trap 'rm -f "$login_page" "$register_page" "$oauth_response"' EXIT

curl -sSL -o "$login_page" "$CTFD_URL/login"
curl -sSL -o "$register_page" "$CTFD_URL/register"

if grep -q 'hikari-auth-google' "$login_page"; then
  echo "FAIL: /login renders the Google OAuth button without credentials"
  exit 1
fi
if grep -q 'hikari-auth-google' "$register_page"; then
  echo "FAIL: /register renders the Google OAuth button without credentials"
  exit 1
fi
echo "PASS: Google OAuth button hidden when HIKARI_GOOGLE_CLIENT_ID is unset"

# /auth/google/login must exist (route registered) but bounce back to
# /login when credentials are missing. Verify the redirect target by
# inspecting Location, not the rendered HTML — flash messages live in
# the session and only show after the redirect lands on /login, which
# requires preserving the cookie. The redirect itself is the proof that
# the route is wired and the gating is in place.
cookies=$(mktemp); trap 'rm -f "$cookies"' RETURN
location=$(curl -sS -o /dev/null -D - -c "$cookies" "$CTFD_URL/auth/google/login" \
  | grep -i '^location:' | tr -d '\r\n' | awk '{print $2}')
case "$location" in
  */login*)
    echo "PASS: /auth/google/login -> $location when credentials missing"
    ;;
  *accounts.google.com*)
    echo "FAIL: /auth/google/login leaked to Google despite missing credentials"
    exit 1
    ;;
  *)
    echo "FAIL: /auth/google/login unexpected Location: $location"
    exit 1
    ;;
esac

# Follow the redirect with the session cookie so the flash survives.
# Location can be absolute or path-only; normalize before curling.
case "$location" in
  http*) target="$location" ;;
  *) target="$CTFD_URL$location" ;;
esac
curl -sSL -b "$cookies" -o "$oauth_response" "$target"
grep -q 'Login com Google não está configurado' "$oauth_response" \
  || { echo "FAIL: /login after bounce did not surface the not-configured flash"; exit 1; }
echo "PASS: /login after bounce shows the not-configured flash message"

echo "OAuth defaults verified."
