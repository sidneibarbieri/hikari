#!/usr/bin/env bash
# Full gameplay path: admin creates a challenge with a known flag, a fresh
# player on a fresh team submits the flag, and the resulting solve and
# activity record are confirmed in the database. This is the core path that
# proves the platform is usable for a competition, not just rendering pages.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}

stamp=$(date +%s)
CHALLENGE_NAME="probe_${stamp}"
CHALLENGE_FLAG="hikari{probe_${stamp}}"
PLAYER_NAME="solver_${stamp}"
PLAYER_EMAIL="solver_${stamp}@hikari.local"
PLAYER_PASSWORD="solver-pw-${stamp}"
TEAM_NAME="solo_${stamp}"
TEAM_PASSWORD="solo-pw-${stamp}"

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

admin_jar=$(mktemp)
player_jar=$(mktemp)
trap 'rm -f "$admin_jar" "$player_jar"' EXIT

echo "== admin logs in =="
page=$(mktemp)
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" "$CTFD_URL/login"
nonce=$(extract_nonce_form "$page")
rm -f "$page"
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "admin login returned $code"; exit 1; }

# CSRF token for the JSON API is embedded in window.init on rendered pages.
page=$(mktemp)
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" -L "$CTFD_URL/admin"
admin_csrf=$(extract_csrf_nonce_js "$page")
rm -f "$page"
[[ -n "$admin_csrf" ]] || { echo "could not extract admin CSRF nonce"; exit 1; }
echo "PASS: admin authenticated, CSRF nonce captured"

echo "== admin creates a visible challenge with a known flag =="
created=$(curl -sS -c "$admin_jar" -b "$admin_jar" \
  -H "Content-Type: application/json" \
  -H "Csrf-Token: $admin_csrf" \
  -X POST "$CTFD_URL/api/v1/challenges" \
  -d "{\"name\":\"$CHALLENGE_NAME\",\"category\":\"probe\",\"description\":\"acceptance probe\",\"value\":100,\"type\":\"standard\",\"state\":\"visible\"}")
challenge_id=$(echo "$created" | jq -r '.data.id // empty')
[[ -n "$challenge_id" ]] \
  || { echo "FAIL: challenge create response: $created"; exit 1; }
echo "PASS: challenge created with id $challenge_id"

flag_response=$(curl -sS -c "$admin_jar" -b "$admin_jar" \
  -H "Content-Type: application/json" \
  -H "Csrf-Token: $admin_csrf" \
  -X POST "$CTFD_URL/api/v1/flags" \
  -d "{\"challenge\":$challenge_id,\"type\":\"static\",\"content\":\"$CHALLENGE_FLAG\"}")
flag_id=$(echo "$flag_response" | jq -r '.data.id // empty')
[[ -n "$flag_id" ]] \
  || { echo "FAIL: flag attach response: $flag_response"; exit 1; }
echo "PASS: flag attached with id $flag_id"

