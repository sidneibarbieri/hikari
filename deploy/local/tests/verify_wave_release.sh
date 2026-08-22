#!/usr/bin/env bash
# Prova as duas garantias da mecânica de ondas que o teste de destravamento não
# alcança, porque lá um único jogador resolve toda a cadeia sozinho.
#
# 1. A onda cai quando a EQUIPE cumpre os pré-requisitos. Numa cadeia linear
#    isso não se distingue de contar por pessoa, porque quem submete acabou de
#    resolver o único portão. A diferença aparece quando a onda depende de DOIS
#    portões e cada membro resolve um: contar por pessoa faz a interseção nunca
#    fechar, e a onda some sem erro nenhum, com o desafio aberto na tela e sem
#    dados no SIEM.
# 2. A onda cai UMA VEZ mesmo sob disputa. Duas equipes que acertam o mesmo
#    portão no mesmo instante leem o campo antes de qualquer uma gravá-lo, e
#    injetam a mesma onda duas vezes. Contagem duplicada torna errada toda
#    resposta baseada em volume, sem nada acusar.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ES_INDEX=${ES_INDEX:-competition1}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

stamp=$(date +%s)
logs_dir=$(mktemp -d)
admin_jar=$(mktemp)
jar_a=$(mktemp)
jar_b=$(mktemp)
page=$(mktemp)
declare -a jar_corrida=() pagina_corrida=()
trap 'rm -rf "$logs_dir" "$admin_jar" "$jar_a" "$jar_b" "$page" ${jar_corrida[@]+"${jar_corrida[@]}"} ${pagina_corrida[@]+"${pagina_corrida[@]}"}' EXIT

abrir_janela_de_submissao() {
  # Outros testes encerram a execução que criam. Sem uma janela aberta toda
  # submissão volta recusada, e o teste reprovaria por um motivo que nada tem
  # a ver com a mecânica de ondas.
  hikari_compose exec -T ctfd python - <<'PYCONF'
from time import time

from CTFd import create_app
from CTFd.utils import set_config

app = create_app()
with app.app_context():
    inicio = int(time())
    set_config("start", inicio)
    set_config("end", inicio + 3600)
    set_config("paused", False)
PYCONF
}

nonce_do_formulario() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

nonce_do_javascript() {
  grep -oE "'csrfNonce':[[:space:]]*\"[^\"]+\"" "$1" | head -1 | sed -E 's/.*"([^"]+)".*/\1/'
}

consultar_banco() {
  hikari_compose exec -T db \
    mariadb -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" -N -B -e "$1"
}

marcas_no_indice() {
  hikari_compose exec -T elasticsearch curl -sS -H 'Content-Type: application/json' \
    -X POST "http://localhost:9200/$ES_INDEX/_search" \
    -d "$(jq -cn --arg m "$1" '{track_total_hits:true,query:{match_phrase:{marker:$m}}}')" \
    | jq -r '.hits.total.value // 0'
}

esperar_marca() {
  local marca=$1 esperado=$2 limite=$((SECONDS + 40)) obtidas
  while (( SECONDS < limite )); do
    obtidas=$(marcas_no_indice "$marca")
    [[ "$obtidas" -ge "$esperado" ]] && { echo "$obtidas"; return 0; }
    sleep 2
  done
  echo "$(marcas_no_indice "$marca")"
  return 1
}

criar_desafio() {
  local nome=$1 marca=$2
  printf '[{"event":"alert","marker":"%s","ts":"2026-01-01T00:00:00Z"}]\n' "$marca" \
    > "$logs_dir/$nome.json"
  curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null \
    -X POST "$CTFD_URL/admin/hikari/add-challenge" \
    -F "name=$nome" -F "category=probe" -F "description=onda" -F "value=100" \
    -F "type=hikari" -F "nonce=$admin_csrf" -F "file_log=@$logs_dir/$nome.json"
  consultar_banco "SELECT id FROM challenges WHERE name='$nome';" | tr -d '[:space:]'
}

registrar_jogador() {
  local jar=$1 nome=$2
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/register"
  curl -sS -c "$jar" -b "$jar" -o /dev/null -X POST "$CTFD_URL/register" \
    --data-urlencode "name=$nome" --data-urlencode "email=$nome@hikari.local" \
    --data-urlencode "password=senha-$stamp" \
    --data-urlencode "nonce=$(nonce_do_formulario "$page")"
}

submeter() {
  local jar=$1 desafio=$2 flag=$3
  curl -sS -c "$jar" -b "$jar" -o "$page" -L "$CTFD_URL/challenges"
  curl -sS -c "$jar" -b "$jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $(nonce_do_javascript "$page")" \
    -X POST "$CTFD_URL/api/v1/challenges/attempt" \
    -d "{\"challenge_id\":$desafio,\"submission\":\"$flag\"}" | jq -r '.data.status'
}

abrir_janela_de_submissao

curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" "$CTFD_URL/login"
curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$(nonce_do_formulario "$page")"
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" -L "$CTFD_URL/admin"
admin_csrf=$(nonce_do_javascript "$page")

