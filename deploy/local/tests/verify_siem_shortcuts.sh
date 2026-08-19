#!/usr/bin/env bash
# Proves every shortcut on the SIEM page finds something.
#
# A shortcut that returns nothing reads as a broken platform to the competitor
# who clicks it in the first minute. Four of the six once queried fields that
# this deployment never had — response, request, user_agent — and a fifth
# opened a fifteen-minute window over logs that are months old.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

page=$(mktemp)
trap 'rm -f "$page"' EXIT

curl -sS -o "$page" "$CTFD_URL/plugins/hikari_plugin/../../hikari/siem" 2>/dev/null || true
# The page needs a session, so the template is read from the container instead.
hikari_compose exec -T ctfd cat \
  /opt/CTFd/CTFd/plugins/hikari_plugin/templates/hikari-siem.html > "$page"

# mapfile arrived in bash 4 and this runs on hosts that still ship bash 3.
consultas=()
while IFS= read -r linha; do
  consultas+=("$linha")
done < <(grep -oE "query:'[^']+'" "$page" | sed "s/^query:'//;s/'$//")
[[ "${#consultas[@]}" -gt 0 ]] || { echo "FAIL: the SIEM page offers no shortcuts"; exit 1; }

janelas=$(grep -c "from:now-" "$page" || true)
[[ "$janelas" -ge "${#consultas[@]}" ]] \
  || { echo "FAIL: only $janelas of ${#consultas[@]} shortcuts carry a time window"; exit 1; }

if grep -qE "from:now-1?[0-9]?[mh]," "$page"; then
  echo "FAIL: a shortcut opens a window shorter than the age of the logs"
  exit 1
fi
echo "PASS: ${#consultas[@]} atalhos, todos com período que cobre os registros"

vazios=0
for codificada in "${consultas[@]}"; do
  consulta=$(python3 -c "import sys,urllib.parse; print(urllib.parse.unquote(sys.argv[1]))" "$codificada")
  total=$(python3 -c "import json,sys; print(json.dumps({'query':{'query_string':{'query':sys.argv[1]}}}))" "$consulta" \
    | hikari_compose exec -T elasticsearch curl -sS -H 'Content-Type: application/json' \
        "http://localhost:9200/competition1/_count" --data-binary @- \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('count', 0))")
  if [[ "$total" == "0" ]]; then
    echo "  vazio: $consulta"
    vazios=$((vazios + 1))
  fi
done
[[ "$vazios" == "0" ]] || { echo "FAIL: $vazios atalho(s) não encontram nenhum evento"; exit 1; }
echo "PASS: todo atalho encontra eventos no índice"

echo
echo "Atalhos do SIEM verificados."
