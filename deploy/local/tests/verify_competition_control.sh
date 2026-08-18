#!/usr/bin/env bash
# Verifies the administrative lifecycle for one isolated competition run.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"
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
  hikari_compose exec -T db mariadb -N -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" \
    -e "SELECT TIMESTAMPDIFF(MINUTE, starts_at, ends_at) FROM hikari_competition_runs WHERE \`key\` = '$run_key';" \
    | tr -d '\r\n'
}

# The dashboard lists every execution, so picking an id by its position in the
# page silently targets whichever draft happens to sit there. The key is what
# identifies the execution this test created.
run_id_for_key() {
  hikari_mariadb -N \
    -e "SELECT id FROM hikari_competition_runs WHERE \`key\` = '$1';" \
    | tr -d '\r\n'
}

run_status() {
  hikari_compose exec -T db mariadb -N -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" \
    -e "SELECT status FROM hikari_competition_runs WHERE \`key\` = '$run_key';" \
    | tr -d '\r\n'
}

configured_start() {
  hikari_compose exec -T db mariadb -N -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" \
    -e "SELECT value FROM config WHERE \`key\` = 'start';" \
    | tr -d '\r\n'
}

remaining_seconds() {
  hikari_compose exec -T db mariadb -N -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" \
    -e "SELECT COALESCE(paused_remaining_seconds, '') FROM hikari_competition_runs WHERE \`key\` = '$run_key';" \
    | tr -d '\r\n'
}

active_test_run() {
  hikari_compose exec -T db mariadb -N -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" \
    -e "SELECT id, \`key\` FROM hikari_competition_runs WHERE status IN ('scheduled', 'running', 'paused') ORDER BY id DESC LIMIT 1;" \
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
  --data-urlencode "duration_hours=4" \
  --data-urlencode "duration_minutes=0")
[[ "$code" == "302" ]] || { echo "FAIL: create run returned $code"; exit 1; }

dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
run_id=$(run_id_for_key "$run_key")
[[ -n "$run_id" ]] || { echo "FAIL: created run was not persisted"; exit 1; }
grep -q "/admin/hikari/competitions/$run_id/start" "$dashboard" \
  || { echo "FAIL: start action missing for created run"; exit 1; }
nonce=$(extract_nonce "$dashboard")
[[ -n "$nonce" ]] || { echo "FAIL: competition nonce missing"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/schedule" \
  --data-urlencode "nonce=$nonce" \
  --data-urlencode "starts_at=2099-01-01T14:00")
[[ "$code" == "302" ]] || { echo "FAIL: schedule run returned $code"; exit 1; }
[[ "$(run_status)" == "scheduled" ]] || { echo "FAIL: execution was not scheduled"; exit 1; }
expected_start=$(date -j -f '%Y-%m-%dT%H:%M %Z' '2099-01-01T14:00 America/Sao_Paulo' '+%s' 2>/dev/null || true)
if [[ -n "$expected_start" ]]; then
  [[ "$(configured_start)" == "$expected_start" ]] \
    || { echo "FAIL: schedule did not store the configured local time"; exit 1; }
fi

dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/start" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "FAIL: start run returned $code"; exit 1; }

dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
grep -q "$run_key" "$dashboard" || { echo "FAIL: execution key not rendered"; exit 1; }
grep -q "Ajuste de prazo em minutos" "$dashboard" \
  || { echo "FAIL: deadline adjustment control missing"; exit 1; }
grep -q "Positivo estende, negativo encurta" "$dashboard" \
  || { echo "FAIL: deadline adjustment guidance missing"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$run_id/adjust" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" \
  --data-urlencode "adjust_minutes=90")
[[ "$code" == "302" ]] || { echo "FAIL: extend run returned $code"; exit 1; }

duration_minutes=$(run_duration_minutes)
[[ "$duration_minutes" =~ ^[0-9]+$ ]] \
  || { echo "FAIL: execution schedule was not persisted"; exit 1; }
[[ "$duration_minutes" -ge 330 ]] \
  || { echo "FAIL: expected a five-and-a-half-hour execution after extension, got $duration_minutes minutes"; exit 1; }

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

# A cancelled schedule must not restore CTFd's unrestricted 0/0 window.
cancel_key="${run_key}-cancelled"
dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" \
  --data-urlencode "key=$cancel_key" \
  --data-urlencode "name=Cancelled Run $stamp" \
  --data-urlencode "scoring_mode=teams" \
  --data-urlencode "duration_hours=4" \
  --data-urlencode "duration_minutes=0")
[[ "$code" == "302" ]] || { echo "FAIL: cancellation test run creation returned $code"; exit 1; }

curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
cancel_id=$(run_id_for_key "$cancel_key")
[[ -n "$cancel_id" ]] || { echo "FAIL: cancellation test run was not persisted"; exit 1; }
grep -q "/admin/hikari/competitions/$cancel_id/schedule" "$dashboard" \
  || { echo "FAIL: cancellation test run lacks schedule action"; exit 1; }
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$cancel_id/schedule" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" \
  --data-urlencode "starts_at=2099-01-01T14:00")
[[ "$code" == "302" ]] || { echo "FAIL: cancellation test schedule returned $code"; exit 1; }

curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$cancel_id/cancel" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: cancellation returned $code"; exit 1; }
cancelled_status=$(hikari_compose exec -T db mariadb -N -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" \
  -e "SELECT status FROM hikari_competition_runs WHERE \`key\` = '$cancel_key';" | tr -d '\r\n')
[[ "$cancelled_status" == "cancelled" ]] || { echo "FAIL: scheduled execution was not cancelled"; exit 1; }
[[ "$(configured_start)" -gt "$(date +%s)" ]] \
  || { echo "FAIL: cancellation reopened the CTFd play window"; exit 1; }

# An execution opened by mistake has to be reversible, and the undo has to stop
# being available the moment the competition becomes real history.
revert_key="${run_key}-revert"
dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" \
  --data-urlencode "key=$revert_key" \
  --data-urlencode "name=Revert Run $stamp" \
  --data-urlencode "scoring_mode=teams" \
  --data-urlencode "duration_hours=4" \
  --data-urlencode "duration_minutes=0")
[[ "$code" == "302" ]] || { echo "FAIL: revert test run creation returned $code"; exit 1; }

revert_status() {
  hikari_mariadb -N \
    -e "SELECT status FROM hikari_competition_runs WHERE \`key\` = '$revert_key';" \
    | tr -d '\r\n'
}

curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
revert_id=$(run_id_for_key "$revert_key")
[[ -n "$revert_id" ]] || { echo "FAIL: revert test run was not persisted"; exit 1; }
grep -q "/admin/hikari/competitions/$revert_id/schedule" "$dashboard" \
  || { echo "FAIL: revert test run lacks schedule action"; exit 1; }

# A draft offers no undo, because there is nothing to undo.
grep -q "/admin/hikari/competitions/$revert_id/revert" "$dashboard" \
  && { echo "FAIL: draft execution offers a revert action"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$revert_id/start" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: revert test start returned $code"; exit 1; }
[[ "$(revert_status)" == "running" ]] || { echo "FAIL: revert test run did not start"; exit 1; }

curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
grep -q "/admin/hikari/competitions/$revert_id/revert" "$dashboard" \
  || { echo "FAIL: running execution offers no revert action"; exit 1; }
grep -q "Voltar para rascunho" "$dashboard" \
  || { echo "FAIL: revert control is not labelled for the operator"; exit 1; }

started_window=$(configured_start)
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$revert_id/revert" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: revert returned $code"; exit 1; }
[[ "$(revert_status)" == "draft" ]] || { echo "FAIL: execution did not return to draft"; exit 1; }

# Returning to draft has to close play again, not leave the started window open.
[[ "$(configured_start)" != "$started_window" ]] \
  || { echo "FAIL: revert left the started play window in place"; exit 1; }
[[ "$(configured_start)" -gt "$(date +%s)" ]] \
  || { echo "FAIL: revert left the CTFd play window open"; exit 1; }

schedule_cleared=$(hikari_mariadb -N \
  -e "SELECT COALESCE(starts_at, 'vazio') FROM hikari_competition_runs WHERE \`key\` = '$revert_key';" \
  | tr -d '\r\n')
[[ "$schedule_cleared" == "vazio" ]] \
  || { echo "FAIL: revert kept the previous start time"; exit 1; }

# The undo is refused once the execution has recorded a score.
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$revert_id/start" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")")
[[ "$code" == "302" ]] || { echo "FAIL: restart for the submission guard returned $code"; exit 1; }

# The start time carries microseconds, and NOW() would round down to the second
# it shares with it, landing the submission before the execution it belongs to.
hikari_mariadb \
  -e "INSERT INTO submissions (challenge_id, user_id, team_id, ip, provided, type, date)
      SELECT c.id, u.id, NULL, '127.0.0.1', 'guarda', 'correct', NOW(6)
        FROM challenges c, users u WHERE u.type = 'admin' LIMIT 1;" > /dev/null

curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/competitions/$revert_id/revert" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")" > /dev/null
[[ "$(revert_status)" == "running" ]] \
  || { echo "FAIL: revert erased an execution that already had a submission"; exit 1; }

hikari_mariadb -e "DELETE FROM submissions WHERE provided = 'guarda';" > /dev/null
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null \
  -X POST "$CTFD_URL/admin/hikari/competitions/$revert_id/finish" \
  --data-urlencode "nonce=$(extract_nonce "$dashboard")"

echo "PASS: run created, started, extended, paused, resumed, finished, and cancelled safely"
# Ending a competition and cancelling a schedule cannot be undone, so neither
# may be one stray click away during an event.
dashboard=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" "$CTFD_URL/admin/hikari/competitions"
for irreversivel in finish cancel revert; do
  linhas=$(grep -c "competitions/[0-9]*/$irreversivel\"" "$dashboard" || true)
  protegidas=$(grep -c "competitions/[0-9]*/$irreversivel\" onsubmit=\"return confirm" "$dashboard" || true)
  [[ "$linhas" == "$protegidas" ]] \
    || { echo "FAIL: $irreversivel aparece $linhas vez(es) e só $protegidas pede confirmação"; exit 1; }
done
echo "PASS: encerrar, cancelar e voltar para rascunho pedem confirmação"

echo "PASS: an execution opened by mistake returns to draft, and refuses to once it has a score"
