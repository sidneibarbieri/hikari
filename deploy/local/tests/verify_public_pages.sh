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
check_page "/scoreboard" "Pontuação"
check_page "/users" "Usuários"
check_page "/teams" "Equipes"
check_page "/hikari/live" "Placar ao vivo"

echo
echo "Public pages verified."