base_id=$(criar_desafio "onda_base_$stamp" "onda_base_marca_$stamp")
meio_id=$(criar_desafio "onda_meio_$stamp" "onda_meio_marca_$stamp")
topo_id=$(criar_desafio "onda_topo_$stamp" "onda_topo_marca_$stamp")
[[ -n "$base_id" && -n "$meio_id" && -n "$topo_id" ]] \
  || { echo "FAIL: desafios da cadeia não foram criados"; exit 1; }

for par in "$base_id:onda_base" "$meio_id:onda_meio"; do
  curl -sS -c "$admin_jar" -b "$admin_jar" -H "Content-Type: application/json" \
    -H "Csrf-Token: $admin_csrf" -X POST "$CTFD_URL/api/v1/flags" \
    -d "{\"challenge\":${par%%:*},\"type\":\"static\",\"content\":\"flag{${par##*:}_$stamp}\"}" >/dev/null
done

curl -sS -c "$admin_jar" -b "$admin_jar" -H "Content-Type: application/json" \
  -H "Csrf-Token: $admin_csrf" -X PATCH "$CTFD_URL/api/v1/challenges/$base_id" \
  -d '{"state":"visible"}' >/dev/null
curl -sS -c "$admin_jar" -b "$admin_jar" -H "Content-Type: application/json" \
  -H "Csrf-Token: $admin_csrf" -X PATCH "$CTFD_URL/api/v1/challenges/$meio_id" \
  -d "{\"state\":\"visible\",\"requirements\":{\"prerequisites\":[$base_id]}}" >/dev/null
curl -sS -c "$admin_jar" -b "$admin_jar" -H "Content-Type: application/json" \
  -H "Csrf-Token: $admin_csrf" -X PATCH "$CTFD_URL/api/v1/challenges/$topo_id" \
  -d "{\"state\":\"visible\",\"requirements\":{\"prerequisites\":[$base_id,$meio_id]}}" >/dev/null

echo "== 1. o cenário base cai no início e as ondas seguintes ficam retidas =="
curl -sSL -c "$admin_jar" -b "$admin_jar" -o /dev/null "$CTFD_URL/admin/hikari/init-competition"
esperar_marca "onda_base_marca_$stamp" 1 >/dev/null \
  || { echo "FAIL: o cenário base não chegou ao índice"; exit 1; }
[[ "$(marcas_no_indice "onda_meio_marca_$stamp")" == "0" ]] \
  || { echo "FAIL: a onda seguinte já estava no índice antes do portão cair"; exit 1; }
echo "PASS: só a onda inicial está no índice"

echo
echo "== 2. a equipe cumpre os portões com o trabalho dividido =="
registrar_jogador "$jar_a" "onda_a_$stamp"
registrar_jogador "$jar_b" "onda_b_$stamp"

curl -sS -c "$jar_a" -b "$jar_a" -o "$page" "$CTFD_URL/teams/new"
curl -sS -c "$jar_a" -b "$jar_a" -o /dev/null -X POST "$CTFD_URL/teams/new" \
  --data-urlencode "name=onda_equipe_$stamp" --data-urlencode "password=equipe-$stamp" \
  --data-urlencode "nonce=$(nonce_do_formulario "$page")"
# Entrar numa equipe no Hikari é pedido e aprovação do capitão, não senha
# compartilhada. O teste percorre esse caminho porque é o que o competidor faz.
equipe_id=$(consultar_banco "SELECT id FROM teams WHERE name='onda_equipe_$stamp';" | tr -d '[:space:]')
[[ -n "$equipe_id" ]] || { echo "FAIL: a equipe não foi criada"; exit 1; }

curl -sSL -c "$jar_b" -b "$jar_b" -o "$page" "$CTFD_URL/hikari/teams/join"
curl -sSL -c "$jar_b" -b "$jar_b" -o /dev/null \
  -X POST "$CTFD_URL/hikari/teams/$equipe_id/request" \
  --data-urlencode "nonce=$(nonce_do_formulario "$page")"

