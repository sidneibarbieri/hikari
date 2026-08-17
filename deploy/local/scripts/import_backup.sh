#!/usr/bin/env bash
# Loads a legacy Hikari .data backup zip into the current stack.
#
# Strategy: bring up a side-car mariadbd against the backup's data files,
# mariadb-dump it to SQL, drop the running ctfd database, restore the dump.
# mariadb-dump produces version-portable SQL that any MariaDB can replay;
# copying tablespaces depends on internal ids matching.
#
# Uploads (.data/CTFd/uploads/) ride along by way of a one-shot Alpine
# container that wipes the running ctfd-uploads volume and lays the backup
# tree in its place.
#
# Usage:
#   bash import_backup.sh <path-to-backup.zip> [--yes]

set -euo pipefail

ZIP=${1:-}
CONFIRM=${2:-}

if [[ -z "$ZIP" ]]; then
  echo "usage: $0 <path-to-backup.zip> [--yes]" >&2
  exit 2
fi
[[ -f "$ZIP" ]] || { echo "not a file: $ZIP" >&2; exit 2; }
ZIP=$(cd "$(dirname "$ZIP")" && pwd)/$(basename "$ZIP")

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"
cd "$LOCAL_DIR"
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}
PROJECT=${COMPOSE_PROJECT_NAME:-$(basename "$LOCAL_DIR")}
compose() {
  hikari_compose -f "$COMPOSE_FILE" -p "$PROJECT" "$@"
}
UPLOADS_VOLUME="${PROJECT}_ctfd-uploads"
NETWORK="${PROJECT}_hikari"
SIDECAR="${PROJECT}-backup-sidecar"
CTFD_URL=${CTFD_URL:-http://localhost:${CTFD_PORT:-8000}}

if [[ "$CONFIRM" != "--yes" ]]; then
  echo "This will REPLACE the ctfd database and uploads with the contents of"
  echo "  $ZIP"
  echo "A mysqldump snapshot of the current database will be written first."
  read -rp "Continue? [y/N] " answer
  case "$answer" in y|Y|yes) ;; *) echo "aborted"; exit 0 ;; esac
fi

stamp=$(date +%s)
artifacts_dir="$(pwd)/artifacts"
mkdir -p "$artifacts_dir"
snapshot_file="$artifacts_dir/snapshot-pre-import-${stamp}.sql"
dump_file="$artifacts_dir/backup-dump-${stamp}.sql"

