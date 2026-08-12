#!/usr/bin/env bash
# Imports a portable challenge package and validates each persisted contract.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}
FIXTURE_DIR="$SCRIPT_DIR/fixtures/challenge-library"
package_key="acceptance-library-$(date +%s)"

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

db_query() {
  docker-compose -f "$COMPOSE_FILE" exec -T db \
    mariadb -uctfd -pctfd ctfd -N -B -e "$1"
}

admin_jar=$(mktemp)
workspace=$(mktemp -d)
trap 'rm -f "$admin_jar"; rm -rf "$workspace"' EXIT

cp -R "$FIXTURE_DIR/." "$workspace"
sed -i.bak "s/acceptance-library/$package_key/g" "$workspace/manifest.json"
rm -f "$workspace/manifest.json.bak"
(cd "$workspace" && zip -q library.zip manifest.json logs/*.json)

page=$(mktemp)
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" "$CTFD_URL/login"
nonce=$(extract_nonce "$page")
rm -f "$page"
code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "FAIL: admin login returned $code"; exit 1; }

page=$(mktemp)
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" \
  "$CTFD_URL/admin/hikari/challenge-library"
grep -q 'Biblioteca de desafios' "$page" \
  || { echo "FAIL: challenge library page is not available to admins"; exit 1; }
nonce=$(extract_nonce "$page")
rm -f "$page"

code=$(curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/admin/hikari/challenge-library" \
  -F "nonce=$nonce" \
  -F "library=@$workspace/library.zip;type=application/zip")
[[ "$code" == "302" ]] || { echo "FAIL: library import returned $code"; exit 1; }

library_id=$(db_query "SELECT id FROM hikari_challenge_library_imports WHERE package_key='$package_key';" | tr -d '[:space:]')
[[ -n "$library_id" ]] || { echo "FAIL: library import was not persisted"; exit 1; }
entry_count=$(db_query "SELECT COUNT(*) FROM hikari_challenge_library_entries WHERE library_import_id=$library_id;" | tr -d '[:space:]')
[[ "$entry_count" == "2" ]] \
  || { echo "FAIL: expected two library entries, found $entry_count"; exit 1; }
flag_count=$(db_query "SELECT COUNT(*) FROM flags WHERE content IN ('hikari{acceptance-initial}', 'hikari{acceptance-dependent}');" | tr -d '[:space:]')
[[ "$flag_count" == "2" ]] \
  || { echo "FAIL: imported challenge flags were not persisted"; exit 1; }
log_count=$(db_query "SELECT COUNT(*) FROM hikari_files WHERE filename LIKE 'library-$package_key-%';" | tr -d '[:space:]')
[[ "$log_count" == "2" ]] \
  || { echo "FAIL: expected two imported log files, found $log_count"; exit 1; }

initial_id=$(db_query "SELECT challenge_id FROM hikari_challenge_library_entries WHERE library_import_id=$library_id AND challenge_key='initial-hunt';" | tr -d '[:space:]')
dependent_id=$(db_query "SELECT challenge_id FROM hikari_challenge_library_entries WHERE library_import_id=$library_id AND challenge_key='dependent-hunt';" | tr -d '[:space:]')
requirements=$(db_query "SELECT requirements FROM challenges WHERE id=$dependent_id;" | tr -d '[:space:]')
[[ "$requirements" == *"$initial_id"* ]] \
  || { echo "FAIL: dependent challenge is missing its prerequisite reference"; exit 1; }
echo "PASS: package import persisted two challenges, flags, logs, and dependency metadata"

page=$(mktemp)
curl -sS -c "$admin_jar" -b "$admin_jar" -o "$page" \
  "$CTFD_URL/admin/hikari/challenge-library"
nonce=$(extract_nonce "$page")
rm -f "$page"
curl -sS -c "$admin_jar" -b "$admin_jar" -o /dev/null \
  -X POST "$CTFD_URL/admin/hikari/challenge-library" \
  -F "nonce=$nonce" \
  -F "library=@$workspace/library.zip;type=application/zip"
duplicate_count=$(db_query "SELECT COUNT(*) FROM hikari_challenge_library_imports WHERE package_key='$package_key';" | tr -d '[:space:]')
[[ "$duplicate_count" == "1" ]] \
  || { echo "FAIL: duplicate package import was accepted"; exit 1; }
echo "PASS: duplicate library package rejected"
