#!/usr/bin/env bash
# Scripted simulation of a small competition against the running stack.
#
#   * three challenges are created by the admin
#   * one two-member team is formed (captain + member)
#   * one lone-wolf player creates their own one-person team
#   * each participant submits a flag
#   * the resulting activity log is exported alongside a summary
#
# Artifacts land under ./artifacts/dry-run-<timestamp>/ for the reviewer to
# inspect afterwards. The script is idempotent on repeat runs because every
# user, team and challenge name is suffixed with a fresh epoch second.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
COMPOSE_FILE=${COMPOSE_FILE:-$(cd "$(dirname "$0")" && pwd)/docker-compose.yml}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari-admin-pw}

stamp=$(date +%s)
artifacts_dir="$(cd "$(dirname "$0")" && pwd)/artifacts/dry-run-${stamp}"
mkdir -p "$artifacts_dir"

CAPTAIN_NAME="capt_${stamp}"
CAPTAIN_EMAIL="capt_${stamp}@hikari.local"
CAPTAIN_PASSWORD="capt-pw-${stamp}"
MEMBER_NAME="memb_${stamp}"
MEMBER_EMAIL="memb_${stamp}@hikari.local"
MEMBER_PASSWORD="memb-pw-${stamp}"
WOLF_NAME="wolf_${stamp}"
WOLF_EMAIL="wolf_${stamp}@hikari.local"
WOLF_PASSWORD="wolf-pw-${stamp}"
TEAM_NAME="alpha_${stamp}"
TEAM_PASSWORD="alpha-secret-${stamp}"
SOLO_NAME="solo_${stamp}"
SOLO_PASSWORD="solo-secret-${stamp}"

extract_nonce_form() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

extract_csrf_nonce_js() {
  grep -oE "'csrfNonce':[[:space:]]*\"[^\"]+\"" "$1" \
    | head -1 | sed -E 's/.*"([^"]+)".*/\1/'
}

login_admin() {
  local jar=$1 page nonce code
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/login"
  nonce=$(extract_nonce_form "$page")
  rm -f "$page"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/login" \
    --data-urlencode "name=$ADMIN_EMAIL" \
    --data-urlencode "password=$ADMIN_PASSWORD" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "admin login failed: $code"; return 1; }
}

admin_csrf() {
  local jar=$1 page csrf
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" -L "$CTFD_URL/admin"
  csrf=$(extract_csrf_nonce_js "$page")
  rm -f "$page"
  printf '%s' "$csrf"
}

player_csrf() {
  local jar=$1 page csrf
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" -L "$CTFD_URL/challenges"
  csrf=$(extract_csrf_nonce_js "$page")
  rm -f "$page"
  printf '%s' "$csrf"
}

create_challenge() {
  local jar=$1 csrf=$2 name=$3 flag=$4
  local response challenge_id
  response=$(curl -sS -c "$jar" -b "$jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
    -X POST "$CTFD_URL/api/v1/challenges" \
    -d "{\"name\":\"$name\",\"category\":\"dry-run\",\"description\":\"dry-run probe\",\"value\":100,\"type\":\"standard\",\"state\":\"visible\"}")
  challenge_id=$(echo "$response" | jq -r '.data.id // empty')
  [[ -n "$challenge_id" ]] || { echo "challenge create failed: $response"; return 1; }
  curl -sS -c "$jar" -b "$jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
    -X POST "$CTFD_URL/api/v1/flags" \
    -d "{\"challenge\":$challenge_id,\"type\":\"static\",\"content\":\"$flag\"}" >/dev/null
  printf '%s' "$challenge_id"
}

register_player() {
  local jar=$1 name=$2 email=$3 password=$4 page nonce code
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/register"
  nonce=$(extract_nonce_form "$page")
  rm -f "$page"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/register" \
    --data-urlencode "name=$name" \
    --data-urlencode "email=$email" \
    --data-urlencode "password=$password" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "register $email failed: $code"; return 1; }
}

login_player() {
  local jar=$1 email=$2 password=$3 page nonce code
  : > "$jar"
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/login"
  nonce=$(extract_nonce_form "$page")
  rm -f "$page"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/login" \
    --data-urlencode "name=$email" \
    --data-urlencode "password=$password" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "login $email failed: $code"; return 1; }
}

create_team() {
  local jar=$1 name=$2 password=$3 page nonce code
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/teams/new"
  nonce=$(extract_nonce_form "$page")
  rm -f "$page"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/teams/new" \
    --data-urlencode "name=$name" \
    --data-urlencode "password=$password" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "team create failed: $code"; return 1; }
}

join_team() {
  local jar=$1 name=$2 password=$3 page nonce code
  page=$(mktemp)
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/teams/join"
  nonce=$(extract_nonce_form "$page")
  rm -f "$page"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/teams/join" \
    --data-urlencode "name=$name" \
    --data-urlencode "password=$password" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "team join failed: $code"; return 1; }
}

