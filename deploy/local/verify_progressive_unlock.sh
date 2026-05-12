#!/usr/bin/env bash
# Exercises the anti-hoarding mechanic that defines Hikari competitively:
# when a hikari challenge is solved, the solve hook activates the log file
# of any challenge whose prerequisites are now satisfied, pushing the new
# log batch into Kafka -> Elasticsearch.
#
# Two hikari challenges, C1 and C2, are created with distinct marker strings
# inside their log JSON. C2 depends on C1. The script then asserts:
#   1. After init_competition: C1's marker is in Elasticsearch, C2's is not.
#   2. After a player solves C1: C2's marker also appears in Elasticsearch.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ES_INDEX=${ES_INDEX:-competition1}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari-admin-pw}
COMPOSE_FILE=${COMPOSE_FILE:-$(cd "$(dirname "$0")" && pwd)/docker-compose.yml}

stamp=$(date +%s)
C1_NAME="prog_c1_${stamp}"
C1_FLAG="hikari{prog_c1_${stamp}}"
C1_MARKER="prog_c1_marker_${stamp}"
C2_NAME="prog_c2_${stamp}"
C2_FLAG="hikari{prog_c2_${stamp}}"
C2_MARKER="prog_c2_marker_${stamp}"

PLAYER_NAME="prog_player_${stamp}"
PLAYER_EMAIL="prog_player_${stamp}@hikari.local"
PLAYER_PASSWORD="prog-pw-${stamp}"
TEAM_NAME="prog_team_${stamp}"
TEAM_PASSWORD="prog-team-pw-${stamp}"

logs_dir=$(mktemp -d)
trap 'rm -rf "$logs_dir" /tmp/hikari-prog-*' EXIT

c1_log="$logs_dir/${C1_NAME}.json"
c2_log="$logs_dir/${C2_NAME}.json"
printf '[{"event":"alert","marker":"%s","ts":"2026-01-01T00:00:00Z"}]\n' "$C1_MARKER" > "$c1_log"
printf '[{"event":"alert","marker":"%s","ts":"2026-01-02T00:00:00Z"}]\n' "$C2_MARKER" > "$c2_log"

extract_nonce_form() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

extract_csrf_nonce_js() {
  grep -oE "'csrfNonce':[[:space:]]*\"[^\"]+\"" "$1" \
    | head -1 | sed -E 's/.*"([^"]+)".*/\1/'
}

db_query() {
  docker-compose -f "$COMPOSE_FILE" exec -T db \
    mariadb -uctfd -pctfd ctfd -N -B -e "$1"
}

es_marker_hits() {
  local marker=$1
  local query
  query=$(jq -cn --arg m "$marker" \
    '{query:{match_phrase:{marker:$m}}}')
  docker-compose -f "$COMPOSE_FILE" exec -T elasticsearch \
    curl -sS -H 'Content-Type: application/json' \
    -X POST "http://localhost:9200/$ES_INDEX/_search" -d "$query" \
    | jq -r '.hits.total.value // 0'
}

wait_for_marker() {
  local marker=$1 deadline=$((SECONDS + 30)) hits
  while (( SECONDS < deadline )); do
    hits=$(es_marker_hits "$marker")
    if [[ "$hits" -ge 1 ]]; then
      echo "$hits"
      return 0
    fi
    sleep 2
  done
  echo "0"
  return 1
}

admin_jar=$(mktemp)
player_jar=$(mktemp)
trap 'rm -rf "$logs_dir" "$admin_jar" "$player_jar" /tmp/hikari-prog-*' EXIT

echo "== admin logs in =="
page=/tmp/hikari-prog-login.html
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" "$CTFD_URL/login"
nonce=$(extract_nonce_form "$page")
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "admin login returned $code"; exit 1; }

page=/tmp/hikari-prog-admin.html
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" -L "$CTFD_URL/admin"
admin_csrf=$(extract_csrf_nonce_js "$page")
echo "PASS: admin authenticated"

echo "== create C1 hikari challenge with log file =="
curl -sS -c "$admin_jar" -b "$admin_jar" \
  -o /tmp/hikari-prog-c1.html -w 'add-challenge C1: %{http_code}\n' \
  -X POST "$CTFD_URL/admin/hikari/add-challenge" \
  -F "name=$C1_NAME" \
  -F "category=probe" \
  -F "description=progressive C1" \
  -F "value=100" \
  -F "type=hikari" \
  -F "nonce=$admin_csrf" \
  -F "file_log=@$c1_log"

c1_id=$(db_query "SELECT id FROM challenges WHERE name='$C1_NAME';" | tr -d '[:space:]')
[[ -n "$c1_id" ]] || { echo "FAIL: C1 not in DB"; cat /tmp/hikari-prog-c1.html; exit 1; }
echo "PASS: C1 created (id $c1_id, log='$(basename $c1_log)')"

echo "== create C2 hikari challenge with log file =="
curl -sS -c "$admin_jar" -b "$admin_jar" \
  -o /tmp/hikari-prog-c2.html -w 'add-challenge C2: %{http_code}\n' \
  -X POST "$CTFD_URL/admin/hikari/add-challenge" \
  -F "name=$C2_NAME" \
  -F "category=probe" \
  -F "description=progressive C2" \
  -F "value=100" \
  -F "type=hikari" \
  -F "nonce=$admin_csrf" \
  -F "file_log=@$c2_log"

