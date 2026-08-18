#!/usr/bin/env bash
# Proves the console tells an operator what competitors will actually meet.
#
# Browsing the grid answers nothing: CTFd lets an administrator past every
# prerequisite on purpose, so everything looks open. The console reads the
# staging from the challenges instead, and has to name the two mistakes that
# are only discovered during an event — a challenge nobody can reach, and a
# challenge left hidden.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

stamp=$(date +%s)
jar=$(mktemp)
page=$(mktemp)
trap 'rm -f "$jar" "$page"' EXIT

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

console() {
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/admin/hikari/competitions"
}

curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/login"
curl -sS -c "$jar" -b "$jar" -o /dev/null -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$(extract_nonce "$page")"

echo "== 1. o console descreve a sequência =="
console
grep -qF "Sequência do jogo" "$page" \
  || { echo "FAIL: the console does not describe the sequence"; exit 1; }
grep -qF "abrem no início" "$page" \
  || { echo "FAIL: the console does not say what opens at the start"; exit 1; }
echo "PASS: sequência descrita a partir dos desafios"

echo
echo "== 2. um desafio preso a um pré-requisito inexistente é denunciado =="
hikari_mariadb -e \
  "INSERT INTO challenges (name, description, max_attempts, value, category, type, state, requirements)
     VALUES ('sequencia-orfa-$stamp', 'preso a um desafio que nao existe', 0, 100,
             'Teste de sequência', 'standard', 'visible', '{\"prerequisites\": [999999]}');" > /dev/null
console
grep -qF "sequencia-orfa-$stamp" "$page" \
  || { echo "FAIL: an unreachable challenge is not reported"; exit 1; }
grep -qF "nunca abrirão" "$page" \
  || { echo "FAIL: the console does not say the challenge never opens"; exit 1; }
echo "PASS: desafio inalcançável apontado com o motivo"

echo
echo "== 3. um desafio esquecido como oculto é contado =="
hikari_mariadb -e \
  "UPDATE challenges SET state = 'hidden', requirements = '{\"prerequisites\": []}'
     WHERE name = 'sequencia-orfa-$stamp';" > /dev/null
console
grep -qF "ocultos, que ninguém verá" "$page" \
  || { echo "FAIL: hidden challenges are not reported"; exit 1; }
grep -qF "sequencia-orfa-$stamp" "$page" \
  && { echo "FAIL: a hidden challenge is still reported as unreachable"; exit 1; }
echo "PASS: oculto contado à parte, sem ser confundido com inalcançável"

hikari_mariadb -e "DELETE FROM challenges WHERE name = 'sequencia-orfa-$stamp';" > /dev/null

echo
echo "Sequência do jogo verificada."
