#!/usr/bin/env bash
# Reproduces a competitor flow against a live CTFd instance:
#   register a fresh user -> login -> create a team -> list challenges.
# Then queries the activity log to assert that the actions were captured
# with the correct actor_id, proving the listener observes traffic from
# non-admin users, not just the admin we used to bootstrap.
#
# Exits non-zero on the first failed assertion with a one-line reason.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
COMPOSE_FILE=${COMPOSE_FILE:-$(cd "$(dirname "$0")" && pwd)/docker-compose.yml}

stamp=$(date +%s)
PLAYER_NAME="player_${stamp}"
PLAYER_EMAIL="player_${stamp}@hikari.local"
PLAYER_PASSWORD="player-pw-${stamp}"
TEAM_NAME="team_${stamp}"
TEAM_PASSWORD="teampw-${stamp}"

cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar" /tmp/hikari-page-*.html' EXIT

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

assert_status() {
  local expected=$1 actual=$2 label=$3
  if [[ "$actual" != "$expected" ]]; then
    echo "FAIL: $label expected $expected, got $actual" >&2
    exit 1
  fi
  echo "PASS: $label ($actual)"
}

db_count() {
  local query=$1
  local result
  result=$(docker-compose -f "$COMPOSE_FILE" exec -T db \
    mariadb -uctfd -pctfd ctfd -N -B -e "$query")
  echo "${result//[[:space:]]/}"
}

echo "== Step 1: register fresh user =="
page=/tmp/hikari-page-register.html
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" "$CTFD_URL/register"
nonce=$(extract_nonce "$page")
[[ -n "$nonce" ]] || { echo "no nonce on /register"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/register" \
  --data-urlencode "name=$PLAYER_NAME" \
  --data-urlencode "email=$PLAYER_EMAIL" \
  --data-urlencode "password=$PLAYER_PASSWORD" \
  --data-urlencode "nonce=$nonce")
assert_status 302 "$code" "POST /register"

player_id=$(db_count "SELECT id FROM users WHERE email='$PLAYER_EMAIL';")
[[ -n "$player_id" ]] || { echo "user not present in DB after register"; exit 1; }
echo "PASS: user persisted with id $player_id"

echo
echo "== Step 2: login as that user =="
# Drop the auto-login cookie from /register and start fresh so we exercise login.
> "$cookie_jar"
page=/tmp/hikari-page-login.html
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" "$CTFD_URL/login"
nonce=$(extract_nonce "$page")

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$PLAYER_EMAIL" \
  --data-urlencode "password=$PLAYER_PASSWORD" \
  --data-urlencode "nonce=$nonce")
assert_status 302 "$code" "POST /login"

echo
echo "== Step 3: create a team =="
page=/tmp/hikari-page-team-new.html
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" \
  -w '%{http_code}' "$CTFD_URL/teams/new")
assert_status 200 "$code" "GET /teams/new"
nonce=$(extract_nonce "$page")
[[ -n "$nonce" ]] || { echo "no nonce on /teams/new"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/teams/new" \
  --data-urlencode "name=$TEAM_NAME" \
  --data-urlencode "password=$TEAM_PASSWORD" \
  --data-urlencode "nonce=$nonce")
assert_status 302 "$code" "POST /teams/new"

team_id=$(db_count "SELECT id FROM teams WHERE name='$TEAM_NAME';")
[[ -n "$team_id" ]] || { echo "team not present in DB after creation"; exit 1; }
echo "PASS: team persisted with id $team_id"

joined=$(db_count "SELECT team_id FROM users WHERE id=$player_id;")
[[ "$joined" == "$team_id" ]] \
  || { echo "FAIL: player team_id=$joined, expected $team_id"; exit 1; }
echo "PASS: player joined team (team_id=$team_id)"

echo
echo "== Step 4: list challenges as logged-in player =="
listing=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  "$CTFD_URL/api/v1/challenges")
success=$(echo "$listing" | jq -r '.success')
[[ "$success" == "true" ]] \
  || { echo "FAIL: /api/v1/challenges returned success=$success body=$listing"; exit 1; }
count=$(echo "$listing" | jq -r '.data | length')
echo "PASS: /api/v1/challenges accessible to player (challenges visible: $count)"

echo
echo "== Step 5: activity log captured the player's actions =="
# Wait briefly because the publish path is async to the request.
sleep 2
captured=$(db_count "SELECT GROUP_CONCAT(event_type ORDER BY occurred_at) FROM hikari_activity WHERE actor_id=$player_id;")
[[ "$captured" == *"user.login"* ]] \
  || { echo "FAIL: no user.login event for player ($captured)"; exit 1; }
echo "PASS: events captured for player id=$player_id: $captured"

echo
echo "Player end-to-end flow verified."
echo "  user=$PLAYER_EMAIL (id $player_id)"
echo "  team=$TEAM_NAME (id $team_id)"