pedido_id=$(consultar_banco \
  "SELECT r.id FROM hikari_team_membership_requests r JOIN users u ON u.id = r.user_id
     WHERE u.name = 'onda_b_$stamp' AND r.status = 'pending';" | tr -d '[:space:]')
[[ -n "$pedido_id" ]] || { echo "FAIL: o pedido de entrada na equipe não foi registrado"; exit 1; }

curl -sSL -c "$jar_a" -b "$jar_a" -o "$page" "$CTFD_URL/hikari/team/requests"
curl -sSL -c "$jar_a" -b "$jar_a" -o /dev/null \
  -X POST "$CTFD_URL/hikari/team/requests/$pedido_id/approve" \
  --data-urlencode "nonce=$(nonce_do_formulario "$page")"

membros=$(consultar_banco \
  "SELECT COUNT(*) FROM users WHERE team_id = $equipe_id;" | tr -d '[:space:]')
[[ "$membros" == "2" ]] \
  || { echo "FAIL: a equipe tem $membros integrante(s); o segundo não entrou"; exit 1; }
echo "PASS: dois integrantes na mesma equipe"

[[ "$(submeter "$jar_a" "$base_id" "flag{onda_base_$stamp}")" == "correct" ]] \
  || { echo "FAIL: o primeiro membro não conseguiu resolver o desafio base"; exit 1; }
esperar_marca "onda_meio_marca_$stamp" 1 >/dev/null \
  || { echo "FAIL: a segunda onda não caiu após o portão"; exit 1; }
echo "PASS: o acerto do primeiro membro liberou a segunda onda"

# Aqui está a divisão de trabalho. A terceira onda depende dos DOIS portões, e
# quem fecha o segundo é o OUTRO membro, que nunca resolveu o primeiro. Contada
# por pessoa, a interseção nunca fecha e a onda não cai. Contada por equipe, cai.
[[ "$(submeter "$jar_b" "$meio_id" "flag{onda_meio_$stamp}")" == "correct" ]] \
  || { echo "FAIL: o segundo membro não conseguiu resolver o desafio do meio"; exit 1; }
esperar_marca "onda_topo_marca_$stamp" 1 >/dev/null \
  || { echo "FAIL: a terceira onda não caiu; a cadeia trava quando a equipe divide o trabalho"; exit 1; }
echo "PASS: a cadeia avança com membros diferentes resolvendo cada portão"

echo
echo "== 3. duas equipes acertando o mesmo portão liberam a onda uma só vez =="
# Cada acerto dispara a liberação por conta própria. Com equipes suficientes,
# dois acertos caem na mesma janela e ambos encontram a onda ainda fechada.
corrida_id=$(criar_desafio "onda_corrida_$stamp" "onda_corrida_marca_$stamp")
portao_id=$(criar_desafio "onda_portao_$stamp" "onda_portao_marca_$stamp")
curl -sS -c "$admin_jar" -b "$admin_jar" -H "Content-Type: application/json" \
  -H "Csrf-Token: $admin_csrf" -X POST "$CTFD_URL/api/v1/flags" \
  -d "{\"challenge\":$portao_id,\"type\":\"static\",\"content\":\"flag{onda_portao_$stamp}\"}" >/dev/null
curl -sS -c "$admin_jar" -b "$admin_jar" -H "Content-Type: application/json" \
  -H "Csrf-Token: $admin_csrf" -X PATCH "$CTFD_URL/api/v1/challenges/$portao_id" \
  -d '{"state":"visible"}' >/dev/null
curl -sS -c "$admin_jar" -b "$admin_jar" -H "Content-Type: application/json" \
  -H "Csrf-Token: $admin_csrf" -X PATCH "$CTFD_URL/api/v1/challenges/$corrida_id" \
  -d "{\"state\":\"visible\",\"requirements\":{\"prerequisites\":[$portao_id]}}" >/dev/null

for indice in 1 2 3 4; do
  jar_corrida[$indice]=$(mktemp)
  pagina_corrida[$indice]=$(mktemp)
  registrar_jogador "${jar_corrida[$indice]}" "onda_c${indice}_$stamp"
  curl -sS -c "${jar_corrida[$indice]}" -b "${jar_corrida[$indice]}" \
    -o "${pagina_corrida[$indice]}" "$CTFD_URL/teams/new"
  curl -sS -c "${jar_corrida[$indice]}" -b "${jar_corrida[$indice]}" -o /dev/null \
    -X POST "$CTFD_URL/teams/new" \
    --data-urlencode "name=onda_equipe_c${indice}_$stamp" \
    --data-urlencode "password=equipe-$stamp" \
    --data-urlencode "nonce=$(nonce_do_formulario "${pagina_corrida[$indice]}")"
  # A página de desafios é buscada antes da largada para que as submissões
  # partam juntas, e não escalonadas pelo tempo de carregar cada página.
  curl -sS -c "${jar_corrida[$indice]}" -b "${jar_corrida[$indice]}" \
    -o "${pagina_corrida[$indice]}" -L "$CTFD_URL/challenges"
done

for indice in 1 2 3 4; do
  curl -sS -c "${jar_corrida[$indice]}" -b "${jar_corrida[$indice]}" -o /dev/null \
    -H "Content-Type: application/json" \
    -H "Csrf-Token: $(nonce_do_javascript "${pagina_corrida[$indice]}")" \
    -X POST "$CTFD_URL/api/v1/challenges/attempt" \
    -d "{\"challenge_id\":$portao_id,\"submission\":\"flag{onda_portao_$stamp}\"}" &
done
wait

esperar_marca "onda_corrida_marca_$stamp" 1 >/dev/null \
  || { echo "FAIL: a onda disputada não caiu"; exit 1; }
sleep 10
injecoes=$(marcas_no_indice "onda_corrida_marca_$stamp")
[[ "$injecoes" == "1" ]] \
  || { echo "FAIL: a onda disputada aparece $injecoes vezes; foi injetada mais de uma vez"; exit 1; }
echo "PASS: a onda disputada tem um único evento no índice"

echo
echo "Liberação de ondas verificada."
