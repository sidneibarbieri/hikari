#!/usr/bin/env bash
# Exercises the local Hikari questionnaire as a competitor and verifies that
# the response is persisted and exported as JSONL for research use.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
COMPOSE_FILE=${COMPOSE_FILE:-$(cd "$(dirname "$0")" && pwd)/docker-compose.yml}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari-admin-pw}

stamp=$(date +%s)
PLAYER_NAME="feedback_${stamp}"
PLAYER_EMAIL="feedback_${stamp}@hikari.local"
PLAYER_PASSWORD="feedback-pw-${stamp}"

cookie_jar=$(mktemp)
admin_cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar" "$admin_cookie_jar" /tmp/hikari-feedback-*.html' EXIT

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

db_value() {
  local query=$1
  docker-compose -f "$COMPOSE_FILE" exec -T db \
    mariadb -uctfd -pctfd ctfd -N -B -e "$query"
}

echo "== register competitor =="
page=/tmp/hikari-feedback-register.html
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
[[ "$code" == "302" ]] || { echo "register returned $code"; exit 1; }

player_id=$(db_value "SELECT id FROM users WHERE email='$PLAYER_EMAIL';" | tr -d '[:space:]')
[[ -n "$player_id" ]] || { echo "user not found after register"; exit 1; }
echo "PASS: competitor persisted with id $player_id"

echo "== submit questionnaire =="
page=/tmp/hikari-feedback-form.html
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" \
  -w '%{http_code}' "$CTFD_URL/hikari/feedback")
[[ "$code" == "200" ]] || { echo "GET /hikari/feedback returned $code"; exit 1; }
nonce=$(extract_nonce "$page")
[[ -n "$nonce" ]] || { echo "no nonce on /hikari/feedback"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/hikari/feedback" \
  --data-urlencode "nonce=$nonce" \
  --data-urlencode "phase=post" \
  --data-urlencode "experience_level=intermediate" \
  --data-urlencode "prior_ctf=y" \
  --data-urlencode "blue_team_familiarity=moderate" \
  --data-urlencode "interface_rating=4" \
  --data-urlencode "challenge_difficulty=adequate" \
  --data-urlencode "dashboard_relevance=high" \
  --data-urlencode "useful_dashboard_elements=timeline and host filters" \
  --data-urlencode "unused_dashboard_elements=none observed" \
  --data-urlencode "learning_effectiveness=4" \
  --data-urlencode "learned_areas=log_analysis" \
  --data-urlencode "learned_areas=incident_response" \
  --data-urlencode "operational_confidence_before=2" \
  --data-urlencode "operational_confidence_after=4" \
  --data-urlencode "realism=partial" \
  --data-urlencode "methodology_notes=Started with timeline triage, then filtered hosts." \
  --data-urlencode "suggested_improvements=Add more guided debrief data.")
[[ "$code" == "302" ]] || { echo "POST /hikari/feedback returned $code"; exit 1; }

rows=$(db_value "SELECT COUNT(*) FROM hikari_feedback_responses WHERE user_id=$player_id;" | tr -d '[:space:]')
[[ "$rows" == "1" ]] || { echo "expected one feedback row for user $player_id, got $rows"; exit 1; }
echo "PASS: feedback response persisted"

phase=$(db_value "SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '$.phase')) FROM hikari_feedback_responses WHERE user_id=$player_id;" | tr -d '[:space:]')
[[ "$phase" == "post" ]] || { echo "expected payload phase post, got $phase"; exit 1; }
echo "PASS: payload remained structured"

echo "== export feedback as admin =="
page=/tmp/hikari-feedback-admin-login.html
curl -sS -c "$admin_cookie_jar" -b "$admin_cookie_jar" -o "$page" "$CTFD_URL/login"
nonce=$(extract_nonce "$page")
curl -sS -c "$admin_cookie_jar" -b "$admin_cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce" >/tmp/hikari-feedback-login-code
[[ "$(cat /tmp/hikari-feedback-login-code)" == "302" ]] || { echo "admin login failed"; exit 1; }

export_body=$(curl -sS -c "$admin_cookie_jar" -b "$admin_cookie_jar" \
  "$CTFD_URL/admin/hikari/research/feedback.jsonl")
echo "$export_body" | python3 -c 'import json, sys; [json.loads(line) for line in sys.stdin if line.strip()]'
echo "$export_body" | grep -q "\"user_id\": $player_id" \
  || { echo "feedback export does not include user_id $player_id"; exit 1; }
echo "PASS: feedback export contains parseable records"

echo
echo "Feedback flow verified."
