#!/usr/bin/env bash
# Runs one competition from end to end with several competitors acting at the
# same time, in the order a real event follows.
#
#   registration window -> teams formed and approved -> start -> hunting and
#   submissions in parallel -> extension -> pause and resume -> close
#
# The per-flow acceptance scripts each prove one contract in isolation. This
# script proves they hold together under the sequence and the concurrency of
# an event: six competitors registering, two shared teams and two single-person
# teams, simultaneous flag
# submissions and SIEM queries, and the administrative controls applied while
# people are playing.
#
# Everything it creates is scoped by a timestamp, so it can run repeatedly
# without colliding with earlier runs. It still writes competitors, teams,
# submissions and a competition schedule, so it belongs on a disposable stack.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

if [[ "${HIKARI_ACCEPTANCE_CONTEXT:-}" != "1" \
  && "${HIKARI_ALLOW_MUTATING_ACCEPTANCE:-}" != "1" ]]; then
  echo "Refusing to simulate a competition on the active stack." >&2
  echo "It would leave simulated competitors and teams beside real accounts." >&2
  echo "Run: bash tests/acceptance_isolated.sh" >&2
  exit 2
fi
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}

stamp=$(date +%s)
run_key="simulacao-$stamp"
workspace=$(mktemp -d)
admin_jar="$workspace/admin.jar"
trap 'rm -rf "$workspace"' EXIT

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

extract_csrf() {
  grep -oE "'csrfNonce':[[:space:]]*\"[0-9a-f]+\"" "$1" \
    | head -1 | sed -E 's/.*"([0-9a-f]+)".*/\1/'
}

db_query() {
  hikari_compose -f "$COMPOSE_FILE" exec -T db \
    mariadb -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" -N -B -e "$1"
}

flush_rate_limit() {
  hikari_compose -f "$COMPOSE_FILE" exec -T cache redis-cli FLUSHALL >/dev/null 2>&1 || true
}

# --- actors ---------------------------------------------------------------

register_competitor() {
  local index=$1
  local jar="$workspace/player-$index.jar"
  local page="$workspace/page-$index.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/register"
  local nonce
  nonce=$(extract_nonce "$page")
  local code
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/register" \
    --data-urlencode "name=jogador_${index}_${stamp}" \
    --data-urlencode "email=jogador_${index}_${stamp}@hikari.local" \
    --data-urlencode "password=senha-${index}-${stamp}" \
    --data-urlencode "nonce=$nonce")
  [[ "$code" == "302" ]] || { echo "FAIL: registration of competitor $index returned $code"; exit 1; }
}

player_csrf() {
  local index=$1
  local jar="$workspace/player-$index.jar"
  local page="$workspace/csrf-$index.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/challenges"
  extract_csrf "$page"
}

# --- 1. administrator prepares the competition ----------------------------

echo "== 1. administrator prepares the competition =="
flush_rate_limit
page="$workspace/login.html"
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" "$CTFD_URL/login"
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$(extract_nonce "$page")")
[[ "$code" == "302" ]] || { echo "FAIL: administrator login returned $code"; exit 1; }

dashboard="$workspace/competitions.html"
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
active_id=$(grep -oE "/admin/hikari/competitions/[0-9]+/finish" "$dashboard" | head -1 | grep -oE '[0-9]+' || true)
if [[ -n "$active_id" ]]; then
  curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null \
    -X POST "$CTFD_URL/admin/hikari/competitions/$active_id/finish" \
    --data-urlencode "nonce=$(extract_nonce "$dashboard")"
  curl -sS -c "$admin_jar" -b "$admin_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
fi

code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" \
  --data-urlencode "key=$run_key" \
  --data-urlencode "name=Simulacao $stamp" \
  --data-urlencode "scoring_mode=teams" \
  --data-urlencode "duration_minutes=240")
