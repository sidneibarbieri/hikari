#!/usr/bin/env bash
# Proves the edition handover: what it refuses, what it writes and what it keeps.
#
# The operation is destructive by design, so the contract has to be verified
# rather than trusted: it must refuse while people are playing, it must change
# nothing without confirmation, it must produce a readable archive, and it must
# leave the challenge collection and the administrators in place.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"
cd "$LOCAL_DIR"

if [[ "${HIKARI_ACCEPTANCE_CONTEXT:-}" != "1" \
  && "${HIKARI_ALLOW_MUTATING_ACCEPTANCE:-}" != "1" ]]; then
  echo "Refusing to archive and reset the active stack." >&2
  echo "Run: bash tests/acceptance_isolated.sh" >&2
  exit 2
fi

workspace=$(mktemp -d)
export ARCHIVE_ROOT="$workspace/arquivo"
restore_database=""

cleanup() {
  if [[ -n "$restore_database" ]]; then
    hikari_compose exec -T db mariadb -uctfd -pctfd \
      -e "DROP DATABASE IF EXISTS \`$restore_database\`;" >/dev/null
  fi
  rm -rf "$workspace"
}
trap cleanup EXIT

# Only the client's password notice is dropped. A real SQL error has to reach
# the operator instead of turning into an empty result.
sql() {
  hikari_compose exec -T db mariadb -uctfd -pctfd ctfd -N -e "$1" \
    2> >(grep -v 'Using a password on the command line' >&2) | tr -d '[:space:]'
}

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; exit 1; }

echo "== 1. a operação recusa enquanto há competição agendada =="
sql "INSERT INTO hikari_competition_runs
     (\`key\`, name, scoring_mode, status, duration_minutes, created_at, updated_at)
     VALUES ('guard-check', 'Guard check', 'teams', 'scheduled', 60, NOW(), NOW());"
if bash scripts/archive_edition.sh --nova-edicao --confirmar > /dev/null 2>&1; then
  fail "the handover ran while a competition was in flight"
fi
sql "DELETE FROM hikari_competition_runs WHERE \`key\` = 'guard-check';"
pass "refused while a competition was scheduled"

echo
echo "== 2. sem confirmação, nada muda =="
users_before=$(sql "SELECT COUNT(*) FROM users;")
bash scripts/archive_edition.sh --nova-edicao > /dev/null
users_after=$(sql "SELECT COUNT(*) FROM users;")
[[ "$users_before" == "$users_after" ]] \
  || fail "the dry run changed the accounts ($users_before -> $users_after)"
[[ ! -d "$ARCHIVE_ROOT" ]] || fail "the dry run wrote an archive"
pass "dry run left the installation and the archive untouched"

echo
echo "== 3. o arquivo da edição é gravado antes de qualquer remoção =="
challenges_before=$(sql "SELECT COUNT(*) FROM challenges;")
admins_before=$(sql "SELECT COUNT(*) FROM users WHERE type = 'admin';")
bash scripts/archive_edition.sh --nova-edicao --confirmar > /dev/null

destination=$(find "$ARCHIVE_ROOT" -mindepth 1 -maxdepth 1 -type d | head -1)
[[ -n "$destination" ]] || fail "no archive directory was created"
for artefact in acervo-desafios.zip banco.sql MANIFESTO.md; do
  [[ -s "$destination/$artefact" ]] || fail "$artefact is missing or empty"
done
for artefact in atividade.jsonl feedback.jsonl; do
  [[ -f "$destination/$artefact" ]] || fail "$artefact is missing"
done
while IFS= read -r line; do
  [[ -z "$line" ]] || printf '%s' "$line" | python3 -c 'import json,sys; json.load(sys.stdin)'
done < "$destination/atividade.jsonl" || fail "the activity export is not readable as JSON"
while IFS= read -r line; do
  [[ -z "$line" ]] || printf '%s' "$line" | python3 -c 'import json,sys; json.load(sys.stdin)'
done < "$destination/feedback.jsonl" || fail "the feedback export is not readable as JSON"
unzip -l "$destination/acervo-desafios.zip" > /dev/null \
  || fail "the challenge collection archive is not a readable zip"
grep -q "Edição arquivada" "$destination/MANIFESTO.md" \
  || fail "the manifest does not describe the archive"
restore_database="hikari_archive_restore_check"
hikari_compose exec -T db mariadb -uctfd -pctfd \
  -e "CREATE DATABASE \`$restore_database\`;"
hikari_compose exec -T db mariadb -uctfd -pctfd "$restore_database" \
  < "$destination/banco.sql"
[[ "$(sql "SELECT COUNT(*) FROM information_schema.tables
              WHERE table_schema = '$restore_database' AND table_name = 'challenges';")" != "0" ]] \
  || fail "the database archive cannot be restored"
pass "archive holds readable telemetry, challenge collection and a restorable database"

echo
echo "== 4. a instalação fica pronta para a próxima edição =="
[[ "$(sql "SELECT COUNT(*) FROM users WHERE type <> 'admin';")" == "0" ]] \
  || fail "competitor accounts survived the reset"
[[ "$(sql "SELECT COUNT(*) FROM teams;")" == "0" ]] || fail "teams survived the reset"
[[ "$(sql "SELECT COUNT(*) FROM submissions;")" == "0" ]] \
  || fail "submissions survived the reset"
[[ "$(sql "SELECT COUNT(*) FROM hikari_activity;")" == "0" ]] \
  || fail "activity survived the reset"
[[ "$(sql "SELECT COUNT(*) FROM users WHERE type = 'admin';")" == "$admins_before" ]] \
  || fail "the administrators were removed"
[[ "$(sql "SELECT COUNT(*) FROM challenges;")" == "$challenges_before" ]] \
  || fail "the challenge collection was damaged"
[[ "$(sql "SELECT COUNT(*) FROM users u LEFT JOIN teams t ON t.id = u.team_id
           WHERE u.team_id IS NOT NULL AND t.id IS NULL;")" == "0" ]] \
  || fail "accounts point at teams that no longer exist"
pass "identities and score cleared, challenges and administrators kept"

echo
echo "Edition handover verified: refusal, dry run, archive and reset."
