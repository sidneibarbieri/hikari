#!/usr/bin/env bash
# Render public Hikari pages and verify each page carries expected content.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}

check_page() {
  local path=$1
  local expected=$2
  local page
  page=$(mktemp)
  local code
  code=$(curl -sSL -o "$page" -w '%{http_code}' "$CTFD_URL$path")
  if [[ "$code" != "200" ]]; then
    echo "FAIL: $path returned $code"
    cat "$page"
    rm -f "$page"
    exit 1
  fi
  if grep -q "Internal Server Error" "$page"; then
    echo "FAIL: $path rendered a server error"
    cat "$page"
    rm -f "$page"
    exit 1
  fi
  grep -q "$expected" "$page" \
    || { echo "FAIL: $path missing expected content: $expected"; rm -f "$page"; exit 1; }
  rm -f "$page"
  echo "PASS: $path renders $expected"
}

check_page "/" "Desafios reais"
check_page "/login" "Entrar no Hikari"
check_page "/register" "Crie uma conta"
# curl reports the absolute Location, so compare the path rather than the
# whole URL, which carries the host and port of whichever stack is running.
scoreboard_target=$(curl -sS -o /dev/null -w '%{redirect_url}' "$CTFD_URL/scoreboard")
[[ "${scoreboard_target#"$CTFD_URL"}" == "/hikari/live" ]] \
  || { echo "FAIL: /scoreboard redirected to '$scoreboard_target' instead of /hikari/live"; exit 1; }
echo "PASS: /scoreboard redirects to the live board"
check_page "/users" "Usuários"
check_page "/teams" "Equipes"
check_page "/hikari/live" "Placar ao vivo"

echo
echo "Public pages verified."
