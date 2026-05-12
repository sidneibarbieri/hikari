#!/usr/bin/env bash
# Two-competitor team scenario: one user creates a team, a second user joins
# it with the team's name+password, and both end up linked to the same team
# in the database. This is the path that lets a team play together.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
COMPOSE_FILE=${COMPOSE_FILE:-$(cd "$(dirname "$0")" && pwd)/docker-compose.yml}

stamp=$(date +%s)
CAPTAIN_NAME="captain_${stamp}"
CAPTAIN_EMAIL="captain_${stamp}@hikari.local"
CAPTAIN_PASSWORD="captain-pw-${stamp}"
MEMBER_NAME="member_${stamp}"
MEMBER_EMAIL="member_${stamp}@hikari.local"
MEMBER_PASSWORD="member-pw-${stamp}"
TEAM_NAME="squad_${stamp}"
TEAM_PASSWORD="squad-secret-${stamp}"

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

db_query() {
  docker-compose -f "$COMPOSE_FILE" exec -T db \
    mariadb -uctfd -pctfd ctfd -N -B -e "$1"
}

register() {
  local jar=$1 name=$2 email=$3 password=$4 page nonce code
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/register"
  nonce=$(extract_nonce "$page")
  rm -f "$page"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/register" \
    --data-urlencode "name=$name" \
    --data-urlencode "email=$email" \
    --data-urlencode "password=$password" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "register $email returned $code"; return 1; }
}

login() {
  local jar=$1 email=$2 password=$3 page nonce code
  : > "$jar"  # fresh session to exercise login
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/login"
  nonce=$(extract_nonce "$page")
  rm -f "$page"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/login" \
    --data-urlencode "name=$email" \
    --data-urlencode "password=$password" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "login $email returned $code"; return 1; }
}

captain_jar=$(mktemp)
member_jar=$(mktemp)
trap 'rm -f "$captain_jar" "$member_jar"' EXIT

echo "== register captain =="
register "$captain_jar" "$CAPTAIN_NAME" "$CAPTAIN_EMAIL" "$CAPTAIN_PASSWORD"
echo "PASS: captain registered"

echo "== captain creates team =="
login "$captain_jar" "$CAPTAIN_EMAIL" "$CAPTAIN_PASSWORD"
page=$(mktemp)
curl -sS -c "$captain_jar" -b "$captain_jar" -o "$page" "$CTFD_URL/teams/new"
nonce=$(extract_nonce "$page")
rm -f "$page"
code=$(curl -sS -c "$captain_jar" -b "$captain_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/teams/new" \
  --data-urlencode "name=$TEAM_NAME" \
  --data-urlencode "password=$TEAM_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "team create returned $code"; exit 1; }
echo "PASS: team $TEAM_NAME created"

echo "== register member and join the team =="
register "$member_jar" "$MEMBER_NAME" "$MEMBER_EMAIL" "$MEMBER_PASSWORD"
login "$member_jar" "$MEMBER_EMAIL" "$MEMBER_PASSWORD"
page=$(mktemp)
curl -sS -c "$member_jar" -b "$member_jar" -o "$page" "$CTFD_URL/teams/join"
nonce=$(extract_nonce "$page")
rm -f "$page"
code=$(curl -sS -c "$member_jar" -b "$member_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/teams/join" \
  --data-urlencode "name=$TEAM_NAME" \
  --data-urlencode "password=$TEAM_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "team join returned $code"; exit 1; }
echo "PASS: member joined team"

echo "== assert both users share the team in the database =="
team_id=$(db_query "SELECT id FROM teams WHERE name='$TEAM_NAME';" | tr -d '[:space:]')
member_count=$(db_query "SELECT COUNT(*) FROM users WHERE team_id=$team_id;" | tr -d '[:space:]')
[[ "$member_count" == "2" ]] \
  || { echo "FAIL: expected 2 members on team_id=$team_id, got $member_count"; exit 1; }
echo "PASS: team $TEAM_NAME (id=$team_id) has $member_count members"

echo
echo "Team flow verified."
