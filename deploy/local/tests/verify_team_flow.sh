#!/usr/bin/env bash
# Two-competitor team scenario: one user creates a team, a second user
# requests entry, and the captain accepts the request. The test verifies that
# the membership is never granted before the captain approves it.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}

stamp=$(date +%s)
CAPTAIN_NAME="capitão_${stamp}"
CAPTAIN_EMAIL="captain_${stamp}@hikari.local"
CAPTAIN_PASSWORD="captain-pw-${stamp}"
MEMBER_NAME="member_${stamp}"
MEMBER_EMAIL="member_${stamp}@hikari.local"
MEMBER_PASSWORD="member-pw-${stamp}"
TEAM_NAME="squad_${stamp}"

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
  local jar=$1 username=$2 password=$3 page nonce code
  : > "$jar"  # fresh session to exercise login
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/login"
  nonce=$(extract_nonce "$page")
  rm -f "$page"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/login" \
    --data-urlencode "name=$username" \
    --data-urlencode "password=$password" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "login $username returned $code"; return 1; }
}

captain_jar=$(mktemp)
member_jar=$(mktemp)
trap 'rm -f "$captain_jar" "$member_jar"' EXIT

echo "== register captain =="
register "$captain_jar" "$CAPTAIN_NAME" "$CAPTAIN_EMAIL" "$CAPTAIN_PASSWORD"
echo "PASS: captain registered"

echo "== captain creates team =="
login "$captain_jar" "$CAPTAIN_NAME" "$CAPTAIN_PASSWORD"
page=$(mktemp)
curl -sS -c "$captain_jar" -b "$captain_jar" -o "$page" "$CTFD_URL/teams/new"
grep -q 'class="hikari-team-form"' "$page" \
  || { echo "FAIL: team creation page is missing the Hikari form layout"; exit 1; }
nonce=$(extract_nonce "$page")
rm -f "$page"
code=$(curl -sS -c "$captain_jar" -b "$captain_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/teams/new" \
  --data-urlencode "name=$TEAM_NAME" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "team create returned $code"; exit 1; }
echo "PASS: team $TEAM_NAME created"

team_id=$(db_query "SELECT id FROM teams WHERE name='$TEAM_NAME';" | tr -d '[:space:]')
[[ -n "$team_id" ]] || { echo "FAIL: team was not persisted"; exit 1; }

echo "== register member and request entry =="
register "$member_jar" "$MEMBER_NAME" "$MEMBER_EMAIL" "$MEMBER_PASSWORD"
login "$member_jar" "$MEMBER_NAME" "$MEMBER_PASSWORD"
page=$(mktemp)
curl -sS -c "$member_jar" -b "$member_jar" -o "$page" "$CTFD_URL/hikari/teams/join"
grep -q "$TEAM_NAME" "$page" \
  || { echo "FAIL: team is missing from the team list"; exit 1; }
nonce=$(extract_nonce "$page")
rm -f "$page"
code=$(curl -sS -c "$member_jar" -b "$member_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/hikari/teams/$team_id/request" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "team request returned $code"; exit 1; }

member_id=$(db_query "SELECT id FROM users WHERE email='$MEMBER_EMAIL';" | tr -d '[:space:]')
pending_team=$(db_query "SELECT COALESCE(team_id, '') FROM users WHERE id=$member_id;" | tr -d '[:space:]')
[[ -z "$pending_team" ]] \
  || { echo "FAIL: membership was granted before captain approval"; exit 1; }
request_id=$(db_query "SELECT id FROM hikari_team_membership_requests WHERE team_id=$team_id AND user_id=$member_id AND status='pending';" | tr -d '[:space:]')
[[ -n "$request_id" ]] || { echo "FAIL: pending membership request not found"; exit 1; }
echo "PASS: request $request_id is pending and the user is not yet a member"

echo "== captain approves entry =="
page=$(mktemp)
curl -sS -c "$captain_jar" -b "$captain_jar" -o "$page" "$CTFD_URL/hikari/team/requests"
grep -q "$MEMBER_NAME" "$page" \
  || { echo "FAIL: captain cannot see the pending request"; exit 1; }
nonce=$(extract_nonce "$page")
rm -f "$page"
code=$(curl -sS -c "$captain_jar" -b "$captain_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/hikari/team/requests/$request_id/approve" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "team approval returned $code"; exit 1; }
echo "PASS: captain approved member"

echo "== assert both users share the team in the database =="
member_count=$(db_query "SELECT COUNT(*) FROM users WHERE team_id=$team_id;" | tr -d '[:space:]')
[[ "$member_count" == "2" ]] \
  || { echo "FAIL: expected 2 members on team_id=$team_id, got $member_count"; exit 1; }
request_status=$(db_query "SELECT status FROM hikari_team_membership_requests WHERE id=$request_id;" | tr -d '[:space:]')
[[ "$request_status" == "approved" ]] \
  || { echo "FAIL: expected request status approved, got $request_status"; exit 1; }
echo "PASS: team $TEAM_NAME (id=$team_id) has $member_count members"

echo
echo "Team flow verified."
