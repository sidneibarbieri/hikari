#!/usr/bin/env bash
# A exportação em massa fecha para quem compete e continua aberta para quem
# organiza, sem afetar a investigação no Discover.
set -euo pipefail

BASE=${BASE:-http://localhost:8000}
SENHA=${SENHA:-revisao_local_2026}
JOGADOR=${JOGADOR:?informe JOGADOR}
ADMIN=${ADMIN:-admin}

entrar() {
  local nome="$1" pote="$2" pagina
  pagina=$(mktemp)
  curl -s -c "$pote" -b "$pote" -o "$pagina" "$BASE/login"
  local nonce
  nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' "$pagina" | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
  curl -s -c "$pote" -b "$pote" -o /dev/null -X POST "$BASE/login" \
    --data-urlencode "name=$nome" --data-urlencode "password=$SENHA" --data-urlencode "nonce=$nonce"
  rm -f "$pagina"
}

codigo() {
  local pote="$1" rota="$2"
  curl -s -c "$pote" -b "$pote" -o /dev/null -w '%{http_code}' \
    -X POST "$BASE/hikari/kibana/$rota" -H 'kbn-xsrf: true' -H 'Content-Type: application/json' -d '{}'
}

conferir() {
  local rotulo="$1" obtido="$2" esperado="$3"
  if [ "$obtido" = "$esperado" ]; then
    echo "PASS: $rotulo (HTTP $obtido)"
  else
    echo "FAIL: $rotulo esperava $esperado e recebeu $obtido"
    exit 1
  fi
}

pote_jogador=$(mktemp); pote_admin=$(mktemp)
entrar "$JOGADOR" "$pote_jogador"
entrar "$ADMIN" "$pote_admin"

echo "== o competidor não leva os logs embora =="
conferir "relatório CSV bloqueado"          "$(codigo "$pote_jogador" 'api/reporting/generate/csv_searchsource')" 403
conferir "relatório interno bloqueado"      "$(codigo "$pote_jogador" 'internal/reporting/generate/csv_searchsource')" 403
conferir "exportação de objetos bloqueada"  "$(codigo "$pote_jogador" 'api/saved_objects/_export')" 403
conferir "console de dev bloqueado"         "$(codigo "$pote_jogador" 'api/console/proxy?path=competition1/_search&method=POST')" 403

echo "== a investigação continua de pé =="
busca=$(curl -s -c "$pote_jogador" -b "$pote_jogador" -o /dev/null -w '%{http_code}' \
  -X POST "$BASE/hikari/kibana/internal/bsearch" -H 'kbn-xsrf: true' -H 'Content-Type: application/json' -d '{}')
if [ "$busca" = "403" ]; then echo "FAIL: a busca do Discover foi bloqueada junto"; exit 1; fi
echo "PASS: a busca do Discover segue passando (HTTP $busca)"

echo "== quem organiza mantém a exportação =="
admin_csv=$(codigo "$pote_admin" 'api/reporting/generate/csv_searchsource')
if [ "$admin_csv" = "403" ]; then echo "FAIL: administrador também foi bloqueado"; exit 1; fi
echo "PASS: administrador não é bloqueado (HTTP $admin_csv)"

echo "== a tentativa fica registrada =="
rm -f "$pote_jogador" "$pote_admin"
echo "Bloqueio de exportação verificado."
