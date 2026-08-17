#!/usr/bin/env bash
# Full-event rehearsal: every action a real event performs, in the real order,
# checked from the point of view of each audience.
#
#   administrator  prepares challenges with a dependency, controls the clock,
#                  shortens it, ends the run early, exports and archives
#   competitors    three teams of three, two and one person, captain approval,
#                  progressive unlock, dirtier haystack, right and wrong flags
#   sponsors       the public live board, standings and recent solves
#
# What this rehearsal cannot replace is judgement: it performs the same set of
# actions a person performs, but it never gets confused, misreads a screen or
# hesitate. It proves the mechanics hold, not that the experience is clear.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

if [[ "${HIKARI_ACCEPTANCE_CONTEXT:-}" != "1" \
  && "${HIKARI_ALLOW_MUTATING_ACCEPTANCE:-}" != "1" ]]; then
  echo "Refusing to rehearse an event on the active stack." >&2
  echo "It would leave rehearsal competitors and teams beside real accounts." >&2
  echo "Run: bash tests/acceptance_isolated.sh" >&2
  exit 2
fi

ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}

stamp=$(date +%s)
run_key="ensaio-$stamp"
workspace=$(mktemp -d)
admin_jar="$workspace/admin.jar"
trap 'rm -rf "$workspace"' EXIT

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; exit 1; }

# grep leaves with 1 when nothing matched and with 2 when it could not read the
# file. Only the first is a zero count; the second has to surface.
count_lines_matching() {
  local pattern=$1 file=$2
  local matches grep_status
  matches=$(grep -c "$pattern" "$file") && grep_status=0 || grep_status=$?
  case $grep_status in
    0) printf '%s' "$matches" ;;
    1) printf '0' ;;
    *) fail "could not read $file while counting occurrences of '$pattern'" ;;
  esac
}

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

extract_csrf() {
  grep -oE "'csrfNonce':[[:space:]]*\"[0-9a-f]+\"" "$1" \
    | head -1 | sed -E 's/.*"([0-9a-f]+)".*/\1/'
}

db_query() {
  hikari_mariadb -N -B -e "$1" | tr -d '\r'
}

flush_rate_limit() {
  hikari_compose exec -T cache redis-cli FLUSHALL > /dev/null
}

siem_documents() {
  hikari_compose exec -T elasticsearch curl -fsS \
    "http://localhost:9200/competition1/_count" \
    | jq '.count'
}

siem_marker_hits() {
  local marker=$1
  local query
  query=$(jq -cn --arg marker "$marker" '{query:{match_phrase:{marker:$marker}}}')
  hikari_compose exec -T elasticsearch curl -fsS \
    -H 'Content-Type: application/json' \
    -X POST 'http://localhost:9200/competition1/_search' -d "$query" \
    | jq -r '.hits.total.value // 0'
}

wait_for_siem_marker() {
  local marker=$1
  local deadline=$((SECONDS + 30))
  local hits
  while (( SECONDS < deadline )); do
    hits=$(siem_marker_hits "$marker")
    if [[ "$hits" -ge 1 ]]; then
      printf '%s\n' "$hits"
      return 0
    fi
    sleep 2
  done
  return 1
}

admin_get() {
  curl -sS -c "$admin_jar" -b "$admin_jar" -o "$1" "$CTFD_URL$2"
}

admin_post() {
  local path=$1; shift
  curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL$path" \
    --data-urlencode "nonce=$(extract_nonce "$workspace/dashboard.html")" "$@"
}

# --- competitor actors ------------------------------------------------------

register_competitor() {
  local index=$1
  local jar="$workspace/player-$index.jar"
  local page="$workspace/register-$index.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/register"
  local code
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/register" \
    --data-urlencode "name=jogador_${index}_${stamp}" \
    --data-urlencode "email=jogador_${index}_${stamp}@hikari.local" \
    --data-urlencode "password=senha-${index}-${stamp}" \
    --data-urlencode "nonce=$(extract_nonce "$page")")
  [[ "$code" == "302" ]] || fail "registration of competitor $index returned $code"
}

create_team() {
  local captain=$1 name=$2
  local jar="$workspace/player-$captain.jar"
  local page="$workspace/team-$captain.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/teams/new"
  local code
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/teams/new" \
    --data-urlencode "name=$name" \
    --data-urlencode "nonce=$(extract_nonce "$page")")
  [[ "$code" == "302" ]] || fail "team creation by competitor $captain returned $code"
  db_query "SELECT id FROM teams WHERE name='$name';" | tr -d '[:space:]'
}