[[ "$code" == "302" ]] || { echo "FAIL: creating the run returned $code"; exit 1; }
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
run_id=$(grep -oE "/admin/hikari/competitions/[0-9]+/start" "$dashboard" | head -1 | grep -oE '[0-9]+')
[[ -n "$run_id" ]] || { echo "FAIL: the created run is not on the dashboard"; exit 1; }

admin_csrf=$(extract_csrf "$dashboard")
[[ -n "$admin_csrf" ]] || { echo "FAIL: no CSRF token for the administrator API"; exit 1; }

challenge_flag="hikari{simulacao-$stamp}"
created=$(curl -sS -c "$admin_jar" -b "$admin_jar" \
  -H "Content-Type: application/json" -H "Csrf-Token: $admin_csrf" \
  -X POST "$CTFD_URL/api/v1/challenges" \
  -d "{\"name\":\"Investigacao simulada $stamp\",\"category\":\"Simulacao\",\"description\":\"Caca ao indicador no SIEM\",\"value\":100,\"type\":\"standard\",\"state\":\"visible\"}")
challenge_id=$(echo "$created" | jq -r '.data.id // empty')
[[ -n "$challenge_id" ]] || { echo "FAIL: challenge not created: $created"; exit 1; }
curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null \
  -H "Content-Type: application/json" -H "Csrf-Token: $admin_csrf" \
  -X POST "$CTFD_URL/api/v1/flags" \
  -d "{\"challenge\":$challenge_id,\"type\":\"static\",\"content\":\"$challenge_flag\"}"
echo "PASS: run $run_id created with one challenge, still not started"

# --- 2. registration window ------------------------------------------------

echo
echo "== 2. registration window: six competitors, four teams =="
for index in 1 2 3 4 5 6; do
  register_competitor "$index"
done
echo "PASS: six competitors registered before the start"

declare -a team_ids=()
for captain in 1 3 5 6; do
  jar="$workspace/player-$captain.jar"
  page="$workspace/team-$captain.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/teams/new"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/teams/new" \
    --data-urlencode "name=equipe_${captain}_${stamp}" \
    --data-urlencode "nonce=$(extract_nonce "$page")")
  [[ "$code" == "302" ]] || { echo "FAIL: team creation by competitor $captain returned $code"; exit 1; }
  team_id=$(db_query "SELECT id FROM teams WHERE name='equipe_${captain}_${stamp}';" | tr -d '[:space:]')
  [[ -n "$team_id" ]] || { echo "FAIL: team of competitor $captain was not persisted"; exit 1; }
  team_ids+=("$team_id")
done
echo "PASS: four teams created, including a single-person team"