cleanup() {
  docker rm -f "$SIDECAR" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> snapshotting current database to $snapshot_file"
hikari_compose exec -T db mariadb-dump -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" \
  --routines --events --triggers "$HIKARI_DB_NAME" \
  > "$snapshot_file"

# Extract under the project directory rather than /tmp because on macOS+Colima
# /tmp is not part of the host filesystem the docker VM can see, and a bind
# mount from there appears empty inside containers.
work_dir="$(pwd)/artifacts/import-${stamp}"
mkdir -p "$work_dir"
trap 'cleanup; rm -rf "$work_dir"' EXIT

echo "==> extracting $ZIP into $work_dir"
unzip -q "$ZIP" -d "$work_dir"
[[ -d "$work_dir/.data/mysql" ]] \
  || { echo "backup missing .data/mysql"; exit 1; }
[[ -d "$work_dir/.data/CTFd/uploads" ]] \
  || { echo "backup missing .data/CTFd/uploads"; exit 1; }

echo "==> aligning ownership of extracted mysql files to mysql:mysql (999)"
docker run --rm -v "$work_dir/.data/mysql":/data alpine \
  chown -R 999:999 /data >/dev/null

echo "==> starting sidecar mariadbd against backup data"
docker rm -f "$SIDECAR" >/dev/null 2>&1 || true
docker run -d --name "$SIDECAR" \
  --network "$NETWORK" \
  -v "$work_dir/.data/mysql":/var/lib/mysql \
  --user 999:999 \
  --entrypoint mariadbd \
  mariadb:11.8 \
  --datadir=/var/lib/mysql \
  --skip-grant-tables --skip-networking=0 \
  --bind-address=0.0.0.0 \
  --user=mysql >/dev/null

deadline=$((SECONDS + 60))
while (( SECONDS < deadline )); do
  if docker exec "$SIDECAR" \
       mariadb -uroot -e "SELECT 1 FROM information_schema.tables LIMIT 1" \
       >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if (( SECONDS >= deadline )); then
  echo "sidecar did not become reachable in 60s"
  docker logs "$SIDECAR" 2>&1 | tail -30
  exit 1
fi
echo "   sidecar responding"

echo "==> dumping ctfd database from sidecar to $dump_file"
docker exec "$SIDECAR" \
  mariadb-dump -uroot --skip-lock-tables --routines --events --triggers ctfd \
  > "$dump_file"
printf '   %s bytes\n' "$(wc -c < "$dump_file" | tr -d '[:space:]')"

echo "==> stopping sidecar"
docker rm -f "$SIDECAR" >/dev/null

echo "==> dropping and recreating ctfd database in the running mariadb"
hikari_compose exec -T db mariadb -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" \
  -e "DROP DATABASE IF EXISTS \`$HIKARI_DB_NAME\`; CREATE DATABASE \`$HIKARI_DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

echo "==> restoring dump into ctfd"
hikari_mariadb < "$dump_file"

echo "==> marking imported CTFd instance as already set up"
hikari_mariadb -e \
  "INSERT INTO config (\`key\`, value)
   SELECT 'setup', '1'
   WHERE NOT EXISTS (SELECT 1 FROM config WHERE \`key\` = 'setup');
   UPDATE config SET value = '1' WHERE \`key\` = 'setup';"

echo "==> replacing $UPLOADS_VOLUME with backup uploads"
docker run --rm \
  -v "$UPLOADS_VOLUME":/dest \
  -v "$work_dir/.data/CTFd/uploads":/src:ro \
  alpine sh -c 'rm -rf /dest/* /dest/..?* /dest/.[!.]* 2>/dev/null; cp -a /src/. /dest/'

echo "==> clearing runtime cache after database replacement"
compose exec -T cache redis-cli FLUSHDB >/dev/null

echo "==> restarting ctfd so create_all picks up new tables (hikari_activity)"
compose restart ctfd >/dev/null
deadline=$((SECONDS + 90))
while (( SECONDS < deadline )); do
  if curl -fsS -o /dev/null --max-time 3 "$CTFD_URL/login"; then
    break
  fi
  sleep 2
done
(( SECONDS < deadline )) || { echo "ctfd did not come back up"; exit 1; }

echo "==> rebuilding competition1 from active challenge log files"
rebuild_script="$SCRIPT_DIR/rebuild_competition_data.py"
container_script="/tmp/rebuild_competition_data.py"
compose cp "$rebuild_script" "ctfd:$container_script"
compose exec -T ctfd python "$container_script"

echo "==> verifying imported state"
users=$(hikari_mariadb -N -B -e "SELECT COUNT(*) FROM users;" | tr -d '[:space:]')
teams=$(hikari_mariadb -N -B -e "SELECT COUNT(*) FROM teams;" | tr -d '[:space:]')
challenges=$(hikari_mariadb -N -B -e "SELECT COUNT(*) FROM challenges;" | tr -d '[:space:]')
solves=$(hikari_mariadb -N -B -e "SELECT COUNT(*) FROM solves;" | tr -d '[:space:]')
activity=$(hikari_mariadb -N -B -e \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='ctfd' AND table_name='hikari_activity';" \
  | tr -d '[:space:]')
competition_events=$(compose exec -T elasticsearch \
  curl -fsS http://localhost:9200/competition1/_count \
  | jq -r '.count')

cat <<EOF

Backup imported.
  users      : $users
  teams      : $teams
  challenges : $challenges
  solves     : $solves
  competition events : $competition_events
  hikari_activity table present : $activity

Pre-import snapshot: $snapshot_file
Backup dump kept at: $dump_file

To recover the previous state:
  source "$LOCAL_DIR/lib/compose.sh"
  hikari_compose -f "$COMPOSE_FILE" -p "$PROJECT" exec -T db \\
    mariadb -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" < $snapshot_file
EOF
