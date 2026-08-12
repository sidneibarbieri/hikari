#!/usr/bin/env bash
# Restores one production checkpoint. This replaces competition data.

set -euo pipefail

ARCHIVE=${1:-}
CONFIRM=${2:-}
if [[ -z "$ARCHIVE" || "$CONFIRM" != "--yes" ]]; then
  echo "usage: $0 <checkpoint.zip> --yes" >&2
  exit 2
fi
[[ -f "$ARCHIVE" ]] || { echo "checkpoint not found: $ARCHIVE" >&2; exit 2; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/../local/lib/compose.sh"
COMPOSE_FILE=${HIKARI_COMPOSE_FILE:-"$SCRIPT_DIR/docker-compose.production.yml"}
COMPOSE_ENV="$SCRIPT_DIR/.compose.env"

[[ -f "$COMPOSE_ENV" ]] || { echo "compose environment not found: $COMPOSE_ENV" >&2; exit 1; }
set -a
source "$COMPOSE_ENV"
set +a

BACKUP_DIR=${HIKARI_BACKUP_DIR:-/opt/hikari/backups}

workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
unzip -q "$ARCHIVE" -d "$workdir"
for required_file in ctfd.sql uploads.tar elasticsearch-repository.tar manifest.json; do
  [[ -f "$workdir/$required_file" ]] || { echo "checkpoint missing $required_file" >&2; exit 1; }
done

compose() {
  hikari_compose \
    -p "${COMPOSE_PROJECT_NAME:-hikari}" \
    -f "$COMPOSE_FILE" \
    --env-file "$COMPOSE_ENV" \
    "$@"
}

restore_id=$(date -u +%Y%m%dT%H%M%SZ)
restore_path="$BACKUP_DIR/elasticsearch/restore/$restore_id"
restore_repository="hikari_restore_$restore_id"
mkdir -p "$restore_path"
tar -C "$restore_path" -xf "$workdir/elasticsearch-repository.tar"
chown -R 1000:0 "$restore_path"

echo "Stopping CTFd while competition data is restored."
compose stop ctfd

echo "Restoring uploaded evidence."
compose run --rm --no-deps --entrypoint sh ctfd -c \
  'find /var/uploads -mindepth 1 -delete'
compose run --rm --no-deps --entrypoint sh ctfd -c \
  'tar -C /var/uploads -xpf -' < "$workdir/uploads.tar"

echo "Restoring MariaDB."
compose exec -T db mariadb -uroot -p"$DATABASE_PASSWORD" -e \
  'DROP DATABASE IF EXISTS ctfd; CREATE DATABASE ctfd CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'
compose exec -T db mariadb -uctfd -p"$DATABASE_PASSWORD" ctfd < "$workdir/ctfd.sql"
compose exec -T cache redis-cli FLUSHALL >/dev/null

echo "Restoring Elasticsearch indices."
compose exec -T elasticsearch curl -fsS -X PUT \
  -H 'Content-Type: application/json' \
  "http://localhost:9200/_snapshot/$restore_repository" \
  -d "{\"type\":\"fs\",\"settings\":{\"location\":\"restore/$restore_id\"}}" >/dev/null
compose exec -T elasticsearch curl -fsS -X DELETE \
  'http://localhost:9200/competition1,hikari_activity?ignore_unavailable=true' >/dev/null
compose exec -T elasticsearch curl -fsS -X POST \
  -H 'Content-Type: application/json' \
  "http://localhost:9200/_snapshot/$restore_repository/snapshot/_restore?wait_for_completion=true" \
  -d '{"indices":"competition1,hikari_activity","include_global_state":false}' >/dev/null

compose up -d ctfd
compose exec -T elasticsearch curl -fsS -X DELETE \
  "http://localhost:9200/_snapshot/$restore_repository" >/dev/null
rm -rf "$restore_path"
echo "Restore complete. Verify the platform and re-import the SIEM dashboard if its saved objects changed."