request_entry() {
  local member=$1 team=$2
  local jar="$workspace/player-$member.jar"
  local page="$workspace/join-$member.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/hikari/teams/join"
  local code
  code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
    -X POST "$CTFD_URL/hikari/teams/$team/request" \
    --data-urlencode "nonce=$(extract_nonce "$page")")
  [[ "$code" == "302" ]] || fail "team-entry request by competitor $member returned $code"
}

approve_entries() {
  local captain=$1
  local jar="$workspace/player-$captain.jar"
  local page="$workspace/approve-$captain.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/hikari/team/requests"
  local request_id
  for request_id in $(grep -oE '/hikari/team/requests/[0-9]+/approve' "$page" \
                      | grep -oE '[0-9]+' | sort -u); do
    local code
    code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
      -X POST "$CTFD_URL/hikari/team/requests/$request_id/approve" \
      --data-urlencode "nonce=$(extract_nonce "$page")")
    [[ "$code" == "302" ]] || fail "approval for request $request_id returned $code"
  done
}

submit_flag() {
  local index=$1 challenge=$2 flag=$3
  local jar="$workspace/player-$index.jar"
  local page="$workspace/challenges-$index.html"
  curl -sS -c "$jar" -b "$jar" -o "$page" "$CTFD_URL/challenges"
  curl -sS -c "$jar" -b "$jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $(extract_csrf "$page")" \
    -X POST "$CTFD_URL/api/v1/challenges/attempt" \
    -d "{\"challenge_id\":$challenge,\"submission\":\"$flag\"}"
}

# CTFd answers a refused submission with HTTP 403 and success=false, and a
# judged submission with success=true plus the verdict in data.status. Reading
# "success" alone would call a wrong flag a solve.
attempt_verdict() {
  jq -r 'if .success then .data.status else "refused" end' <<< "$1"
}

hunt_in_siem() {
  local index=$1
  local jar="$workspace/player-$index.jar"
  curl -sS -c "$jar" -b "$jar" -o /dev/null "$CTFD_URL/hikari/kibana/app/discover"
  curl -sS -c "$jar" -b "$jar" -o /dev/null \
    -H "Content-Type: application/json" -H "kbn-xsrf: true" \
    -X POST "$CTFD_URL/hikari/kibana/internal/search/ese" \
    -d "{\"params\":{\"index\":\"competition1\",\"body\":{\"query\":{\"query_string\":{\"query\":\"event.action:logon AND source.ip:10.0.0.$index\"}}}}}"
}

# ===========================================================================
echo "== ATO 1. o administrador prepara a edição =="
# ===========================================================================

flush_rate_limit
page="$workspace/login.html"
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" "$CTFD_URL/login"
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$(extract_nonce "$page")")
[[ "$code" == "302" ]] || fail "administrator login returned $code"

admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
active_id=$(grep -oE "/admin/hikari/competitions/[0-9]+/finish" "$workspace/dashboard.html" \
  | head -1 | grep -oE '[0-9]+' || true)
if [[ -n "$active_id" ]]; then
  admin_post "/admin/hikari/competitions/$active_id/finish" > /dev/null
  admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
fi

admin_csrf=$(extract_csrf "$workspace/dashboard.html")
[[ -n "$admin_csrf" ]] || fail "no CSRF token for the administrator API"

api_post() {
  curl -sS -c "$admin_jar" -b "$admin_jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $admin_csrf" \
    -X POST "$CTFD_URL$1" -d "$2"
}

create_hikari_challenge() {
  local name=$1 description=$2 value=$3 log_file=$4
  local response="$workspace/add-$(date +%s%N).html"
  local code
  code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o "$response" -w '%{http_code}' \
    -X POST "$CTFD_URL/admin/hikari/add-challenge" \
    -F "name=$name" \
    -F 'category=Ensaio' \
    -F "description=$description" \
    -F "value=$value" \
    -F 'type=hikari' \
    -F "nonce=$admin_csrf" \
    -F "file_log=@$log_file")
  [[ "$code" == "302" ]] || fail "creating Hikari challenge '$name' returned $code"
  db_query "SELECT id FROM challenges WHERE name='$name';" | tr -d '[:space:]'
}