# Competitors 2 and 4 request entry into the first two teams. Competitor 6
# creates a one-person team, which is the supported individual path in a
# team-scored competition.
for pair in "2:${team_ids[0]}" "4:${team_ids[1]}"; do
  member=${pair%%:*}
  team=${pair##*:}
  jar="$workspace/player-$member.jar"
  page="$workspace/join-$member.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/hikari/teams/join"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/hikari/teams/$team/request" \
    --data-urlencode "nonce=$(extract_nonce "$page")")
  [[ "$code" == "302" ]] || { echo "FAIL: join request from competitor $member returned $code"; exit 1; }
done

pending=$(db_query "SELECT COUNT(*) FROM hikari_team_membership_requests WHERE status='pending';" | tr -d '[:space:]')
[[ "$pending" -ge 2 ]] || { echo "FAIL: expected two pending requests, found $pending"; exit 1; }

joined_before_approval=$(db_query "SELECT COUNT(*) FROM users WHERE name IN ('jogador_2_${stamp}','jogador_4_${stamp}') AND team_id IS NOT NULL;" | tr -d '[:space:]')
[[ "$joined_before_approval" == "0" ]] \
  || { echo "FAIL: a competitor joined a team without approval"; exit 1; }
echo "PASS: entry requests are pending and grant no membership on their own"

for pair in "1:2" "3:4"; do
  captain=${pair%%:*}
  member=${pair##*:}
  member_id=$(db_query "SELECT id FROM users WHERE name='jogador_${member}_${stamp}';" | tr -d '[:space:]')
  request_id=$(db_query "SELECT id FROM hikari_team_membership_requests WHERE user_id=$member_id AND status='pending';" | tr -d '[:space:]')
  jar="$workspace/player-$captain.jar"
  page="$workspace/requests-$captain.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/hikari/team/requests"
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/hikari/team/requests/$request_id/approve" \
    --data-urlencode "nonce=$(extract_nonce "$page")")
  [[ "$code" == "302" ]] || { echo "FAIL: approval by captain $captain returned $code"; exit 1; }
done
approved=$(db_query "SELECT COUNT(*) FROM users WHERE name IN ('jogador_2_${stamp}','jogador_4_${stamp}') AND team_id IS NOT NULL;" | tr -d '[:space:]')
[[ "$approved" == "2" ]] || { echo "FAIL: expected two approved members, found $approved"; exit 1; }
echo "PASS: captains approved the members, who are now on their teams"

solo_members=$(db_query "SELECT COUNT(*) FROM users WHERE team_id=${team_ids[3]};" | tr -d '[:space:]')
[[ "$solo_members" == "1" ]] \
  || { echo "FAIL: expected the individual team to have one member, found $solo_members"; exit 1; }
echo "PASS: individual participation has a one-person score owner"

# --- 3. the competition has not started ------------------------------------

echo
echo "== 3. before the start, playing surfaces stay closed =="
jar="$workspace/player-1.jar"
csrf=$(player_csrf 1)
attempt=$(curl -sS -c "$jar" -b "$jar" \
  -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
  -X POST "$CTFD_URL/api/v1/challenges/attempt" \
  -d "{\"challenge_id\":$challenge_id,\"submission\":\"$challenge_flag\"}")
early_success=$(echo "$attempt" | jq -r '.success // empty')
early_status=$(echo "$attempt" | jq -r '.data.status // empty')
[[ "$early_status" != "correct" ]] \
  || { echo "FAIL: a flag was accepted before the competition started"; exit 1; }
siem_code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' "$CTFD_URL/hikari/siem")
[[ "$siem_code" != "200" ]] \
  || { echo "FAIL: the SIEM answered a competitor before the start"; exit 1; }
echo "PASS: submissions and SIEM are blocked before the start (attempt=${early_success:-refused}, siem=$siem_code)"

# --- 4. start ---------------------------------------------------------------

echo
echo "== 4. administrator starts the competition =="
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/start" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: start returned $code"; exit 1; }
status=$(db_query "SELECT status FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$status" == "running" ]] || { echo "FAIL: expected status running, found $status"; exit 1; }

siem_code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' "$CTFD_URL/hikari/siem")
[[ "$siem_code" == "200" ]] || { echo "FAIL: the SIEM did not open after the start ($siem_code)"; exit 1; }
echo "PASS: competition running and the SIEM opened to competitors"

# --- 5. simultaneous play ---------------------------------------------------

echo
echo "== 5. six competitors hunting and submitting at the same time =="
declare -a player_processes=()
for index in 1 2 3 4 5 6; do
  (
    jar="$workspace/player-$index.jar"
    csrf=$(player_csrf "$index")
    curl -sS -c "$jar" -b "$jar" -o /dev/null "$CTFD_URL/hikari/siem"
    # Open Discover and run a KQL search through the authenticated proxy, the
    # same path a competitor's browser uses. Both are recorded with attribution.
    curl -sS -c "$jar" -b "$jar" -o /dev/null "$CTFD_URL/hikari/kibana/app/discover"
    curl -sS -c "$jar" -b "$jar" -o /dev/null \
      -H "Content-Type: application/json" -H "kbn-xsrf: true" \
      -X POST "$CTFD_URL/hikari/kibana/internal/search/ese" \
      -d "{\"params\":{\"index\":\"competition1\",\"body\":{\"query\":{\"query_string\":{\"query\":\"source.ip:10.0.0.$index\"}}}}}"
    curl -sS -c "$jar" -b "$jar" \
      -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
      -X POST "$CTFD_URL/api/v1/challenges/attempt" \
      -d "{\"challenge_id\":$challenge_id,\"submission\":\"errado-$index\"}" >/dev/null
    curl -sS -c "$jar" -b "$jar" \
      -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
      -X POST "$CTFD_URL/api/v1/challenges/attempt" \
      -d "{\"challenge_id\":$challenge_id,\"submission\":\"$challenge_flag\"}" >/dev/null
  ) &
  player_processes+=("$!")
