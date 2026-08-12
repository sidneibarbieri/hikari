#!/usr/bin/env bash
# Verifies the administrative lifecycle for one isolated competition run.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}
stamp=$(date +%s)
run_key="acceptance-${stamp}"

cookie_jar=$(mktemp)
login_page=$(mktemp)
trap 'rm -f "$cookie_jar" "$login_page"' EXIT

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

run_duration_minutes() {
  docker-compose -f "$COMPOSE_FILE" exec -T db mariadb -N -uctfd -pctfd ctfd \
    -e "SELECT TIMESTAMPDIFF(MINUTE, starts_at, ends_at) FROM hikari_competition_runs WHERE \`key\` = '$run_key';" \
    | tr -d '\r\n'
}

run_status() {
  docker-compose -f "$COMPOSE_FILE" exec -T db mariadb -N -uctfd -pctfd ctfd \
    -e "SELECT status FROM hikari_competition_runs WHERE \`key\` = '$run_key';" \
    | tr -d '\r\n'
}

remaining_seconds() {
  docker-compose -f "$COMPOSE_FILE" exec -T db mariadb -N -uctfd -pctfd ctfd \
    -e "SELECT COALESCE(paused_remaining_seconds, '') FROM hikari_competition_runs WHERE \`key\` = '$run_key';" \
    | tr -d '\r\n'
}

active_test_run() {
  docker-compose -f "$COMPOSE_FILE" exec -T db mariadb -N -uctfd -pctfd ctfd \
    -e "SELECT id, \`key\` FROM hikari_competition_runs WHERE status IN ('running', 'paused') ORDER BY id DESC LIMIT 1;" \
    | tr -d '\r'
}

curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$login_page" "$CTFD_URL/login"
nonce=$(extract_nonce "$login_page")
[[ -n "$nonce" ]] || { echo "FAIL: login nonce missing"; exit 1; }
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "FAIL: admin login returned $code"; exit 1; }

dashboard=$(mktemp)
trap 'rm -f "$cookie_jar" "$login_page" "$dashboard"' EXIT
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" -w '%{http_code}' \
  "$CTFD_URL/admin/hikari/competitions")
[[ "$code" == "200" ]] || { echo "FAIL: competition dashboard returned $code"; exit 1; }
grep -q "Nova execução" "$dashboard" || { echo "FAIL: lifecycle dashboard is incomplete"; exit 1; }

# A repeated local run may have left the prior test execution active. Only a
# run created by this test is closed; an operator-owned execution is preserved.
active_info=$(active_test_run)
if [[ -n "$active_info" ]]; then
  IFS=$'\t' read -r active_id active_key <<< "$active_info"
  [[ "$active_key" == acceptance-* ]] \
    || { echo "FAIL: active operator execution '$active_key' prevents lifecycle test"; exit 1; }
  code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/admin/hikari/competitions/$active_id/finish" \
    --data-urlencode "nonce=$(extract_nonce "$dashboard")")
  [[ "$code" == "302" ]] || { echo "FAIL: cleanup finish returned $code"; exit 1; }
  curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
fi

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" \
  --data-urlencode "key=$run_key" \
  --data-urlencode "name=Acceptance Run $stamp" \
  --data-urlencode "scoring_mode=teams" \
  --data-urlencode "duration_minutes=240")
[[ "$code" == "302" ]] || { echo "FAIL: create run returned $code"; exit 1; }

dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
run_id=$(grep -oE "/admin/hikari/competitions/[0-9]+/start" "$dashboard" | head -1 | grep -oE '[0-9]+')
[[ -n "$run_id" ]] || { echo "FAIL: start action missing for created run"; exit 1; }
nonce=$(extract_nonce "$dashboard")
[[ -n "$nonce" ]] || { echo "FAIL: competition nonce missing"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/start" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "FAIL: start run returned $code"; exit 1; }

dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
grep -q "$run_key" "$dashboard" || { echo "FAIL: execution key not rendered"; exit 1; }
grep -q "+2 h" "$dashboard" || { echo "FAIL: extension control missing"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/extend" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" \
  --data-urlencode "hours=2")
[[ "$code" == "302" ]] || { echo "FAIL: extend run returned $code"; exit 1; }

duration_minutes=$(run_duration_minutes)
[[ "$duration_minutes" =~ ^[0-9]+$ ]] \
  || { echo "FAIL: execution schedule was not persisted"; exit 1; }
[[ "$duration_minutes" -ge 360 ]] \
  || { echo "FAIL: expected a six-hour execution after extension, got $duration_minutes minutes"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/pause" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: pause run returned $code"; exit 1; }
[[ "$(run_status)" == "paused" ]] || { echo "FAIL: execution was not paused"; exit 1; }
paused_seconds=$(remaining_seconds)
[[ "$paused_seconds" =~ ^[0-9]+$ && "$paused_seconds" -gt 0 ]] \
  || { echo "FAIL: remaining time was not preserved on pause"; exit 1; }

dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/resume" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: resume run returned $code"; exit 1; }
[[ "$(run_status)" == "running" ]] || { echo "FAIL: execution was not resumed"; exit 1; }
[[ -z "$(remaining_seconds)" ]] || { echo "FAIL: pause state remained after resume"; exit 1; }

dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/finish" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: finish run returned $code"; exit 1; }
[[ "$(run_status)" == "finished" ]] || { echo "FAIL: execution was not finished"; exit 1; }

echo "PASS: run created, started, extended, paused, resumed, and finished"
