#!/usr/bin/env bash
# Checks that a competitor is judged on the investigation, not on the typing.
#
# The answers here are values copied out of a log — a process name, a phrase in
# Portuguese, a hash. Comparing them case by case fails a team that found the
# right evidence and transcribed it differently, which is not what the event is
# measuring. Nine answers are also short enough to guess, so the number of
# attempts has to mean something.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

stamp=$(date +%s)
jar=$(mktemp)
page=$(mktemp)
trap 'limpar' EXIT

limpar() {
  hikari_mariadb -e \
    "DELETE FROM submissions WHERE user_id IN (SELECT id FROM users WHERE name = 'just_$stamp');
     DELETE FROM flags WHERE challenge_id IN (SELECT id FROM challenges WHERE name = 'just-$stamp');
     DELETE FROM hikari_challenges WHERE id IN (SELECT id FROM challenges WHERE name = 'just-$stamp');
     UPDATE users SET team_id = NULL WHERE name = 'just_$stamp';
     UPDATE teams SET captain_id = NULL WHERE name = 'eq_just_$stamp';
     DELETE FROM teams WHERE name = 'eq_just_$stamp';
     DELETE FROM users WHERE name = 'just_$stamp';
     DELETE FROM challenges WHERE name = 'just-$stamp';" > /dev/null 2>&1 || true
  rm -f "$jar" "$page"
}

nonce_de() { grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'; }
token_de() { grep -oE "'csrfNonce': *\"[^\"]+\"" "$1" | head -1 | sed -E 's/.*"([^"]+)"/\1/'; }

echo "== 1. as respostas da edição ignoram maiúsculas =="
# A regra vale para o acervo que vai ao evento, que é o que a biblioteca
# registra. Desafios criados por outros testes são transitórios e não fazem
# parte de edição nenhuma.
sensiveis=$(hikari_mariadb -N -B -e \
  "SELECT COUNT(*) FROM flags f
     JOIN challenges c ON c.id = f.challenge_id
     JOIN hikari_challenge_library_entries e ON e.challenge_id = c.id
    WHERE c.state = 'visible' AND (f.data IS NULL OR f.data <> 'case_insensitive');" | tr -d '[:space:]')
[[ "$sensiveis" == "0" ]] \
  || { echo "FAIL: $sensiveis resposta(s) ainda exigem capitalização exata"; exit 1; }
echo "PASS: nenhuma resposta reprova por capitalização"

echo
echo "== 2. uma resposta em caixa trocada resolve o desafio =="
hikari_mariadb -e \
  "INSERT INTO challenges (name, description, max_attempts, value, category, type, state)
     VALUES ('just-$stamp', 'Prova de justiça na comparação.', 0, 100, 'Triagem e Métricas', 'standard', 'visible');
   INSERT INTO flags (challenge_id, type, content, data)
     SELECT id, 'static', 'flag{Injeção De Código}', 'case_insensitive'
       FROM challenges WHERE name = 'just-$stamp';" > /dev/null
desafio=$(hikari_mariadb -N -B -e "SELECT id FROM challenges WHERE name = 'just-$stamp';" | tr -d '[:space:]')

curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/register"
curl -sS -c "$jar" -b "$jar" -o /dev/null -X POST "$CTFD_URL/register" \
  --data-urlencode "name=just_$stamp" --data-urlencode "email=just_$stamp@teste.local" \
  --data-urlencode "password=JusticaTeste123" --data-urlencode "nonce=$(nonce_de "$page")"
curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/teams/new"
curl -sS -c "$jar" -b "$jar" -o /dev/null -X POST "$CTFD_URL/teams/new" \
  --data-urlencode "name=eq_just_$stamp" --data-urlencode "nonce=$(nonce_de "$page")"

hikari_compose exec -T ctfd python - <<'PY' > /dev/null
from time import time
from CTFd import create_app
from CTFd.utils import set_config
app = create_app()
with app.app_context():
    agora = int(time())
    set_config("start", agora - 600)
    set_config("end", agora + 7200)
    set_config("paused", False)
PY

curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/challenges"
token=$(token_de "$page")
resposta=$(curl -sS -c "$jar" -b "$jar" -X POST "$CTFD_URL/api/v1/challenges/attempt" \
  -H "Content-Type: application/json" -H "CSRF-Token: $token" \
  -d "{\"challenge_id\": $desafio, \"submission\": \"FLAG{INJEÇÃO DE CÓDIGO}\"}")
estado=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['data']['status'])" "$resposta")
[[ "$estado" == "correct" ]] \
  || { echo "FAIL: a resposta certa em outra caixa foi recusada ($estado)"; exit 1; }
echo "PASS: 'FLAG{INJEÇÃO DE CÓDIGO}' resolve 'flag{Injeção De Código}'"

echo
echo "== 3. respostas curtas não aceitam tentativa infinita =="
curtas=$(hikari_mariadb -N -B -e \
  "SELECT COUNT(*) FROM challenges c
     JOIN flags f ON f.challenge_id = c.id
     JOIN hikari_challenge_library_entries e ON e.challenge_id = c.id
    WHERE c.state = 'visible' AND c.max_attempts = 0
      AND CHAR_LENGTH(REPLACE(REPLACE(f.content,'flag{',''),'}','')) <= 6;" | tr -d '[:space:]')
[[ "$curtas" == "0" ]] \
  || { echo "FAIL: $curtas desafio(s) de resposta curta aceitam tentativas ilimitadas"; exit 1; }
echo "PASS: toda resposta curta tem limite de tentativas"

echo
echo "Justiça da resposta verificada."