echo "== player registers, joins fresh team, submits the flag =="
page=$(mktemp)
curl -sS -c "$player_jar" -b "$player_jar" -o "$page" "$CTFD_URL/register"
nonce=$(extract_nonce_form "$page")
rm -f "$page"
code=$(curl -sS -c "$player_jar" -b "$player_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/register" \
  --data-urlencode "name=$PLAYER_NAME" \
  --data-urlencode "email=$PLAYER_EMAIL" \
  --data-urlencode "password=$PLAYER_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "register returned $code"; exit 1; }

page=$(mktemp)
curl -sS -c "$player_jar" -b "$player_jar" -o "$page" "$CTFD_URL/teams/new"
nonce=$(extract_nonce_form "$page")
rm -f "$page"
code=$(curl -sS -c "$player_jar" -b "$player_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/teams/new" \
  --data-urlencode "name=$TEAM_NAME" \
  --data-urlencode "password=$TEAM_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "team create returned $code"; exit 1; }

page=$(mktemp)
curl -sS -c "$player_jar" -b "$player_jar" -o "$page" -L "$CTFD_URL/challenges"
player_csrf=$(extract_csrf_nonce_js "$page")
rm -f "$page"
[[ -n "$player_csrf" ]] || { echo "no player CSRF nonce"; exit 1; }

view_response=$(curl -sS -c "$player_jar" -b "$player_jar" \
  "$CTFD_URL/api/v1/challenges/$challenge_id")
view_success=$(echo "$view_response" | jq -r '.success')
[[ "$view_success" == "true" ]] \
  || { echo "FAIL: challenge view response: $view_response"; exit 1; }
echo "PASS: challenge detail viewed through player API"

for wrong_flag in "wrong-${stamp}-1" "wrong-${stamp}-2"; do
  attempt=$(curl -sS -c "$player_jar" -b "$player_jar" \
    -H "Content-Type: application/json" \
    -H "Csrf-Token: $player_csrf" \
    -X POST "$CTFD_URL/api/v1/challenges/attempt" \
    -d "{\"challenge_id\":$challenge_id,\"submission\":\"$wrong_flag\"}")
  status=$(echo "$attempt" | jq -r '.data.status')
  [[ "$status" == "incorrect" ]] \
    || { echo "FAIL: wrong submit status=$status body=$attempt"; exit 1; }
done
echo "PASS: two incorrect submissions rejected"

attempt=$(curl -sS -c "$player_jar" -b "$player_jar" \
  -H "Content-Type: application/json" \
  -H "Csrf-Token: $player_csrf" \
  -X POST "$CTFD_URL/api/v1/challenges/attempt" \
  -d "{\"challenge_id\":$challenge_id,\"submission\":\"$CHALLENGE_FLAG\"}")
status=$(echo "$attempt" | jq -r '.data.status')
[[ "$status" == "correct" ]] \
  || { echo "FAIL: submit status=$status body=$attempt"; exit 1; }
echo "PASS: player submission accepted (status=correct)"

echo "== assert solve persisted in DB =="
player_id=$(db_query "SELECT id FROM users WHERE email='$PLAYER_EMAIL';" | tr -d '[:space:]')
solves=$(db_query "SELECT COUNT(*) FROM solves WHERE challenge_id=$challenge_id AND user_id=$player_id;" | tr -d '[:space:]')
[[ "$solves" == "1" ]] \
  || { echo "FAIL: expected 1 solve, found $solves"; exit 1; }
echo "PASS: 1 solve row recorded for player_id=$player_id challenge_id=$challenge_id"

echo "== assert challenge.attempt captured in activity log =="
sleep 2
attempts=$(db_query "SELECT COUNT(*) FROM hikari_activity WHERE event_type='challenge.attempt' AND actor_id=$player_id AND target_id=$challenge_id;" | tr -d '[:space:]')
[[ "$attempts" -ge 3 ]] \
  || { echo "FAIL: no challenge.attempt activity recorded ($attempts)"; exit 1; }
echo "PASS: $attempts challenge.attempt event(s) captured for player on challenge $challenge_id"

views=$(db_query "SELECT COUNT(*) FROM hikari_activity WHERE event_type='challenge.view' AND actor_id=$player_id AND target_id=$challenge_id;" | tr -d '[:space:]')
[[ "$views" -ge 1 ]] \
  || { echo "FAIL: no challenge.view activity recorded ($views)"; exit 1; }
echo "PASS: challenge.view event captured for player on challenge $challenge_id"

incorrect_attempts=$(db_query "SELECT COUNT(*) FROM hikari_activity WHERE event_type='challenge.attempt' AND actor_id=$player_id AND target_id=$challenge_id AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.attempt.result'))='incorrect';" | tr -d '[:space:]')
[[ "$incorrect_attempts" -ge 2 ]] \
  || { echo "FAIL: expected 2 incorrect attempt payloads, found $incorrect_attempts"; exit 1; }
echo "PASS: incorrect flag attempts are classified for brute-force analysis"

correct_attempts=$(db_query "SELECT COUNT(*) FROM hikari_activity WHERE event_type='challenge.attempt' AND actor_id=$player_id AND target_id=$challenge_id AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.attempt.result'))='correct';" | tr -d '[:space:]')
[[ "$correct_attempts" -ge 1 ]] \
  || { echo "FAIL: expected 1 correct attempt payload, found $correct_attempts"; exit 1; }
echo "PASS: correct flag attempt is classified"

raw_submission_leaks=$(db_query "SELECT COUNT(*) FROM hikari_activity WHERE event_type='challenge.attempt' AND actor_id=$player_id AND target_id=$challenge_id AND JSON_EXTRACT(payload, '$.attempt.submission') IS NOT NULL;" | tr -d '[:space:]')
[[ "$raw_submission_leaks" == "0" ]] \
  || { echo "FAIL: raw flag submissions leaked into activity payload"; exit 1; }
echo "PASS: raw flag submissions are not stored"

echo "== assert challenge attempts reached Elasticsearch activity index =="
deadline=$((SECONDS + 30))
es_attempts=0
while (( SECONDS < deadline )); do
  es_response=$(docker-compose -f "$COMPOSE_FILE" exec -T elasticsearch \
    curl -sS "http://localhost:9200/hikari-activity/_search" \
      -H "Content-Type: application/json" \
      -d "$(jq -cn \
        --argjson actor_id "$player_id" \
        --argjson target_id "$challenge_id" \
        '{size:20,query:{bool:{filter:[
          {term:{"event_type.keyword":"challenge.attempt"}},
          {term:{actor_id:$actor_id}},
          {term:{target_id:$target_id}}
        ]}}}')")
  es_attempts=$(echo "$es_response" | jq -r '.hits.total.value // 0')
  if [[ "$es_attempts" -ge 3 ]]; then
    break
  fi
  sleep 2
done
[[ "$es_attempts" -ge 3 ]] \
  || { echo "FAIL: expected challenge.attempt documents in Elasticsearch, found $es_attempts"; exit 1; }
echo "PASS: $es_attempts challenge.attempt document(s) reached Elasticsearch"

echo
echo "Challenge submission flow verified."
echo "  challenge=$CHALLENGE_NAME (id $challenge_id)"
echo "  flag=$CHALLENGE_FLAG"
echo "  solver=$PLAYER_EMAIL (id $player_id)"
