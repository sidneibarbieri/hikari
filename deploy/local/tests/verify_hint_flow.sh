#!/usr/bin/env bash
# Walks a challenge the way a competitor does, hint included.
#
# The hints used to live inside the description, where they were free and
# unavoidable. Moving them into CTFd's own hints puts a price on them, and a
# price only means something if the content is really hidden until it is paid
# and the score really drops when it is. This checks all of that, and that the
# flag still solves the challenge afterwards.

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
trap 'limpar' EXIT

limpar() {
  hikari_mariadb -e \
    "DELETE FROM unlocks WHERE user_id IN (SELECT id FROM users WHERE name = 'dica_$stamp');
     DELETE FROM solves WHERE id IN (SELECT id FROM submissions WHERE provided LIKE 'flag{dica-$stamp}');
     DELETE FROM submissions WHERE user_id IN (SELECT id FROM users WHERE name = 'dica_$stamp');
     DELETE FROM hints WHERE challenge_id IN (SELECT id FROM challenges WHERE name = 'dica-$stamp');
     DELETE FROM flags WHERE challenge_id IN (SELECT id FROM challenges WHERE name = 'dica-$stamp');
     DELETE FROM hikari_challenges WHERE id IN (SELECT id FROM challenges WHERE name = 'dica-$stamp');
     UPDATE users SET team_id = NULL WHERE name = 'dica_$stamp';
     UPDATE teams SET captain_id = NULL WHERE name = 'eq_dica_$stamp';
     DELETE FROM teams WHERE name = 'eq_dica_$stamp';
     DELETE FROM users WHERE name = 'dica_$stamp';
     DELETE FROM challenges WHERE name = 'dica-$stamp';" > /dev/null 2>&1 || true
  rm -f "$jar" "$page"
}

nonce_de() { grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'; }
token_de() { grep -oE "'csrfNonce': *\"[^\"]+\"" "$1" | head -1 | sed -E 's/.*"([^"]+)"/\1/'; }

echo "== 1. um desafio com dica paga =="
hikari_mariadb -e \
  "INSERT INTO challenges (name, description, max_attempts, value, category, type, state)
     VALUES ('dica-$stamp', 'Descricao que basta para resolver.', 0, 100, 'Teste de dica', 'standard', 'visible');
   INSERT INTO flags (challenge_id, type, content, data)
     SELECT id, 'static', 'flag{dica-$stamp}', 'case_insensitive'
       FROM challenges WHERE name = 'dica-$stamp';
   INSERT INTO hints (challenge_id, type, content, cost)
     SELECT id, 'standard', 'Isto acelera, mas nao e necessario.', 30 FROM challenges WHERE name = 'dica-$stamp';" > /dev/null
desafio=$(hikari_mariadb -N -B -e "SELECT id FROM challenges WHERE name = 'dica-$stamp';" | tr -d '[:space:]')
dica=$(hikari_mariadb -N -B -e "SELECT id FROM hints WHERE challenge_id = $desafio;" | tr -d '[:space:]')
[[ -n "$desafio" && -n "$dica" ]] || { echo "FAIL: challenge or hint was not created"; exit 1; }
echo "PASS: desafio $desafio com dica $dica custando 30 de 100 pontos"

echo
echo "== 2. o competidor entra e a competição está aberta =="
curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/register"
curl -sS -c "$jar" -b "$jar" -o /dev/null -X POST "$CTFD_URL/register" \
  --data-urlencode "name=dica_$stamp" --data-urlencode "email=dica_$stamp@teste.local" \
  --data-urlencode "password=DicaTeste123" --data-urlencode "nonce=$(nonce_de "$page")"
curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/teams/new"
curl -sS -c "$jar" -b "$jar" -o /dev/null -X POST "$CTFD_URL/teams/new" \
  --data-urlencode "name=eq_dica_$stamp" --data-urlencode "nonce=$(nonce_de "$page")"
# The config table is keyed by id, not by name, so writing it with SQL adds a
# second row for the same setting instead of replacing the first one.
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

code=$(curl -sS -c "$jar" -b "$jar" -o "$page" -w '%{http_code}' "$CTFD_URL/challenges")
[[ "$code" == "200" ]] || { echo "FAIL: challenges page returned $code"; exit 1; }
token=$(token_de "$page")
[[ -n "$token" ]] || { echo "FAIL: no CSRF token for the API"; exit 1; }
echo "PASS: competidor com equipe vê a tela de desafios"

echo
echo "== 3. a dica fica escondida antes de ser paga =="
conteudo=$(curl -sS -c "$jar" -b "$jar" "$CTFD_URL/api/v1/hints/$dica" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data'].get('content') or '')")
[[ -z "$conteudo" ]] \
  || { echo "FAIL: the hint content was readable without paying: $conteudo"; exit 1; }
echo "PASS: conteúdo da dica não vem antes do desbloqueio"

echo
echo "== 4. sem saldo, a dica é recusada =="
resposta=$(curl -sS -c "$jar" -b "$jar" -X POST "$CTFD_URL/api/v1/unlocks" \
  -H "Content-Type: application/json" -H "CSRF-Token: $token" \
  -d "{\"target\": $dica, \"type\": \"hints\"}")
sucesso=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['success'])" "$resposta")
[[ "$sucesso" == "False" ]] \
  || { echo "FAIL: a competitor with no points unlocked a hint that costs 30"; exit 1; }
echo "PASS: recusada por saldo insuficiente"

echo
echo "== 5. a flag resolve o desafio =="
resposta=$(curl -sS -c "$jar" -b "$jar" -X POST "$CTFD_URL/api/v1/challenges/attempt" \
  -H "Content-Type: application/json" -H "CSRF-Token: $token" \
  -d "{\"challenge_id\": $desafio, \"submission\": \"flag{dica-$stamp}\"}")
estado=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['data']['status'])" "$resposta")
[[ "$estado" == "correct" ]] || { echo "FAIL: the flag did not solve the challenge: $estado"; exit 1; }
echo "PASS: flag aceita, desafio resolvido"

echo
echo "== 6. com saldo, a dica abre e cobra o preço =="
antes=$(curl -sS -c "$jar" -b "$jar" "$CTFD_URL/api/v1/teams/me" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['score'])")
resposta=$(curl -sS -c "$jar" -b "$jar" -X POST "$CTFD_URL/api/v1/unlocks" \
  -H "Content-Type: application/json" -H "CSRF-Token: $token" \
  -d "{\"target\": $dica, \"type\": \"hints\"}")
sucesso=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['success'])" "$resposta")
[[ "$sucesso" == "True" ]] || { echo "FAIL: a competitor with points could not unlock the hint: $resposta"; exit 1; }

conteudo=$(curl -sS -c "$jar" -b "$jar" "$CTFD_URL/api/v1/hints/$dica" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data'].get('content') or '')")
[[ "$conteudo" == "Isto acelera, mas nao e necessario." ]] \
  || { echo "FAIL: the unlocked hint did not return its content: '$conteudo'"; exit 1; }

depois=$(curl -sS -c "$jar" -b "$jar" "$CTFD_URL/api/v1/teams/me" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['score'])")
[[ "$((antes - depois))" == "30" ]] \
  || { echo "FAIL: the hint cost $((antes - depois)) points instead of 30"; exit 1; }
echo "PASS: dica aberta, conteúdo entregue e 30 pontos debitados ($antes -> $depois)"

echo
echo "Jornada do desafio verificada: flag resolve, dica custa e só abre com saldo."