# CTFd stores the dependency on the challenge itself. Check the status code so
# a rejected update cannot be mistaken for a successful prerequisite setup.
set_challenge_requirements() {
  local challenge_id=$1 prerequisite_id=$2
  local status
  status=$(curl -sS -o /dev/null -w '%{http_code}' -c "$admin_jar" -b "$admin_jar" \
    -H "Content-Type: application/json" -H "Csrf-Token: $admin_csrf" \
    -X PATCH "$CTFD_URL/api/v1/challenges/$challenge_id" \
    -d "{\"requirements\":{\"prerequisites\":[$prerequisite_id]}}")
  [[ "$status" =~ ^2 ]] \
    || fail "setting the prerequisite for challenge $challenge_id returned $status"
}

# Two Hikari challenges: the second has both a challenge prerequisite and an
# associated log set that must be released only after the first solve.
gateway_flag="hikari{ensaio-porta-$stamp}"
deep_flag="hikari{ensaio-profundo-$stamp}"
gateway_marker="ensaio-porta-marker-$stamp"
deep_marker="ensaio-profundo-marker-$stamp"
gateway_log="$workspace/gateway.json"
deep_log="$workspace/deep.json"
printf '[{"marker":"%s","event.action":"logon","source.ip":"10.0.0.1"}]\n' \
  "$gateway_marker" > "$gateway_log"
printf '[{"marker":"%s","event.action":"lateral_movement","source.ip":"10.0.0.2"}]\n' \
  "$deep_marker" > "$deep_log"

gateway_id=$(create_hikari_challenge "Acesso inicial $stamp" \
  'Identifique o primeiro acesso suspeito.' 100 "$gateway_log")
[[ -n "$gateway_id" ]] || fail "gateway Hikari challenge was not created"
api_post "/api/v1/flags" \
  "{\"challenge\":$gateway_id,\"type\":\"static\",\"content\":\"$gateway_flag\"}" > /dev/null

deep_id=$(create_hikari_challenge "Movimentação lateral $stamp" \
  'Siga o atacante depois do acesso inicial.' 300 "$deep_log")
[[ -n "$deep_id" ]] || fail "dependent Hikari challenge was not created"
api_post "/api/v1/flags" \
  "{\"challenge\":$deep_id,\"type\":\"static\",\"content\":\"$deep_flag\"}" > /dev/null

set_challenge_requirements "$deep_id" "$gateway_id"

requirements=$(db_query "SELECT requirements FROM challenges WHERE id=$deep_id;")
[[ "$requirements" == *"$gateway_id"* ]] \
  || fail "the dependency between the two challenges was not stored"
pass "two challenges created, the second depending on the first"

code=$(admin_post "/admin/hikari/competitions" \
  --data-urlencode "key=$run_key" \
  --data-urlencode "name=Ensaio operacional $stamp" \
  --data-urlencode "scoring_mode=teams" \
  --data-urlencode "duration_minutes=240")
[[ "$code" == "302" ]] || fail "creating the run returned $code"
admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
run_id=$(grep -oE "/admin/hikari/competitions/[0-9]+/start" "$workspace/dashboard.html" \
  | head -1 | grep -oE '[0-9]+')
[[ -n "$run_id" ]] || fail "the created run is not on the dashboard"
pass "run $run_id created as a draft, play still closed"

# ===========================================================================
echo
echo "== ATO 2. inscrições: três equipes de três, duas e uma pessoa =="
# ===========================================================================

for index in 1 2 3 4 5 6; do
  register_competitor "$index"
done
pass "six competitors registered while the competition had not started"

team_alfa=$(create_team 1 "equipe_alfa_$stamp")
team_beta=$(create_team 4 "equipe_beta_$stamp")
team_solo=$(create_team 6 "equipe_solo_$stamp")
pass "three teams created, including a one-person team"

request_entry 2 "$team_alfa"
request_entry 3 "$team_alfa"
request_entry 5 "$team_beta"

pending=$(db_query "SELECT COUNT(*) FROM hikari_team_membership_requests WHERE status='pending';" | tr -d '[:space:]')
[[ "$pending" == "3" ]] || fail "expected 3 pending entry requests, found $pending"
joined=$(db_query "SELECT COUNT(*) FROM users WHERE name LIKE 'jogador\_%\_$stamp' AND team_id IS NOT NULL;" | tr -d '[:space:]')
[[ "$joined" == "3" ]] || fail "a request alone put someone on a team ($joined members)"
pass "entry requests are pending and grant no membership on their own"

