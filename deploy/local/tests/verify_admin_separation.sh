#!/usr/bin/env bash
# Proves an administrator runs the competition without entering it.
#
# An administrator has to review challenges before the event and may submit a
# flag to check one works. None of that may reach the board the audience reads,
# and the screen that asks competitors to join a team must not ask the person
# running the event to join it.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

stamp=$(date +%s)
admin_jar=$(mktemp)
player_jar=$(mktemp)
page=$(mktemp)
trap 'rm -f "$admin_jar" "$player_jar" "$page"' EXIT

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

sign_in() {
  local jar=$1 name=$2 password=$3
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/login"
  curl -sS -c "$jar" -b "$jar" -o /dev/null \
    -X POST "$CTFD_URL/login" \
    --data-urlencode "name=$name" \
    --data-urlencode "password=$password" \
    --data-urlencode "nonce=$(extract_nonce "$page")"
}

board_total_solves() {
  curl -sS "$CTFD_URL/hikari/live/data" | python3 -c 'import json,sys; print(json.load(sys.stdin)["total_solves"])'
}

echo "== 1. a tela de equipe reconhece quem administra =="
sign_in "$admin_jar" "$ADMIN_EMAIL" "$ADMIN_PASSWORD"
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" "$CTFD_URL/team"
grep -qF "Você está como administrador" "$page" \
  || { echo "FAIL: an administrator is still asked to join the competition"; exit 1; }
grep -qF "/admin/challenges" "$page" \
  || { echo "FAIL: the administrator is not pointed at the registered challenges"; exit 1; }
grep -qF "Entrar na competição" "$page" \
  && { echo "FAIL: the administrator is offered a place in the competition"; exit 1; }
echo "PASS: quem administra recebe o caminho de conferência, não um lugar no jogo"

echo
echo "== 2. quem compete continua vendo a mesma tela =="
player="sep_${stamp}"
curl -sS -c "$player_jar" -b "$player_jar" -o "$page" "$CTFD_URL/register"
code=$(curl -sS -c "$player_jar" -b "$player_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/register" \
  --data-urlencode "name=$player" \
  --data-urlencode "email=${player}@teste.local" \
  --data-urlencode "password=SeparacaoTeste123" \
  --data-urlencode "nonce=$(extract_nonce "$page")")
[[ "$code" == "302" ]] || { echo "FAIL: register returned $code"; exit 1; }
curl -sS -c "$player_jar" -b "$player_jar" -o "$page" "$CTFD_URL/team"
grep -qF "Entrar na competição" "$page" \
  || { echo "FAIL: a competitor lost the way into the competition"; exit 1; }
grep -qF "Você está como administrador" "$page" \
  && { echo "FAIL: a competitor is told they administer the platform"; exit 1; }
echo "PASS: competidor mantém a tela de sempre"

echo
echo "== 3. o que um administrador resolve não conta para ninguém =="
before=$(board_total_solves)
hikari_mariadb -e \
  "INSERT INTO submissions (challenge_id, user_id, team_id, ip, provided, type, date)
     SELECT c.id, u.id, u.team_id, '127.0.0.1', 'separacao-$stamp', 'correct', NOW(6)
       FROM challenges c, users u
      WHERE u.type = 'admin'
        AND c.id NOT IN (SELECT challenge_id FROM solves WHERE user_id = u.id)
      ORDER BY c.id DESC, u.id ASC LIMIT 1;
   INSERT INTO solves (id, challenge_id, user_id, team_id)
     SELECT id, challenge_id, user_id, team_id FROM submissions
      WHERE provided = 'separacao-$stamp';" > /dev/null

after=$(board_total_solves)
recorded=$(hikari_mariadb -N -B -e \
  "SELECT COUNT(*) FROM submissions WHERE provided = 'separacao-$stamp';" | tr -d '[:space:]')

hikari_mariadb -e \
  "DELETE FROM solves WHERE id IN (SELECT id FROM submissions WHERE provided = 'separacao-$stamp');
   DELETE FROM submissions WHERE provided = 'separacao-$stamp';" > /dev/null

[[ "$recorded" == "1" ]] || { echo "FAIL: the administrator solve was never recorded, so the test proves nothing"; exit 1; }
[[ "$before" == "$after" ]] \
  || { echo "FAIL: an administrator solve moved the public count from $before to $after"; exit 1; }
echo "PASS: solve de administrador registrado no banco e ausente do placar"

echo
echo "== 4. o painel mostra o desafio como o competidor o verá =="
challenge_id=$(hikari_mariadb -N -B -e "SELECT id FROM challenges ORDER BY id DESC LIMIT 1;" | tr -d '[:space:]')
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" -w '%{http_code}' \
  "$CTFD_URL/admin/challenges/preview/$challenge_id")
[[ "$code" == "200" ]] || { echo "FAIL: challenge preview returned $code"; exit 1; }
grep -qi "submission" "$page" \
  || { echo "FAIL: the preview does not show the answer field the competitor uses"; exit 1; }
echo "PASS: pré-visualização disponível para conferir enunciado e resposta"

hikari_mariadb -e "DELETE FROM users WHERE name = '$player';" > /dev/null

echo
echo "Separação entre quem administra e quem compete verificada."