done
for process_id in "${player_processes[@]}"; do
  wait "$process_id"
done
echo "PASS: six parallel sessions completed without error"

solves=$(db_query "SELECT COUNT(*) FROM solves WHERE challenge_id=$challenge_id;" | tr -d '[:space:]')
[[ "$solves" -ge 1 ]] || { echo "FAIL: no solve was recorded"; exit 1; }
wrong=$(db_query "SELECT COUNT(*) FROM submissions WHERE challenge_id=$challenge_id AND type='incorrect';" | tr -d '[:space:]')
[[ "$wrong" -ge 1 ]] || { echo "FAIL: no incorrect submission was recorded"; exit 1; }
echo "PASS: $solves solve(s) and $wrong incorrect submission(s) recorded"

# One solve per team: CTFd credits the team, so a second member solving the
# same challenge must not double the score.
team_solves=$(db_query "SELECT COUNT(DISTINCT team_id) FROM solves WHERE challenge_id=$challenge_id AND team_id IS NOT NULL;" | tr -d '[:space:]')
solve_rows=$(db_query "SELECT COUNT(*) FROM solves WHERE challenge_id=$challenge_id AND team_id IS NOT NULL;" | tr -d '[:space:]')
[[ "$team_solves" == "$solve_rows" ]] \
  || { echo "FAIL: the same team scored the challenge more than once"; exit 1; }
echo "PASS: each team scored the challenge at most once"

activity=$(db_query "SELECT COUNT(*) FROM hikari_activity WHERE competition_key='$run_key';" | tr -d '[:space:]')
[[ "$activity" -ge 6 ]] || { echo "FAIL: activity for this run is too sparse ($activity)"; exit 1; }
query_actors=$(db_query "SELECT COUNT(DISTINCT actor_id) FROM hikari_activity WHERE competition_key='$run_key' AND event_type='kibana.query';" | tr -d '[:space:]')
[[ "$query_actors" == "6" ]] || { echo "FAIL: expected SIEM queries from six competitors, found $query_actors"; exit 1; }
echo "PASS: $activity activity records for this run, including queries from six competitors"

# --- 6. controls applied while people play ---------------------------------

echo
echo "== 6. extension, pause and resume during the competition =="
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
ends_before=$(db_query "SELECT FLOOR(UNIX_TIMESTAMP(ends_at)) FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/adjust" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" \
  --data-urlencode "adjust_minutes=90")
[[ "$code" == "302" ]] || { echo "FAIL: extension returned $code"; exit 1; }
ends_after=$(db_query "SELECT FLOOR(UNIX_TIMESTAMP(ends_at)) FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ $((ends_after - ends_before)) -eq 5400 ]] \
  || { echo "FAIL: expected 90 more minutes, got $(( (ends_after - ends_before) / 60 ))"; exit 1; }
echo "PASS: 90 minutes added to the schedule"

curl -sS -c "$admin_jar" -b "$admin_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/pause" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")"
status=$(db_query "SELECT status FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$status" == "paused" ]] || { echo "FAIL: expected status paused, found $status"; exit 1; }

csrf=$(player_csrf 5)
jar="$workspace/player-5.jar"
attempt=$(curl -sS -c "$jar" -b "$jar" \
  -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
  -X POST "$CTFD_URL/api/v1/challenges/attempt" \
  -d "{\"challenge_id\":$challenge_id,\"submission\":\"$challenge_flag\"}")
paused_status=$(echo "$attempt" | jq -r '.data.status // empty')
[[ "$paused_status" != "correct" ]] \
  || { echo "FAIL: a flag was accepted while the competition was paused"; exit 1; }
echo "PASS: submissions refused while paused"

curl -sS -c "$admin_jar" -b "$admin_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/resume" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")"
status=$(db_query "SELECT status FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$status" == "running" ]] || { echo "FAIL: expected status running after resume, found $status"; exit 1; }
echo "PASS: competition resumed"