approve_entries 1
approve_entries 4
alfa_size=$(db_query "SELECT COUNT(*) FROM users WHERE team_id=$team_alfa;" | tr -d '[:space:]')
beta_size=$(db_query "SELECT COUNT(*) FROM users WHERE team_id=$team_beta;" | tr -d '[:space:]')
solo_size=$(db_query "SELECT COUNT(*) FROM users WHERE team_id=$team_solo;" | tr -d '[:space:]')
[[ "$alfa_size" == "3" && "$beta_size" == "2" && "$solo_size" == "1" ]] \
  || fail "team sizes after approval were $alfa_size/$beta_size/$solo_size, expected 3/2/1"
pass "captains approved their members: teams of 3, 2 and 1"

# ===========================================================================
echo
echo "== ATO 3. antes do start, ninguém joga =="
# ===========================================================================

attempt=$(submit_flag 1 "$gateway_id" "$gateway_flag")
[[ "$(attempt_verdict "$attempt")" != "correct" ]] \
  || fail "a flag was accepted before the competition started"
siem_code=$(curl -sS -c "$workspace/player-1.jar" -b "$workspace/player-1.jar" \
  -o /dev/null -w '%{http_code}' "$CTFD_URL/hikari/siem")
[[ "$siem_code" == "403" ]] || fail "the SIEM answered $siem_code before the start"
# Earlier steps of the suite leave their own solves in this disposable stack,
# so only the two challenges of this rehearsal can be counted here.
solves_before=$(db_query "SELECT COUNT(*) FROM solves
  WHERE challenge_id IN ($gateway_id, $deep_id);" | tr -d '[:space:]')
[[ "$solves_before" == "0" ]] \
  || fail "$solves_before solve(s) on the rehearsal challenges existed before the start"
pass "submissions refused and SIEM closed before the start"

# ===========================================================================
echo
echo "== ATO 4. o administrador dá o start =="
# ===========================================================================

admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
code=$(admin_post "/admin/hikari/competitions/$run_id/start" \
  --data-urlencode "start_mode=now")
[[ "$code" == "302" ]] || fail "starting the run returned $code"
status=$(db_query "SELECT status FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$status" == "running" ]] || fail "the run is $status instead of running"
siem_code=$(curl -sS -c "$workspace/player-1.jar" -b "$workspace/player-1.jar" \
  -o /dev/null -w '%{http_code}' "$CTFD_URL/hikari/siem")
[[ "$siem_code" == "200" ]] || fail "the SIEM answered $siem_code after the start"
pass "competition running and the SIEM open to competitors"

gateway_hits=$(wait_for_siem_marker "$gateway_marker") \
  || fail "the initial Hikari log set was not indexed after the competition start"
deep_hits_before=$(siem_marker_hits "$deep_marker")
[[ "$deep_hits_before" == "0" ]] \
  || fail "the dependent Hikari log set appeared before its prerequisite was solved"
pass "initial logs available; dependent logs withheld until the prerequisite solve"

# ===========================================================================
echo
echo "== ATO 5. os competidores investigam e resolvem =="
# ===========================================================================

haystack_before=$(siem_documents)

# The dependent challenge must not even be reachable before its prerequisite.
early=$(submit_flag 2 "$deep_id" "$deep_flag")
[[ "$(attempt_verdict "$early")" != "correct" ]] \
  || fail "the dependent challenge was solved before its prerequisite"
pass "the dependent challenge refuses submissions while locked"

for index in 1 2 3 4 5 6; do
  hunt_in_siem "$index" &
done
wait
pass "six competitors queried the SIEM at the same time"

wrong=$(submit_flag 3 "$gateway_id" "hikari{palpite-errado}")
[[ "$(attempt_verdict "$wrong")" == "incorrect" ]] \
  || fail "a wrong flag got verdict '$(attempt_verdict "$wrong")' instead of incorrect"

for solver in 1 4 6; do
  result=$(submit_flag "$solver" "$gateway_id" "$gateway_flag")
  [[ "$(attempt_verdict "$result")" == "correct" ]] \
    || fail "competitor $solver got verdict '$(attempt_verdict "$result")' on the gateway challenge"
done
pass "each team solved the first challenge, wrong flags rejected"

# With the prerequisite solved the second challenge opens up.
# A teammate, not the original solver, continues the investigation. This
# proves that team scoring and progressive challenges share team progress.
after_unlock=$(submit_flag 2 "$deep_id" "$deep_flag")
[[ "$(attempt_verdict "$after_unlock")" == "correct" ]] \
  || fail "the dependent challenge stayed locked after its prerequisite"