c2_id=$(db_query "SELECT id FROM challenges WHERE name='$C2_NAME';" | tr -d '[:space:]')
[[ -n "$c2_id" ]] || { echo "FAIL: C2 not in DB"; cat /tmp/hikari-prog-c2.html; exit 1; }
echo "PASS: C2 created (id $c2_id, log='$(basename $c2_log)')"

echo "== flag for C1, prerequisites for C2 (C2 requires C1), make both visible =="
curl -sS -c "$admin_jar" -b "$admin_jar" \
  -H "Content-Type: application/json" -H "Csrf-Token: $admin_csrf" \
  -X POST "$CTFD_URL/api/v1/flags" \
  -d "{\"challenge\":$c1_id,\"type\":\"static\",\"content\":\"$C1_FLAG\"}" >/dev/null

curl -sS -c "$admin_jar" -b "$admin_jar" \
  -H "Content-Type: application/json" -H "Csrf-Token: $admin_csrf" \
  -X PATCH "$CTFD_URL/api/v1/challenges/$c1_id" \
  -d '{"state":"visible"}' >/dev/null

curl -sS -c "$admin_jar" -b "$admin_jar" \
  -H "Content-Type: application/json" -H "Csrf-Token: $admin_csrf" \
  -X PATCH "$CTFD_URL/api/v1/challenges/$c2_id" \
  -d "{\"state\":\"visible\",\"requirements\":{\"prerequisites\":[$c1_id]}}" >/dev/null

actual=$(db_query "SELECT requirements FROM challenges WHERE id=$c2_id;")
echo "PASS: C2 prerequisites = $actual"

echo "== start competition: C1's log should activate =="
curl -sSL -c "$admin_jar" -b "$admin_jar" \
  -o /dev/null -w 'init_competition: %{http_code}\n' \
  "$CTFD_URL/admin/hikari/init-competition"

c1_hits=$(wait_for_marker "$C1_MARKER") || c1_hits=0
[[ "$c1_hits" -ge 1 ]] \
  || { echo "FAIL: C1 marker not in ES after init_competition"; exit 1; }
echo "PASS: C1 log indexed in ES (marker=$C1_MARKER, hits=$c1_hits)"

c2_pre_hits=$(es_marker_hits "$C2_MARKER")
[[ "$c2_pre_hits" == "0" ]] \
  || { echo "FAIL: C2 marker already in ES before solve ($c2_pre_hits)"; exit 1; }
echo "PASS: C2 log NOT yet in ES (anti-hoarding correctly holding back)"

echo "== player registers, joins fresh team, solves C1 =="
page=/tmp/hikari-prog-reg.html
curl -sS -c "$player_jar" -b "$player_jar" -o "$page" "$CTFD_URL/register"
nonce=$(extract_nonce_form "$page")
curl -sS -c "$player_jar" -b "$player_jar" -o /dev/null \
  -X POST "$CTFD_URL/register" \
  --data-urlencode "name=$PLAYER_NAME" \
  --data-urlencode "email=$PLAYER_EMAIL" \
  --data-urlencode "password=$PLAYER_PASSWORD" \
  --data-urlencode "nonce=$nonce"

page=/tmp/hikari-prog-team.html
curl -sS -c "$player_jar" -b "$player_jar" -o "$page" "$CTFD_URL/teams/new"
nonce=$(extract_nonce_form "$page")
curl -sS -c "$player_jar" -b "$player_jar" -o /dev/null \
  -X POST "$CTFD_URL/teams/new" \
  --data-urlencode "name=$TEAM_NAME" \
  --data-urlencode "password=$TEAM_PASSWORD" \
  --data-urlencode "nonce=$nonce"

page=/tmp/hikari-prog-chals.html
curl -sS -c "$player_jar" -b "$player_jar" -o "$page" -L "$CTFD_URL/challenges"
player_csrf=$(extract_csrf_nonce_js "$page")

attempt=$(curl -sS -c "$player_jar" -b "$player_jar" \
  -H "Content-Type: application/json" -H "Csrf-Token: $player_csrf" \
  -X POST "$CTFD_URL/api/v1/challenges/attempt" \
  -d "{\"challenge_id\":$c1_id,\"submission\":\"$C1_FLAG\"}")
status=$(echo "$attempt" | jq -r '.data.status')
[[ "$status" == "correct" ]] \
  || { echo "FAIL: C1 submission status=$status body=$attempt"; exit 1; }
echo "PASS: player solved C1"

echo "== C2's log should now be activated by the solve hook =="
c2_hits=$(wait_for_marker "$C2_MARKER") || c2_hits=0
[[ "$c2_hits" -ge 1 ]] \
  || { echo "FAIL: C2 marker not in ES 30s after solve"; exit 1; }
echo "PASS: C2 log indexed in ES (marker=$C2_MARKER, hits=$c2_hits)"

echo "== confirm logs_activated flags in the database =="
c1_active=$(db_query "SELECT logs_activated FROM hikari_challenges WHERE id=$c1_id;" | tr -d '[:space:]')
c2_active=$(db_query "SELECT logs_activated FROM hikari_challenges WHERE id=$c2_id;" | tr -d '[:space:]')
[[ "$c1_active" == "1" && "$c2_active" == "1" ]] \
  || { echo "FAIL: logs_activated mismatch C1=$c1_active C2=$c2_active"; exit 1; }
echo "PASS: logs_activated=true for both C1 and C2"

echo
echo "Progressive challenge unlock verified."
echo "  C1=$C1_NAME (id $c1_id)  C2=$C2_NAME (id $c2_id) requires C1"
echo "  C1 marker hits in ES: $c1_hits"
echo "  C2 marker hits in ES: $c2_hits"
