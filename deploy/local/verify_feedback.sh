#!/usr/bin/env bash
# Exercises the local Hikari questionnaire as a competitor and verifies that
# the response is persisted as structured JSON and exported as JSONL.

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
trap 'rm -f "$cookie_jar" "$admin_cookie_jar" /tmp/hikari-feedback-*.html /tmp/hikari-feedback-login-code' EXIT

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

grep -q "NASA Task Load Index" "$page" \
  || { echo "feedback page missing NASA-TLX section"; exit 1; }
grep -q "System Usability Scale" "$page" \
  || { echo "feedback page missing SUS section"; exit 1; }
grep -q "NIST NICE" "$page" \
  || { echo "feedback page missing NICE self-assessment section"; exit 1; }
grep -q "MITRE ATT" "$page" \
  || { echo "feedback page missing MITRE tactics section"; exit 1; }
echo "PASS: questionnaire surfaces all instrument sections"

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/hikari/feedback" \
  --data-urlencode "nonce=$nonce" \
  --data-urlencode "phase=post" \
  --data-urlencode "years_cyber_experience=3_5" \
  --data-urlencode "primary_role=soc_analyst_t2" \
  --data-urlencode "prior_ctf_count=4_10" \
  --data-urlencode "years_soc_experience=1_2" \
  --data-urlencode "formal_education=vendor_certification" \
  --data-urlencode "self_cyber_defense_analyst=4" \
  --data-urlencode "self_incident_responder=3" \
  --data-urlencode "self_threat_warning_analyst=3" \
  --data-urlencode "self_forensics_analyst=2" \
  --data-urlencode "self_vuln_assessment_analyst=2" \
  --data-urlencode "tool_kibana=4" \
  --data-urlencode "tool_kql=3" \
  --data-urlencode "tool_attack_framework=4" \
  --data-urlencode "tool_other_siem=3" \
  --data-urlencode "mitre_tactics_practised=initial_access" \
  --data-urlencode "mitre_tactics_practised=execution" \
  --data-urlencode "mitre_tactics_practised=defense_evasion" \
  --data-urlencode "mitre_tactics_practised=command_and_control" \
  --data-urlencode "tlx_mental_demand=6" \
  --data-urlencode "tlx_temporal_demand=4" \
  --data-urlencode "tlx_performance=3" \
  --data-urlencode "tlx_effort=5" \
  --data-urlencode "tlx_frustration=3" \
  --data-urlencode "sus_would_use_frequently=5" \
  --data-urlencode "sus_unnecessarily_complex=2" \
  --data-urlencode "sus_easy_to_use=4" \
  --data-urlencode "sus_needed_support=2" \
  --data-urlencode "sus_functions_well_integrated=5" \
  --data-urlencode "sus_too_much_inconsistency=1" \
  --data-urlencode "sus_quick_to_learn=4" \
  --data-urlencode "sus_cumbersome=2" \
  --data-urlencode "sus_felt_confident=4" \
  --data-urlencode "sus_needed_to_learn_a_lot=2" \
  --data-urlencode "learning_log_analysis=4" \
  --data-urlencode "learning_pattern_correlation=4" \
  --data-urlencode "learning_hypothesis_generation=3" \
  --data-urlencode "learning_tool_fluency=5" \
  --data-urlencode "learning_time_to_detect=3" \
  --data-urlencode "learning_documentation=3" \
  --data-urlencode "realism_attack_chain=4" \
  --data-urlencode "realism_telemetry=4" \
  --data-urlencode "realism_pace=4" \
  --data-urlencode "methodology_coherence=4" \
  --data-urlencode "nps_recommend=9" \
  --data-urlencode "most_valuable_technique=Pivoting on user agent + process tree." \
  --data-urlencode "biggest_learning_blocker=Documentation drift between scenarios." \
  --data-urlencode "suggested_scenarios=Cloud-native lateral movement." \
  --data-urlencode "other_comments=Solid pacing.")
[[ "$code" == "302" ]] || { echo "POST /hikari/feedback returned $code"; exit 1; }
echo "PASS: questionnaire submission accepted (302)"

rows=$(db_value "SELECT COUNT(*) FROM hikari_feedback_responses WHERE user_id=$player_id;" | tr -d '[:space:]')
[[ "$rows" == "1" ]] || { echo "expected one feedback row for user $player_id, got $rows"; exit 1; }
echo "PASS: response persisted as a single row"

phase=$(db_value "SELECT JSON_UNQUOTE(JSON_EXTRACT(payload, '\$.phase')) FROM hikari_feedback_responses WHERE user_id=$player_id;" | tr -d '[:space:]')
[[ "$phase" == "post" ]] || { echo "expected payload phase post, got '$phase'"; exit 1; }
tlx_mental=$(db_value "SELECT JSON_EXTRACT(payload, '\$.tlx_mental_demand') FROM hikari_feedback_responses WHERE user_id=$player_id;" | tr -d '[:space:]')
[[ "$tlx_mental" == "6" ]] || { echo "expected tlx_mental_demand=6 got '$tlx_mental'"; exit 1; }
sus_freq=$(db_value "SELECT JSON_EXTRACT(payload, '\$.sus_would_use_frequently') FROM hikari_feedback_responses WHERE user_id=$player_id;" | tr -d '[:space:]')
[[ "$sus_freq" == "5" ]] || { echo "expected sus_would_use_frequently=5 got '$sus_freq'"; exit 1; }
nps=$(db_value "SELECT JSON_EXTRACT(payload, '\$.nps_recommend') FROM hikari_feedback_responses WHERE user_id=$player_id;" | tr -d '[:space:]')
[[ "$nps" == "9" ]] || { echo "expected nps_recommend=9 got '$nps'"; exit 1; }
echo "PASS: payload carries NASA-TLX, SUS, and NPS fields"

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
echo "$export_body" | grep -q "tlx_mental_demand" \
  || { echo "feedback export does not include NASA-TLX fields"; exit 1; }
echo "PASS: feedback export contains parseable records with research fields"

echo
echo "Feedback flow verified."
