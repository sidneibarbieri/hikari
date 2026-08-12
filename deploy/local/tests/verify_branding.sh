#!/usr/bin/env bash
# Confirms the Hikari brand is in place where it should be:
#   * the home page no longer carries the CTFd marketing block
#   * the rendered footer reads as Hikari, not "Powered by CTFd"
#   * the theme stylesheet is linked
# Each check looks for Hikari content in rendered HTML.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}

page=$(mktemp)
trap 'rm -f "$page"' EXIT

code=$(curl -sSL -o "$page" -w '%{http_code}' "$CTFD_URL/")
[[ "$code" == "200" ]] || { echo "FAIL: home page returned $code"; exit 1; }
echo "PASS: home page 200"

grep -q "Desafios reais, ameaças ocultas" "$page" \
  || { echo "FAIL: home page missing impact line"; exit 1; }
grep -q 'class="hikari-wordmark">Hikari</h1>' "$page" \
  || { echo "FAIL: home page missing Hikari wordmark"; exit 1; }
grep -q "Caça a ameaças gamificada para equipes de defesa." "$page" \
  || { echo "FAIL: home page missing operational strapline"; exit 1; }
grep -q "Placar ao vivo" "$page" \
  || { echo "FAIL: home page missing live scoreboard action"; exit 1; }
grep -q "hikari-support-item" "$page" \
  || { echo "FAIL: home page missing support section"; exit 1; }
echo "PASS: home page renders the Hikari landing block"

if grep -q "A cool CTF platform from" "$page"; then
  echo "FAIL: home page still contains the CTFd marketing line"; exit 1
fi
if grep -qE 'fa-(twitter|facebook|github)' "$page"; then
  echo "FAIL: home page still carries CTFd social icons"; exit 1
fi
echo "PASS: CTFd marketing block removed"

if grep -q "Powered by CTFd" "$page" || grep -q "Desenvolvido por CTFd" "$page"; then
  if ! grep -q "footer.footer { display: none" "$page"; then
    echo "FAIL: CTFd footer not hidden and not overridden"; exit 1
  fi
fi
grep -q 'class="hikari-footer"' "$page" \
  || { echo "FAIL: Hikari footer block not present"; exit 1; }
echo "PASS: footer replaced with Hikari attribution"

grep -q '/plugins/hikari_plugin/assets/theme.css' "$page" \
  || { echo "FAIL: theme.css not linked from rendered HTML"; exit 1; }
echo "PASS: design tokens stylesheet linked"

admin_cookie=$(mktemp)
admin_login=$(mktemp)
admin_page=$(mktemp)
trap 'rm -f "$page" "$admin_cookie" "$admin_login" "$admin_page"' EXIT

curl -sS -c "$admin_cookie" -b "$admin_cookie" -o "$admin_login" \
  "$CTFD_URL/login"
nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' "$admin_login" \
  | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
code=$(curl -sS -c "$admin_cookie" -b "$admin_cookie" -o /dev/null \
  -w '%{http_code}' -X POST "$CTFD_URL/login" \
  --data-urlencode "name=${ADMIN_EMAIL:-admin@hikari.local}" \
  --data-urlencode "password=${ADMIN_PASSWORD:-hikari_comp@2026}" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "FAIL: admin login returned $code"; exit 1; }

curl -sS -c "$admin_cookie" -b "$admin_cookie" -o "$admin_page" \
  "$CTFD_URL/admin"
if grep -q "A new CTFd version is available" "$admin_page"; then
  echo "FAIL: admin page renders the upstream update banner"; exit 1
fi
echo "PASS: upstream update banner disabled"

echo
echo "Branding verified."