submit_flag() {
  local jar=$1 csrf=$2 challenge_id=$3 flag=$4 response status
  response=$(curl -sS -c "$jar" -b "$jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
    -X POST "$CTFD_URL/api/v1/challenges/attempt" \
    -d "{\"challenge_id\":$challenge_id,\"submission\":\"$flag\"}")
  status=$(echo "$response" | jq -r '.data.status')
  [[ "$status" == "correct" ]] \
    || { echo "submit failed: $response"; return 1; }
}

echo "==> dry run artifacts at $artifacts_dir"

admin_jar=$(mktemp); trap 'rm -f "$admin_jar"' EXIT
login_admin "$admin_jar"
csrf=$(admin_csrf "$admin_jar")
echo "admin authenticated"

declare -a challenge_ids
declare -a challenge_flags
declare -a challenge_names
for i in 1 2 3; do
  name="dry_run_${stamp}_c${i}"
  flag="hikari{${stamp}_c${i}}"
  cid=$(create_challenge "$admin_jar" "$csrf" "$name" "$flag")
  challenge_ids+=("$cid")
  challenge_flags+=("$flag")
  challenge_names+=("$name")
  echo "challenge $name id=$cid"
done

captain_jar=$(mktemp); member_jar=$(mktemp); wolf_jar=$(mktemp)
trap 'rm -f "$admin_jar" "$captain_jar" "$member_jar" "$wolf_jar"' EXIT

echo "==> team alpha: captain registers, creates team"
register_player "$captain_jar" "$CAPTAIN_NAME" "$CAPTAIN_EMAIL" "$CAPTAIN_PASSWORD"
login_player "$captain_jar" "$CAPTAIN_EMAIL" "$CAPTAIN_PASSWORD"
create_team "$captain_jar" "$TEAM_NAME" "$TEAM_PASSWORD"

echo "==> team alpha: member registers, joins"
register_player "$member_jar" "$MEMBER_NAME" "$MEMBER_EMAIL" "$MEMBER_PASSWORD"
login_player "$member_jar" "$MEMBER_EMAIL" "$MEMBER_PASSWORD"
join_team "$member_jar" "$TEAM_NAME" "$TEAM_PASSWORD"

echo "==> lone wolf registers and creates own team"
register_player "$wolf_jar" "$WOLF_NAME" "$WOLF_EMAIL" "$WOLF_PASSWORD"
login_player "$wolf_jar" "$WOLF_EMAIL" "$WOLF_PASSWORD"
create_team "$wolf_jar" "$SOLO_NAME" "$SOLO_PASSWORD"

echo "==> captain solves challenge 1"
csrf_captain=$(player_csrf "$captain_jar")
submit_flag "$captain_jar" "$csrf_captain" "${challenge_ids[0]}" "${challenge_flags[0]}"

echo "==> member solves challenge 2"
csrf_member=$(player_csrf "$member_jar")
submit_flag "$member_jar" "$csrf_member" "${challenge_ids[1]}" "${challenge_flags[1]}"

echo "==> lone wolf solves challenge 3"
csrf_wolf=$(player_csrf "$wolf_jar")
submit_flag "$wolf_jar" "$csrf_wolf" "${challenge_ids[2]}" "${challenge_flags[2]}"

echo "==> exporting activity log"
curl -sS -c "$admin_jar" -b "$admin_jar" \
  "$CTFD_URL/admin/hikari/research/export.jsonl" \
  -o "$artifacts_dir/hikari-activity.jsonl"

scoreboard=$(curl -sS -c "$admin_jar" -b "$admin_jar" \
  "$CTFD_URL/api/v1/scoreboard")
echo "$scoreboard" | jq . > "$artifacts_dir/scoreboard.json"

# Summary report. The reviewer reads this file to understand the run; the
# other files are the raw artifacts they reproduce.
{
  echo "Hikari dry-run summary"
  echo "======================"
  echo
  printf 'timestamp: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'artifacts: %s\n' "$artifacts_dir"
  echo
  echo "challenges:"
  for i in 0 1 2; do
    printf '  - %s (id %s) flag=%s\n' \
      "${challenge_names[$i]}" "${challenge_ids[$i]}" "${challenge_flags[$i]}"
  done
  echo
  echo "participants:"
  printf '  team %s\n' "$TEAM_NAME"
  printf '    captain %s\n' "$CAPTAIN_EMAIL"
  printf '    member  %s\n' "$MEMBER_EMAIL"
  printf '  lone wolf team %s\n' "$SOLO_NAME"
  printf '    member  %s\n' "$WOLF_EMAIL"
  echo
  printf 'activity records exported: %s\n' "$(wc -l < "$artifacts_dir/hikari-activity.jsonl" | tr -d '[:space:]')"
} > "$artifacts_dir/SUMMARY.txt"

cat "$artifacts_dir/SUMMARY.txt"
echo
echo "Dry run complete."