# --- 7. feedback and closing ------------------------------------------------

echo
echo "== 7. feedback, closing and research data =="
jar="$workspace/player-1.jar"
page="$workspace/feedback.html"
curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/hikari/feedback"
code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/hikari/feedback" \
  --data-urlencode "nonce=$(extract_nonce "$page")" \
  --data-urlencode "phase=post" \
  --data-urlencode "years_cyber_experience=3_5" \
  --data-urlencode "primary_role=soc_analyst_t2" \
  --data-urlencode "tlx_mental_demand=5" \
  --data-urlencode "sus_easy_to_use=4" \
  --data-urlencode "nps_recommend=9")
[[ "$code" == "302" ]] || { echo "FAIL: feedback submission returned $code"; exit 1; }
feedback_rows=$(db_query "SELECT COUNT(*) FROM hikari_feedback_responses WHERE competition_key='$run_key';" | tr -d '[:space:]')
[[ "$feedback_rows" -ge 1 ]] || { echo "FAIL: feedback was not attributed to this run"; exit 1; }
echo "PASS: feedback recorded against run $run_key"

curl -sS -c "$admin_jar" -b "$admin_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/finish" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: closing returned $code"; exit 1; }
status=$(db_query "SELECT status FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$status" == "finished" ]] || { echo "FAIL: expected status finished, found $status"; exit 1; }

csrf=$(player_csrf 6)
jar="$workspace/player-6.jar"
attempt=$(curl -sS -c "$jar" -b "$jar" \
  -H "Content-Type: application/json" -H "Csrf-Token: $csrf" \
  -X POST "$CTFD_URL/api/v1/challenges/attempt" \
  -d "{\"challenge_id\":$challenge_id,\"submission\":\"$challenge_flag\"}")
closed_status=$(echo "$attempt" | jq -r '.data.status // empty')
[[ "$closed_status" != "correct" ]] \
  || { echo "FAIL: a flag was accepted after the competition closed"; exit 1; }
echo "PASS: submissions refused after closing"

winner=$(db_query "SELECT t.name FROM teams t JOIN solves s ON s.team_id = t.id
  WHERE s.challenge_id=$challenge_id GROUP BY t.id ORDER BY COUNT(s.id) DESC LIMIT 1;" | tr -d '\n')
[[ -n "$winner" ]] || { echo "FAIL: the scoreboard produced no leading team"; exit 1; }
echo "PASS: leading team readable from the scoreboard: $winner"

export_file="$workspace/activity.jsonl"
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$export_file" \
  "$CTFD_URL/admin/hikari/research/export.jsonl?competition_key=$run_key"
grep -q "$run_key" "$export_file" \
  || { echo "FAIL: the activity export carries no record of this run"; exit 1; }
grep -Fq "$challenge_flag" "$export_file" \
  && { echo "FAIL: the activity export contains a submitted flag"; exit 1; }
lines=$(grep -c "$run_key" "$export_file")
echo "PASS: research export carries $lines record(s) from this run without submitted flags"

echo
echo "Competition simulated end to end: registration, teams with approval, blocked start, parallel play, extension, pause, resume, closing, feedback and research export."
