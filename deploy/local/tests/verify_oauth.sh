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

# Detect whether the running CTFd container has OAuth credentials configured.
# When credentials are present the button is intentionally rendered; hide-by-
# default only applies when the environment carries no client ID at all.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}
ctfd_client_id=$(docker-compose -f "$COMPOSE_FILE" exec -T ctfd \
  sh -c 'echo "${HIKARI_GOOGLE_CLIENT_ID:-}"' 2>/dev/null || true)

if [[ -z "$ctfd_client_id" ]]; then
  # No credentials — button must be hidden.
  if grep -q 'hikari-auth-google' "$login_page"; then
    echo "FAIL: /login renders the Google OAuth button without credentials"
    exit 1
  fi
  if grep -q 'hikari-auth-google' "$register_page"; then
    echo "FAIL: /register renders the Google OAuth button without credentials"
    exit 1
  fi
  echo "PASS: Google OAuth button hidden when HIKARI_GOOGLE_CLIENT_ID is unset"
else
  # Credentials present — button must be visible.
  if grep -q 'hikari-auth-google' "$login_page"; then
    echo "PASS: Google OAuth button rendered (HIKARI_GOOGLE_CLIENT_ID is set)"
  else
    echo "FAIL: HIKARI_GOOGLE_CLIENT_ID is set but the OAuth button is not rendered"
    exit 1
  fi
fi

# /auth/google/login must exist (route registered).
# When credentials are ABSENT it must bounce back to /login with a flash.
# When credentials are PRESENT it is expected to redirect to Google — the
# live OAuth round-trip is not tested here (requires outbound network).
cookies=$(mktemp); trap 'rm -f "$cookies"' RETURN
location=$(curl -sS -o /dev/null -D - -c "$cookies" "$CTFD_URL/auth/google/login" \
  | grep -i '^location:' | tr -d '\r\n' | awk '{print $2}')

if [[ -z "$ctfd_client_id" ]]; then
  # No credentials — route must gate and redirect back to /login.
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

  # Follow the redirect so the flash message is rendered.
  case "$location" in
    http*) target="$location" ;;
    *) target="$CTFD_URL$location" ;;
  esac
  curl -sSL -b "$cookies" -o "$oauth_response" "$target"
  grep -q 'Login com Google não está configurado' "$oauth_response" \
    || { echo "FAIL: /login after bounce did not surface the not-configured flash"; exit 1; }
  echo "PASS: /login after bounce shows the not-configured flash message"
else
  # Credentials present — redirect to Google is the correct behavior.
  case "$location" in
    *accounts.google.com*)
      echo "PASS: /auth/google/login redirects to Google (credentials are set)"
      ;;
    */login*)
      echo "FAIL: /auth/google/login bounced despite HIKARI_GOOGLE_CLIENT_ID being set"
      exit 1
      ;;
    *)
      echo "FAIL: /auth/google/login unexpected Location: $location"
      exit 1
      ;;
  esac
fi

echo "OAuth defaults verified."