pass "solving the prerequisite unlocked the dependent challenge"

deep_hits_after=$(wait_for_siem_marker "$deep_marker") \
  || fail "the dependent Hikari log set was not indexed after the prerequisite solve"
[[ "$deep_hits_after" -gt "$deep_hits_before" ]] \
  || fail "the dependent log count did not increase after the prerequisite solve"
pass "the prerequisite solve released the next Hikari log set"

haystack_after=$(siem_documents)
echo "  palheiro do SIEM: $haystack_before -> $haystack_after documento(s)"

solves=$(db_query "SELECT COUNT(*) FROM solves
  WHERE challenge_id IN ($gateway_id, $deep_id);" | tr -d '[:space:]')
[[ "$solves" -ge 4 ]] || fail "expected at least 4 solves, found $solves"
per_team=$(db_query "SELECT COUNT(*) FROM (SELECT team_id, challenge_id FROM solves
                      WHERE challenge_id IN ($gateway_id, $deep_id)
                      GROUP BY team_id, challenge_id HAVING COUNT(*) > 1) AS repeated;" | tr -d '[:space:]')
[[ "$per_team" == "0" ]] || fail "a team scored the same challenge more than once"
pass "$solves solve(s) recorded, none counted twice for the same team"

# ===========================================================================
echo
echo "== ATO 6. a experiência de quem assiste =="
# ===========================================================================

code=$(curl -sS -o /dev/null -w '%{http_code}' "$CTFD_URL/hikari/live")
[[ "$code" == "200" ]] || fail "the live board answered $code to an anonymous visitor"

# The page renders in the browser, so the standings a sponsor actually sees
# come from this endpoint rather than from the served HTML.
board="$workspace/live.json"
code=$(curl -sS -o "$board" -w '%{http_code}' "$CTFD_URL/hikari/live/data")
[[ "$code" == "200" ]] || fail "the live board data answered $code to an anonymous visitor"

jq -e --arg team "equipe_alfa_$stamp" \
  '[.team_standings[].name] | index($team)' "$board" > /dev/null \
  || fail "the leading team is absent from the live board data"
jq -e '(.individual_standings | length) > 0' "$board" > /dev/null \
  || fail "the live board omits individual contribution"
jq -e '(.recent_solves | length) > 0' "$board" > /dev/null \
  || fail "the live board omits recent solves"
pass "an anonymous visitor sees teams, individual contribution and recent solves"

# Three teams solved the gateway challenge, so exactly one of those solves is
# the first. Marking two, or none, would misinform everyone watching.
first_bloods=$(jq --arg name "Acesso inicial $stamp" \
  '[.recent_solves[] | select(.challenge_name == $name and .first_blood)] | length' "$board")
[[ "$first_bloods" == "1" ]] \
  || fail "the gateway challenge shows $first_bloods first bloods instead of exactly one"
pass "the first team to solve a challenge is marked on the board"

redirect_target=$(curl -sS -o /dev/null -w '%{redirect_url}' "$CTFD_URL/scoreboard")
[[ "${redirect_target#"$CTFD_URL"}" == "/hikari/live" ]] \
  || fail "the old scoreboard redirected to '$redirect_target' instead of the live board"
pass "the scoreboard route sends visitors to the single live board"

# ===========================================================================
echo
echo "== ATO 7. o administrador controla o relógio =="
# ===========================================================================

ends_before=$(db_query "SELECT FLOOR(UNIX_TIMESTAMP(ends_at)) FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
code=$(admin_post "/admin/hikari/competitions/$run_id/adjust" --data-urlencode "adjust_minutes=90")
[[ "$code" == "302" ]] || fail "extending returned $code"
ends_after=$(db_query "SELECT FLOOR(UNIX_TIMESTAMP(ends_at)) FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ $((ends_after - ends_before)) -eq 5400 ]] \
  || fail "expected 90 more minutes, got $(((ends_after - ends_before) / 60))"
pass "90 minutes added"

admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
code=$(admin_post "/admin/hikari/competitions/$run_id/adjust" --data-urlencode "adjust_minutes=-60")
[[ "$code" == "302" ]] || fail "shortening returned $code"
ends_shorter=$(db_query "SELECT FLOOR(UNIX_TIMESTAMP(ends_at)) FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ $((ends_after - ends_shorter)) -eq 3600 ]] \
  || fail "expected 60 fewer minutes, got $(((ends_after - ends_shorter) / 60))"
pass "60 minutes removed"

admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
admin_post "/admin/hikari/competitions/$run_id/adjust" --data-urlencode "adjust_minutes=-270" > /dev/null
still_running=$(db_query "SELECT status FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$still_running" == "running" ]] || fail "an absurd shortening ended the competition"
ends_after_rejected_shortening=$(db_query "SELECT FLOOR(UNIX_TIMESTAMP(ends_at)) FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$ends_after_rejected_shortening" == "$ends_shorter" ]] \
  || fail "a shortening below the minimum remaining time changed the deadline"
pass "a shortening below five minutes remaining is refused"

admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
admin_post "/admin/hikari/competitions/$run_id/pause" > /dev/null
paused=$(submit_flag 4 "$deep_id" "$deep_flag")
[[ "$(attempt_verdict "$paused")" != "correct" ]] || fail "a flag was accepted while paused"
admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
admin_post "/admin/hikari/competitions/$run_id/resume" > /dev/null
status=$(db_query "SELECT status FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$status" == "running" ]] || fail "the run is $status after resume"
pass "pause refuses submissions and resume restores play"

# ===========================================================================
echo
echo "== ATO 8. encerramento antecipado e feedback =="
# ===========================================================================

feedback_jar="$workspace/player-1.jar"
page="$workspace/feedback.html"
curl -sS -c "$feedback_jar" -b "$feedback_jar" -o "$page" "$CTFD_URL/hikari/feedback"
code=$(curl -sS -c "$feedback_jar" -b "$feedback_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/hikari/feedback" \
  --data-urlencode "nonce=$(extract_nonce "$page")" \
  --data-urlencode "phase=post" \
  --data-urlencode "years_cyber_experience=3_5" \
  --data-urlencode "primary_role=soc_analyst_t2" \
  --data-urlencode "tlx_mental_demand=5" \
  --data-urlencode "sus_easy_to_use=4" \
  --data-urlencode "nps_recommend=9")
[[ "$code" == "302" ]] || fail "feedback submission returned $code"
pass "feedback accepted with the optional multiselect left empty"

admin_get "$workspace/dashboard.html" "/admin/hikari/competitions"
code=$(admin_post "/admin/hikari/competitions/$run_id/finish")
[[ "$code" == "302" ]] || fail "ending the run early returned $code"
status=$(db_query "SELECT status FROM hikari_competition_runs WHERE id=$run_id;" | tr -d '[:space:]')
[[ "$status" == "finished" ]] || fail "the run is $status after finishing"
late=$(submit_flag 5 "$gateway_id" "$gateway_flag")
[[ "$(attempt_verdict "$late")" != "correct" ]] || fail "a flag was accepted after the run ended"
pass "the run ended early and submissions stopped"

# ===========================================================================
echo
echo "== ATO 9. os dados da edição sobrevivem =="
# ===========================================================================

export_file="$workspace/export.jsonl"
curl -fsS -c "$admin_jar" -b "$admin_jar" -o "$export_file" \
  "$CTFD_URL/admin/hikari/research/export.jsonl?competition_key=$run_key"
records=$(count_lines_matching "$run_key" "$export_file")
[[ "$records" -gt 0 ]] || fail "the research export carries no record of this run"
head -1 "$export_file" | python3 -c 'import json,sys; json.loads(sys.stdin.read())' \
  || fail "the research export is not readable as JSON"

kibana_events=$(db_query "SELECT COUNT(*) FROM hikari_activity
  WHERE competition_key='$run_key' AND event_type LIKE 'kibana.%';" | tr -d '[:space:]')
[[ "$kibana_events" -ge 6 ]] \
  || fail "only $kibana_events SIEM event(s) attributed, expected one per competitor"
pass "$records record(s) exported, $kibana_events of them SIEM queries with attribution"

feedback_file="$workspace/feedback.jsonl"
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$feedback_file" \
  "$CTFD_URL/admin/hikari/research/feedback.jsonl?competition_key=$run_key"
[[ -s "$feedback_file" ]] || fail "the feedback export is empty"
pass "feedback exported for this run"

challenges_kept=$(db_query "SELECT COUNT(*) FROM challenges;" | tr -d '[:space:]')
echo
echo "Ensaio operacional concluído."
echo "  equipes: 3 (de 3, 2 e 1 pessoa)   solves: $solves   desafios preservados: $challenges_kept"
